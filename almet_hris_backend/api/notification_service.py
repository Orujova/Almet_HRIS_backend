# api/notification_service.py - UPDATED WITH SENT/RECEIVED SEPARATION

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
                    business_trip_subject_prefix='[BUSINESS TRIP]',
                    vacation_subject_prefix='[VACATION]'
                )
        return self._settings
    
    def get_received_emails(self, access_token, subject_filter, top=50):
        """
        📥 RECEIVED EMAILS - Gələn mailləri gətir
        
        Args:
            access_token: Microsoft Graph access token
            subject_filter: Subject text to filter by
            top: Number of emails to retrieve
        
        Returns:
            list: List of received email objects
        """
        return self._get_emails_from_folder(
            access_token=access_token,
            folder_endpoint="/me/messages",  # Default inbox
            subject_filter=subject_filter,
            top=top,
            email_type="RECEIVED"
        )
    
    def get_sent_emails(self, access_token, subject_filter, top=50):
        """
        📤 SENT EMAILS - Göndərilən mailləri gətir
        
        Args:
            access_token: Microsoft Graph access token
            subject_filter: Subject text to filter by
            top: Number of emails to retrieve
        
        Returns:
            list: List of sent email objects
        """
        return self._get_emails_from_folder(
            access_token=access_token,
            folder_endpoint="/me/mailFolders/sentitems/messages",  # Sent items folder
            subject_filter=subject_filter,
            top=top,
            email_type="SENT"
        )
    
    def _get_emails_from_folder(self, access_token, folder_endpoint, subject_filter, top=50, email_type="RECEIVED"):
        """
        Internal method to get emails from specific folder
        
        Args:
            access_token: Microsoft Graph access token
            folder_endpoint: Graph API endpoint for folder
            subject_filter: Subject filter
            top: Number of emails
            email_type: "RECEIVED" or "SENT"
        
        Returns:
            list: Email objects with type tag
        """
        try:
            escaped_filter = subject_filter.replace("'", "''")
            filter_query = f"contains(subject, '{escaped_filter}')"
            
            params = {
                '$filter': filter_query,
                '$top': min(top, 50),
                '$orderby': 'receivedDateTime desc',
                '$select': 'id,subject,from,toRecipients,receivedDateTime,sentDateTime,isRead,hasAttachments,importance,bodyPreview'
            }
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            logger.info(f"📧 Fetching {email_type} emails with subject: {subject_filter}")
            
            response = requests.get(
                f"{self.graph_endpoint}{folder_endpoint}",
                headers=headers,
                params=params,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                emails = data.get('value', [])
                
                # Add email_type tag to each email
                for email in emails:
                    email['email_type'] = email_type
                
                logger.info(f"✅ Retrieved {len(emails)} {email_type} emails")
                return emails
            
            elif response.status_code == 400:
                logger.warning("⚠️ Filter failed, trying client-side filter...")
                return self._get_emails_client_side_filter(
                    access_token, folder_endpoint, subject_filter, top, email_type
                )
            else:
                logger.error(f"Failed to get {email_type} emails: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Error getting {email_type} emails: {str(e)}")
            return []
    
    def _get_emails_client_side_filter(self, access_token, folder_endpoint, subject_filter, top=50, email_type="RECEIVED"):
        """
        Fallback: Client-side filtering
        """
        try:
            params = {
                '$top': min(top * 3, 100),
                '$orderby': 'receivedDateTime desc',
                '$select': 'id,subject,from,toRecipients,receivedDateTime,sentDateTime,isRead,hasAttachments,importance,bodyPreview'
            }
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            response = requests.get(
                f"{self.graph_endpoint}{folder_endpoint}",
                headers=headers,
                params=params,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                all_emails = data.get('value', [])
                
                subject_filter_lower = subject_filter.lower()
                filtered_emails = [
                    email for email in all_emails 
                    if subject_filter_lower in email.get('subject', '').lower()
                ]
                
                # Add email_type tag
                for email in filtered_emails:
                    email['email_type'] = email_type
                
                filtered_emails = filtered_emails[:top]
                
                logger.info(f"✅ Client-side: {len(filtered_emails)} {email_type} emails")
                return filtered_emails
            
            return []
                
        except Exception as e:
            logger.error(f"Client-side filter failed: {str(e)}")
            return []
    
    def get_all_emails_by_type(self, access_token, subject_filter, top=50, email_type="all"):
        """
        📬 COMBINED - Həm gələn həm də göndərilən mailləri gətir
        
        Args:
            access_token: Microsoft Graph access token
            subject_filter: Subject filter
            top: Number of emails per type
            email_type: "received", "sent", or "all"
        
        Returns:
            dict: {"received": [...], "sent": [...], "all": [...]}
        """
        result = {
            "received": [],
            "sent": [],
            "all": []
        }
        
        try:
            if email_type in ["received", "all"]:
                result["received"] = self.get_received_emails(access_token, subject_filter, top)
            
            if email_type in ["sent", "all"]:
                result["sent"] = self.get_sent_emails(access_token, subject_filter, top)
            
            if email_type == "all":
                # Combine and sort by date
                all_emails = result["received"] + result["sent"]
                all_emails.sort(key=lambda x: x.get('receivedDateTime', ''), reverse=True)
                result["all"] = all_emails[:top]
            
            return result
            
        except Exception as e:
            logger.error(f"Error in get_all_emails_by_type: {str(e)}")
            return result
    
    # ==================== EXISTING METHODS ====================
    
    def send_email(self, recipient_email, subject, body_html, body_text=None, 
                   sender_email=None, access_token=None, related_model=None, 
                   related_object_id=None, sent_by=None, request=None):
        """Send email via Microsoft Graph API"""
        
        if not self.settings.enable_email_notifications:
            logger.info("Email notifications are disabled")
            return False
        
        if not access_token:
            if request:
                access_token = extract_graph_token_from_request(request)
        
        if not access_token:
            logger.error("❌ Microsoft Graph token is required")
            return False
        
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
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            logger.info(f"📧 Sending email to {recipient_email}")
            
            response = requests.post(
                f"{self.graph_endpoint}/me/sendMail",
                headers=headers,
                json=message,
                timeout=30
            )
            
            if response.status_code == 202:
                logger.info(f"✅ Email sent successfully")
                notification_log.mark_as_sent()
                return True
            else:
                error_msg = f"Failed: {response.status_code}"
                logger.error(error_msg)
                notification_log.mark_as_failed(error_msg)
                return False
                
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            logger.error(error_msg)
            notification_log.mark_as_failed(error_msg)
            return False
    
    def mark_email_as_read(self, access_token, message_id):
        """Mark email as read"""
        try:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            response = requests.patch(
                f"{self.graph_endpoint}/me/messages/{message_id}",
                headers=headers,
                json={"isRead": True},
                timeout=30
            )
            
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Error marking email as read: {str(e)}")
            return False
    
    def mark_email_as_unread(self, access_token, message_id):
        """Mark email as unread"""
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
            
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Error marking email as unread: {str(e)}")
            return False
    
    def mark_multiple_emails_as_read(self, access_token, message_ids):
        """Mark multiple emails as read"""
        results = {'success': 0, 'failed': 0, 'total': len(message_ids)}
        
        for message_id in message_ids:
            if self.mark_email_as_read(access_token, message_id):
                results['success'] += 1
            else:
                results['failed'] += 1
        
        return results


# Singleton instance
notification_service = NotificationService()