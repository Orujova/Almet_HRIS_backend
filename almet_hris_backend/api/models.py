# api/models.py - ENHANCED: Complete Employee Management System with Advanced Contract Status Management

from django.contrib.postgres.indexes import GinIndex
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from datetime import date, timedelta
import uuid
import logging

# dateutil əvəzinə Python built-in datetime istifadə edəcəyik
from datetime import datetime, timedelta
try:
    from dateutil.relativedelta import relativedelta
except ImportError:
    # Fallback if dateutil is not available
    relativedelta = None

logger = logging.getLogger(__name__)

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

# Soft Delete Manager
class ActiveManager(models.Manager):
    """Manager that excludes soft-deleted objects"""
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)

class AllObjectsManager(models.Manager):
    """Manager that includes soft-deleted objects"""
    def get_queryset(self):
        return super().get_queryset()

# Base model with soft delete functionality
class SoftDeleteModel(models.Model):
    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='deleted_%(class)ss')
    
    objects = ActiveManager()  # Default manager excludes deleted
    all_objects = AllObjectsManager()  # Manager that includes deleted
    
    class Meta:
        abstract = True
    
    def soft_delete(self, user=None):
        """Soft delete the object"""
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.deleted_by = user
        self.save()
    
    def restore(self):
        """Restore a soft-deleted object"""
        self.is_deleted = False
        self.deleted_at = None
        self.deleted_by = None
        self.save()

# Business Structure Models
class BusinessFunction(SoftDeleteModel):
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=10, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.code} - {self.name}"

    class Meta:
        ordering = ['code']

class Department(SoftDeleteModel):
    name = models.CharField(max_length=100)
    business_function = models.ForeignKey(BusinessFunction, on_delete=models.CASCADE, related_name='departments')
    head_of_department = models.ForeignKey('Employee', on_delete=models.SET_NULL, null=True, blank=True, related_name='departments_headed')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.business_function.code} - {self.name}"

    class Meta:
        ordering = ['business_function__code']
        unique_together = ['business_function', 'name']

class Unit(SoftDeleteModel):
    name = models.CharField(max_length=100)
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='units')
    unit_head = models.ForeignKey('Employee', on_delete=models.SET_NULL, null=True, blank=True, related_name='units_headed')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.department.business_function.code} - {self.name}"

    class Meta:
        ordering = ['department__business_function__code']
        unique_together = ['department', 'name']

class JobFunction(SoftDeleteModel):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']

# Position Groups with enhanced grading integration
class PositionGroup(SoftDeleteModel):
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
    
    # Grading shorthand mappings for level display
    GRADING_SHORTCUTS = {
        'VC': 'VC',
        'DIRECTOR': 'DIR',
        'MANAGER': 'MGR',
        'HEAD OF DEPARTMENT': 'HOD',
        'SENIOR SPECIALIST': 'SS',
        'SPECIALIST': 'SP',
        'JUNIOR SPECIALIST': 'JS',
        'BLUE COLLAR': 'BC',
    }
    
    name = models.CharField(max_length=50, choices=POSITION_LEVELS, unique=True)
    hierarchy_level = models.IntegerField(unique=True)
    grading_shorthand = models.CharField(max_length=10, editable=False)  # Auto-generated
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        # Auto-generate grading shorthand
        self.grading_shorthand = self.GRADING_SHORTCUTS.get(self.name, self.name[:3].upper())
        super().save(*args, **kwargs)

    def get_grading_levels(self):
        """Returns grading levels with shortcuts for this position"""
        return [
            {'code': f"{self.grading_shorthand}_LD", 'display': f"{self.grading_shorthand}-LD", 'full_name': 'Lower Decile'},
            {'code': f"{self.grading_shorthand}_LQ", 'display': f"{self.grading_shorthand}-LQ", 'full_name': 'Lower Quartile'},
            {'code': f"{self.grading_shorthand}_M", 'display': f"{self.grading_shorthand}-M", 'full_name': 'Median'},
            {'code': f"{self.grading_shorthand}_UQ", 'display': f"{self.grading_shorthand}-UQ", 'full_name': 'Upper Quartile'},
            {'code': f"{self.grading_shorthand}_UD", 'display': f"{self.grading_shorthand}-UD", 'full_name': 'Upper Decile'},
        ]

    def __str__(self):
        return self.get_name_display()

    class Meta:
        ordering = ['hierarchy_level']

