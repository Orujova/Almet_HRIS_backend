# api/system_email_service.py
"""
System Email Service - Application Permissions ilə email göndərmək
User access token lazım deyil, application öz tokenini alır
"""

import logging
import requests
from django.conf import settings
from django.core.cache import cache
import msal

logger = logging.getLogger(__name__)


class SystemEmailService:
    """
    🔐 Application Permissions ilə email göndərmək
    shadmin@almettrading.com-dan user token olmadan göndərir
    """
    
    def __init__(self):
        self.graph_endpoint = "https://graph.microsoft.com/v1.0"
        
        # ⚙️ Azure AD Application settings (settings.py-dən oxuyur)
        self.tenant_id = getattr(settings, 'MICROSOFT_TENANT_ID', '')
        self.client_id = getattr(settings, 'MICROSOFT_CLIENT_ID', '')
        # self.client_secret = getattr(settings, 'AZURE_CLIENT_SECRET', '')
        
        self.authority = f"https://login.microsoftonline.com/{self.tenant_id}"
        self.scope = ["https://graph.microsoft.com/.default"]
        
        # Cache key
        self.cache_key = "system_email_access_token"
    
    def get_application_token(self):
        """
        🔑 Application token al (Client Credentials Flow)
        Bu token user-dən asılı deyil, application-ın öz token-idir
        
        Returns:
            str: Access token or None
        """
        # Cache-də varmı bax
        cached_token = cache.get(self.cache_key)
        if cached_token:
            logger.info("Using cached application token")
            return cached_token
        
        try:
            # MSAL ilə token al
            app = msal.ConfidentialClientApplication(
                client_id=self.client_id,
                # client_credential=self.client_secret,
                authority=self.authority
            )
            
            logger.info(" Acquiring application token...")
            
            result = app.acquire_token_for_client(scopes=self.scope)
            
            if "access_token" in result:
                token = result["access_token"]
                expires_in = result.get("expires_in", 3600)
                
                # Cache-lə (5 dəqiqə əvvəl expire edirik ki, problem olmasın)
                cache.set(self.cache_key, token, timeout=expires_in - 300)
                
                logger.info("Application token acquired successfully")
                return token
            else:
                error = result.get("error_description", result.get("error", "Unknown error"))
                logger.error(f" Token acquisition failed: {error}")
                return None
                
        except Exception as e:
            logger.error(f"❌Error acquiring application token: {e}")
            return None
    
    def send_email_as_system(self, from_email, to_email, subject, body_html):
        """
        📧 System mailbox-dan email göndər (Application Permission)
        
        Args:
            from_email: Göndərən mailbox (məs: shadmin@almettrading.com)
            to_email: Alıcının maili
            subject: Email mövzusu
            body_html: HTML body
        
        Returns:
            dict: {success: bool, message: str, message_id: str}
        """
        try:
            # Application token al
            access_token = self.get_application_token()
            
            if not access_token:
                return {
                    'success': False,
                    'message': 'Failed to get application access token',
                    'message_id': None
                }
            
            # Email message hazırla
            message = {
                "message": {
                    "subject": subject,
                    "body": {
                        "contentType": "HTML",
                        "content": body_html
                    },
                    "toRecipients": [
                        {
                            "emailAddress": {
                                "address": to_email
                            }
                        }
                    ]
                },
                "saveToSentItems": "true"
            }
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            logger.info(f"📧 Sending system email from {from_email} to {to_email}")
            
            # API endpoint: /users/{from_email}/sendMail
            response = requests.post(
                f"{self.graph_endpoint}/users/{from_email}/sendMail",
                headers=headers,
                json=message,
                timeout=30
            )
            
            if response.status_code == 202:
                logger.info(f" System email sent successfully")
                return {
                    'success': True,
                    'message': 'Email sent successfully',
                    'message_id': response.headers.get('request-id', '')
                }
            else:
                error_msg = f"Failed: {response.status_code} - {response.text}"
                logger.error(error_msg)
                return {
                    'success': False,
                    'message': error_msg,
                    'message_id': None
                }
                
        except Exception as e:
            error_msg = f"Exception: {str(e)}"
            logger.error(error_msg)
            return {
                'success': False,
                'message': error_msg,
                'message_id': None
            }
    
    def send_bulk_emails_as_system(self, from_email, recipients, subject, body_html):
        """
        📧 Çoxlu email göndər (batch)
        
        Args:
            from_email: Göndərən mailbox
            recipients: List of email addresses
            subject: Email subject
            body_html: HTML body
        
        Returns:
            dict: {success_count: int, failed_count: int, results: list}
        """
        results = {
            'success_count': 0,
            'failed_count': 0,
            'results': []
        }
        
        for recipient in recipients:
            result = self.send_email_as_system(
                from_email=from_email,
                to_email=recipient,
                subject=subject,
                body_html=body_html
            )
            
            if result['success']:
                results['success_count'] += 1
            else:
                results['failed_count'] += 1
            
            results['results'].append({
                'recipient': recipient,
                'success': result['success'],
                'message': result['message']
            })
        
        return results


# Singleton instance
system_email_service = SystemEmailService()