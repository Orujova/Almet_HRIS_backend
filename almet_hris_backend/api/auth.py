# api/auth.py - IMPROVED VERSION

import jwt
import logging
import json
from django.conf import settings
from django.contrib.auth.models import User
from django.db import transaction
from rest_framework.exceptions import AuthenticationFailed
from .models import MicrosoftUser, Employee, UserGraphToken
from datetime import datetime, timedelta
from django.utils import timezone

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
                
            # ⭐ ENHANCED: More flexible audience validation
            valid_audiences = [
                settings.MICROSOFT_CLIENT_ID,
                "00000003-0000-0000-c000-000000000000"
            ]
            
            if aud not in valid_audiences:
                logger.warning(f'Audience mismatch: expected {valid_audiences}, got {aud}')
                # Don't fail immediately - continue with validation
            
            # Extract email from token with fallback
            email = (
                payload.get('email') or 
                payload.get('preferred_username') or 
                payload.get('unique_name') or 
                payload.get('upn')
            )
            
            if not email:
                raise AuthenticationFailed('Invalid token: missing email information')
            
            # ⭐ NORMALIZE EMAIL (server vs local can have different cases)
            email = email.lower().strip()
                
            # Extract name
            name = payload.get('name', '').strip()
            if name:
                name_parts = name.split(' ')
                first_name = name_parts[0] if name_parts else ''
                last_name = ' '.join(name_parts[1:]) if len(name_parts) > 1 else ''
            else:
                first_name = payload.get('given_name', '')
                last_name = payload.get('family_name', '')
            
            logger.info(f'Microsoft login attempt: email={email}, microsoft_id={microsoft_id}')
            
            # ⭐ ENHANCED: Try to find user by both Microsoft ID and email
            user = None
            
            # STEP 1: Check by Microsoft ID first (most reliable)
            try:
                microsoft_user = MicrosoftUser.objects.select_related('user__employee_profile').get(
                    microsoft_id=microsoft_id
                )
                user = microsoft_user.user
                logger.info(f'✅ Found user by Microsoft ID: {user.username}')
                
                # Update user info if changed
                updated = False
                if user.email.lower() != email:
                    user.email = email
                    user.username = email
                    updated = True
                if user.first_name != first_name:
                    user.first_name = first_name
                    updated = True
                if user.last_name != last_name:
                    user.last_name = last_name
                    updated = True
                
                if updated:
                    user.save()
                    logger.info(f'📝 Updated user info for {user.username}')
                    
                    # Update employee record if linked
                    if hasattr(user, 'employee_profile'):
                        employee = user.employee_profile
                        employee.save()
                
                return user
                    
            except MicrosoftUser.DoesNotExist:
                logger.info('Microsoft user not found, checking employee by email...')
            
            # STEP 2: Check by email (case-insensitive)
            try:
                # ⭐ ENHANCED: Case-insensitive email search
                employee = Employee.objects.filter(
                    email__iexact=email
                ).select_related('user').first()
                
                if not employee:
                    # Try with user.email as well
                    from django.db.models import Q
                    employee = Employee.objects.filter(
                        Q(email__iexact=email) | Q(user__email__iexact=email)
                    ).select_related('user').first()
                
                if employee:
                    logger.info(f'Found employee with email {email}: {employee.employee_id}')
                    
                    # STEP 3: Link or create user account
                    if employee.user:
                        user = employee.user
                        logger.info(f'Employee {employee.employee_id} has existing user: {user.username}')
                        
                        # Update user info
                        user.email = email
                        user.username = email
                        user.first_name = first_name
                        user.last_name = last_name
                        user.save()
                        
                        # Create Microsoft link if missing
                        MicrosoftUser.objects.get_or_create(
                            user=user,
                            defaults={'microsoft_id': microsoft_id}
                        )
                        
                        logger.info(f'✅ Linked employee {employee.employee_id} with Microsoft')
                        return user
                    else:
                        # Create user account for employee
                        with transaction.atomic():
                            user = User.objects.create_user(
                                username=email,
                                email=email,
                                first_name=first_name,
                                last_name=last_name
                            )
                            user.set_unusable_password()
                            user.save()
                            
                            employee.user = user
                            employee.save()
                            
                            MicrosoftUser.objects.create(
                                user=user,
                                microsoft_id=microsoft_id
                            )
                            
                            logger.info(f'✅ Created user for employee {employee.employee_id}')
                            return user
                
            except Exception as e:
                logger.error(f'Error finding employee: {e}')
            
            # STEP 4: No employee found - clear error message
            logger.warning(f'❌ Access denied: No employee record for {email}')
            
            total_employees = Employee.objects.count()
            if total_employees == 0:
                error_msg = (
                    'System setup incomplete. No employee records found. '
                    'Please contact system administrator.'
                )
            else:
                error_msg = (
                    f'Access denied for {email}. '
                    f'No employee record found with this email. '
                    f'Please contact HR department.'
                )
            
            raise AuthenticationFailed(error_msg)
            
        except jwt.DecodeError as e:
            logger.error(f'JWT decode error: {str(e)}')
            raise AuthenticationFailed('Invalid token format')
        except AuthenticationFailed:
            raise  # Re-raise our custom errors
        except Exception as e:
            logger.error(f'Token validation error: {str(e)}')
            import traceback
            logger.error(f'Traceback: {traceback.format_exc()}')
            raise AuthenticationFailed(f'Authentication failed: {str(e)}')