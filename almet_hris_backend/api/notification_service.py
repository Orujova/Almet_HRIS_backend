# api/notification_service.py - UPDATED
"""
Notification Service - FIXED
Uses Microsoft Graph Token for sending emails
Separate from JWT authentication token
"""

import logging
import requests
from django.conf import settings
from .notification_models import NotificationSettings, NotificationLog
from .token_helpers import extract_graph_token_from_request

logger = logging.getLogger(__name__)


class NotificationService:
    """Service for sending notifications via Microsoft Graph API"""
    
    def __init__(self):
        self.graph_endpoint = "https://graph.microsoft.com/v1.0"
        self._settings = None
    
    @property
    def settings(self):
        """Lazy load settings"""
        if self._settings is None:
            try:
                self._settings = NotificationSettings.get_active()
            except Exception as e:
                logger.warning(f"Could not load notification settings: {e}")
                from types import SimpleNamespace
                self._settings = SimpleNamespace(
                    enable_email_notifications=True,
                    business_trip_subject_prefix='[BUSINESS TRIP]'
                )
        return self._settings
    
    def send_email(self, recipient_email, subject, body_html, body_text=None, 
                   sender_email=None, access_token=None, related_model=None, 
                   related_object_id=None, sent_by=None, request=None):
        """
        Send email via Microsoft Graph API
        
        CRITICAL: access_token must be Microsoft Graph Token, NOT JWT!
        
        Args:
            recipient_email: Recipient email address
            subject: Email subject
            body_html: HTML email body
            body_text: Plain text email body (optional)
            sender_email: Sender email (optional)
            access_token: Microsoft Graph access token (NOT JWT!)
            related_model: Related model name (e.g., 'BusinessTripRequest')
            related_object_id: Related object ID
            sent_by: User who triggered the notification
            request: Django request object (to extract token if not provided)
        """
        
        if not self.settings.enable_email_notifications:
            logger.info("Email notifications are disabled")
            return False
        
        # ✅ Try to get Graph token from multiple sources
        if not access_token:
            if request:
                access_token = extract_graph_token_from_request(request)
                logger.info(f"Extracted Graph token from request: {bool(access_token)}")
        
        if not access_token:
            logger.error("❌ Microsoft Graph token is required for sending emails")
            logger.error("   Token must be provided via:")
            logger.error("   1. access_token parameter")
            logger.error("   2. X-Graph-Token header")
            logger.error("   3. Stored in database (UserGraphToken)")
            return False
        
        # Log token info (first/last chars only for security)
        if len(access_token) > 20:
            token_preview = f"{access_token[:10]}...{access_token[-10:]}"
            logger.info(f"Using Graph token: {token_preview}")
        
        # Create notification log
        notification_log = NotificationLog.objects.create(
            notification_type='EMAIL',
            recipient_email=recipient_email,
            subject=subject,
            body=body_html,
            related_model=related_model or '',
            related_object_id=str(related_object_id) if related_object_id else '',
            status='PENDING',
            sent_by=sent_by
        )
        
        try:
            # Prepare email message
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
                                "address": recipient_email
                            }
                        }
                    ]
                },
                "saveToSentItems": "true"
            }
            
            # ✅ CRITICAL: Use Microsoft Graph token
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            logger.info(f"📧 Sending email to {recipient_email}")
            logger.info(f"   Subject: {subject}")
            
            # Send via Microsoft Graph API
            response = requests.post(
                f"{self.graph_endpoint}/me/sendMail",
                headers=headers,
                json=message,
                timeout=30
            )
            
            logger.info(f"Graph API response: {response.status_code}")
            
            if response.status_code == 202:
                logger.info(f"✅ Email sent successfully to {recipient_email}")
                notification_log.mark_as_sent()
                return True
            else:
                error_msg = f"Failed to send email: {response.status_code}"
                if response.text:
                    error_msg += f" - {response.text[:500]}"
                    logger.error(f"Response body: {response.text}")
                
                logger.error(error_msg)
                notification_log.mark_as_failed(error_msg)
                
                # Check for specific errors
                if response.status_code == 401:
                    logger.error("❌ 401 Unauthorized: Graph token is invalid or expired")
                    logger.error("   User needs to login again to refresh Graph token")
                elif response.status_code == 403:
                    logger.error("❌ 403 Forbidden: Graph token lacks Mail.Send permission")
                
                return False
                
        except requests.exceptions.Timeout:
            error_msg = "Email sending timeout after 30 seconds"
            logger.error(error_msg)
            notification_log.mark_as_failed(error_msg)
            return False
        except Exception as e:
            error_msg = f"Error sending email: {str(e)}"
            logger.error(error_msg)
            import traceback
            logger.error(traceback.format_exc())
            notification_log.mark_as_failed(error_msg)
            return False
    
    def send_bulk_emails(self, recipients, subject, body_html, body_text=None, 
                        access_token=None, sent_by=None, request=None):
        """
        Send email to multiple recipients
        
        Args:
            recipients: List of email addresses
            subject: Email subject
            body_html: HTML email body
            body_text: Plain text body (optional)
            access_token: Microsoft Graph access token
            sent_by: User who triggered the notification
            request: Django request object
        
        Returns:
            dict: {'success': int, 'failed': int, 'total': int}
        """
        # Get token once for all emails
        if not access_token and request:
            access_token = extract_graph_token_from_request(request)
        
        results = {'success': 0, 'failed': 0, 'total': len(recipients)}
        
        for recipient in recipients:
            success = self.send_email(
                recipient_email=recipient,
                subject=subject,
                body_html=body_html,
                body_text=body_text,
                access_token=access_token,
                sent_by=sent_by
            )
            
            if success:
                results['success'] += 1
            else:
                results['failed'] += 1
        
        return results


# Singleton instance
notification_service = NotificationService()