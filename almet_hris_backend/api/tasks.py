# api/tasks.py
from celery import shared_task
from django.utils import timezone
from datetime import date
import logging

logger = logging.getLogger(__name__)

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