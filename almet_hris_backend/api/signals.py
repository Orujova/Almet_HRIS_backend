# api/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Employee
from .status_management import EmployeeStatusManager
import logging

logger = logging.getLogger(__name__)

@receiver(post_save, sender=Employee)
def auto_update_employee_status(sender, instance, created, **kwargs):
    """
    ✅ Avtomatik status yenilənməsi
    Hər dəfə employee save olanda status yoxlanılır və avtomatik düzəldilir
    """
    
    # Skip if this is during creation (new employee)
    if created:
        logger.info(f"✅ New employee created: {instance.employee_id} - skipping auto status update")
        return
    
    # Skip if deleted
    if instance.is_deleted:
        return
    
    # Skip if explicitly told not to auto-update (bulk operations)
    if getattr(instance, '_skip_auto_status_update', False):
        return
    
    try:
        # Check if status needs update
        required_status, reason = EmployeeStatusManager.calculate_required_status(instance)
        
        # If status needs to change
        if required_status and required_status != instance.status:
            logger.info(
                f"🔄 Auto-updating status for {instance.employee_id}: "
                f"{instance.status.name if instance.status else 'None'} → {required_status.name}"
            )
            logger.info(f"   Reason: {reason}")
            
            # ✅ CRITICAL: Update without triggering signal again
            Employee.objects.filter(pk=instance.pk).update(status=required_status)
            
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
                    'old_status': instance.status.name if instance.status else None,
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


