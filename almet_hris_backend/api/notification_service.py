# api/notification_service.py - COMPLETE WITH GET_EMAILS_BY_SUBJECT
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
    
    def get_emails_by_subject(self, access_token, subject_filter, top=50):
        """
        Get emails from user's mailbox filtered by subject
        
        Args:
            access_token: Microsoft Graph access token
            subject_filter: Subject text to filter by (e.g., '[BUSINESS TRIP]')
            top: Number of emails to retrieve (max 50)
        
        Returns:
            list: List of email objects from Graph API
        """
        try:
            # Method 1: Try with OData filter first
            # Escape special characters for OData filter
            escaped_filter = subject_filter.replace("'", "''")
            filter_query = f"contains(subject, '{escaped_filter}')"
            
            # Query parameters
            params = {
                '$filter': filter_query,
                '$top': min(top, 50),  # Graph API limits to 50
                '$orderby': 'receivedDateTime desc',
                '$select': 'id,subject,from,receivedDateTime,isRead,hasAttachments,importance,bodyPreview'
            }
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            logger.info(f"📧 Fetching emails with subject filter: {subject_filter}")
            logger.info(f"   Filter query: {filter_query}")
            
            # Get emails from mailbox
            response = requests.get(
                f"{self.graph_endpoint}/me/messages",
                headers=headers,
                params=params,
                timeout=30
            )
            
            logger.info(f"Graph API response: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                emails = data.get('value', [])
                logger.info(f"✅ Retrieved {len(emails)} emails with filter")
                
                # If no emails found with filter, try without filter and filter client-side
                if len(emails) == 0:
                    logger.info("No emails found with server filter, trying client-side filter...")
                    return self._get_emails_client_side_filter(access_token, subject_filter, top)
                
                return emails
            else:
                error_msg = f"Failed to get emails: {response.status_code}"
                if response.text:
                    error_msg += f" - {response.text[:500]}"
                    logger.error(f"Response body: {response.text}")
                
                logger.error(error_msg)
                
                # Check for specific errors
                if response.status_code == 401:
                    logger.error("❌ 401 Unauthorized: Graph token is invalid or expired")
                elif response.status_code == 403:
                    logger.error("❌ 403 Forbidden: Graph token lacks Mail.Read permission")
                elif response.status_code == 400:
                    # Bad filter query, try client-side filtering
                    logger.warning("❌ 400 Bad Request: Filter query failed, trying client-side filter...")
                    return self._get_emails_client_side_filter(access_token, subject_filter, top)
                
                return []
                
        except requests.exceptions.Timeout:
            logger.error("Email retrieval timeout after 30 seconds")
            return []
        except Exception as e:
            logger.error(f"Error getting emails: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return []
    
    def _get_emails_client_side_filter(self, access_token, subject_filter, top=50):
        """
        Fallback method: Get all recent emails and filter client-side
        
        Args:
            access_token: Microsoft Graph access token
            subject_filter: Subject text to filter by
            top: Number of emails to retrieve
        
        Returns:
            list: Filtered email objects
        """
        try:
            # Get recent emails without server-side filter
            params = {
                '$top': min(top * 3, 100),  # Get more emails to filter from
                '$orderby': 'receivedDateTime desc',
                '$select': 'id,subject,from,receivedDateTime,isRead,hasAttachments,importance,bodyPreview'
            }
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            logger.info(f"📧 Fetching recent emails for client-side filtering...")
            
            response = requests.get(
                f"{self.graph_endpoint}/me/messages",
                headers=headers,
                params=params,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                all_emails = data.get('value', [])
                
                # Filter client-side (case-insensitive)
                subject_filter_lower = subject_filter.lower()
                filtered_emails = [
                    email for email in all_emails 
                    if subject_filter_lower in email.get('subject', '').lower()
                ]
                
                # Limit to requested top count
                filtered_emails = filtered_emails[:top]
                
                logger.info(f"✅ Client-side filter: Found {len(filtered_emails)} matching emails out of {len(all_emails)} total")
                
                return filtered_emails
            else:
                logger.error(f"Failed to get emails for client-side filter: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Client-side filter failed: {str(e)}")
            return []
    
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

    def mark_email_as_read(self, access_token, message_id):
        """
        Mark an email as read
        
        Args:
            access_token: Microsoft Graph access token
            message_id: Email message ID from Graph API
        
        Returns:
            bool: Success status
        """
        try:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            # Update message isRead property
            response = requests.patch(
                f"{self.graph_endpoint}/me/messages/{message_id}",
                headers=headers,
                json={"isRead": True},
                timeout=30
            )
            
            if response.status_code == 200:
                logger.info(f"✅ Email {message_id} marked as read")
                return True
            else:
                logger.error(f"Failed to mark email as read: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Error marking email as read: {str(e)}")
            return False


    def mark_email_as_unread(self, access_token, message_id):
        """
        Mark an email as unread
        
        Args:
            access_token: Microsoft Graph access token
            message_id: Email message ID from Graph API
        
        Returns:
            bool: Success status
        """
        try:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            response = requests.patch(
                f"{self.graph_endpoint}/me/messages/{message_id}",
                headers=headers,
                json={"isRead": False},
                timeout=30
            )
            
            if response.status_code == 200:
                logger.info(f"✅ Email {message_id} marked as unread")
                return True
            else:
                logger.error(f"Failed to mark email as unread: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Error marking email as unread: {str(e)}")
            return False
    
    
    def mark_multiple_emails_as_read(self, access_token, message_ids):
        """
        Mark multiple emails as read
        
        Args:
            access_token: Microsoft Graph access token
            message_ids: List of email message IDs
        
        Returns:
            dict: Results with success/failed counts
        """
        results = {'success': 0, 'failed': 0, 'total': len(message_ids)}
        
        for message_id in message_ids:
            if self.mark_email_as_read(access_token, message_id):
                results['success'] += 1
            else:
                results['failed'] += 1
        
        return results
    
# Singleton instance
notification_service = NotificationService()