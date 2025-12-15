# api/celebration_signals.py
"""
Django Signals for Celebration Notifications
Automatically triggers emails when:
- Employee position_group changes (promotion/transfer)

⚠️ IMPORTANT: Import this in api/signals.py to register
"""

import logging
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from .models import Employee
from .celebration_notification_service import celebration_notification_service

logger = logging.getLogger(__name__)


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
        
        # Send notification asynchronously (optional: use Celery for production)
        try:
            celebration_notification_service.send_position_change_notification(
                employee=instance,
                old_position=str(old_position),
                new_position=str(new_position),
                change_type=change_type
            )
            logger.info(f"✅ Position change notification sent for {instance.first_name}")
        except Exception as e:
            logger.error(f"❌ Failed to send position change notification: {e}")


# Optional: Add signal for new employees
@receiver(post_save, sender=Employee)
def welcome_new_employee(sender, instance, created, **kwargs):
    """
    👋 Optional: Send welcome email to new employees
    """
    if created and not instance.is_deleted:
        logger.info(f"👋 New employee created: {instance.first_name} {instance.last_name}")
        # You can add welcome email logic here if needed