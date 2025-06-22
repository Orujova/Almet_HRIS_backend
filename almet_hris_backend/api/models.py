


from django.contrib.postgres.indexes import GinIndex

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.postgres.indexes import GinIndex
from datetime import date, timedelta
import uuid
import logging

# dateutil əvəzinə Python built-in datetime istifadə edəcəyik
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta  # Bu package install edilməlidir


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





# Business Structure Models
class BusinessFunction(models.Model):
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

class Department(models.Model):
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
        # Fix: Make department names unique within each business function
        unique_together = ['business_function', 'name']

class Unit(models.Model):
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
        # Fix: Make unit names unique within each department
        unique_together = ['department', 'name']

class JobFunction(models.Model):
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
        base_levels = ['LD', 'LQ', 'M', 'UQ', 'UD']
        return {level: f"{self.grading_shorthand}_{level}" for level in base_levels}

    def __str__(self):
        return self.get_name_display()

    class Meta:
        ordering = ['hierarchy_level']

# Employee Tags for categorization
class EmployeeTag(models.Model):
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

# Employee Status with color hierarchy management
class EmployeeStatus(models.Model):
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
        ('VACANT', 'Vacant Position'),  # New for vacancy management
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
    
    name = models.CharField(max_length=50, unique=True)
    status_type = models.CharField(max_length=20, choices=STATUS_TYPES, default='ACTIVE')
    color = models.CharField(max_length=7, default='#6B7280')
    affects_headcount = models.BooleanField(default=True, help_text="Whether this status counts toward active headcount")
    allows_org_chart = models.BooleanField(default=True, help_text="Whether employees with this status appear in org chart")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        # Auto-assign color based on status type if not explicitly set
        if not self.color or self.color == '#6B7280':
            self.color = self.STATUS_COLOR_HIERARCHY.get(self.status_type, '#6B7280')
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']
        verbose_name = "Employee Status"
        verbose_name_plural = "Employee Statuses"

# Vacancy Management Model
class VacantPosition(models.Model):
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

# Employee Documents
class EmployeeDocument(models.Model):
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
    file_path = models.CharField(max_length=500)
    file_size = models.PositiveIntegerField(null=True, blank=True)
    mime_type = models.CharField(max_length=100, blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='uploaded_documents')

    def __str__(self):
        return f"{self.employee.full_name} - {self.name}"

    class Meta:
        ordering = ['-uploaded_at']

# Main Employee Model with Enhanced Features
class Employee(models.Model):
    GENDER_CHOICES = [
        ('MALE', 'Male'),
        ('FEMALE', 'Female'),
    ]
    
    CONTRACT_DURATION_CHOICES = [
        ('3_MONTHS', '3 Months'),
        ('6_MONTHS', '6 Months'),
        ('1_YEAR', '1 Year'),
        ('2_YEARS', '2 Years'),
        ('3_YEARS', '3 Years'),
        ('PERMANENT', 'Permanent'),
    ]
    
    # Basic Information
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='employee_profile')
    employee_id = models.CharField(max_length=50, unique=True, help_text="HC Number")
    
    # Auto-generated full name
    full_name = models.CharField(max_length=300, editable=False, default='')
    
    # Personal Information
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, null=True, blank=True)
    address = models.TextField(blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    emergency_contact = models.TextField(blank=True, null=True)
    profile_image = models.CharField(max_length=500, blank=True, null=True)
    
    # Job Information with enhanced grading integration
    business_function = models.ForeignKey(BusinessFunction, on_delete=models.PROTECT, related_name='employees')
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name='employees')
    unit = models.ForeignKey(Unit, on_delete=models.PROTECT, related_name='employees', null=True, blank=True)
    job_function = models.ForeignKey(JobFunction, on_delete=models.PROTECT, related_name='employees')
    job_title = models.CharField(max_length=200)
    position_group = models.ForeignKey(PositionGroup, on_delete=models.PROTECT, related_name='employees')
    
    # Enhanced grading system integration
    grade = models.CharField(max_length=50, blank=True, help_text="Current salary grade from grading system")
    grading_level = models.CharField(max_length=10, blank=True, help_text="Specific grading level (e.g., MGR_UQ)")
    
    # Employment Dates with enhanced contract management
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    contract_duration = models.CharField(max_length=20, choices=CONTRACT_DURATION_CHOICES, default='PERMANENT')
    contract_start_date = models.DateField(null=True, blank=True)
    contract_end_date = models.DateField(null=True, blank=True, editable=False)  # Auto-calculated
    
    # Management Hierarchy
    line_manager = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='direct_reports')
    
    # Status and Visibility
    status = models.ForeignKey(EmployeeStatus, on_delete=models.PROTECT, related_name='employees')
    is_visible_in_org_chart = models.BooleanField(default=True)
    
    # Tags and categorization
    tags = models.ManyToManyField(EmployeeTag, blank=True, related_name='employees')
    
    # Additional Information
    notes = models.TextField(blank=True)
    
    # Linked vacancy (if employee was hired for a specific vacant position)
    filled_vacancy = models.OneToOneField(VacantPosition, on_delete=models.SET_NULL, null=True, blank=True, related_name='hired_employee')
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        # Auto-generate full name
        if self.user:
            first_name = self.user.first_name or ''
            last_name = self.user.last_name or ''
            self.full_name = f"{first_name} {last_name}".strip()
        
        # Auto-calculate contract end date - FIX: Try/except əlavə edildi
        if self.contract_start_date and self.contract_duration != 'PERMANENT':
            try:
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
            except ImportError:
                # Fallback to approximate calculation if dateutil is not available
                days_mapping = {
                    '3_MONTHS': 90,
                    '6_MONTHS': 180,
                    '1_YEAR': 365,
                    '2_YEARS': 730,
                    '3_YEARS': 1095
                }
                days = days_mapping.get(self.contract_duration, 365)
                self.contract_end_date = self.contract_start_date + timedelta(days=days)
        else:
            self.contract_end_date = None
        
        # Auto-generate grading level based on position group
        if self.position_group and not self.grading_level:
            self.grading_level = f"{self.position_group.grading_shorthand}_M"  # Default to median
        
        # Link to vacant position if applicable
        if not self.filled_vacancy and hasattr(self, '_vacancy_id'):
            try:
                vacancy = VacantPosition.objects.get(id=self._vacancy_id)
                vacancy.mark_as_filled(self)
                self.filled_vacancy = vacancy
            except VacantPosition.DoesNotExist:
                pass
        
        super().save(*args, **kwargs)

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

    def get_contract_duration_display(self):
        """Get formatted contract duration"""
        if self.contract_duration == 'PERMANENT':
            return 'Permanent'
        elif self.contract_end_date:
            return f"{self.get_contract_duration_display()} (Until {self.contract_end_date.strftime('%d/%m/%Y')})"
        return dict(self.CONTRACT_DURATION_CHOICES).get(self.contract_duration, self.contract_duration)

    def get_direct_reports_count(self):
        """Get count of direct reports"""
        return self.direct_reports.filter(status__affects_headcount=True).count()

    def get_grading_display(self):
        """Get formatted grading display with shorthand"""
        if self.grading_level:
            parts = self.grading_level.split('_')
            if len(parts) == 2:
                position_short, level = parts
                return f"{position_short}-{level}"
        return self.grade or "No Grade"

    def update_contract_status(self):
        """Update employee status based on contract dates"""
        today = date.today()
        
        if self.contract_end_date and self.contract_end_date <= today:
            # Contract has expired
            expired_status, _ = EmployeeStatus.objects.get_or_create(
                name="Contract Expired",
                defaults={'status_type': 'INACTIVE', 'affects_headcount': False}
            )
            self.status = expired_status
            self.save()

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

