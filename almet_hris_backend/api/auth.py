import jwt
import logging
import json
from django.conf import settings
from django.contrib.auth.models import User
from django.db import transaction
from rest_framework.exceptions import AuthenticationFailed
from .models import MicrosoftUser, Employee

logger = logging.getLogger(__name__)

class MicrosoftTokenValidator:
    @staticmethod
    def validate_token(id_token):
        try:
            logger.info('=== Starting Microsoft token validation ===')
            
            # Decode token without signature verification for development
            payload = jwt.decode(id_token, options={"verify_signature": False})
            
            # Extract required fields
            aud = payload.get('aud')
            microsoft_id = payload.get('sub')
            
            if not microsoft_id:
                raise AuthenticationFailed('Invalid token: missing subject identifier')
                
            # Validate audience
            valid_audiences = [
                settings.MICROSOFT_CLIENT_ID,
                "00000003-0000-0000-c000-000000000000"
            ]
            
            if aud not in valid_audiences:
                raise AuthenticationFailed(f'Invalid audience: expected one of {valid_audiences}, got {aud}')
            
            # Extract email from token
            email = (payload.get('email') or 
                    payload.get('preferred_username') or 
                    payload.get('unique_name') or 
                    payload.get('upn'))
            
            if not email:
                raise AuthenticationFailed('Invalid token: missing email information')
                
            # Extract name
            name = payload.get('name', '').strip()
            if name:
                name_parts = name.split(' ')
                first_name = name_parts[0] if name_parts else ''
                last_name = ' '.join(name_parts[1:]) if len(name_parts) > 1 else ''
            else:
                first_name = payload.get('given_name', '')
                last_name = payload.get('family_name', '')
            
            logger.info(f'Microsoft login attempt: email={email}, first_name={first_name}, last_name={last_name}')
            
            # STEP 1: Check if this Microsoft ID already exists
            try:
                microsoft_user = MicrosoftUser.objects.select_related('user__employee_profile').get(
                    microsoft_id=microsoft_id
                )
                user = microsoft_user.user
                logger.info(f'Found existing Microsoft user: {user.username}')
                
                # Update user information if changed
                updated = False
                if user.email != email:
                    user.email = email
                    user.username = email  # Keep username synced with email
                    updated = True
                if user.first_name != first_name:
                    user.first_name = first_name
                    updated = True
                if user.last_name != last_name:
                    user.last_name = last_name
                    updated = True
                
                if updated:
                    user.save()
                    # Also update employee record if linked
                    if hasattr(user, 'employee_profile'):
                        employee = user.employee_profile
                        employee.save()  # This will update full_name
                
                return user
                    
            except MicrosoftUser.DoesNotExist:
                pass  # Continue to check for employee
            
            # STEP 2: Check if there's an existing employee with this email
            try:
                employee = Employee.objects.get(email=email)
                logger.info(f'Found existing employee with email {email}: {employee.employee_id}')
                
                # STEP 3: Check if this employee already has a user account
                if employee.user:
                    # Employee has user account - link with Microsoft
                    user = employee.user
                    logger.info(f'Employee {employee.employee_id} already has user account: {user.username}')
                    
                    # Update user info from Microsoft
                    user.email = email
                    user.username = email
                    user.first_name = first_name
                    user.last_name = last_name
                    user.save()
                    
                    # Link with Microsoft account
                    MicrosoftUser.objects.create(
                        user=user,
                        microsoft_id=microsoft_id
                    )
                    
                    logger.info(f'Linked existing employee {employee.employee_id} user account with Microsoft')
                    return user
                else:
                    # STEP 4: Employee exists but has no user account - create one
                    with transaction.atomic():
                        # Create user account for this employee
                        user = User.objects.create_user(
                            username=email,
                            email=email,
                            first_name=first_name,
                            last_name=last_name
                        )
                        user.set_unusable_password()  # Microsoft auth only
                        user.save()
                        
                        # CRITICAL: Link user to employee
                        employee.user = user
                        employee.save()  # This will update full_name from user fields
                        
                        # Link with Microsoft account
                        MicrosoftUser.objects.create(
                            user=user,
                            microsoft_id=microsoft_id
                        )
                        
                        logger.info(f'Created user account for existing employee {employee.employee_id} and linked with Microsoft')
                        return user
                    
            except Employee.DoesNotExist:
                # STEP 5: No employee found with this email - deny access
                logger.warning(f'Microsoft login denied: No employee record found for {email}')
                
                # Check if there are any employees at all (for better error message)
                total_employees = Employee.objects.count()
                if total_employees == 0:
                    error_msg = (
                        f'System setup incomplete. No employee records found in database. '
                        f'Please contact system administrator to set up employee data first.'
                    )
                else:
                    error_msg = (
                        f'Access denied for {email}. '
                        f'No employee record found with this email address. '
                        f'Please contact HR department to verify your employee record and email address.'
                    )
                
                raise AuthenticationFailed(error_msg)
            
        except jwt.DecodeError as e:
            logger.error(f'JWT decode error: {str(e)}')
            raise AuthenticationFailed('Invalid token format')
        except Exception as e:
            if isinstance(e, AuthenticationFailed):
                raise e  # Re-raise our custom authentication errors
            logger.error(f'Token validation error: {str(e)}')
            import traceback
            logger.error(f'Traceback: {traceback.format_exc()}')
            raise AuthenticationFailed(f'Authentication failed: {str(e)}')
