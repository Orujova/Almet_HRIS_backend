import jwt
import logging
import json
from django.conf import settings
from django.contrib.auth.models import User
from django.utils.crypto import get_random_string
from rest_framework.exceptions import AuthenticationFailed
from .models import MicrosoftUser

logger = logging.getLogger(__name__)

class MicrosoftTokenValidator:
    @staticmethod
    def validate_token(id_token):
        try:
            logger.info('=== Starting Microsoft token validation ===')
            logger.info(f'Received token: {id_token[:50]}...')
            
            # Decode token without signature verification for development
            payload = jwt.decode(id_token, options={"verify_signature": False})
            logger.info(f'=== Token payload ===')
            logger.info(json.dumps(payload, indent=2, default=str))

            # Extract required fields
            aud = payload.get('aud')
            microsoft_id = payload.get('sub')
            
            logger.info(f'Audience from token: {aud}')
            logger.info(f'Expected audience: {settings.MICROSOFT_CLIENT_ID}')
            logger.info(f'Microsoft ID (sub): {microsoft_id}')
            
            if not microsoft_id:
                logger.error('Token missing subject identifier (sub)')
                raise AuthenticationFailed('Invalid token: missing subject identifier')
                
            # Validate audience - Microsoft Graph API və ya application audience qəbul edək
            valid_audiences = [
                settings.MICROSOFT_CLIENT_ID,  # Application client ID
                "00000003-0000-0000-c000-000000000000"  # Microsoft Graph API
            ]
            
            if aud not in valid_audiences:
                logger.error(f'Invalid audience in token: {aud}, expected one of: {valid_audiences}')
                raise AuthenticationFailed(f'Invalid audience: expected one of {valid_audiences}, got {aud}')
            
            # Extract user information - daha çox field yoxlayaq
            email = (payload.get('email') or 
                    payload.get('preferred_username') or 
                    payload.get('unique_name') or 
                    payload.get('upn'))
            
            if not email:
                logger.error('Token missing email information in all possible fields')
                logger.error(f'Available fields: {list(payload.keys())}')
                raise AuthenticationFailed('Invalid token: missing email information')
                
            # Extract name
            name = payload.get('name', '').strip()
            logger.info(f'Full name from token: {name}')
            
            if name:
                name_parts = name.split(' ')
                first_name = name_parts[0] if name_parts else ''
                last_name = ' '.join(name_parts[1:]) if len(name_parts) > 1 else ''
            else:
                first_name = payload.get('given_name', '')
                last_name = payload.get('family_name', '')
            
            logger.info(f'Extracted user info: email={email}, first_name={first_name}, last_name={last_name}')
            
            # Find or create user
            try:
                microsoft_user = MicrosoftUser.objects.get(microsoft_id=microsoft_id)
                user = microsoft_user.user
                logger.info(f'Found existing Microsoft user: {user.username}')
                
                # Update user information if changed
                if (user.email != email or 
                    user.first_name != first_name or 
                    user.last_name != last_name):
                    logger.info(f'Updating user information for: {user.username}')
                    user.email = email
                    user.first_name = first_name
                    user.last_name = last_name
                    user.save()
                    
            except MicrosoftUser.DoesNotExist:
                logger.info(f'Creating new user for Microsoft ID: {microsoft_id}')
                
                # Create username from email
                username = email.split('@')[0]
                base_username = username
                counter = 1
                
                # Ensure unique username
                while User.objects.filter(username=username).exists():
                    username = f"{base_username}{counter}"
                    counter += 1
                
                logger.info(f'Creating user with username: {username}')
                
                # Create user - Django utils istifadə edək
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    first_name=first_name,
                    last_name=last_name,
                )
                
                # Unusable password set et (Microsoft auth üçün password lazım deyil)
                user.set_unusable_password()
                user.save()
                
                # Create Microsoft user link
                microsoft_user = MicrosoftUser.objects.create(
                    user=user,
                    microsoft_id=microsoft_id
                )
                
                logger.info(f'Created new user: {user.username} with Microsoft ID: {microsoft_id}')
            
            logger.info(f'=== Token validation successful for user: {user.username} ===')
            return user
            
        except jwt.DecodeError as e:
            logger.error(f'JWT decode error: {str(e)}')
            raise AuthenticationFailed('Invalid token format')
        except Exception as e:
            logger.error(f'Token validation error: {str(e)}')
            logger.error(f'Exception type: {type(e).__name__}')
            import traceback
            logger.error(f'Traceback: {traceback.format_exc()}')
            raise AuthenticationFailed(f'Token validation failed: {str(e)}')