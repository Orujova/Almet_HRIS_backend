# api/notification_service.py
"""
Notification Service
Handles email sending via Microsoft Graph API
Uses authenticated user's token to send emails
"""

import logging
import requests
from django.conf import settings
from .notification_models import NotificationSettings, NotificationLog

logger = logging.getLogger(__name__)


class NotificationService:
    """Service for sending notifications via Microsoft Graph API"""
    
    def __init__(self):
        self.graph_endpoint = "https://graph.microsoft.com/v1.0"
        self._settings = None
    
    @property
    def settings(self):
        """Lazy load settings to avoid import-time database access"""
        if self._settings is None:
            try:
                self._settings = NotificationSettings.get_active()
            except Exception as e:
                logger.warning(f"Could not load notification settings: {e}")
                # Return default settings object without saving to DB
                from types import SimpleNamespace
                self._settings = SimpleNamespace(
                    enable_email_notifications=True,
                    business_trip_subject_prefix='[BUSINESS TRIP]'
                )
        return self._settings
    
    def send_email(self, recipient_email, subject, body_html, body_text=None, 
                   sender_email=None, access_token=None, related_model=None, 
                   related_object_id=None, sent_by=None):
        """
        Send email via Microsoft Graph API
        
        Args:
            recipient_email: Recipient email address
            subject: Email subject
            body_html: HTML email body
            body_text: Plain text email body (optional)
            sender_email: Sender email (optional, uses default)
            access_token: Microsoft Graph access token (REQUIRED - not JWT!)
            related_model: Related model name (e.g., 'BusinessTripRequest')
            related_object_id: Related object ID
            sent_by: User who triggered the notification
        """
        
        if not self.settings.enable_email_notifications:
            logger.info("Email notifications are disabled")
            return False
        
        if not access_token:
            logger.error("Access token is required for sending emails")
            return False
        
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
            sender = sender_email 
            
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
            
            # CRITICAL: Use Microsoft Graph token, not JWT
            # The token should be from MSAL authentication, not Django JWT
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            logger.info(f"Attempting to send email to {recipient_email}")
            
            # Send via Microsoft Graph API
            response = requests.post(
                f"{self.graph_endpoint}/me/sendMail",
                headers=headers,
                json=message,
                timeout=30
            )
            
            if response.status_code == 202:
                logger.info(f"✅ Email sent successfully to {recipient_email}")
                notification_log.mark_as_sent()
                return True
            else:
                error_msg = f"Failed to send email: {response.status_code} - {response.text}"
                logger.error(error_msg)
                notification_log.mark_as_failed(error_msg)
                return False
                
        except Exception as e:
            error_msg = f"Error sending email: {str(e)}"
            logger.error(error_msg)
            notification_log.mark_as_failed(error_msg)
            return False
    
    def send_bulk_emails(self, recipients, subject, body_html, body_text=None, 
                        access_token=None, sent_by=None):
        """
        Send email to multiple recipients
        
        Args:
            recipients: List of email addresses
            subject: Email subject
            body_html: HTML email body
            body_text: Plain text body (optional)
            access_token: Microsoft Graph access token
            sent_by: User who triggered the notification
        
        Returns:
            dict: {'success': int, 'failed': int, 'total': int}
        """
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
    
    def get_sent_emails(self, access_token, top=50):
        """
        Get sent emails from user's mailbox
        
        Args:
            access_token: Microsoft Graph access token
            top: Number of emails to retrieve (default: 50)
        
        Returns:
            list: List of sent emails
        """
        try:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            response = requests.get(
                f"{self.graph_endpoint}/me/mailFolders/SentItems/messages?$top={top}&$orderby=sentDateTime desc",
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json().get('value', [])
            else:
                logger.error(f"Failed to get sent emails: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Error getting sent emails: {e}")
            return []
    
    def get_emails_by_subject(self, access_token, subject_filter, top=50):
        """
        Get emails by subject filter
        
        Args:
            access_token: Microsoft Graph access token
            subject_filter: Subject text to filter (e.g., "[BUSINESS TRIP]")
            top: Number of emails to retrieve
        
        Returns:
            list: Filtered emails
        """
        try:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            # Use $filter query parameter
            filter_query = f"startswith(subject,'{subject_filter}')"
            url = f"{self.graph_endpoint}/me/messages?$filter={filter_query}&$top={top}&$orderby=receivedDateTime desc"
            
            response = requests.get(url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                return response.json().get('value', [])
            else:
                logger.error(f"Failed to filter emails: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Error filtering emails: {e}")
            return []


# Singleton instance
notification_service = NotificationService()