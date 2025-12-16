# api/signals.py
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from .models import Employee
from .status_management import EmployeeStatusManager
import logging

logger = logging.getLogger(__name__)

# ==================== STATUS MANAGEMENT SIGNALS ====================

@receiver(post_save, sender=Employee)
def auto_update_employee_status(sender, instance, created, **kwargs):
    """
    ✅ Avtomatik status yenilənməsi - FIXED
    """
    
    # Skip if explicitly disabled (for bulk operations)
    if getattr(instance, '_skip_auto_status_update', False):
        return
    
    # Skip if deleted
    if instance.is_deleted:
        return
    
    # ✅ FIX: Only skip for BRAND NEW employees (created=True)
    # For existing employees, always check status
    if created:
        logger.info(f"✅ New employee created: {instance.employee_id} - initial status set")
        return
    
    try:
        # Check if status needs update
        required_status, reason = EmployeeStatusManager.calculate_required_status(instance)
        
        # If status needs to change
        if required_status and required_status != instance.status:
            logger.info(
                f"🔄 Auto-updating status for {instance.employee_id}: "
                f"{instance.status.name if instance.status else 'None'} -> {required_status.name}"
            )
            logger.info(f"   Reason: {reason}")
            
            # ✅ CRITICAL: Update using queryset to avoid triggering signal again
            Employee.objects.filter(pk=instance.pk).update(status=required_status)
            
            # Refresh instance
            instance.refresh_from_db()
            
            # Log activity
            from .models import EmployeeActivity
            EmployeeActivity.objects.create(
                employee=instance,
                activity_type='STATUS_CHANGED',
                description=f"Status automatically updated to {required_status.name}. Reason: {reason}",
                performed_by=None,
                metadata={
                    'automatic': True,
                    'trigger': 'post_save_signal',
                    'reason': reason,
                    'new_status': required_status.name
                }
            )
            
            logger.info(f"   ✅ Status updated successfully")
        else:
            logger.debug(f"   ℹ️  No status update needed for {instance.employee_id}")
            
    except Exception as e:
        logger.error(f"❌ Error in auto_update_employee_status for {instance.employee_id}: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")


# ==================== CELEBRATION NOTIFICATION SIGNALS ====================

@receiver(pre_save, sender=Employee)
def track_position_change(sender, instance, **kwargs):
    """
    📝 Track position_group changes before saving
    Stores old position in instance for comparison
    """
    if instance.pk:  # Only for existing employees
        try:
            old_employee = Employee.objects.get(pk=instance.pk)
            instance._old_position_group = old_employee.position_group
        except Employee.DoesNotExist:
            instance._old_position_group = None
    else:
        instance._old_position_group = None


@receiver(post_save, sender=Employee)
def send_position_change_notification(sender, instance, created, **kwargs):
    """
    📧 Send celebration email when position_group changes
    
    Automatically detects:
    - Promotions (position level increase)
    - Transfers (position change)
    """
    if created:
        # New employee - no notification needed
        return
    
    # Check if position_group changed
    old_position = getattr(instance, '_old_position_group', None)
    new_position = instance.position_group
    
    if old_position and new_position and old_position != new_position:
        logger.info(f"📝 Position change detected for {instance.first_name} {instance.last_name}")
        logger.info(f"   Old: {old_position} → New: {new_position}")
        
        # Determine if promotion or transfer
        # You can add custom logic here to detect promotions
        # For now, treat all changes as position changes
        change_type = 'promotion'  # or 'transfer' based on your logic
        
        # Send notification asynchronously using Celery
        try:
            from .tasks import send_position_change_email
            send_position_change_email.delay(
                employee_id=instance.id,
                old_position=str(old_position),
                new_position=str(new_position),
                change_type=change_type
            )
            logger.info(f"✅ Position change notification task queued for {instance.first_name}")
        except Exception as e:
            logger.error(f"❌ Failed to queue position change notification: {e}")
            
            # Fallback: Send synchronously if Celery fails
            try:
                from .celebration_notification_service import celebration_notification_service
                celebration_notification_service.send_position_change_notification(
                    employee=instance,
                    old_position=str(old_position),
                    new_position=str(new_position),
                    change_type=change_type
                )
            except Exception as fallback_error:
                logger.error(f"❌ Fallback notification also failed: {fallback_error}")


# ==================== WELCOME EMAIL SIGNAL ====================

@receiver(pre_save, sender=Employee)
def track_employee_changes_for_welcome(sender, instance, **kwargs):
    """
    📝 Track changes before saving for welcome email detection
    """
    if instance.pk:
        try:
            old = Employee.objects.get(pk=instance.pk)
            instance._old_status = old.status
            instance._old_start_date = old.start_date
            instance._old_is_deleted = old.is_deleted
            
            logger.debug(f"🔍 PRE_SAVE: Tracking changes for {instance.employee_id}")
            logger.debug(f"   Old Status: {old.status.name if old.status else 'None'}")
            logger.debug(f"   New Status: {instance.status.name if instance.status else 'None'}")
            logger.debug(f"   Old Start Date: {old.start_date}")
            logger.debug(f"   New Start Date: {instance.start_date}")
            logger.debug(f"   Old is_deleted: {old.is_deleted}")
            logger.debug(f"   New is_deleted: {instance.is_deleted}")
        except Employee.DoesNotExist:
            instance._old_status = None
            instance._old_start_date = None
            instance._old_is_deleted = None
            logger.debug(f"🔍 PRE_SAVE: New employee (no old data)")
    else:
        instance._old_status = None
        instance._old_start_date = None
        instance._old_is_deleted = None
        logger.debug(f"🔍 PRE_SAVE: Brand new employee")