# Employee Tags for categorization
class EmployeeTag(SoftDeleteModel):
    TAG_TYPES = [
        ('LEAVE', 'Leave Related'),
        ('STATUS', 'Status Related'),
        ('SKILL', 'Skill Related'),
        ('PROJECT', 'Project Related'),
        ('PERFORMANCE', 'Performance Related'),
        ('OTHER', 'Other'),
    ]
    
    name = models.CharField(max_length=50, unique=True)
    tag_type = models.CharField(max_length=20, choices=TAG_TYPES, default='OTHER')
    color = models.CharField(max_length=7, default='#6B7280')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['tag_type', 'name']

class ContractTypeConfig(SoftDeleteModel):
    """Configuration for different contract types and their status transitions"""
    
    contract_type = models.CharField(
        max_length=50, 
        unique=True, 
        help_text="Contract type identifier (e.g., 3_MONTHS, 5_MONTHS, 18_MONTHS, etc.)"
    )
    display_name = models.CharField(max_length=100)
    
    # Status Configuration
    onboarding_days = models.IntegerField(default=7, help_text="Days for onboarding status")
    probation_days = models.IntegerField(default=0, help_text="Days for probation status after onboarding")
    
    # Auto-transition settings
    enable_auto_transitions = models.BooleanField(default=True, help_text="Enable automatic status transitions")
    transition_to_inactive_on_end = models.BooleanField(default=True, help_text="Auto transition to inactive when contract ends")
    
    # Notification settings
    notify_days_before_end = models.IntegerField(default=30, help_text="Days before contract end to send notifications")
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def get_total_days_until_active(self):
        """Get total days until employee becomes active"""
        return self.onboarding_days + self.probation_days
    
    @classmethod
    def get_contract_choices(cls):
        """Get dynamic contract choices from database"""
        active_configs = cls.objects.filter(is_active=True)
        return [(config.contract_type, config.display_name) for config in active_configs]
    
    @classmethod
    def get_or_create_defaults(cls):
        """Create default contract configurations"""
        defaults = [
            ('3_MONTHS', '3 Months Contract', 7, 7, True, True, 7),
            ('6_MONTHS', '6 Months Contract', 7, 14, True, True, 14),
            ('1_YEAR', '1 Year Contract', 7, 90, True, True, 30),
            ('2_YEARS', '2 Years Contract', 7, 90, True, True, 30),
            ('3_YEARS', '3 Years Contract', 7, 90, True, True, 30),
            ('PERMANENT', 'Permanent Contract', 7, 0, True, False, 0),
        ]
        
        created_configs = {}
        for contract_type, display_name, onboarding, probation, auto_trans, inactive_on_end, notify_days in defaults:
            config, created = cls.objects.get_or_create(
                contract_type=contract_type,
                defaults={
                    'display_name': display_name,
                    'onboarding_days': onboarding,
                    'probation_days': probation,
                    'enable_auto_transitions': auto_trans,
                    'transition_to_inactive_on_end': inactive_on_end,
                    'notify_days_before_end': notify_days,
                    'is_active': True
                }
            )
            created_configs[contract_type] = config
            if created:
                logger.info(f"Created default contract config: {contract_type}")
        
        return created_configs
    
    def __str__(self):
        return self.display_name
    
    class Meta:
        ordering = ['contract_type']
        verbose_name = "Contract Type Configuration"
        verbose_name_plural = "Contract Type Configurations"
