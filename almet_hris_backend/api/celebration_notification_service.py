# api/celebration_notification_service.py
"""
Celebration Notification Service
- Birthday notifications
- Work anniversary notifications  
- Position change (promotion/transfer) notifications
Sends emails using system mailbox (Application Permissions)
"""

import logging
from datetime import date, timedelta
from django.utils import timezone
from .models import Employee
from .celebration_models import Celebration, CelebrationWish
from .system_email_service import system_email_service
from .notification_models import NotificationSettings

logger = logging.getLogger(__name__)


class CelebrationNotificationService:
    """
    Celebration notification handler
    Sends emails from system mailbox to all staff distribution lists
    """
    
    def __init__(self):
        self.system_sender = 'myalmet@almettrading.com'
        
        # 📧 Distribution lists for all staff
        self.all_staff_emails = [
            'alltradeuk@almettrading.co.uk',    # UK
            'alltrade@almettrading.com',        # LLC
            'allholding@almettrading.com',      # Holding
            # 'n.orujova@almettrading.com',
            # 'n.garibova@almettrading.com'
        ]
    
    def send_birthday_notification(self, employee):
        """
        🎂 Send birthday celebration email (NO AGE)
    
        Args:
            employee: Employee instance
    
        Returns:
            bool: Success status
        """
        try:
            if not employee.date_of_birth:
                logger.warning(f"No birth date for {employee.first_name} {employee.last_name}")
                return False
    
            # Email subject
            subject = f"🎂 Happy Birthday {employee.first_name} {employee.last_name}!"
    
            # Email body (Outlook-friendly / table-based)
            body_html = f"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Happy Birthday</title>
</head>

<body style="margin:0; padding:0; background:#EEF2F7;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#EEF2F7; padding:26px 0;">
    <tr>
      <td align="center">

        <!-- Outer wrapper -->
        <table role="presentation" width="800" cellspacing="0" cellpadding="0"
               style="width:800px; max-width:800px;">

         

          <!-- Card -->
          <tr>
            <td style="background:#FFFFFF; border-radius:18px; overflow:hidden; box-shadow:0 10px 26px rgba(16,24,40,0.10);">

              <!-- Slim header bar -->
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
                <tr>
                  <td style="background:#30539b; height:8px; line-height:8px; font-size:0;">&nbsp;</td>
                </tr>
              </table>

              <!-- Header content -->
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="padding:22px 26px 10px 26px;">
                <tr>
                  <td style="font-family:Segoe UI, Arial, sans-serif;">
                    
                    <div style="font-size:26px; font-weight:800; color:#101828; margin-top:6px; letter-spacing:-0.2px;">
                      Happy Birthday, {employee.first_name} {employee.last_name}! <span style="font-weight:700;">🎉</span>
                    </div>
                  </td>
                </tr>
              </table>

              <!-- Main content -->
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="padding:0 26px 22px 26px;">
                <tr>
                  <td style="font-family:Segoe UI, Arial, sans-serif; color:#101828;">

                    <!-- Greeting -->
                    <div style="font-size:16px; line-height:1.7; margin-top:8px;">
                      Dear Team,<br><br>
                      Today we celebrate <b>{employee.first_name} {employee.last_name}</b>’s birthday. 🎈🎂
                    </div>

                    <!-- Soft highlight (NOT boxy) -->
                    <table role="presentation" width="100%" cellspacing="0" cellpadding="0"
                           style="margin:16px 0 10px 0; background:#F6F8FF; border-radius:14px;">
                      <tr>
                        <td style="padding: 14px;">
                          <div style="font-size:14px; font-weight:800; color:#30539b; margin-bottom:6px;">
                            A warm wish 💙
                          </div>
                          <div style="font-size:15px; line-height:1.7; color:#101828;">
                            Please join us in wishing {employee.first_name} a wonderful day filled with joy,
                            positivity, and success.
                          </div>
                        </td>
                      </tr>
                    </table>

                   

                    <div style="font-size:14px; line-height:1.7; color:#475467; margin-top:12px;">
                      Thank you for being a valued member of the Almet family. We appreciate your hard work and dedication.
                    </div>

                    <!-- CTA button -->
                    <table role="presentation" cellspacing="0" cellpadding="0" style="margin-top:16px;">
                      <tr>
                        <td style=" border-radius:12px;">
                          <span style="display:inline-block; padding:12px 16px; color:#30539b; font-size:14px; font-weight:800;">
                            🎁 Wishing you a fantastic year ahead!
                          </span>
                        </td>
                      </tr>
                    </table>

                  </td>
                </tr>
              </table>

              <!-- Footer -->
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#FBFCFE; border-top:1px solid #EEF2F6;">
                <tr>
                  <td style="padding:14px 26px; font-family:Segoe UI, Arial, sans-serif; color:#667085; font-size:12px; line-height:1.6;">
                    This is an automated celebration notification from Almet Holding.<br>
                    © {date.today().year} Almet Holding. All rights reserved.
                  </td>
                </tr>
              </table>

            </td>
          </tr>

        

        </table>

      </td>
    </tr>
  </table>
