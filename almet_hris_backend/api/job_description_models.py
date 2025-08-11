# api/job_description_models.py

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import MinLengthValidator
import uuid

class JobDescription(models.Model):
    """Main Job Description model"""
    
    # Primary fields
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job_title = models.CharField(max_length=200, verbose_name="Job Title")
    
    # Hierarchical and organizational data from existing models
    business_function = models.ForeignKey(
        'BusinessFunction', 
        on_delete=models.CASCADE,
        verbose_name="Business Function"
    )
    department = models.ForeignKey(
        'Department', 
        on_delete=models.CASCADE,
        verbose_name="Department"
    )
    unit = models.ForeignKey(
        'Unit', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        verbose_name="Unit"
    )
    position_group = models.ForeignKey(
        'PositionGroup', 
        on_delete=models.CASCADE,
        verbose_name="Position Group/Hierarchy"
    )
    grading_level = models.CharField(
        max_length=10, 
        help_text="Grading level from position group"
    )
    
    # Reports to (Manager/Supervisor - Employee from existing system)
    reports_to = models.ForeignKey(
        'Employee', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='subordinate_job_descriptions',
        verbose_name="Reports To (Manager)"
    )
    
    # Employee this job description is for (can be existing employee or manual entry)
    assigned_employee = models.ForeignKey(
        'Employee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_job_descriptions',
        verbose_name="Assigned Employee"
    )
    
    # Manual employee info (when no existing employee)
    manual_employee_name = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Employee Name (Manual)"
    )

    manual_employee_phone = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Employee Phone (Manual)"
    )
    
    # Job details
    job_purpose = models.TextField(
        validators=[MinLengthValidator(50)],
        help_text="Main purpose and objectives of the role"
    )
    
    # Status and approval
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('PENDING_LINE_MANAGER', 'Pending Line Manager Approval'),
        ('PENDING_EMPLOYEE', 'Pending Employee Approval'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('REVISION_REQUIRED', 'Revision Required'),
    ]
    
    status = models.CharField(
        max_length=25, 
        choices=STATUS_CHOICES, 
        default='DRAFT'
    )
    
    # Approval workflow
    line_manager_approved_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='line_manager_approved_job_descriptions'
    )
    line_manager_approved_at = models.DateTimeField(null=True, blank=True)
    line_manager_comments = models.TextField(blank=True)
    
    employee_approved_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='employee_approved_job_descriptions'
    )
    employee_approved_at = models.DateTimeField(null=True, blank=True)
    employee_comments = models.TextField(blank=True)
    
    # Digital signatures
    line_manager_signature = models.FileField(
        upload_to='job_descriptions/signatures/line_managers/',
        null=True, 
        blank=True
    )
    employee_signature = models.FileField(
        upload_to='job_descriptions/signatures/employees/',
        null=True, 
        blank=True
    )
    
    # Metadata
    created_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True,
        related_name='created_job_descriptions'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True,
        related_name='updated_job_descriptions'
    )
    
    # Version control
    version = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'job_descriptions'
        verbose_name = 'Job Description'
        verbose_name_plural = 'Job Descriptions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['job_title']),
            models.Index(fields=['status']),
            models.Index(fields=['business_function', 'department']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.job_title} - {self.department.name} ({self.status})"
    
    def get_status_display_with_color(self):
        """Get status with color coding"""
        status_colors = {
            'DRAFT': '#6B7280',
            'PENDING_LINE_MANAGER': '#F59E0B',
            'PENDING_EMPLOYEE': '#3B82F6',
            'APPROVED': '#10B981',
            'REJECTED': '#EF4444',
            'REVISION_REQUIRED': '#8B5CF6',
        }
        return {
            'status': self.get_status_display(),
            'color': status_colors.get(self.status, '#6B7280')
        }
    
    def can_be_approved_by_line_manager(self, user):
        """Check if user can approve as line manager"""
        if self.status != 'PENDING_LINE_MANAGER':
            return False
        
        # Check if user is the reports_to manager
        if self.reports_to:
            return self.reports_to.user == user
        
        return False
    
    def can_be_approved_by_employee(self, user):
        """Check if user can approve as employee"""
        if self.status != 'PENDING_EMPLOYEE':
            return False
        
        # Check if user is the assigned employee
        if self.assigned_employee:
            return self.assigned_employee.user == user
        
        return False
    
    def get_employee_info(self):
        """Get employee information (existing or manual)"""
        if self.assigned_employee:
            return {
                'type': 'existing',
                'id': self.assigned_employee.id,
                'name': self.assigned_employee.full_name,
             
                'phone': self.assigned_employee.phone,
                'employee_id': self.assigned_employee.employee_id
            }
        elif self.manual_employee_name:
            return {
                'type': 'manual',
                'name': self.manual_employee_name,
               
                'phone': self.manual_employee_phone
            }
        return None
    
    def get_manager_info(self):
        """Get manager information"""
        if self.reports_to:
            return {
                'id': self.reports_to.id,
                'name': self.reports_to.full_name,
             
                'job_title': self.reports_to.job_title,
                'employee_id': self.reports_to.employee_id
            }
        return None
    
    def approve_by_line_manager(self, user, comments="", signature=None):
        """Approve by line manager"""
        if not self.can_be_approved_by_line_manager(user):
            raise ValueError("User cannot approve this job description as line manager")
        
        self.line_manager_approved_by = user
        self.line_manager_approved_at = timezone.now()
        self.line_manager_comments = comments
        if signature:
            self.line_manager_signature = signature
        
        # Move to employee approval
        self.status = 'PENDING_EMPLOYEE'
        self.save()
    
    def approve_by_employee(self, user, comments="", signature=None):
        """Approve by employee"""
        if not self.can_be_approved_by_employee(user):
            raise ValueError("User cannot approve this job description as employee")
        
        self.employee_approved_by = user
        self.employee_approved_at = timezone.now()
        self.employee_comments = comments
        if signature:
            self.employee_signature = signature
        
        # Final approval
        self.status = 'APPROVED'
        self.save()
    
    def reject(self, user, reason):
        """Reject job description"""
        self.status = 'REJECTED'
        if self.reports_to and self.reports_to.line_manager and self.reports_to.line_manager.user == user:
            self.line_manager_comments = reason
        elif self.reports_to and self.reports_to.user == user:
            self.employee_comments = reason
        self.save()
    
    def request_revision(self, user, reason):
        """Request revision"""
        self.status = 'REVISION_REQUIRED'
        if self.reports_to and self.reports_to.line_manager and self.reports_to.line_manager.user == user:
            self.line_manager_comments = reason
        elif self.reports_to and self.reports_to.user == user:
            self.employee_comments = reason
        self.save()