# Enhanced Employee Status Model with Contract Integration
class EmployeeStatus(SoftDeleteModel):
    STATUS_TYPES = [
        ('ACTIVE', 'Active'),
        ('INACTIVE', 'Inactive'),
        ('ONBOARDING', 'Onboarding'),
        ('PROBATION', 'Probation'),
        ('NOTICE_PERIOD', 'Notice Period'),
        ('TERMINATED', 'Terminated'),
        ('RESIGNED', 'Resigned'),
        ('SUSPENDED', 'Suspended'),
        ('LEAVE', 'On Leave'),
        ('VACANT', 'Vacant Position'),
    ]
    
    # Color hierarchy for automatic assignment
    STATUS_COLOR_HIERARCHY = {
        'ACTIVE': '#10B981',      # Green
        'ONBOARDING': '#3B82F6',  # Blue
        'PROBATION': '#F59E0B',   # Yellow
        'NOTICE_PERIOD': '#EF4444', # Red
        'TERMINATED': '#6B7280',  # Gray
        'RESIGNED': '#6B7280',    # Gray
        'SUSPENDED': '#DC2626',   # Dark Red
        'LEAVE': '#8B5CF6',       # Purple
        'VACANT': '#F97316',      # Orange
        'INACTIVE': '#9CA3AF',    # Light Gray
    }
    
    # Basic Information
    name = models.CharField(max_length=50, unique=True)
    status_type = models.CharField(max_length=20, choices=STATUS_TYPES, default='ACTIVE')
    color = models.CharField(max_length=7, default='#6B7280')
    description = models.TextField(blank=True, help_text="Description of this status")
    
    # Display Order
    order = models.IntegerField(default=0, help_text="Display order for status")
    
    # Behavior Settings
    affects_headcount = models.BooleanField(default=True, help_text="Whether this status counts toward active headcount")
    allows_org_chart = models.BooleanField(default=True, help_text="Whether employees with this status appear in org chart")
    
    # Auto Transition Settings
    auto_transition_enabled = models.BooleanField(default=False, help_text="Enable automatic status transitions")
    auto_transition_days = models.IntegerField(null=True, blank=True, help_text="Days after which to auto-transition")
    auto_transition_to = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, 
                                         related_name='transitions_from', help_text="Status to transition to")
    is_transitional = models.BooleanField(default=False, help_text="Whether this is a transitional status")
    transition_priority = models.IntegerField(default=0, null=True, blank=True, help_text="Priority for transitions")
    
    # Notification Settings
    send_notifications = models.BooleanField(default=False, help_text="Send notifications for this status")
    notification_template = models.TextField(default='', blank=True, help_text="Notification template")
    
    # System Settings
    is_system_status = models.BooleanField(default=False, help_text="Whether this is a system-managed status")
    is_default_for_new_employees = models.BooleanField(default=False, help_text="Use as default for new employees")
    
    # Status
    is_active = models.BooleanField(default=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        # Auto-assign color based on status type if not explicitly set
        if not self.color or self.color == '#6B7280':
            self.color = self.STATUS_COLOR_HIERARCHY.get(self.status_type, '#6B7280')
        
        # Auto-assign order based on status type if not set
        if not self.order:
            status_order_mapping = {
                'ONBOARDING': 1,
                'PROBATION': 2,
                'ACTIVE': 3,
                'NOTICE_PERIOD': 4,
                'LEAVE': 5,
                'SUSPENDED': 6,
                'INACTIVE': 7,
                'RESIGNED': 8,
                'TERMINATED': 9,
                'VACANT': 10,
            }
            self.order = status_order_mapping.get(self.status_type, 99)
        
        # Auto-set transitional flag for certain status types
        if self.status_type in ['ONBOARDING', 'PROBATION', 'NOTICE_PERIOD']:
            self.is_transitional = True
        
        super().save(*args, **kwargs)

    @classmethod
    def get_or_create_default_statuses(cls):
        """Create default statuses if they don't exist"""
        default_statuses = [
            # name, status_type, affects_headcount, allows_org_chart, order, auto_transition, is_transitional, is_default
            ('ONBOARDING', 'ONBOARDING', True, True, 1, True, True, True),
            ('PROBATION', 'PROBATION', True, True, 2, True, True, False),
            ('ACTIVE', 'ACTIVE', True, True, 3, False, False, False),
            ('INACTIVE', 'INACTIVE', False, False, 7, False, False, False),
            ('ON LEAVE', 'LEAVE', False, False, 5, False, False, False),
        ]
        
        created_statuses = {}
        for name, status_type, affects_headcount, allows_org_chart, order, auto_transition, is_transitional, is_default in default_statuses:
            status, created = cls.objects.get_or_create(
                name=name,
                defaults={
                    'status_type': status_type,
                    'affects_headcount': affects_headcount,
                    'allows_org_chart': allows_org_chart,
                    'order': order,
                    'auto_transition_enabled': auto_transition,
                    'is_transitional': is_transitional,
                    'is_default_for_new_employees': is_default,
                    'send_notifications': False,
                    'notification_template': '',
                    'is_system_status': True,
                    'transition_priority': 0,
                    'is_active': True
                }
            )
            created_statuses[name] = status
            if created:
                logger.info(f"Created default status: {name}")
        
        return created_statuses

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['order', 'name']
        verbose_name = "Employee Status"
        verbose_name_plural = "Employee Statuses"

# Enhanced Vacancy Management Model
class VacantPosition(SoftDeleteModel):
    VACANCY_TYPES = [
        ('NEW_POSITION', 'New Position'),
        ('REPLACEMENT', 'Replacement'),
        ('EXPANSION', 'Expansion'),
        ('TEMPORARY', 'Temporary'),
    ]
    
    URGENCY_LEVELS = [
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
        ('CRITICAL', 'Critical'),
    ]
    
    # Basic Information
    position_id = models.CharField(max_length=50, unique=True, help_text="Unique vacancy identifier")
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    # Organizational Structure
    business_function = models.ForeignKey(BusinessFunction, on_delete=models.PROTECT)
    department = models.ForeignKey(Department, on_delete=models.PROTECT)
    unit = models.ForeignKey(Unit, on_delete=models.PROTECT, null=True, blank=True)
    job_function = models.ForeignKey(JobFunction, on_delete=models.PROTECT)
    position_group = models.ForeignKey(PositionGroup, on_delete=models.PROTECT)
    
    # Vacancy Details
    vacancy_type = models.CharField(max_length=20, choices=VACANCY_TYPES)
    urgency = models.CharField(max_length=10, choices=URGENCY_LEVELS, default='MEDIUM')
    expected_start_date = models.DateField()
    expected_salary_range_min = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    expected_salary_range_max = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    
    # Management
    reporting_to = models.ForeignKey('Employee', on_delete=models.SET_NULL, null=True, blank=True, related_name='vacant_positions_managed')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    # Status tracking
    is_filled = models.BooleanField(default=False)
    filled_by = models.ForeignKey('Employee', on_delete=models.SET_NULL, null=True, blank=True, related_name='position_filled')
    filled_date = models.DateField(null=True, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def mark_as_filled(self, employee):
        """Mark vacancy as filled by an employee"""
        self.is_filled = True
        self.filled_by = employee
        self.filled_date = timezone.now().date()
        self.save()

    def __str__(self):
        return f"{self.position_id} - {self.title}"

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Vacant Position"
        verbose_name_plural = "Vacant Positions"

# Employee Documents with optional uploads
class EmployeeDocument(SoftDeleteModel):
    DOCUMENT_TYPES = [
        ('CONTRACT', 'Employment Contract'),
        ('ID', 'ID Document'),
        ('CERTIFICATE', 'Certificate'),
        ('CV', 'Curriculum Vitae'),
        ('PERFORMANCE', 'Performance Review'),
        ('OTHER', 'Other'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey('Employee', on_delete=models.CASCADE, related_name='documents')
    name = models.CharField(max_length=255)
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPES, default='OTHER')
    file_path = models.CharField(max_length=500, blank=True, null=True)  # Optional file path
    file_size = models.PositiveIntegerField(null=True, blank=True)
    mime_type = models.CharField(max_length=100, blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='uploaded_documents')

    def __str__(self):
        return f"{self.employee.full_name} - {self.name}"

    class Meta:
        ordering = ['-uploaded_at']

# Complete Employee Model with Enhanced Contract and Status Management
class Employee(SoftDeleteModel):
    GENDER_CHOICES = [
        ('MALE', 'Male'),
        ('FEMALE', 'Female'),
    ]
    
   
    RENEWAL_STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('NOT_APPLICABLE', 'Not Applicable'),
    ]
    
    # Basic Information
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='employee_profile')
    employee_id = models.CharField(max_length=50, unique=True, help_text="HC Number")
    
    # Auto-generated full name
    full_name = models.CharField(max_length=300, editable=False, default='')
    
    # Personal Information (ENHANCED with father_name)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, null=True, blank=True)
    father_name = models.CharField(max_length=200, blank=True, null=True, help_text="Father's name (optional)")
    address = models.TextField(blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    emergency_contact = models.TextField(blank=True, null=True)
    profile_image = models.CharField(max_length=500, blank=True, null=True)
    
    # Job Information
    business_function = models.ForeignKey(BusinessFunction, on_delete=models.PROTECT, related_name='employees')
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name='employees')
    unit = models.ForeignKey(Unit, on_delete=models.PROTECT, related_name='employees', null=True, blank=True)
    job_function = models.ForeignKey(JobFunction, on_delete=models.PROTECT, related_name='employees')
    job_title = models.CharField(max_length=200)
    position_group = models.ForeignKey(PositionGroup, on_delete=models.PROTECT, related_name='employees')
    
    # Enhanced grading system integration
    grading_level = models.CharField(max_length=15, default='', help_text="Specific grading level (e.g., MGR_UQ)")
    
    # Employment Dates
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    
    # Enhanced contract management
    contract_duration = models.CharField(
        max_length=50, 
        default='PERMANENT',
        help_text="Contract duration type - references ContractTypeConfig"
    )
    contract_start_date = models.DateField(null=True, blank=True)
    contract_end_date = models.DateField(null=True, blank=True, editable=False)  # Auto-calculated
    contract_extensions = models.IntegerField(default=0, help_text="Number of contract extensions")
    last_extension_date = models.DateField(null=True, blank=True)
    renewal_status = models.CharField(max_length=20, choices=RENEWAL_STATUS_CHOICES, default='NOT_APPLICABLE')
    
    # Management Hierarchy (ENHANCED)
    line_manager = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='direct_reports', help_text="Line manager for this employee")
    
    # Status and Visibility
    status = models.ForeignKey(EmployeeStatus, on_delete=models.PROTECT, related_name='employees')
    is_visible_in_org_chart = models.BooleanField(default=True)
    
    # Tags and categorization
    tags = models.ManyToManyField(EmployeeTag, blank=True, related_name='employees')
    
    # Additional Information
    notes = models.TextField(default='', blank=True)
    
    # Linked vacancy (if employee was hired for a specific vacant position)
    filled_vacancy = models.OneToOneField(VacantPosition, on_delete=models.SET_NULL, null=True, blank=True, related_name='hired_employee')
    
    # Audit fields
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_employees')
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='updated_employees')
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        # Auto-generate full name
        if self.user:
            first_name = self.user.first_name or ''
            last_name = self.user.last_name or ''
            self.full_name = f"{first_name} {last_name}".strip()
        
        # Auto-calculate contract end date
        if self.contract_start_date and self.contract_duration != 'PERMANENT':
            try:
                if relativedelta:
                    if self.contract_duration == '3_MONTHS':
                        self.contract_end_date = self.contract_start_date + relativedelta(months=3)
                    elif self.contract_duration == '6_MONTHS':
                        self.contract_end_date = self.contract_start_date + relativedelta(months=6)
                    elif self.contract_duration == '1_YEAR':
                        self.contract_end_date = self.contract_start_date + relativedelta(years=1)
                    elif self.contract_duration == '2_YEARS':
                        self.contract_end_date = self.contract_start_date + relativedelta(years=2)
                    elif self.contract_duration == '3_YEARS':
                        self.contract_end_date = self.contract_start_date + relativedelta(years=3)
                else:
                    # Fallback to approximate calculation
                    days_mapping = {
                        '3_MONTHS': 90,
                        '6_MONTHS': 180,
                        '1_YEAR': 365,
                        '2_YEARS': 730,
                        '3_YEARS': 1095
                    }
                    days = days_mapping.get(self.contract_duration, 365)
                    self.contract_end_date = self.contract_start_date + timedelta(days=days)
            except Exception as e:
                logger.error(f"Error calculating contract end date: {e}")
                self.contract_end_date = None
        else:
            self.contract_end_date = None
        
        # Auto-generate grading level based on position group (default to median)
        if self.position_group and not self.grading_level:
            self.grading_level = f"{self.position_group.grading_shorthand}_M"  # Default to median
        
        # Auto-assign status if not set (during creation)
        if not self.status_id:
            self.auto_assign_status()
        
        # Set renewal status based on contract
        if self.contract_duration == 'PERMANENT':
            self.renewal_status = 'NOT_APPLICABLE'
        elif not self.renewal_status or self.renewal_status == 'NOT_APPLICABLE':
            self.renewal_status = 'PENDING'
        
        # Link to vacant position if applicable
        if not self.filled_vacancy and hasattr(self, '_vacancy_id'):
            try:
                vacancy = VacantPosition.objects.get(id=self._vacancy_id)
                vacancy.mark_as_filled(self)
                self.filled_vacancy = vacancy
            except VacantPosition.DoesNotExist:
                pass
        
        super().save(*args, **kwargs)

    def auto_assign_status(self):
        """Auto-assign status based on start date and contract"""
        try:
            default_statuses = EmployeeStatus.get_or_create_default_statuses()
            
            # Default to onboarding for new employees
            self.status = default_statuses.get('ONBOARDING', 
                                             EmployeeStatus.objects.filter(is_default_for_new_employees=True).first())
            
            if not self.status:
                # Fallback to any active status
                self.status = EmployeeStatus.objects.filter(is_active=True).first()
                
        except Exception as e:
            logger.error(f"Error auto-assigning status: {e}")

    def get_required_status_based_on_contract(self):
        """Get required status based on contract configuration and dates"""
        try:
            current_date = date.today()
            
            # Check if contract has ended
            if self.contract_end_date and self.contract_end_date <= current_date:
                inactive_status = EmployeeStatus.objects.filter(status_type='INACTIVE').first()
                return inactive_status, f"Contract ended on {self.contract_end_date}"
            
            # Get contract configuration
            try:
                contract_config = ContractTypeConfig.objects.get(contract_type=self.contract_duration)
            except ContractTypeConfig.DoesNotExist:
                # Create default config if it doesn't exist
                contract_configs = ContractTypeConfig.get_or_create_defaults()
                contract_config = contract_configs.get(self.contract_duration)
                if not contract_config:
                    return self.status, "No contract configuration found"
            
            if not contract_config.enable_auto_transitions:
                return self.status, "Auto transitions disabled for this contract type"
            
            # Calculate days since start
            days_since_start = (current_date - self.start_date).days
            
            # Determine required status based on contract configuration
            if days_since_start <= contract_config.onboarding_days:
                # Still in onboarding period
                onboarding_status = EmployeeStatus.objects.filter(status_type='ONBOARDING').first()
                return onboarding_status, f"Onboarding period ({days_since_start}/{contract_config.onboarding_days} days)"
            
            elif days_since_start <= (contract_config.onboarding_days + contract_config.probation_days):
                # In probation period
                probation_status = EmployeeStatus.objects.filter(status_type='PROBATION').first()
                remaining_days = (contract_config.onboarding_days + contract_config.probation_days) - days_since_start
                return probation_status, f"Probation period ({remaining_days} days remaining)"
            
            else:
                # Should be active
                active_status = EmployeeStatus.objects.filter(status_type='ACTIVE').first()
                return active_status, "Onboarding and probation completed"
                
        except Exception as e:
            logger.error(f"Error calculating required status for {self.employee_id}: {e}")
            return self.status, f"Error: {str(e)}"

    def update_status_automatically(self, force_update=False):
        """Update employee status based on contract configuration"""
        try:
            required_status, reason = self.get_required_status_based_on_contract()
            
            if not required_status:
                return False
            
            # Check if status needs to be updated
            if self.status != required_status or force_update:
                old_status = self.status
                self.status = required_status
                self.save()
                
                # Log activity
                EmployeeActivity.objects.create(
                    employee=self,
                    activity_type='STATUS_CHANGED',
                    description=f"Status automatically updated from {old_status.name} to {required_status.name}. Reason: {reason}",
                    performed_by=None,  # System update
                    metadata={
                        'old_status': old_status.name,
                        'new_status': required_status.name,
                        'reason': reason,
                        'automatic': True,
                        'contract_type': self.contract_duration,
                        'days_since_start': (date.today() - self.start_date).days
                    }
                )
                
                logger.info(f"Employee {self.employee_id} status updated automatically: {old_status.name} → {required_status.name}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error updating status automatically for {self.employee_id}: {e}")
            return False

    def extend_contract(self, extension_months, user=None):
        """Extend employee contract"""
        if self.contract_duration == 'PERMANENT':
            return False, "Cannot extend permanent contract"
        
        if not self.contract_end_date:
            return False, "No contract end date to extend"
        
        try:
            if relativedelta:
                new_end_date = self.contract_end_date + relativedelta(months=extension_months)
            else:
                # Approximate calculation
                new_end_date = self.contract_end_date + timedelta(days=extension_months * 30)
            
            old_end_date = self.contract_end_date
            self.contract_end_date = new_end_date
            self.contract_extensions += 1
            self.last_extension_date = timezone.now().date()
            self.renewal_status = 'APPROVED'
            
            if user:
                self.updated_by = user
            
            self.save()
            
            # Log activity
            EmployeeActivity.objects.create(
                employee=self,
                activity_type='CONTRACT_UPDATED',
                description=f"Contract extended by {extension_months} months. New end date: {new_end_date}",
                performed_by=user,
                metadata={
                    'extension_months': extension_months,
                    'old_end_date': str(old_end_date),
                    'new_end_date': str(new_end_date),
                    'extension_count': self.contract_extensions
                }
            )
            
            return True, f"Contract extended successfully until {new_end_date}"
            
        except Exception as e:
            logger.error(f"Error extending contract for {self.employee_id}: {e}")
            return False, f"Error extending contract: {str(e)}"

    def add_tag(self, tag, user=None):
        """Add a tag to the employee"""
        if not self.tags.filter(id=tag.id).exists():
            self.tags.add(tag)
            
            # Log activity
            EmployeeActivity.objects.create(
                employee=self,
                activity_type='TAG_ADDED',
                description=f"Tag '{tag.name}' added",
                performed_by=user,
                metadata={'tag_id': tag.id, 'tag_name': tag.name}
            )
            return True
        return False

    def remove_tag(self, tag, user=None):
        """Remove a tag from the employee"""
        if self.tags.filter(id=tag.id).exists():
            self.tags.remove(tag)
            
            # Log activity
            EmployeeActivity.objects.create(
                employee=self,
                activity_type='TAG_REMOVED',
                description=f"Tag '{tag.name}' removed",
                performed_by=user,
                metadata={'tag_id': tag.id, 'tag_name': tag.name}
            )
            return True
        return False

    def change_line_manager(self, new_manager, user=None):
        """Change employee's line manager"""
        old_manager = self.line_manager
        self.line_manager = new_manager
        if user:
            self.updated_by = user
        self.save()
        
        # Log activity
        old_manager_name = old_manager.full_name if old_manager else 'None'
        new_manager_name = new_manager.full_name if new_manager else 'None'
        
        EmployeeActivity.objects.create(
            employee=self,
            activity_type='MANAGER_CHANGED',
            description=f"Line manager changed from {old_manager_name} to {new_manager_name}",
            performed_by=user,
            metadata={
                'old_manager_id': old_manager.id if old_manager else None,
                'new_manager_id': new_manager.id if new_manager else None,
                'old_manager_name': old_manager_name,
                'new_manager_name': new_manager_name
            }
        )

    @property
    def years_of_service(self):
        """Calculate years of service"""
        if self.start_date:
            end_date = self.end_date or date.today()
            delta = end_date - self.start_date
            return round(delta.days / 365.25, 1)
        return 0

    @property
    def current_status_display(self):
        """Get formatted status display"""
        if self.status:
            return f"{self.status.name}"
        return "No Status"

    def get_contract_duration_choices(self):
        """Get available contract duration choices"""
        return ContractTypeConfig.get_contract_choices()
    
    def get_contract_config(self):
        """Get contract configuration for this employee"""
        try:
            return ContractTypeConfig.objects.get(
                contract_type=self.contract_duration,
                is_active=True
            )
        except ContractTypeConfig.DoesNotExist:
            return None
    
    def clean(self):
        """Validate contract_duration exists in configurations"""
        super().clean()
        if self.contract_duration:
            try:
                ContractTypeConfig.objects.get(
                    contract_type=self.contract_duration,
                    is_active=True
                )
            except ContractTypeConfig.DoesNotExist:
                from django.core.exceptions import ValidationError
                raise ValidationError(f"Contract type '{self.contract_duration}' is not configured or inactive")

    def get_direct_reports_count(self):
        """Get count of direct reports"""
        return self.direct_reports.filter(status__affects_headcount=True, is_deleted=False).count()

    def get_grading_display(self):
        """Get formatted grading display with shorthand"""
        if self.grading_level:
            parts = self.grading_level.split('_')
            if len(parts) == 2:
                position_short, level = parts
                return f"{position_short}-{level}"
        return "No Grade"

    def get_status_preview(self):
        """Get status preview without updating"""
        required_status, reason = self.get_required_status_based_on_contract()
        current_status = self.status
        
        return {
            'current_status': current_status.name if current_status else None,
            'required_status': required_status.name if required_status else None,
            'needs_update': current_status != required_status,
            'reason': reason,
            'contract_type': self.contract_duration,
            'days_since_start': (date.today() - self.start_date).days,
            'contract_end_date': self.contract_end_date
        }

    def __str__(self):
        return f"{self.employee_id} - {self.full_name}"

    class Meta:
        ordering = ['employee_id']
        indexes = [
            models.Index(fields=['employee_id']),
            models.Index(fields=['start_date']),
            models.Index(fields=['status']),
            models.Index(fields=['position_group']),
            models.Index(fields=['business_function', 'department']),
            models.Index(fields=['is_deleted']),
            models.Index(fields=['contract_end_date']),
            models.Index(fields=['line_manager']),
        ]