</body>
</html>
"""

    
            # Send to all staff distribution lists
            success_count = 0
            for recipient in self.all_staff_emails:
                result = system_email_service.send_email_as_system(
                    from_email=self.system_sender,
                    to_email=recipient,
                    subject=subject,
                    body_html=body_html
                )
    
                if result.get('success'):
                    success_count += 1
                    logger.info(f"✅ Birthday email sent to {recipient}")
                else:
                    logger.error(f"❌ Failed to send birthday email to {recipient}: {result.get('message')}")
    
            return success_count > 0
    
        except Exception as e:
            logger.error(f"Error sending birthday notification: {e}")
            return False

    def send_work_anniversary_notification(self, employee, years):
        """
        🏆 Send work anniversary celebration email
        """
        try:
            if not employee.start_date:
                logger.warning(f"No start date for {employee.first_name} {employee.last_name}")
                return False
    
            subject = f"🏆 {years} Year{'s' if years != 1 else ''} with Almet – {employee.first_name}!"
    
            body_html = f"""
    <!doctype html>
    <html>
    <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Work Anniversary</title>
    </head>
    
    <body style="margin:0; padding:0; background:#EEF2F7;">
    <table width="100%" cellspacing="0" cellpadding="0" style="background:#EEF2F7; padding:26px 0;">
    <tr>
    <td align="center">
    
    <table width="800" cellspacing="0" cellpadding="0" style="width:800px; max-width:800px;">

    
    <tr>
    <td style="background:#FFFFFF; border-radius:18px; overflow:hidden;
               box-shadow:0 10px 26px rgba(16,24,40,0.10);">
    
    <!-- Accent line -->
    <table width="100%" cellspacing="0" cellpadding="0">
    <tr><td style="background:#253360; height:8px; font-size:0;"></td></tr>
    </table>
    
    <!-- Header -->
    <table width="100%" cellspacing="0" cellpadding="0" style="padding:22px 26px 10px 26px;">
    <tr>
    <td style="font-family:Segoe UI, Arial, sans-serif;">
  
    <div style="font-size:26px; margin-bottom:8px; font-weight:800; color:#101828; margin-top:6px;">
    {years} Year Anniversary 🎉
    </div>
    </td>
    </tr>
    </table>
    
    <!-- Content -->
    <table width="100%" cellspacing="0" cellpadding="0" style="padding:0 26px 22px 26px;">
    <tr>
    <td style="font-family:Segoe UI, Arial, sans-serif; color:#101828;">
    
    <div style="font-size:16px; line-height:1.7;">
    Dear Team,<br><br>
    Today we celebrate <b>{employee.first_name} {employee.last_name}</b>’s
    <b>{years}-year anniversary</b> with Almet Holding.
    </div>
    
    <!-- Soft highlight -->
    <table width="100%" cellspacing="0" cellpadding="0"
           style="margin:16px 0; background:#F6F8FF; border-radius:14px;">
    <tr>
    <td style="padding:16px;">
    <div style="font-size:14px; font-weight:800; color:#253360; margin-bottom:6px;">
    Thank you for the journey 💙
    </div>
    <div style="font-size:15px; line-height:1.7;">
    Your dedication, professionalism, and contribution have made a meaningful
    impact on our team and company.
    </div>
    </td>
    </tr>
    </table>
    

    
    <div style="font-size:14px; color:#475467; line-height:1.7; margin-top:12px;">
    Here’s to many more successful years together! 🥂
    </div>
    
    </td>
    </tr>
    </table>
    
    <!-- Footer -->
    <table width="100%" cellspacing="0" cellpadding="0" style="border-top:1px solid #EEF2F6;">
    <tr>
    <td style="padding:14px 26px; font-size:12px; color:#667085; font-family:Segoe UI, Arial;">
    This is an automated celebration notification from Almet Holding.<br>
    © {date.today().year} Almet Holding. All rights reserved.
    </td>
    </tr>
    </table>
    
    </td>
    </tr>
    

    
    </table>
    
    </td>
    </tr>
    </table>
    </body>
    </html>
    """
    
            success_count = 0
            for recipient in self.all_staff_emails:
                result = system_email_service.send_email_as_system(
                    from_email=self.system_sender,
                    to_email=recipient,
                    subject=subject,
                    body_html=body_html
                )
                if result.get("success"):
                    success_count += 1
    
            return success_count > 0
    
        except Exception as e:
            logger.error(f"Error sending anniversary notification: {e}")
            return False

    def send_position_change_notification(self, employee, old_position, new_position, change_type="promotion"):
        """
        📈 Promotion / Role Change email
        """
        try:
            if change_type == "promotion":
                subject = f"🎉 Congratulations {employee.first_name} on Your Promotion!"
                accent = "#0B6B4D"
                title = "Promotion Announcement"
  
                intro = "We are delighted to announce"
            else:
                subject = f"🔄 {employee.first_name} – New Role Announcement"
                accent = "#1D4ED8"
                title = "Role Change Announcement"
            
                intro = "We are pleased to announce"
    
            body_html = f"""
    <!doctype html>
    <html>
    <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{title}</title>
    </head>
    
    <body style="margin:0; padding:0; background:#EEF2F7;">
    <table width="100%" cellspacing="0" cellpadding="0" style="background:#EEF2F7; padding:26px 0;">
    <tr>
    <td align="center">
    
    <table width="800" cellspacing="0" cellpadding="0">
    
    <tr>
    <td style="background:#FFFFFF; border-radius:18px; overflow:hidden;
               box-shadow:0 10px 26px rgba(16,24,40,0.10);">
    
    <!-- Accent -->
    <table width="100%" cellspacing="0" cellpadding="0">
    <tr><td style="background:{accent}; height:8px;"></td></tr>
    </table>
    
    <!-- Header -->
    <table width="100%" cellspacing="0" cellpadding="0" style="padding:22px 26px 10px 26px;">
    <tr>
    <td style="font-family:Segoe UI, Arial;">
   
    <div style="font-size:26px; font-weight:800; color:#101828; margin-top:6px;">
     {title}
    </div>
    </td>
    </tr>
    </table>
    
    <!-- Content -->
    <table width="100%" cellspacing="0" cellpadding="0" style="padding:0 26px 22px 26px;">
    <tr>
    <td style="font-family:Segoe UI, Arial; color:#101828;">
    
    <div style="font-size:16px; margin-bottom:8px; line-height:1.7;">
    Dear Team,<br><br>
    {intro} that <b>{employee.first_name} {employee.last_name}</b>
    has moved into a new role.
    </div>
    
    <!-- Position flow -->
    <table width="100%" cellspacing="0" cellpadding="0"
           style="margin:18px 0; background:#F6F8FF; border-radius:14px;">
    <tr>
    <td style="padding:16px; text-align:center;">
    <span style="display:inline-block; padding:10px 14px; border-radius:10px;
                 background:#FFFFFF; font-weight:700;">
    {old_position}
    </span>
    <span style="margin:0 12px; font-weight:800;">→</span>
    <span style="display:inline-block; padding:10px 14px; border-radius:10px;
                 background:#FFFFFF; font-weight:800;">
    {new_position}
    </span>
    </td>
    </tr>
    </table>
    
    <div style="font-size:15px; margin-top:8px; line-height:1.7;">
    {employee.first_name} has consistently demonstrated professionalism,
    dedication, and strong performance. We are confident this change
    will bring new opportunities for growth and success.
    </div>
    

    
    </td>
    </tr>
    </table>
    
    <!-- Footer -->
    <table width="100%" cellspacing="0" cellpadding="0" style="border-top:1px solid #EEF2F6;">
    <tr>
    <td style="padding:14px 26px; font-size:12px; color:#667085; font-family:Segoe UI, Arial;">
    This is an automated celebration notification from Almet Holding.<br>
    © {date.today().year} Almet Holding. All rights reserved.
    </td>
    </tr>
    </table>
    
    </td>
    </tr>
    </table>
    
    </td>
    </tr>
    </table>
    </body>
    </html>
    """
    
            success_count = 0
            for recipient in self.all_staff_emails:
                result = system_email_service.send_email_as_system(
                    from_email=self.system_sender,
                    to_email=recipient,
                    subject=subject,
                    body_html=body_html
                )
                if result.get("success"):
                    success_count += 1
    
            return success_count > 0
    
        except Exception as e:
            logger.error(f"Error sending position change notification: {e}")
            return False
    
    def send_welcome_email(self, employee):
        """
        👋 Send welcome email to new employee (soft card / Outlook-friendly)
    
        Args:
            employee: Employee instance
    
        Returns:
            bool: Success status
        """
        try:
            subject = f"🎉 Welcome to Almet Holding, {employee.first_name}!"
    
            full_name = f"{employee.first_name} {employee.last_name}".strip()
            position = employee.position_group or "Team Member"
            department = employee.department or "N/A"
            email = employee.email or "N/A"
            start_date = employee.start_date.strftime("%B %d, %Y") if employee.start_date else "N/A"
    
            body_html = f"""
    <!doctype html>
    <html>
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <title>Welcome</title>
    </head>
    
    <body style="margin:0; padding:0; background:#EEF2F7;">
      <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#EEF2F7; padding:26px 0;">
        <tr>
          <td align="center">
    
            <table role="presentation" width="800" cellspacing="0" cellpadding="0" style="width:800px; max-width:800px;">
    
          
    
              <!-- Card -->
              <tr>
                <td style="background:#FFFFFF; border-radius:18px; overflow:hidden; box-shadow:0 10px 26px rgba(16,24,40,0.10);">
    
                  <!-- Accent line -->
                  <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
                    <tr><td style="background:#30539b; height:8px; font-size:0; line-height:8px;">&nbsp;</td></tr>
                  </table>
    
                  <!-- Header -->
                  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="padding:22px 26px 10px 26px;">
                    <tr>
                      <td style="font-family:Segoe UI, Arial, sans-serif;">
                      
                        <div style="font-size:26px; font-weight:800; color:#101828; margin-top:6px; letter-spacing:-0.2px;">
                          Welcome to the team, {employee.first_name}! 🎉
                        </div>
                        <div style="font-size:14px; color:#475467; margin-top:8px; line-height:1.6;">
                          We’re excited to have you with us.
                        </div>
                      </td>
                    </tr>
                  </table>
    
                  <!-- Content -->
                  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="padding:0 26px 22px 26px;">
                    <tr>
                      <td style="font-family:Segoe UI, Arial, sans-serif; color:#101828;">
    
                        <div style="font-size:16px; margin-bottom:12px; line-height:1.7; margin-top:6px;">
                          Dear Team,<br><br>
                          Please join us in welcoming <b>{full_name}</b> to the Almet Holding family. 🌟
                        </div>
    
                        <!-- Profile (soft, not boxy) -->
                        <table role="presentation" width="100%" cellspacing="0" cellpadding="0"
                               style="margin:16px 0; background:#F6F8FF; border-radius:14px;">
                          <tr>
                            <td style="padding:16px;">
                              <div style="font-size:14px; font-weight:800; color:#30539b; margin-bottom:10px;">
                                New team member
                              </div>
    
                              <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
                                <tr>
                                  <td style="padding:10px 12px; background:#FFFFFF; border-radius:12px;">
                                    <div style="font-size:18px; font-weight:800; color:#101828;">{full_name}</div>
                                    <div style="font-size:13px; color:#475467; margin-top:4px;">
                                      {position}{f" • {department}" if department != "N/A" else ""}
                                    </div>
                                  </td>
                                </tr>
                              </table>
    
                             
                            </td>
                          </tr>
                        </table>
    
                        <div style="font-size:15px; margin-top:8px; line-height:1.7; color:#101828;">
                          {employee.first_name} is joining us as <b>{position}</b>
                          {f"in the <b>{department}</b> department" if department != "N/A" else ""}.
                          We’re confident {employee.first_name} will be a valuable addition to our team.
                        </div>
    
                       
    
                        <div style="font-size:14px; line-height:1.7; color:#475467; margin-top:12px;">
                          Let’s make sure {employee.first_name} feels right at home and has everything needed to succeed in this new role.
                        </div>
    
                        <!-- CTA -->
                        <table role="presentation" cellspacing="0" cellpadding="0" style="margin-top:16px;">
                          <tr>
                            <td style=" border-radius:12px;">
                              <span style="display:inline-block; padding:12px 16px; color:#30539b; font-size:14px; font-weight:800;">
                                🎉 Welcome aboard, {employee.first_name}!
                              </span>
                            </td>
                          </tr>
                        </table>
    
                      </td>
                    </tr>
                  </table>
    
                  <!-- Footer -->
                  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#FBFCFE; border-top:1px solid #EEF2F6;">
                    <tr>
                      <td style="padding:14px 26px; font-family:Segoe UI, Arial, sans-serif; color:#667085; font-size:12px; line-height:1.6;">
                        This is an automated welcome notification from Almet Holding.<br>
                        © {date.today().year} Almet Holding. All rights reserved.
                      </td>
                    </tr>
                  </table>
    
                </td>
              </tr>
    
            
    
            </table>
    
          </td>
        </tr>
      </table>
    </body>
    </html>
    """
    
            success_count = 0
            for recipient in self.all_staff_emails:
                result = system_email_service.send_email_as_system(
                    from_email=self.system_sender,
                    to_email=recipient,
                    subject=subject,
                    body_html=body_html
                )
    
                if result.get("success"):
                    success_count += 1
                    logger.info(f"✅ Welcome email sent to {recipient}")
                else:
                    logger.error(f"❌ Failed to send welcome email to {recipient}: {result.get('message')}")
    
            return success_count > 0
    
        except Exception as e:
            logger.error(f"Error sending welcome notification: {e}")
            return False

    def check_and_send_daily_celebrations(self):
        """
        🔄 Daily check for birthdays and work anniversaries
        Run this as a scheduled task (e.g., daily at 9 AM)
        
        Returns:
            dict: Summary of sent notifications
        """
        today = date.today()
        results = {
            'birthdays_sent': 0,
            'anniversaries_sent': 0,
            'errors': []
        }
        
        try:
            employees = Employee.objects.filter(is_deleted=False)
            
            for emp in employees:
                # Check birthdays
                if emp.date_of_birth:
                    if emp.date_of_birth.month == today.month and emp.date_of_birth.day == today.day:
                        logger.info(f"🎂 Processing birthday for {emp.first_name} {emp.last_name}")
                        if self.send_birthday_notification(emp):
                            results['birthdays_sent'] += 1
                
                # Check work anniversaries
                if emp.start_date:
                    if emp.start_date.month == today.month and emp.start_date.day == today.day:
                        years = today.year - emp.start_date.year
                        if years > 0:  # At least 1 year
                            logger.info(f"🏆 Processing {years}-year anniversary for {emp.first_name} {emp.last_name}")
                            if self.send_work_anniversary_notification(emp, years):
                                results['anniversaries_sent'] += 1
            
            logger.info(f"✅ Daily celebration check complete: {results}")
            return results
            
        except Exception as e:
            error_msg = f"Error in daily celebration check: {e}"
            logger.error(error_msg)
            results['errors'].append(error_msg)
            return results


# Singleton instance
celebration_notification_service = CelebrationNotificationService()