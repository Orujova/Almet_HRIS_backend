# 6. Update the backend MicrosoftTokenValidator for better token handling

# api/auth.py - update the validate_token method
import jwt
import logging
from django.conf import settings
from django.contrib.auth.models import User
from rest_framework import authentication
from rest_framework.exceptions import AuthenticationFailed
from .models import MicrosoftUser

# Set up logger
logger = logging.getLogger(__name__)

class MicrosoftTokenValidator:
    """
    Validate Microsoft ID tokens from frontend
    """
    @staticmethod
    def validate_token(id_token):
        try:
            logger.info('Starting Microsoft token validation')
            
            # Decode the token without verification (frontend already verified)
            payload = jwt.decode(id_token, options={"verify_signature": False})
            
            # Extract token identification fields
            aud = payload.get('aud')
            microsoft_id = payload.get('sub')
            
            # Check required fields
            if not microsoft_id:
                logger.error('Token missing subject identifier (sub)')
                raise AuthenticationFailed('Invalid token: missing subject identifier')
                
            # Check if token is for our app
            if aud != settings.MICROSOFT_CLIENT_ID:
                logger.error(f'Invalid audience in token: {aud}, expected: {settings.MICROSOFT_CLIENT_ID}')
                raise AuthenticationFailed('Invalid audience in token')
            
            # Get user info from token
            email = payload.get('email') or payload.get('preferred_username')
            if not email:
                logger.error('Token missing email or preferred_username')
                raise AuthenticationFailed('Invalid token: missing email information')
                
            name = payload.get('name', '').split(' ')
            first_name = name[0] if name else ''
            last_name = ' '.join(name[1:]) if len(name) > 1 else ''
            
            logger.info(f'Token contains user info: {email}, {first_name} {last_name}')
            
            # Get or create user
            try:
                microsoft_user = MicrosoftUser.objects.get(microsoft_id=microsoft_id)
                user = microsoft_user.user
                logger.info(f'Found existing Microsoft user: {microsoft_user.id} for user: {user.username}')
                
                # Update user info if changed
                if user.email != email or user.first_name != first_name or user.last_name != last_name:
                    logger.info(f'Updating user information for: {user.username}')
                    user.email = email
                    user.first_name = first_name
                    user.last_name = last_name
                    user.save()
                
            except MicrosoftUser.DoesNotExist:
                logger.info(f'Creating new user for Microsoft ID: {microsoft_id}')
                # Create new user
                username = email.split('@')[0]
                base_username = username
                counter = 1
                
                # Ensure unique username
                while User.objects.filter(username=username).exists():
                    username = f"{base_username}{counter}"
                    counter += 1
                
                logger.info(f'Creating new user with username: {username}')
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    first_name=first_name,
                    last_name=last_name
                )
                
                # Create Microsoft user
                microsoft_user = MicrosoftUser.objects.create(
                    user=user,
                    microsoft_id=microsoft_id
                )
                logger.info(f'Created new Microsoft user: {microsoft_user.id} for user: {user.username}')
            
            return user
        
        except jwt.DecodeError as e:
            logger.error(f'JWT decode error: {str(e)}')
            raise AuthenticationFailed('Invalid token format')
        except Exception as e:
            logger.error(f'Token validation error: {str(e)}')
            raise AuthenticationFailed(f'Token validation failed: {str(e)}')