# Employee Activity Log for tracking changes
class EmployeeActivity(models.Model):
    ACTIVITY_TYPES = [
        ('CREATED', 'Employee Created'),
        ('UPDATED', 'Employee Updated'),
        ('STATUS_CHANGED', 'Status Changed'),
        ('MANAGER_CHANGED', 'Manager Changed'),
        ('POSITION_CHANGED', 'Position Changed'),
        ('CONTRACT_UPDATED', 'Contract Updated'),
        ('DOCUMENT_UPLOADED', 'Document Uploaded'),
        ('GRADE_CHANGED', 'Grade Changed'),
        ('TAG_ADDED', 'Tag Added'),
        ('TAG_REMOVED', 'Tag Removed'),
        ('SOFT_DELETED', 'Employee Soft Deleted'),
        ('RESTORED', 'Employee Restored'),
        ('BULK_CREATED', 'Bulk Created'),
        ('STATUS_AUTO_UPDATED', 'Status Auto Updated'),
    ]
    
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='activities')
    activity_type = models.CharField(max_length=20, choices=ACTIVITY_TYPES)
    description = models.TextField()
    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.employee.full_name} - {self.activity_type}"

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Employee Activity"
        verbose_name_plural = "Employee Activities"


class ContractStatusManager:
    """Helper class for managing contract-based status transitions"""
    
    @staticmethod
    def bulk_update_employee_statuses(employee_ids=None, force_update=False):
        """Bulk update employee statuses based on contract configurations"""
        # Import here to avoid circular import
        from .status_management import EmployeeStatusManager
        
        if employee_ids:
            employees = Employee.objects.filter(id__in=employee_ids)
        else:
            employees = Employee.objects.all()
        
        updated_count = 0
        for employee in employees:
            if EmployeeStatusManager.update_employee_status(employee, force_update):
                updated_count += 1
        
        logger.info(f"Bulk status update completed: {updated_count} employees updated")
        return updated_count
    
    @staticmethod
    def get_employees_needing_status_update():
        """Get employees whose status needs to be updated"""
        # Import here to avoid circular import
        from .status_management import EmployeeStatusManager
        
        employees_to_update = []
        
        for employee in Employee.objects.all():
            preview = EmployeeStatusManager.get_status_preview(employee)
            if preview['needs_update']:
                employees_to_update.append({
                    'employee': employee,
                    'current_status': preview['current_status'],
                    'required_status': preview['required_status'],
                    'reason': preview['reason']
                })
        
        return employees_to_update
    
    @staticmethod
    def get_contract_expiring_soon(days=30):
        """Get employees whose contracts are expiring soon"""
        expiry_date = date.today() + timedelta(days=days)
        
        return Employee.objects.filter(
            contract_end_date__lte=expiry_date,
            contract_end_date__gte=date.today(),
            contract_duration__in=['3_MONTHS', '6_MONTHS', '1_YEAR', '2_YEARS', '3_YEARS'],
            is_deleted=False
        ).select_related('status', 'business_function', 'department')

# Signal handlers for automatic status updates
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=Employee)
def employee_post_save_handler(sender, instance, created, **kwargs):
    """Handle employee post-save operations"""
    if created:
        # Log creation activity
        EmployeeActivity.objects.create(
            employee=instance,
            activity_type='CREATED',
            description=f"Employee {instance.full_name} was created",
            performed_by=getattr(instance, '_created_by_user', None),
            metadata={
                'employee_id': instance.employee_id,
                'contract_type': instance.contract_duration,
                'initial_status': instance.status.name if instance.status else None
            }
        )