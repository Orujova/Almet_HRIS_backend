# api/models.py

from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from datetime import timedelta
import uuid

class MicrosoftUser(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='microsoft_user')
    microsoft_id = models.CharField(max_length=255, unique=True)
    access_token = models.TextField(blank=True, null=True)
    refresh_token = models.TextField(blank=True, null=True)
    token_expires = models.DateTimeField(blank=True, null=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.microsoft_id}"

    class Meta:
        verbose_name = "Microsoft User"
        verbose_name_plural = "Microsoft Users"

# Business Functions
class BusinessFunction(models.Model):
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=10, unique=True)  # HLD, TRD, GEO, UK
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']

# Departments
class Department(models.Model):
    name = models.CharField(max_length=100)
    business_function = models.ForeignKey(BusinessFunction, on_delete=models.CASCADE, related_name='departments')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} - {self.business_function.name}"

    class Meta:
        ordering = ['name']
        unique_together = ['name', 'business_function']

# Units (Sub-departments)
class Unit(models.Model):
    name = models.CharField(max_length=100)
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='units')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} - {self.department.name}"

    class Meta:
        ordering = ['name']
        unique_together = ['name', 'department']

# Job Functions
class JobFunction(models.Model):
    name = models.CharField(max_length=200, unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']

# Position Groups with no default data
class PositionGroup(models.Model):
    POSITION_LEVELS = [
        ('VC', 'Vice Chairman'),
        ('DIRECTOR', 'Director'),
        ('MANAGER', 'Manager'),
        ('HEAD OF DEPARTMENT', 'Head of Department'),
        ('SENIOR SPECIALIST', 'Senior Specialist'),
        ('SPECIALIST', 'Specialist'),
        ('JUNIOR SPECIALIST', 'Junior Specialist'),
        ('BLUE COLLAR', 'Blue Collar'),
    ]
    
    name = models.CharField(max_length=50, choices=POSITION_LEVELS, unique=True)
    hierarchy_level = models.IntegerField(unique=True)  # User will set this manually
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.get_name_display()

    class Meta:
        ordering = ['hierarchy_level']

# Employee Tags with predefined types
class EmployeeTag(models.Model):
    TAG_TYPES = [
        ('LEAVE', 'Leave Related'),
        ('STATUS', 'Status Related'),
        ('SKILL', 'Skill Related'),
        ('PROJECT', 'Project Related'),
        ('OTHER', 'Other'),
    ]
    
    name = models.CharField(max_length=50, unique=True)
    tag_type = models.CharField(max_length=20, choices=TAG_TYPES, default='OTHER')
    color = models.CharField(max_length=7, default='#6B7280')  # Hex color
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']

# Employee Status Model with automatic status management
class EmployeeStatus(models.Model):
    name = models.CharField(max_length=50, unique=True)
    color = models.CharField(max_length=7, default='#6B7280')  # Hex color
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']
        verbose_name = "Employee Status"
        verbose_name_plural = "Employee Statuses"

# Employee Documents
class EmployeeDocument(models.Model):
    DOCUMENT_TYPES = [
        ('CONTRACT', 'Employment Contract'),
        ('ID', 'ID Document'),
        ('CERTIFICATE', 'Certificate'),
        ('CV', 'Curriculum Vitae'),
        ('OTHER', 'Other'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey('Employee', on_delete=models.CASCADE, related_name='documents')
    name = models.CharField(max_length=255)
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPES, default='OTHER')
    file_path = models.CharField(max_length=500)  # Path to file storage
    file_size = models.PositiveIntegerField(null=True, blank=True)  # File size in bytes
    mime_type = models.CharField(max_length=100, blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='uploaded_documents')

    def __str__(self):
        return f"{self.employee.full_name} - {self.name}"

    class Meta:
        ordering = ['-uploaded_at']

# Main Employee Model with automatic status management
class Employee(models.Model):
    GENDER_CHOICES = [
        ('MALE', 'Male'),
        ('FEMALE', 'Female'),
    ]
    
    CONTRACT_DURATION_CHOICES = [
        ('3_MONTHS', '3 Months'),
        ('6_MONTHS', '6 Months'),
        ('1_YEAR', '1 Year'),
        ('PERMANENT', 'Permanent'),
    ]
    
    # Basic Information
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='employee_profile')
    employee_id = models.CharField(max_length=50, unique=True, help_text="HC Number")
    
    # Full name field (automatically generated from first_name + last_name)
    full_name = models.CharField(max_length=300, editable=False, help_text="Auto-generated from first and last name", default='')
    
    # Personal Information
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, null=True, blank=True)
    address = models.TextField(blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    emergency_contact = models.TextField(blank=True, null=True)
    profile_image = models.CharField(max_length=500, blank=True, null=True)  # URL/path to image
    
    # Job Information
    business_function = models.ForeignKey(BusinessFunction, on_delete=models.PROTECT, related_name='employees')
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name='employees')
    unit = models.ForeignKey(Unit, on_delete=models.PROTECT, related_name='employees', null=True, blank=True)
    job_function = models.ForeignKey(JobFunction, on_delete=models.PROTECT, related_name='employees')
    job_title = models.CharField(max_length=200)
    position_group = models.ForeignKey(PositionGroup, on_delete=models.PROTECT, related_name='employees')
    grade = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(8)])
    
    # Employment Dates
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    
    # Contract Information for automatic status management
    contract_duration = models.CharField(
        max_length=20, 
        choices=CONTRACT_DURATION_CHOICES, 
        default='PERMANENT',
        help_text="Contract duration for automatic status management"
    )
    contract_start_date = models.DateField(
        null=True, 
        blank=True,
        help_text="Contract start date for probation period calculation"
    )
    
    # Management Structure
    line_manager = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='direct_reports')
    
    # Status (Avtomatik təyin edilir - signal vasitəsilə)
    status = models.ForeignKey(
        EmployeeStatus, 
        on_delete=models.PROTECT, 
        related_name='employees',
        null=True, 
        blank=True,
        help_text="Status avtomatik olaraq contract və tarix əsasında təyin edilir"
    )
    tags = models.ManyToManyField(EmployeeTag, blank=True, related_name='employees')
    
    # Visibility in org chart - separate field for API control
    is_visible_in_org_chart = models.BooleanField(default=True)
    
    # Additional Information
    notes = models.TextField(blank=True, null=True)
    
    # Audit Information
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_employees')
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='updated_employees')

    def save(self, *args, **kwargs):
        # Auto-generate full_name from user's first_name and last_name
        if self.user:
            self.full_name = f"{self.user.first_name} {self.user.last_name}".strip()
        
        # Set contract_start_date if not set and employee is being created
        if not self.contract_start_date and not self.pk:
            self.contract_start_date = self.start_date
        
        super().save(*args, **kwargs)
        
        # Update status based on business rules after saving
        self.update_automatic_status()
    
    def update_automatic_status(self):
        """Update employee status based on business rules"""
        from django.utils import timezone
        
        current_date = timezone.now().date()
        
        # Get or create required statuses
        onboarding_status, _ = EmployeeStatus.objects.get_or_create(
            name='ONBOARDING',
            defaults={'color': '#FFA500', 'is_active': True}
        )
        probation_status, _ = EmployeeStatus.objects.get_or_create(
            name='PROBATION',
            defaults={'color': '#FFD700', 'is_active': True}
        )
        active_status, _ = EmployeeStatus.objects.get_or_create(
            name='ACTIVE',
            defaults={'color': '#28A745', 'is_active': True}
        )
        on_leave_status, _ = EmployeeStatus.objects.get_or_create(
            name='ON LEAVE',
            defaults={'color': '#DC3545', 'is_active': True}
        )
        
        # Determine required status
        required_status = None
        
        # If employee has end_date, set to ON LEAVE
        if self.end_date and self.end_date <= current_date:
            required_status = on_leave_status
            reason = 'End date reached'
        else:
            # Calculate days since start
            days_since_start = (current_date - self.start_date).days
            
            # ONBOARDING: First 7 days for all employees
            if days_since_start <= 7:
                required_status = onboarding_status
                reason = 'Within first 7 days of employment'
            
            # PROBATION period based on contract duration
            elif self.contract_duration != 'PERMANENT':
                probation_days = self._get_probation_days()
                
                if days_since_start <= probation_days:
                    required_status = probation_status
                    reason = f'Probation period for {self.contract_duration}'
                else:
                    required_status = active_status
                    reason = 'Completed onboarding and probation periods'
            else:
                # ACTIVE: For permanent contracts after onboarding
                required_status = active_status
                reason = 'Completed onboarding period (permanent contract)'
        
        # Update status if changed
        if self.status != required_status:
            old_status = self.status
            self.status = required_status
            Employee.objects.filter(id=self.id).update(status=required_status)
            self._log_status_change(required_status.name, reason)
            return True
        
        return False
    
    def _get_probation_days(self):
        """Get probation period days based on contract duration"""
        probation_mapping = {
            '3_MONTHS': 7,      # 7 days probation for 3-month contract
            '6_MONTHS': 14,     # 2 weeks probation for 6-month contract
            '1_YEAR': 90,       # 3 months probation for 1-year contract
            'PERMANENT': 0,     # No probation for permanent contracts
        }
        return probation_mapping.get(self.contract_duration, 0)
    
    def _log_status_change(self, new_status, reason):
        """Log status change activity"""
        try:
            EmployeeActivity.objects.create(
                employee=self,
                activity_type='STATUS_CHANGED',
                description=f"Status automatically changed to {new_status}: {reason}",
                performed_by=None,  # System generated
                metadata={
                    'new_status': new_status,
                    'reason': reason,
                    'automatic': True
                }
            )
        except Exception:
            # Avoid infinite loops if there are issues with activity logging
            pass
    
    @property
    def line_manager_hc_number(self):
        return self.line_manager.employee_id if self.line_manager else None
    
    @property
    def direct_reports_count(self):
        return self.direct_reports.filter(status__name='ACTIVE').count()
    
    @property
    def years_of_service(self):
        """Calculate years of service"""
        from django.utils import timezone
        end_date = self.end_date or timezone.now().date()
        return (end_date - self.start_date).days / 365.25
    
    @property
    def current_status_display(self):
        """Get current status with automatic status check"""
        # Quick status calculation without saving
        from django.utils import timezone
        current_date = timezone.now().date()
        
        # Quick check for end date
        if self.end_date and self.end_date <= current_date:
            return 'ON LEAVE'
        
        days_since_start = (current_date - self.start_date).days
        
        if days_since_start <= 7:
            return 'ONBOARDING'
        elif self.contract_duration != 'PERMANENT' and days_since_start <= self._get_probation_days():
            return 'PROBATION'
        else:
            return 'ACTIVE'

    def __str__(self):
        return f"{self.employee_id} - {self.full_name}"

    class Meta:
        ordering = ['employee_id']
        verbose_name = "Employee"
        verbose_name_plural = "Employees"

