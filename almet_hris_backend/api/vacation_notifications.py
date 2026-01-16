# api/vacation_notifications.py
"""
Vacation Notification Manager
Handles all email notifications for vacation workflow:
- Request created → Line Manager
- Line Manager approved → HR
- HR approved → Employee (Final Approval)
- Request rejected → Employee
- Schedule registered → Employee
"""

import logging
from .notification_service import notification_service
from .notification_models import NotificationSettings

logger = logging.getLogger(__name__)


class VacationNotificationManager:
    """Manager for Vacation related notifications"""
    
    def __init__(self):
        self.service = notification_service
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
                    vacation_subject_prefix='[VACATION]'
                )
        return self._settings
    
    def _get_subject_prefix(self, request_id):
        """Generate subject prefix with request ID"""
        prefix = self.settings.vacation_subject_prefix
        return f"{prefix} Request #{request_id}"
    
    def notify_request_created(self, vacation_request, access_token=None):
        """Notify Line Manager when request created"""
        try:
            line_manager = vacation_request.line_manager
            if not line_manager or not line_manager.user or not line_manager.user.email:
                logger.warning(f"No line manager email for {vacation_request.request_id}")
                return False
            
            subject = f"{self._get_subject_prefix(vacation_request.request_id)} - Pending Your Approval"
            
            # ✅ Half day display
            period_info = f"{vacation_request.start_date.strftime('%Y-%m-%d')} to {vacation_request.end_date.strftime('%Y-%m-%d')}"
            if vacation_request.is_half_day:
                period_info = f"{vacation_request.start_date.strftime('%Y-%m-%d')} (Half Day: {vacation_request.half_day_start_time.strftime('%H:%M')} - {vacation_request.half_day_end_time.strftime('%H:%M')})"
            
            body_html = f"""
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                    .header {{ background-color: #366092; color: white; padding: 20px; text-align: center; }}
                    .content {{ background-color: #f9f9f9; padding: 20px; border: 1px solid #ddd; }}
                    .info-row {{ margin: 10px 0; }}
                    .label {{ font-weight: bold; color: #366092; }}
                    .button {{ 
                        display: inline-block; 
                        padding: 12px 24px; 
                        background-color: #366092; 
                        color: white; 
                        text-decoration: none; 
                        border-radius: 5px; 
                        margin: 20px 0;
                    }}
                    .footer {{ margin-top: 20px; font-size: 12px; color: #777; text-align: center; }}
                    .half-day-badge {{ 
                        background-color: #FFA500; 
                        color: white; 
                        padding: 4px 8px; 
                        border-radius: 4px; 
                        font-size: 11px;
                        font-weight: bold;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h2>New Vacation Request</h2>
                    </div>
                    <div class="content">
                        <p>Dear {line_manager.full_name},</p>
                        <p>A new vacation request has been submitted and requires your approval.</p>
                        
                        <div class="info-row">
                            <span class="label">Request ID:</span> {vacation_request.request_id}
                        </div>
                        <div class="info-row">
                            <span class="label">Employee:</span> {vacation_request.employee.full_name}
                        </div>
                        <div class="info-row">
                            <span class="label">Vacation Type:</span> {vacation_request.vacation_type.name}
                            {' <span class="half-day-badge">HALF DAY</span>' if vacation_request.is_half_day else ''}
                        </div>
                        <div class="info-row">
                            <span class="label">Period:</span> {period_info}
                        </div>
                        <div class="info-row">
                            <span class="label">Duration:</span> {vacation_request.number_of_days} days
                        </div>
                        {f'<div class="info-row"><span class="label">Comment:</span> {vacation_request.comment}</div>' if vacation_request.comment else ''}
                        
                        <center>
                            <a href="https://myalmet.com/vacation" class="button">
                                Review Request
                            </a>
                        </center>
                    </div>
                    <div class="footer">
                        <p>This is an automated notification from Almet HRIS System</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            return self.service.send_email(
                recipient_email=line_manager.user.email,
                subject=subject,
                body_html=body_html,
                access_token=access_token,
                related_model='VacationRequest',
                related_object_id=vacation_request.id,
                sent_by=vacation_request.requester
            )
            
        except Exception as e:
            logger.error(f"Error sending request created notification: {e}")
            return False
    
    
    def notify_uk_additional_approval_needed(self, vacation_request, access_token=None):
        """✅ NEW: Notify UK Additional Approver"""
        try:
            uk_approver = vacation_request.uk_additional_approver
            if not uk_approver or not uk_approver.user or not uk_approver.user.email:
                logger.warning(f"No UK approver email for {vacation_request.request_id}")
                return False
            
            subject = f"{self._get_subject_prefix(vacation_request.request_id)} - UK Additional Approval Required"
            
            period_info = f"{vacation_request.start_date.strftime('%Y-%m-%d')} to {vacation_request.end_date.strftime('%Y-%m-%d')}"
            if vacation_request.is_half_day:
                period_info = f"{vacation_request.start_date.strftime('%Y-%m-%d')} (Half Day)"
            
            body_html = f"""
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                    .header {{ background-color: #8B0000; color: white; padding: 20px; text-align: center; }}
                    .content {{ background-color: #f9f9f9; padding: 20px; border: 1px solid #ddd; }}
                    .info-row {{ margin: 10px 0; }}
                    .label {{ font-weight: bold; color: #8B0000; }}
                    .approved {{ color: #28a745; font-weight: bold; }}
                    .button {{ 
                        display: inline-block; 
                        padding: 12px 24px; 
                        background-color: #8B0000; 
                        color: white; 
                        text-decoration: none; 
                        border-radius: 5px; 
                        margin: 20px 0;
                    }}
                    .uk-badge {{ 
                        background-color: #8B0000; 
                        color: white; 
                        padding: 4px 8px; 
                        border-radius: 4px; 
                        font-size: 11px;
                        font-weight: bold;
                    }}
                    .footer {{ margin-top: 20px; font-size: 12px; color: #777; text-align: center; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h2>UK Vacation Request - Additional Approval Required</h2>
                    </div>
                    <div class="content">
                        <p>Dear {uk_approver.full_name},</p>
                        <p class="approved">✓ Line Manager has approved this UK vacation request (5+ days).</p>
                        <p><span class="uk-badge">UK EMPLOYEE</span> This request now requires your additional approval as Vice Chairman.</p>
                        
                        <div class="info-row">
                            <span class="label">Request ID:</span> {vacation_request.request_id}
                        </div>
                        <div class="info-row">
                            <span class="label">Employee:</span> {vacation_request.employee.full_name}
                        </div>
                        <div class="info-row">
                            <span class="label">Business Function:</span> {vacation_request.employee.business_function.name if vacation_request.employee.business_function else 'N/A'}
                        </div>
                        <div class="info-row">
                            <span class="label">Vacation Type:</span> {vacation_request.vacation_type.name}
                        </div>
                        <div class="info-row">
                            <span class="label">Period:</span> {period_info}
                        </div>
                        <div class="info-row">
                            <span class="label">Duration:</span> {vacation_request.number_of_days} days
                        </div>
                        <div class="info-row">
                            <span class="label">Approved by Line Manager:</span> {vacation_request.line_manager.full_name if vacation_request.line_manager else 'N/A'}
                        </div>
                        {f'<div class="info-row"><span class="label">Line Manager Comment:</span> {vacation_request.line_manager_comment}</div>' if vacation_request.line_manager_comment else ''}
                        
                        <center>
                            <a href="https://myalmet.com/vacation" class="button">
                                Review & Approve Request
                            </a>
                        </center>
                        
                        <p style="margin-top: 20px; font-size: 14px; color: #666;">
                            This request requires your approval as UK employees with 5+ day vacation requests need Vice Chairman authorization.
                        </p>
                    </div>
                    <div class="footer">
                        <p>This is an automated notification from Almet HRIS System</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            return self.service.send_email(
                recipient_email=uk_approver.user.email,
                subject=subject,
                body_html=body_html,
                access_token=access_token,
                related_model='VacationRequest',
                related_object_id=vacation_request.id,
                sent_by=vacation_request.line_manager_approved_by
            )
            
        except Exception as e:
            logger.error(f"Error sending UK approval notification: {e}")
            return False
    
    def notify_uk_additional_approved(self, vacation_request, access_token=None):
        """✅ NEW: Notify HR when UK Additional Approver approves"""
        try:
            hr = vacation_request.hr_representative
            if not hr or not hr.user or not hr.user.email:
                logger.warning(f"No HR email for {vacation_request.request_id}")
                return False
            
            subject = f"{self._get_subject_prefix(vacation_request.request_id)} - UK Additional Approved - Pending HR"
            
            body_html = f"""
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                    .header {{ background-color: #366092; color: white; padding: 20px; text-align: center; }}
                    .content {{ background-color: #f9f9f9; padding: 20px; border: 1px solid #ddd; }}
                    .info-row {{ margin: 10px 0; }}
                    .label {{ font-weight: bold; color: #366092; }}
                    .approved {{ color: #28a745; font-weight: bold; }}
                    .button {{ 
                        display: inline-block; 
                        padding: 12px 24px; 
                        background-color: #366092; 
                        color: white; 
                        text-decoration: none; 
                        border-radius: 5px; 
                        margin: 20px 0;
                    }}
                    .footer {{ margin-top: 20px; font-size: 12px; color: #777; text-align: center; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h2>UK Vacation Request - HR Processing Required</h2>
                    </div>
                    <div class="content">
                        <p>Dear {hr.full_name},</p>
                        <p class="approved">✓ UK Additional Approver (Vice Chairman) has approved this request.</p>
                        <p>The request now requires your final HR processing and approval.</p>
                        
                        <div class="info-row">
                            <span class="label">Request ID:</span> {vacation_request.request_id}
                        </div>
                        <div class="info-row">
                            <span class="label">Employee:</span> {vacation_request.employee.full_name}
                        </div>
                        <div class="info-row">
                            <span class="label">Vacation Type:</span> {vacation_request.vacation_type.name}
                        </div>
                        <div class="info-row">
                            <span class="label">Duration:</span> {vacation_request.number_of_days} days
                        </div>
                        <div class="info-row">
                            <span class="label">UK Additional Approver:</span> {vacation_request.uk_additional_approver.full_name if vacation_request.uk_additional_approver else 'N/A'}
                        </div>
                        {f'<div class="info-row"><span class="label">UK Approver Comment:</span> {vacation_request.uk_additional_comment}</div>' if vacation_request.uk_additional_comment else ''}
                        
                        <center>
                            <a href="https://myalmet.com/vacation" class="button">
                                Process Request
                            </a>
                        </center>
                    </div>
                    <div class="footer">
                        <p>This is an automated notification from Almet HRIS System</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            return self.service.send_email(
                recipient_email=hr.user.email,
                subject=subject,
                body_html=body_html,
                access_token=access_token,
                related_model='VacationRequest',
                related_object_id=vacation_request.id,
                sent_by=vacation_request.uk_additional_approved_by
            )
            
        except Exception as e:
            logger.error(f"Error sending UK additional approved notification: {e}")
            return False
    def notify_line_manager_approved(self, vacation_request, access_token=None):
        """
        Notify HR when Line Manager approves
        
        Args:
            vacation_request: VacationRequest instance
            access_token: Microsoft Graph access token
        """
        try:
            hr = vacation_request.hr_representative
            if not hr or not hr.user or not hr.user.email:
                logger.warning(f"No HR representative email for vacation request {vacation_request.request_id}")
                return False
            
            subject = f"{self._get_subject_prefix(vacation_request.request_id)} - Line Manager Approved - Pending HR Processing"
            
            body_html = f"""
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                    .header {{ background-color: #366092; color: white; padding: 20px; text-align: center; }}
                    .content {{ background-color: #f9f9f9; padding: 20px; border: 1px solid #ddd; }}
                    .info-row {{ margin: 10px 0; }}
                    .label {{ font-weight: bold; color: #366092; }}
                    .approved {{ color: #28a745; font-weight: bold; }}
                    .button {{ 
                        display: inline-block; 
                        padding: 12px 24px; 
                        background-color: #366092; 
                        color: white; 
                        text-decoration: none; 
                        border-radius: 5px; 
                        margin: 20px 0;
                    }}
                    .footer {{ margin-top: 20px; font-size: 12px; color: #777; text-align: center; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h2>Vacation Request - HR Processing Required</h2>
                    </div>
                    <div class="content">
                        <p>Dear {hr.full_name},</p>
                        <p class="approved">✓ Line Manager has approved this vacation request.</p>
                        <p>The request now requires your final HR processing and approval.</p>
                        
                        <div class="info-row">
                            <span class="label">Request ID:</span> {vacation_request.request_id}
                        </div>
                        <div class="info-row">
                            <span class="label">Employee:</span> {vacation_request.employee.full_name}
                        </div>
                        <div class="info-row">
                            <span class="label">Department:</span> {vacation_request.employee.department.name if vacation_request.employee.department else 'N/A'}
                        </div>
                        <div class="info-row">
                            <span class="label">Vacation Type:</span> {vacation_request.vacation_type.name}
                        </div>
                        <div class="info-row">
                            <span class="label">Period:</span> {vacation_request.start_date.strftime('%Y-%m-%d')} to {vacation_request.end_date.strftime('%Y-%m-%d')}
                        </div>
                        <div class="info-row">
                            <span class="label">Duration:</span> {vacation_request.number_of_days} days
                        </div>
                        <div class="info-row">
                            <span class="label">Approved by:</span> {vacation_request.line_manager.full_name if vacation_request.line_manager else 'N/A'}
                        </div>
                        {f'<div class="info-row"><span class="label">Line Manager Comment:</span> {vacation_request.line_manager_comment}</div>' if vacation_request.line_manager_comment else ''}
                        
                        <center>
                            <a href="https://myalmet.com/vacation" class="button">
                                Process Request
                            </a>
                        </center>
                        
                        <p style="margin-top: 20px; font-size: 14px; color: #666;">
                            Please complete the HR processing and final approval.
                        </p>
                    </div>
                    <div class="footer">
                        <p>This is an automated notification from Almet HRIS System</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            return self.service.send_email(
                recipient_email=hr.user.email,
                subject=subject,
                body_html=body_html,
                access_token=access_token,
                related_model='VacationRequest',
                related_object_id=vacation_request.id,
                sent_by=vacation_request.line_manager_approved_by
            )
            
        except Exception as e:
            logger.error(f"Error sending line manager approved notification: {e}")
            return False
    
    def notify_hr_approved(self, vacation_request, access_token=None):
        """
        Notify Employee when HR approves (final approval)
        
        Args:
            vacation_request: VacationRequest instance
            access_token: Microsoft Graph access token
        """
        try:
            employee = vacation_request.employee
            if not employee.user or not employee.user.email:
                logger.warning(f"No employee email for vacation request {vacation_request.request_id}")
                return False
            
            subject = f"{self._get_subject_prefix(vacation_request.request_id)} - APPROVED ✓"
            
            body_html = f"""
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                    .header {{ background-color: #28a745; color: white; padding: 20px; text-align: center; }}
                    .content {{ background-color: #f9f9f9; padding: 20px; border: 1px solid #ddd; }}
                    .info-row {{ margin: 10px 0; }}
                    .label {{ font-weight: bold; color: #366092; }}
                    .success-box {{ 
                        background-color: #d4edda; 
                        border: 1px solid #c3e6cb; 
                        padding: 15px; 
                        margin: 20px 0; 
                        border-radius: 5px;
                        color: #155724;
                        text-align: center;
                        font-size: 18px;
                        font-weight: bold;
                    }}
                    .button {{ 
                        display: inline-block; 
                        padding: 12px 24px; 
                        background-color: #28a745; 
                        color: white; 
                        text-decoration: none; 
                        border-radius: 5px; 
                        margin: 20px 0;
                    }}
                    .footer {{ margin-top: 20px; font-size: 12px; color: #777; text-align: center; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h2>✓ Vacation Request Approved</h2>
                    </div>
                    <div class="content">
                        <p>Dear {employee.full_name},</p>
                        
                        <div class="success-box">
                            ✓ Your vacation request has been APPROVED!
                        </div>
                        
                        <p>All required approvals have been completed. Your vacation details are as follows:</p>
                        
                        <div class="info-row">
                            <span class="label">Request ID:</span> {vacation_request.request_id}
                        </div>
                        <div class="info-row">
                            <span class="label">Vacation Type:</span> {vacation_request.vacation_type.name}
                        </div>
                        <div class="info-row">
                            <span class="label">Period:</span> {vacation_request.start_date.strftime('%Y-%m-%d')} to {vacation_request.end_date.strftime('%Y-%m-%d')}
                        </div>
                        <div class="info-row">
                            <span class="label">Duration:</span> {vacation_request.number_of_days} days
                        </div>
                        <div class="info-row">
                            <span class="label">Return Date:</span> {vacation_request.return_date.strftime('%Y-%m-%d') if vacation_request.return_date else 'N/A'}
                        </div>
                        
                        <center>
                            <a href="https://myalmet.com/vacation" class="button">
                                View Vacation Details
                            </a>
                        </center>
                        
                        <p style="margin-top: 20px; font-size: 14px; color: #666;">
                            Enjoy your time off!
                        </p>
                    </div>
                    <div class="footer">
                        <p>This is an automated notification from Almet HRIS System</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            return self.service.send_email(
                recipient_email=employee.user.email,
                subject=subject,
                body_html=body_html,
                access_token=access_token,
                related_model='VacationRequest',
                related_object_id=vacation_request.id,
                sent_by=vacation_request.hr_approved_by
            )
            
        except Exception as e:
            logger.error(f"Error sending HR approved notification: {e}")
            return False
    
    def notify_request_rejected(self, vacation_request, access_token=None):
        """
        Notify Employee when request is rejected
        
        Args:
            vacation_request: VacationRequest instance
            access_token: Microsoft Graph access token
        """
        try:
            employee = vacation_request.employee
            if not employee.user or not employee.user.email:
                logger.warning(f"No employee email for vacation request {vacation_request.request_id}")
                return False
            
            # Determine who rejected
            rejected_by_name = "Unknown"
            rejection_stage = "Unknown"
            
            if vacation_request.status == 'REJECTED_LINE_MANAGER':
                rejected_by_name = vacation_request.line_manager.full_name if vacation_request.line_manager else "Line Manager"
                rejection_stage = "Line Manager Review"
            elif vacation_request.status == 'REJECTED_HR':
                rejected_by_name = vacation_request.hr_representative.full_name if vacation_request.hr_representative else "HR"
                rejection_stage = "HR Review"
            
            subject = f"{self._get_subject_prefix(vacation_request.request_id)} - REJECTED ✗"
            
            body_html = f"""
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                    .header {{ background-color: #dc3545; color: white; padding: 20px; text-align: center; }}
                    .content {{ background-color: #f9f9f9; padding: 20px; border: 1px solid #ddd; }}
                    .info-row {{ margin: 10px 0; }}
                    .label {{ font-weight: bold; color: #366092; }}
                    .reject-box {{ 
                        background-color: #f8d7da; 
                        border: 1px solid #f5c6cb; 
                        padding: 15px; 
                        margin: 20px 0; 
                        border-radius: 5px;
                        color: #721c24;
                    }}
                    .button {{ 
                        display: inline-block; 
                        padding: 12px 24px; 
                        background-color: #366092; 
                        color: white; 
                        text-decoration: none; 
                        border-radius: 5px; 
                        margin: 20px 0;
                    }}
                    .footer {{ margin-top: 20px; font-size: 12px; color: #777; text-align: center; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h2>✗ Vacation Request Rejected</h2>
                    </div>
                    <div class="content">
                        <p>Dear {employee.full_name},</p>
                        
                        <div class="reject-box">
                            <p style="margin: 0; font-weight: bold;">Your vacation request has been rejected.</p>
                        </div>
                        
                        <div class="info-row">
                            <span class="label">Request ID:</span> {vacation_request.request_id}
                        </div>
                        <div class="info-row">
                            <span class="label">Rejected at:</span> {rejection_stage}
                        </div>
                        <div class="info-row">
                            <span class="label">Rejected by:</span> {rejected_by_name}
                        </div>
                        <div class="info-row">
                            <span class="label">Vacation Type:</span> {vacation_request.vacation_type.name}
                        </div>
                        <div class="info-row">
                            <span class="label">Period:</span> {vacation_request.start_date.strftime('%Y-%m-%d')} to {vacation_request.end_date.strftime('%Y-%m-%d')}
                        </div>
                        
                        {f'''
                        <div class="reject-box" style="margin-top: 20px;">
                            <p style="margin: 0;"><span class="label">Reason for Rejection:</span></p>
                            <p style="margin: 10px 0 0 0;">{vacation_request.rejection_reason}</p>
                        </div>
                        ''' if vacation_request.rejection_reason else ''}
                        
                        <center>
                            <a href="https://www.myalmet.com/requests/vacation/" class="button">
                                View Request Details
                            </a>
                        </center>
                        
                        <p style="margin-top: 20px; font-size: 14px; color: #666;">
                            If you have questions about this rejection, please contact {rejected_by_name} or your HR representative.
                        </p>
                    </div>
                    <div class="footer">
                        <p>This is an automated notification from Almet HRIS System</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            return self.service.send_email(
                recipient_email=employee.user.email,
                subject=subject,
                body_html=body_html,
                access_token=access_token,
                related_model='VacationRequest',
                related_object_id=vacation_request.id,
                sent_by=vacation_request.rejected_by
            )
            
        except Exception as e:
            logger.error(f"Error sending rejection notification: {e}")
            return False
    
    def notify_schedule_registered(self, vacation_schedule, access_token=None):
        """
        Notify Employee when their schedule is registered as taken
        
        Args:
            vacation_schedule: VacationSchedule instance
            access_token: Microsoft Graph access token
        """
        try:
            employee = vacation_schedule.employee
            if not employee.user or not employee.user.email:
                logger.warning(f"No employee email for vacation schedule {vacation_schedule.id}")
                return False
            
            subject = f"[VACATION] Schedule Registered - SCH{vacation_schedule.id}"
            
            body_html = f"""
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                    .header {{ background-color: #28a745; color: white; padding: 20px; text-align: center; }}
                    .content {{ background-color: #f9f9f9; padding: 20px; border: 1px solid #ddd; }}
                    .info-row {{ margin: 10px 0; }}
                    .label {{ font-weight: bold; color: #366092; }}
                    .footer {{ margin-top: 20px; font-size: 12px; color: #777; text-align: center; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h2>Vacation Schedule Registered</h2>
                    </div>
                    <div class="content">
                        <p>Dear {employee.full_name},</p>
                        <p>Your vacation schedule has been registered as taken.</p>
                        
                        <div class="info-row">
                            <span class="label">Schedule ID:</span> SCH{vacation_schedule.id}
                        </div>
                        <div class="info-row">
                            <span class="label">Vacation Type:</span> {vacation_schedule.vacation_type.name}
                        </div>
                        <div class="info-row">
                            <span class="label">Period:</span> {vacation_schedule.start_date.strftime('%Y-%m-%d')} to {vacation_schedule.end_date.strftime('%Y-%m-%d')}
                        </div>
                        <div class="info-row">
                            <span class="label">Duration:</span> {vacation_schedule.number_of_days} days
                        </div>
                        
                        <p style="margin-top: 20px; font-size: 14px; color: #666;">
                            Your vacation balance has been updated accordingly.
                        </p>
                    </div>
                    <div class="footer">
                        <p>This is an automated notification from Almet HRIS System</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            return self.service.send_email(
                recipient_email=employee.user.email,
                subject=subject,
                body_html=body_html,
                access_token=access_token,
                related_model='VacationSchedule',
                related_object_id=vacation_schedule.id,
                sent_by=vacation_schedule.last_edited_by or vacation_schedule.created_by
            )
            
        except Exception as e:
            logger.error(f"Error sending schedule registered notification: {e}")
            return False


# Singleton instance
notification_manager = VacationNotificationManager()