class JobDescriptionSection(models.Model):
    """Flexible sections for job descriptions"""
    
    SECTION_TYPES = [
        ('CRITICAL_DUTIES', 'Critical Duties'),
        ('MAIN_KPIS', 'Main KPIs'),
        ('JOB_DUTIES', 'Job Duties'),
        ('REQUIREMENTS', 'Requirements'),
        ('CUSTOM', 'Custom Section'),
    ]
    
    job_description = models.ForeignKey(
        JobDescription, 
        on_delete=models.CASCADE,
        related_name='sections'
    )
    section_type = models.CharField(max_length=20, choices=SECTION_TYPES)
    title = models.CharField(max_length=200)
    content = models.TextField()
    order = models.PositiveIntegerField(default=0)
    
    class Meta:
        db_table = 'job_description_sections'
        ordering = ['order', 'id']
        unique_together = ['job_description', 'section_type', 'order']
    
    def __str__(self):
        return f"{self.job_description.job_title} - {self.get_section_type_display()}"


class JobDescriptionSkill(models.Model):
    """Core skills for job descriptions"""
    
    PROFICIENCY_LEVELS = [
        ('BASIC', 'Basic'),
        ('INTERMEDIATE', 'Intermediate'),
        ('ADVANCED', 'Advanced'),
        ('EXPERT', 'Expert'),
    ]
    
    job_description = models.ForeignKey(
        JobDescription, 
        on_delete=models.CASCADE,
        related_name='required_skills'
    )
    skill = models.ForeignKey(
        'Skill', 
        on_delete=models.CASCADE,
        help_text="Skill from competency system"
    )
    proficiency_level = models.CharField(
        max_length=15, 
        choices=PROFICIENCY_LEVELS,
        default='INTERMEDIATE'
    )
    is_mandatory = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'job_description_skills'
        unique_together = ['job_description', 'skill']
    
    def __str__(self):
        return f"{self.skill.name} ({self.get_proficiency_level_display()})"