# Employee Activity Log
class EmployeeActivity(models.Model):
    ACTIVITY_TYPES = [
        ('CREATED', 'Employee Created'),
        ('UPDATED', 'Employee Updated'),
        ('STATUS_CHANGED', 'Status Changed'),
        ('DOCUMENT_UPLOADED', 'Document Uploaded'),
        ('MANAGER_CHANGED', 'Manager Changed'),
        ('PROMOTION', 'Promotion'),
        ('TRANSFER', 'Transfer'),
        ('ORG_CHART_VISIBILITY_CHANGED', 'Org Chart Visibility Changed'),
        ('CONTRACT_UPDATED', 'Contract Updated'),
        ('OTHER', 'Other Activity'),
    ]
    
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='activities')
    activity_type = models.CharField(max_length=30, choices=ACTIVITY_TYPES)
    description = models.TextField()
    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict, blank=True)  # Additional data as JSON

    def __str__(self):
        return f"{self.employee.full_name} - {self.get_activity_type_display()}"

    class Meta:
        ordering = ['-timestamp']
        verbose_name = "Employee Activity"
        verbose_name_plural = "Employee Activities"


# Signal to automatically update employee statuses daily
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=Employee)
def update_employee_status_on_save(sender, instance, created, **kwargs):
    """Update employee status when employee is saved"""
    if created:
        # For new employees, status will be set in the save method
        pass
    else:
        # For existing employees, check if status needs update
        instance.update_automatic_status()


