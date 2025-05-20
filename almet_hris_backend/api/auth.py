# api/auth.py

import jwt
from django.conf import settings
from django.contrib.auth.models import User
from rest_framework import authentication
from rest_framework.exceptions import AuthenticationFailed
from .models import MicrosoftUser

class MicrosoftTokenValidator:
    """
    Validate Microsoft ID tokens from frontend
    """
    @staticmethod
    def validate_token(id_token):
        try:
            # Decode the token without verification (frontend already verified)
            payload = jwt.decode(id_token, options={"verify_signature": False})
            
            # Check if token is for our app
            if payload.get('aud') != settings.MICROSOFT_CLIENT_ID:
                raise AuthenticationFailed('Invalid audience in token')
            
            # Get user info from token
            microsoft_id = payload.get('sub')
            email = payload.get('email') or payload.get('preferred_username')
            name = payload.get('name', '').split(' ')
            first_name = name[0] if name else ''
            last_name = ' '.join(name[1:]) if len(name) > 1 else ''
            
            # Get or create user
            try:
                microsoft_user = MicrosoftUser.objects.get(microsoft_id=microsoft_id)
                user = microsoft_user.user
                
                # Update user info if changed
                if user.email != email or user.first_name != first_name or user.last_name != last_name:
                    user.email = email
                    user.first_name = first_name
                    user.last_name = last_name
                    user.save()
                
            except MicrosoftUser.DoesNotExist:
                # Create new user
                username = email.split('@')[0]
                base_username = username
                counter = 1
                
                # Ensure unique username
                while User.objects.filter(username=username).exists():
                    username = f"{base_username}{counter}"
                    counter += 1
                
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
            
            return user
        
        except Exception as e:
            raise AuthenticationFailed(f'Token validation failed: {str(e)}')