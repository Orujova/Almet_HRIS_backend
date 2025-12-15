# api/tasks.py
from celery import shared_task
from django.utils import timezone
from datetime import date
import logging

logger = logging.getLogger(__name__)

# ==================== EMPLOYEE STATUS TASKS ====================

@shared_task(name='api.tasks.update_all_employee_statuses')
def update_all_employee_statuses():
    """
    Celery task to automatically update all employee statuses based on contract dates
    Runs periodically (hourly/daily) to ensure status is always current
    """
    from .models import Employee
    from .status_management import EmployeeStatusManager
    
    try:
        logger.info("=" * 80)
        logger.info(f"🔄 AUTOMATIC STATUS UPDATE STARTED: {timezone.now()}")
        logger.info("=" * 80)
        
        # Get all active employees (not deleted)
        employees = Employee.objects.filter(is_deleted=False).select_related('status', 'business_function', 'department')
        
        total_employees = employees.count()
        updated_count = 0
        error_count = 0
        
        logger.info(f"📊 Processing {total_employees} employees")
        
        for employee in employees:
            try:
                # Check if status needs update
                preview = EmployeeStatusManager.get_status_preview(employee)
                
                if preview['needs_update']:
                    logger.info(f"⚡ Updating employee {employee.employee_id} ({employee.full_name})")
                    logger.info(f"   Current: {preview['current_status']} → Required: {preview['required_status']}")
                    logger.info(f"   Reason: {preview['reason']}")
                    
                    # Update the status
                    if EmployeeStatusManager.update_employee_status(employee, force_update=False, user=None):
                        updated_count += 1
                        logger.info(f"   ✅ Updated successfully")
                    else:
                        logger.warning(f"   ⚠️ Update returned False for {employee.employee_id}")
                
            except Exception as e:
                error_count += 1
                logger.error(f"❌ Error updating employee {employee.employee_id}: {str(e)}")
                continue
        
        logger.info("=" * 80)
        logger.info(f"✅ AUTOMATIC STATUS UPDATE COMPLETED")
        logger.info(f"📊 Total Employees: {total_employees}")
        logger.info(f"🔄 Updated: {updated_count}")
        logger.info(f"❌ Errors: {error_count}")
        logger.info(f"⏰ Completed at: {timezone.now()}")
        logger.info("=" * 80)
        
        return {
            'success': True,
            'total_employees': total_employees,
            'updated_count': updated_count,
            'error_count': error_count,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"💥 CRITICAL ERROR in automatic status update: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task(name='api.tasks.update_single_employee_status')
def update_single_employee_status(employee_id):
    """Update status for a single employee"""
    from .models import Employee
    from .status_management import EmployeeStatusManager
    
    try:
        employee = Employee.objects.get(id=employee_id)
        result = EmployeeStatusManager.update_employee_status(employee, force_update=False, user=None)
        
        logger.info(f"✅ Single employee update: {employee.employee_id} - Result: {result}")
        return {'success': True, 'updated': result}
        
    except Employee.DoesNotExist:
        logger.error(f"❌ Employee {employee_id} not found")
        return {'success': False, 'error': 'Employee not found'}
    except Exception as e:
        logger.error(f"❌ Error updating employee {employee_id}: {str(e)}")
        return {'success': False, 'error': str(e)}


# ==================== CELEBRATION NOTIFICATION TASKS ====================

@shared_task(name='api.tasks.send_daily_celebration_notifications')
def send_daily_celebration_notifications():
    """
    🎉 Send daily celebration notifications for birthdays and work anniversaries
    Runs every day at 9:00 AM
    """
    from .celebration_notification_service import celebration_notification_service
    
    try:
        logger.info("=" * 80)
        logger.info(f"🎉 DAILY CELEBRATION CHECK STARTED: {timezone.now()}")
        logger.info("=" * 80)
        
        results = celebration_notification_service.check_and_send_daily_celebrations()
        
        logger.info("=" * 80)
        logger.info(f"✅ DAILY CELEBRATION CHECK COMPLETED")
        logger.info(f"🎂 Birthdays sent: {results['birthdays_sent']}")
        logger.info(f"🏆 Anniversaries sent: {results['anniversaries_sent']}")
        logger.info(f"❌ Errors: {len(results.get('errors', []))}")
        logger.info(f"⏰ Completed at: {timezone.now()}")
        logger.info("=" * 80)
        
        return {
            'success': True,
            'birthdays_sent': results['birthdays_sent'],
            'anniversaries_sent': results['anniversaries_sent'],
            'errors': results.get('errors', []),
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        error_msg = f"💥 CRITICAL ERROR in daily celebration check: {str(e)}"
        logger.error(error_msg)
        import traceback
        logger.error(traceback.format_exc())
        
        return {
            'success': False,
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task(name='api.tasks.send_position_change_email')
def send_position_change_email(employee_id, old_position, new_position, change_type='promotion'):
    """
    📧 Send position change notification email (async)
    
    Args:
        employee_id: Employee ID
        old_position: Previous position
        new_position: New position
        change_type: 'promotion' or 'transfer'
    """
    from .models import Employee
    from .celebration_notification_service import celebration_notification_service
    
    try:
        employee = Employee.objects.get(id=employee_id)
        
        logger.info(f"📧 Sending position change notification for {employee.first_name} {employee.last_name}")
        
        success = celebration_notification_service.send_position_change_notification(
            employee=employee,
            old_position=old_position,
            new_position=new_position,
            change_type=change_type
        )
        
        if success:
            logger.info(f"✅ Position change notification sent successfully")
            return {'success': True, 'employee_id': employee_id}
        else:
            logger.error(f"❌ Failed to send position change notification")
            return {'success': False, 'employee_id': employee_id, 'error': 'Send failed'}
        
    except Employee.DoesNotExist:
        error_msg = f"❌ Employee {employee_id} not found"
        logger.error(error_msg)
        return {'success': False, 'error': 'Employee not found'}
    except Exception as e:
        error_msg = f"❌ Error sending position change email: {str(e)}"
        logger.error(error_msg)
        import traceback
        logger.error(traceback.format_exc())
        return {'success': False, 'error': str(e)}


@shared_task(name='api.tasks.send_birthday_notification')
def send_birthday_notification(employee_id):
    """
    🎂 Send birthday notification email (async)
    """
    from .models import Employee
    from .celebration_notification_service import celebration_notification_service
    
    try:
        employee = Employee.objects.get(id=employee_id)
        
        logger.info(f"🎂 Sending birthday notification for {employee.first_name} {employee.last_name}")
        
        success = celebration_notification_service.send_birthday_notification(employee)
        
        if success:
            logger.info(f"✅ Birthday notification sent successfully")
            return {'success': True, 'employee_id': employee_id}
        else:
            logger.error(f"❌ Failed to send birthday notification")
            return {'success': False, 'employee_id': employee_id, 'error': 'Send failed'}
        
    except Employee.DoesNotExist:
        error_msg = f"❌ Employee {employee_id} not found"
        logger.error(error_msg)
        return {'success': False, 'error': 'Employee not found'}
    except Exception as e:
        error_msg = f"❌ Error sending birthday email: {str(e)}"
        logger.error(error_msg)
        return {'success': False, 'error': str(e)}


@shared_task(name='api.tasks.send_anniversary_notification')
def send_anniversary_notification(employee_id, years):
    """
    🏆 Send work anniversary notification email (async)
    """
    from .models import Employee
    from .celebration_notification_service import celebration_notification_service
    
    try:
        employee = Employee.objects.get(id=employee_id)
        
        logger.info(f"🏆 Sending {years}-year anniversary notification for {employee.first_name} {employee.last_name}")
        
        success = celebration_notification_service.send_work_anniversary_notification(employee, years)
        
        if success:
            logger.info(f"✅ Anniversary notification sent successfully")
            return {'success': True, 'employee_id': employee_id, 'years': years}
        else:
            logger.error(f"❌ Failed to send anniversary notification")
            return {'success': False, 'employee_id': employee_id, 'error': 'Send failed'}
        
    except Employee.DoesNotExist:
        error_msg = f"❌ Employee {employee_id} not found"
        logger.error(error_msg)
        return {'success': False, 'error': 'Employee not found'}
    except Exception as e:
        error_msg = f"❌ Error sending anniversary email: {str(e)}"
        logger.error(error_msg)
        return {'success': False, 'error': str(e)}


@shared_task(name='api.tasks.send_welcome_email_task')
def send_welcome_email_task(employee_id):
    """
    👋 Send welcome email to new employee (async)
    """
    from .models import Employee
    from .celebration_notification_service import celebration_notification_service
    
    try:
        employee = Employee.objects.get(id=employee_id)
        
        logger.info(f"👋 Sending welcome email for {employee.first_name} {employee.last_name}")
        
        success = celebration_notification_service.send_welcome_email(employee)
        
        if success:
            logger.info(f"✅ Welcome email sent successfully")
            return {'success': True, 'employee_id': employee_id}
        else:
            logger.error(f"❌ Failed to send welcome email")
            return {'success': False, 'employee_id': employee_id, 'error': 'Send failed'}
        
    except Employee.DoesNotExist:
        error_msg = f"❌ Employee {employee_id} not found"
        logger.error(error_msg)
        return {'success': False, 'error': 'Employee not found'}
    except Exception as e:
        error_msg = f"❌ Error sending welcome email: {str(e)}"
        logger.error(error_msg)
        import traceback
        logger.error(traceback.format_exc())
        return {'success': False, 'error': str(e)}