# Management command to run daily status updates
# This should be added to a management command and run via cron job
def update_all_employee_statuses():
    """
    Function to update all employee statuses
    Should be called daily via management command
    """
    from django.utils import timezone
    
    employees = Employee.objects.all()
    updated_count = 0
    
    for employee in employees:
        old_status = employee.status.name if employee.status else None
        employee.update_automatic_status()
        employee.refresh_from_db()
        new_status = employee.status.name if employee.status else None
        
        if old_status != new_status:
            updated_count += 1
    
    return updated_count


# ========================
# SIGNALS - Employee Status Avtomatik İdarəetmə
# ========================

from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=Employee)
def auto_set_employee_status(sender, instance, created, **kwargs):
    """
    Employee yaradıldıqda və ya yenilənəndə avtomatik status təyin et
    """
    # Yalnız Employee tamamilə yaradıldıqdan sonra status update et
    # Bu recursive save-dən qaçınmaq üçün
    if not hasattr(instance, '_status_updating'):
        instance._status_updating = True
        
        try:
            # Əgər status management module var ise import et
            from .status_management import EmployeeStatusManager
            
            # Yeni yaradılan employee-lər üçün və ya status yoxlanması
            if created or not instance.status:
                # Default status-ları yarat
                EmployeeStatusManager.get_or_create_default_statuses()
                
                # Status-u avtomatik təyin et
                EmployeeStatusManager.update_employee_status(instance, force_update=True)
                
                # Log activity (yalnız yeni employee-lər üçün)
                if created:
                    from .models import EmployeeActivity
                    EmployeeActivity.objects.create(
                        employee=instance,
                        activity_type='CREATED',
                        description=f"Employee {instance.full_name} yaradıldı və avtomatik status təyin edildi",
                        performed_by=None,  # System
                        metadata={
                            'auto_status_assigned': True,
                            'contract_duration': instance.contract_duration,
                            'start_date': str(instance.start_date)
                        }
                    )
        except ImportError:
            # Əgər status_management module yoxdur, heç nə etmə
            pass
        except Exception as e:
            # Log error but don't break employee creation
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error in auto_set_employee_status for {instance.employee_id}: {e}")
        
        finally:
            # Flag-ı təmizlə
            if hasattr(instance, '_status_updating'):
                delattr(instance, '_status_updating')