@receiver(post_save, sender=Employee)
def welcome_new_employee(sender, instance, created, **kwargs):
    """
    👋 Send welcome email when:
    1. New employee created with start_date
    2. Status changes from Vacant to Active/Working
    3. Start date is added to existing employee
    """
    logger.info("=" * 80)
    logger.info(f"🔍 POST_SAVE: Welcome email check for {instance.employee_id}")
    logger.info(f"   Created: {created}")
    logger.info(f"   Is Deleted: {instance.is_deleted}")
    logger.info(f"   Current Status: {instance.status.name if instance.status else 'None'}")
    logger.info(f"   Start Date: {instance.start_date}")
    
    should_send_welcome = False
    trigger_reason = ""
    
    # Case 1: Brand new employee with start_date
    if created and not instance.is_deleted and instance.start_date:
        should_send_welcome = True
        trigger_reason = "New employee created with start_date"
        logger.info(f"✅ TRIGGER: {trigger_reason}")
        logger.info(f"   >>> should_send_welcome set to TRUE")
    
    # Case 2: Existing employee changes
    elif not created and not instance.is_deleted:
        old_status = getattr(instance, '_old_status', None)
        old_start_date = getattr(instance, '_old_start_date', None)
        old_is_deleted = getattr(instance, '_old_is_deleted', None)
        
        logger.info(f"   Old Status: {old_status.name if old_status else 'None'}")
        logger.info(f"   Old Start Date: {old_start_date}")
        logger.info(f"   Old is_deleted: {old_is_deleted}")
        
        # Status: Vacant → Not Vacant (and has start_date)
        status_changed_from_vacant = (
            old_status and 
            old_status.name == 'Vacant' and 
            instance.status and 
            instance.status.name != 'Vacant' and
            instance.start_date  # Must have start_date
        )
        
        # Start date added (was None, now has value)
        start_date_added = (
            not old_start_date and 
            instance.start_date and
            instance.status and
            instance.status.name != 'Vacant'  # Not vacant status
        )
        
        # Was deleted, now active
        reactivated = (
            old_is_deleted == True and
            instance.is_deleted == False and
            instance.start_date and
            instance.status and
            instance.status.name != 'Vacant'
        )
        
        if status_changed_from_vacant:
            should_send_welcome = True
            trigger_reason = f"Status changed from Vacant to {instance.status.name}"
            logger.info(f"✅ TRIGGER: {trigger_reason}")
            
        elif start_date_added:
            should_send_welcome = True
            trigger_reason = "Start date added to existing employee"
            logger.info(f"✅ TRIGGER: {trigger_reason}")
            
        elif reactivated:
            should_send_welcome = True
            trigger_reason = "Employee reactivated from deleted state"
            logger.info(f"✅ TRIGGER: {trigger_reason}")
        else:
            logger.info(f"❌ NO TRIGGER: Conditions not met")
    else:
        logger.info(f"❌ NO TRIGGER: Either deleted or brand new without start_date")
    
    # Send email if conditions met
    logger.info(f"🔍 Final check - should_send_welcome: {should_send_welcome}")
    
    if should_send_welcome:
        logger.info(f"📧 STARTING welcome email process for {instance.first_name} {instance.last_name}")
        logger.info(f"   Reason: {trigger_reason}")
        logger.info(f"   Employee ID: {instance.id}")
        logger.info(f"   Employee Name: {instance.first_name} {instance.last_name}")
        logger.info(f"   Position: {instance.position_group}")
        logger.info(f"   Department: {instance.department}")
        logger.info(f"   Start Date: {instance.start_date}")
        
        # ✅ FIRST TRY: Direct synchronous send (most reliable)
        try:
            logger.info(f"   🔄 Attempting DIRECT synchronous send...")
            logger.info(f"   Importing celebration_notification_service...")
            
            from .celebration_notification_service import celebration_notification_service
            
            logger.info(f"   ✅ Service imported successfully")
            logger.info(f"   Calling send_welcome_email()...")
            
            success = celebration_notification_service.send_welcome_email(instance)
            
            logger.info(f"   📬 send_welcome_email() returned: {success}")
            
            if success:
                logger.info(f"✅ ✅ ✅ Welcome email sent SUCCESSFULLY to distribution list!")
            else:
                logger.error(f"❌ ❌ ❌ Welcome email send returned False - check service logs above")
                
        except Exception as e:
            logger.error(f"❌ Failed to send welcome email directly: {e}")
            import traceback
            logger.error(f"   Traceback: {traceback.format_exc()}")
            
            # ✅ SECOND TRY: Celery (if available)
            try:
                logger.info(f"   🔄 Attempting Celery queue as backup...")
                from .tasks import send_welcome_email_task
                
                send_welcome_email_task.delay(employee_id=instance.id)
                logger.info(f"✅ Welcome email task queued to Celery")
                
            except Exception as celery_error:
                logger.error(f"❌ Celery also failed: {celery_error}")
                import traceback
                logger.error(f"   Traceback: {traceback.format_exc()}")
    else:
        logger.info(f"❌ NOT sending welcome email - conditions not met")
    
    logger.info("=" * 80)