# Headcount Summary Model for reporting
class HeadcountSummary(models.Model):
    """Model for storing headcount summaries and analytics"""
    
    summary_date = models.DateField(unique=True)
    
    # Overall headcount
    total_employees = models.IntegerField(default=0)
    active_employees = models.IntegerField(default=0)
    inactive_employees = models.IntegerField(default=0)
    vacant_positions = models.IntegerField(default=0)
    
    # By business function
    headcount_by_function = models.JSONField(default=dict)
    
    # By department
    headcount_by_department = models.JSONField(default=dict)
    
    # By position group
    headcount_by_position = models.JSONField(default=dict)
    
    # By status
    headcount_by_status = models.JSONField(default=dict)
    
    # Contract analysis
    contract_analysis = models.JSONField(default=dict)
    
    # Additional metrics
    avg_years_of_service = models.FloatField(default=0)
    new_hires_month = models.IntegerField(default=0)
    departures_month = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)

    @classmethod
    def generate_summary(cls, date=None):
        """Generate headcount summary for a specific date"""
        from django.db.models import Count, Avg
        
        if date is None:
            date = date.today()
        
        # Get employee counts
        active_statuses = EmployeeStatus.objects.filter(affects_headcount=True)
        
        total_employees = Employee.objects.count()
        active_employees = Employee.objects.filter(status__in=active_statuses).count()
        inactive_employees = total_employees - active_employees
        vacant_positions = VacantPosition.objects.filter(is_filled=False).count()
        
        # Business function breakdown
        function_data = {}
        for func in BusinessFunction.objects.filter(is_active=True):
            func_count = Employee.objects.filter(
                business_function=func,
                status__in=active_statuses
            ).count()
            function_data[func.name] = func_count
        
        # Department breakdown  
        dept_data = {}
        for dept in Department.objects.filter(is_active=True):
            dept_count = Employee.objects.filter(
                department=dept,
                status__in=active_statuses
            ).count()
            dept_data[f"{dept.business_function.code}-{dept.name}"] = dept_count
        
        # Position group breakdown
        position_data = {}
        for pos in PositionGroup.objects.filter(is_active=True):
            pos_count = Employee.objects.filter(
                position_group=pos,
                status__in=active_statuses
            ).count()
            position_data[pos.get_name_display()] = pos_count
        
        # Status breakdown
        status_data = {}
        for status in EmployeeStatus.objects.filter(is_active=True):
            status_count = Employee.objects.filter(status=status).count()
            status_data[status.name] = status_count
        
        # Contract analysis
        contract_data = {}
        for duration in Employee.CONTRACT_DURATION_CHOICES:
            contract_count = Employee.objects.filter(
                contract_duration=duration[0],
                status__in=active_statuses
            ).count()
            contract_data[duration[1]] = contract_count
        
        # Create or update summary
        summary, created = cls.objects.update_or_create(
            summary_date=date,
            defaults={
                'total_employees': total_employees,
                'active_employees': active_employees,
                'inactive_employees': inactive_employees,
                'vacant_positions': vacant_positions,
                'headcount_by_function': function_data,
                'headcount_by_department': dept_data,
                'headcount_by_position': position_data,
                'headcount_by_status': status_data,
                'contract_analysis': contract_data,
                'avg_years_of_service': 0,  # Would need more complex calculation
                'new_hires_month': 0,  # Would need date filtering
                'departures_month': 0,  # Would need date filtering
            }
        )
        
        return summary

    def __str__(self):
        return f"Headcount Summary - {self.summary_date}"

    class Meta:
        ordering = ['-summary_date']
        verbose_name = "Headcount Summary"
        verbose_name_plural = "Headcount Summaries"