@receiver(post_save, sender=Employee)
def log_employee_changes(sender, instance, created, **kwargs):
    """
    Employee dəyişikliklərini log et
    """
    # Yalnız update zamanı (create zamanı yox)
    if not created and not hasattr(instance, '_logging_activity'):
        instance._logging_activity = True
        
        try:
            # Contract duration dəyişib-dəyişmədiyini yoxla
            if hasattr(instance, '_original_contract_duration'):
                old_duration = instance._original_contract_duration
                new_duration = instance.contract_duration
                
                if old_duration != new_duration:
                    EmployeeActivity.objects.create(
                        employee=instance,
                        activity_type='CONTRACT_UPDATED',
                        description=f"Contract müddəti dəyişdi: {old_duration} → {new_duration}",
                        performed_by=None,
                        metadata={
                            'old_contract_duration': old_duration,
                            'new_contract_duration': new_duration,
                            'automatic_log': True
                        }
                    )
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error in log_employee_changes for {instance.employee_id}: {e}")
        
        finally:
            if hasattr(instance, '_logging_activity'):
                delattr(instance, '_logging_activity')

# Contract duration dəyişikliklərini track etmək üçün
@receiver(post_save, sender=Employee)
def track_contract_changes(sender, instance, **kwargs):
    """
    Contract duration dəyişikliklərini track et
    """
    # Original value-nu save et
    if instance.pk:
        try:
            original = Employee.objects.get(pk=instance.pk)
            instance._original_contract_duration = original.contract_duration
        except Employee.DoesNotExist:
            pass