class JobDescriptionBehavioralCompetency(models.Model):
    """Behavioral competencies for job descriptions"""
    
    PROFICIENCY_LEVELS = [
        ('BASIC', 'Basic'),
        ('INTERMEDIATE', 'Intermediate'),
        ('ADVANCED', 'Advanced'),
        ('EXPERT', 'Expert'),
    ]
    
    job_description = models.ForeignKey(
        JobDescription, 
        on_delete=models.CASCADE,
        related_name='behavioral_competencies'
    )
    competency = models.ForeignKey(
        'BehavioralCompetency', 
        on_delete=models.CASCADE,
        help_text="Competency from competency system"
    )
    proficiency_level = models.CharField(
        max_length=15, 
        choices=PROFICIENCY_LEVELS,
        default='INTERMEDIATE'
    )
    is_mandatory = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'job_description_behavioral_competencies'
        unique_together = ['job_description', 'competency']
    
    def __str__(self):
        return f"{self.competency.name} ({self.get_proficiency_level_display()})"


# Extra tables for additional resources

class JobBusinessResource(models.Model):
    """Business resources for job descriptions"""
    
    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        db_table = 'job_business_resources'
        ordering = ['category', 'name']
    
    def __str__(self):
        return self.name


class AccessMatrix(models.Model):
    """Access rights matrix for job descriptions"""
    
    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True)
    access_level = models.CharField(max_length=50)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        db_table = 'access_matrix'
        verbose_name_plural = 'Access Matrix'
        ordering = ['access_level', 'name']
    
    def __str__(self):
        return f"{self.name} ({self.access_level})"


class CompanyBenefit(models.Model):
    """Company benefits for job descriptions"""
    
    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True)
    benefit_type = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        db_table = 'company_benefits'
        ordering = ['benefit_type', 'name']
    
    def __str__(self):
        return self.name


# Junction tables for many-to-many relationships

class JobDescriptionBusinessResource(models.Model):
    """Link job descriptions to business resources"""
    
    job_description = models.ForeignKey(
        JobDescription, 
        on_delete=models.CASCADE,
        related_name='business_resources'
    )
    resource = models.ForeignKey(JobBusinessResource, on_delete=models.CASCADE)
    
    class Meta:
        db_table = 'job_description_business_resources'
        unique_together = ['job_description', 'resource']


class JobDescriptionAccessMatrix(models.Model):
    """Link job descriptions to access rights"""
    
    job_description = models.ForeignKey(
        JobDescription, 
        on_delete=models.CASCADE,
        related_name='access_rights'
    )
    access_matrix = models.ForeignKey(AccessMatrix, on_delete=models.CASCADE)
    
    class Meta:
        db_table = 'job_description_access_matrix'
        unique_together = ['job_description', 'access_matrix']


class JobDescriptionCompanyBenefit(models.Model):
    """Link job descriptions to company benefits"""
    
    job_description = models.ForeignKey(
        JobDescription, 
        on_delete=models.CASCADE,
        related_name='company_benefits'
    )
    benefit = models.ForeignKey(CompanyBenefit, on_delete=models.CASCADE)
    
    class Meta:
        db_table = 'job_description_company_benefits'
        unique_together = ['job_description', 'benefit']


class JobDescriptionActivity(models.Model):
    """Activity log for job descriptions"""
    
    ACTIVITY_TYPES = [
        ('CREATED', 'Created'),
        ('UPDATED', 'Updated'),
        ('SUBMITTED_FOR_APPROVAL', 'Submitted for Approval'),
        ('APPROVED_BY_LINE_MANAGER', 'Approved by Line Manager'),
        ('APPROVED_BY_EMPLOYEE', 'Approved by Employee'),
        ('REJECTED', 'Rejected'),
        ('REVISION_REQUESTED', 'Revision Requested'),
        ('RESUBMITTED', 'Resubmitted'),
    ]
    
    job_description = models.ForeignKey(
        JobDescription, 
        on_delete=models.CASCADE,
        related_name='activities'
    )
    activity_type = models.CharField(max_length=30, choices=ACTIVITY_TYPES)
    description = models.TextField()
    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    performed_at = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        db_table = 'job_description_activities'
        ordering = ['-performed_at']
    
    def __str__(self):
        return f"{self.job_description.job_title} - {self.get_activity_type_display()}"
    
    
    
    
    