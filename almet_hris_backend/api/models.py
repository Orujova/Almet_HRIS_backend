# api/models.py

from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
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
    description = models.TextField(blank=True, null=True)
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
    description = models.TextField(blank=True, null=True)
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
    description = models.TextField(blank=True, null=True)
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
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']

# Position Groups
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
    description = models.TextField(blank=True, null=True)
    hierarchy_level = models.IntegerField(unique=True)  # 1=VC, 2=Director, etc.
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.get_name_display()

    class Meta:
        ordering = ['hierarchy_level']

# Offices
class Office(models.Model):
    name = models.CharField(max_length=100, unique=True)
    address = models.TextField(blank=True, null=True)
    business_function = models.ForeignKey(BusinessFunction, on_delete=models.CASCADE, related_name='offices')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']

# Employee Tags
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
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']

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

# Main Employee Model
class Employee(models.Model):
    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('ON LEAVE', 'On Leave'),
        ('PROBATION', 'Probation'),
        ('ON BOARDING', 'On Boarding'),
        ('TERMINATED', 'Terminated'),
        ('SUSPENDED', 'Suspended'),
    ]
    
    # Basic Information
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='employee_profile')
    employee_id = models.CharField(max_length=50, unique=True, help_text="HC Number")
    
    # Personal Information
    date_of_birth = models.DateField(null=True, blank=True)
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
    office = models.ForeignKey(Office, on_delete=models.PROTECT, related_name='employees')
    
    # Employment Dates
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    
    # Management Structure
    line_manager = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='direct_reports')
    
    # Status and Tags
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE')
    tags = models.ManyToManyField(EmployeeTag, blank=True, related_name='employees')
    
    # Visibility in org chart
    is_visible_in_org_chart = models.BooleanField(default=True)
    
    # Additional Information
    notes = models.TextField(blank=True, null=True)
    
    # Audit Information
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_employees')
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='updated_employees')

    @property
    def full_name(self):
        return f"{self.user.first_name} {self.user.last_name}".strip()
    
    @property
    def line_manager_hc_number(self):
        return self.line_manager.employee_id if self.line_manager else None
    
    @property
    def direct_reports_count(self):
        return self.direct_reports.filter(status='ACTIVE').count()

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
        ('OTHER', 'Other Activity'),
    ]
    
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='activities')
    activity_type = models.CharField(max_length=20, choices=ACTIVITY_TYPES)
    description = models.TextField()
    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict, blank=True)  # Additional data as JSON

    def __str__(self):
        return f"{self.employee.full_name} - {self.get_activity_type_display()}"

    class Meta:
        ordering = ['-timestamp']
        verbose_name = "Employee Activity"
        verbose_name_plural = "Employee Activities"