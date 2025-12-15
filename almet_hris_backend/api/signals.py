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
        logger.info(f"🔔 Position change detected for {instance.first_name} {instance.last_name}")
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