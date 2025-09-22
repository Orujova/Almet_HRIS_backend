# api/vacation_models.py - Updated Vacation Management System Models

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from datetime import date, timedelta
from django.db import transaction
from django.core.exceptions import ValidationError
import logging
from .models import Employee, SoftDeleteModel, ActiveManager, AllObjectsManager

logger = logging.getLogger(__name__)

class VacationSetting(SoftDeleteModel):
    """Global vacation system settings"""
    
    # Production calendar settings
    non_working_days = models.JSONField(
        default=list,
        help_text="List of non-working dates (holidays, etc.) in YYYY-MM-DD format"
    )
    
    # Default HR representative
    default_hr_representative = models.ForeignKey(
        Employee,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='hr_vacation_settings',
        help_text="Default HR representative for vacation approvals"
    )
    
    # Vacation balance settings
    allow_negative_balance = models.BooleanField(
        default=False,
        help_text="Allow vacation requests when remaining balance is zero"
    )
    
    # Schedule editing settings
    max_schedule_edits = models.PositiveIntegerField(
        default=3,
        help_text="Maximum number of times a scheduled vacation can be edited"
    )
    
    # Notification settings
    notification_days_before = models.PositiveIntegerField(
        default=7,
        help_text="Days before vacation start to send notifications"
    )
    notification_frequency = models.PositiveIntegerField(
        default=1,
        help_text="How many times to send notifications"
    )
    
    # Active settings
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        verbose_name = "Vacation Setting"
        verbose_name_plural = "Vacation Settings"
    
    def __str__(self):
        return f"Vacation Settings (Active: {self.is_active})"
    
    @classmethod
    def get_active_settings(cls):
        """Get active vacation settings"""
        return cls.objects.filter(is_active=True).first()
    
    def is_working_day(self, check_date):
        """Check if a date is a working day"""
        # Check if it's weekend
        if check_date.weekday() >= 5:  # Saturday = 5, Sunday = 6
            return False
        
        # Check if it's in non-working days list
        date_str = check_date.strftime('%Y-%m-%d')
        return date_str not in self.non_working_days
    
    def calculate_working_days(self, start_date, end_date):
        """Calculate working days between two dates"""
        if start_date > end_date:
            return 0
        
        working_days = 0
        current_date = start_date
        
        while current_date <= end_date:
            if self.is_working_day(current_date):
                working_days += 1
            current_date += timedelta(days=1)
        
        return working_days
    
    def calculate_return_date(self, end_date):
        """Calculate next working day after end date"""
        return_date = end_date + timedelta(days=1)
        while not self.is_working_day(return_date):
            return_date += timedelta(days=1)
        return return_date

class VacationType(SoftDeleteModel):
    """Types of vacation/leave"""
    
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True)
    
    # Type settings
    requires_approval = models.BooleanField(default=True)
    affects_balance = models.BooleanField(default=True)
    max_consecutive_days = models.PositiveIntegerField(
        null=True, 
        blank=True,
        help_text="Maximum consecutive days for this type"
    )
    
    # Colors for UI
    color = models.CharField(max_length=7, default='#3B82F6')
    
    # Status
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
        verbose_name = "Vacation Type"
        verbose_name_plural = "Vacation Types"
    
    def __str__(self):
        return f"{self.code} - {self.name}"

class EmployeeVacationBalance(SoftDeleteModel):
    """Employee vacation balance tracking"""
    
    employee = models.ForeignKey(
        Employee, 
        on_delete=models.CASCADE, 
        related_name='vacation_balances'
    )
    year = models.PositiveIntegerField()
    
    # Balance fields
    start_balance = models.DecimalField(
        max_digits=5, 
        decimal_places=1, 
        default=0,
        help_text="Starting balance for the year (remaining from previous year)"
    )
    yearly_balance = models.DecimalField(
        max_digits=5, 
        decimal_places=1, 
        default=0,
        help_text="Yearly allocated vacation days"
    )
    used_days = models.DecimalField(
        max_digits=5, 
        decimal_places=1, 
        default=0,
        help_text="Days already used"
    )
    scheduled_days = models.DecimalField(
        max_digits=5, 
        decimal_places=1, 
        default=0,
        help_text="Days scheduled but not yet taken"
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        unique_together = ['employee', 'year']
        ordering = ['-year', 'employee__employee_id']
        verbose_name = "Employee Vacation Balance"
        verbose_name_plural = "Employee Vacation Balances"
    
    def __str__(self):
        return f"{self.employee.full_name} - {self.year} Balance"
    
    @property
    def total_balance(self):
        """Calculate total available balance"""
        return self.start_balance + self.yearly_balance
    
    @property
    def remaining_balance(self):
        """Calculate remaining balance"""
        return self.total_balance - self.used_days - self.scheduled_days
    
    @property
    def should_be_planned(self):
        """Calculate days that should be planned (yearly balance - scheduled days)"""
        return max(0, self.yearly_balance - self.scheduled_days)
    
    def can_request_days(self, requested_days):
        """Check if employee can request specified days"""
        settings = VacationSetting.get_active_settings()
        if settings and settings.allow_negative_balance:
            return True
        return self.remaining_balance >= requested_days
    
    def reserve_days(self, days):
        """Reserve days for scheduled vacation"""
        self.scheduled_days += days
        self.save()
    
    def unreserve_days(self, days):
        """Unreserve days from scheduled vacation"""
        self.scheduled_days = max(0, self.scheduled_days - days)
        self.save()
    
    def use_days(self, days):
        """Mark days as used"""
        self.used_days += days
        self.scheduled_days = max(0, self.scheduled_days - days)
        self.save()

class VacationRequest(SoftDeleteModel):
    """Main vacation request model"""
    
    REQUEST_TYPES = [
        ('IMMEDIATE', 'Request Immediately'),
        ('SCHEDULED', 'Scheduled')
    ]
    
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('IN_PROGRESS', 'In Progress'),
        ('PENDING_LINE_MANAGER', 'Pending Line Manager Approval'),
        ('PENDING_HR', 'Pending HR Approval'),
        ('APPROVED', 'Approved'),
        ('REJECTED_LINE_MANAGER', 'Rejected by Line Manager'),
        ('REJECTED_HR', 'Rejected by HR'),
        ('CANCELLED', 'Cancelled'),
        ('REGISTERED', 'Registered'),  # For scheduled requests that are taken
        ('COMPLETED', 'Completed'),
    ]
    
    # Request identification
    request_id = models.CharField(max_length=50, unique=True, editable=False)
    
    # Employee information
    employee = models.ForeignKey(
        Employee, 
        on_delete=models.CASCADE, 
        related_name='vacation_requests'
    )
    requester = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='vacation_requests_made',
        help_text="Person who made the request (for 'for my employee' cases)"
    )
    
    # Request type
    request_type = models.CharField(max_length=20, choices=REQUEST_TYPES)
    
    # Vacation details
    vacation_type = models.ForeignKey(VacationType, on_delete=models.PROTECT)
    start_date = models.DateField()
    end_date = models.DateField()
    return_date = models.DateField(editable=False)  # Auto-calculated
    number_of_days = models.DecimalField(
        max_digits=5, 
        decimal_places=1, 
        editable=False
    )  # Auto-calculated
    
    # Additional information
    comment = models.TextField(blank=True)
    
    # Approval workflow
    line_manager = models.ForeignKey(
        Employee,
        on_delete=models.SET_NULL,
        null=True,
        related_name='vacation_requests_to_approve'
    )
    hr_representative = models.ForeignKey(
        Employee,
        on_delete=models.SET_NULL,
        null=True,
        related_name='vacation_requests_hr_approval'
    )
    
    # Status tracking
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='DRAFT')
    
    # Approval tracking
    line_manager_approved_at = models.DateTimeField(null=True, blank=True)
    line_manager_approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='line_manager_vacation_approvals'
    )
    line_manager_comment = models.TextField(blank=True)
    
    hr_approved_at = models.DateTimeField(null=True, blank=True)
    hr_approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='hr_vacation_approvals'
    )
    hr_comment = models.TextField(blank=True)
    
    # Rejection tracking
    rejected_at = models.DateTimeField(null=True, blank=True)
    rejected_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='vacation_rejections'
    )
    rejection_reason = models.TextField(blank=True)
    
    # Schedule editing tracking (for SCHEDULED requests)
    edit_count = models.PositiveIntegerField(default=0)
    last_edited_at = models.DateTimeField(null=True, blank=True)
    last_edited_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='vacation_edits'
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Vacation Request"
        verbose_name_plural = "Vacation Requests"
        indexes = [
            models.Index(fields=['employee', 'status']),
            models.Index(fields=['start_date', 'end_date']),
            models.Index(fields=['status', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.request_id} - {self.employee.full_name} ({self.start_date} to {self.end_date})"
    
    def save(self, *args, **kwargs):
        # Generate request ID
        if not self.request_id:
            self.request_id = self.generate_request_id()
        
        # Calculate return date and number of days
        self.calculate_dates()
        
        # Auto-assign line manager and HR
        self.auto_assign_approvers()
        
        super().save(*args, **kwargs)
    
    def generate_request_id(self):
        """Generate unique request ID"""
        year = timezone.now().year
        last_request = VacationRequest.objects.filter(
            request_id__startswith=f'VR{year}'
        ).order_by('-request_id').first()
        
        if last_request:
            try:
                last_number = int(last_request.request_id[6:])  # VR2024 prefix = 6 chars
                next_number = last_number + 1
            except (ValueError, IndexError):
                next_number = 1
        else:
            next_number = 1
        
        return f'VR{year}{next_number:04d}'
    
    def calculate_dates(self):
        """Calculate return date and working days"""
        if not self.start_date or not self.end_date:
            return
        
        settings = VacationSetting.get_active_settings()
        if settings:
            # Calculate working days
            self.number_of_days = settings.calculate_working_days(
                self.start_date, 
                self.end_date
            )
            
            # Calculate return date (next working day after end_date)
            self.return_date = settings.calculate_return_date(self.end_date)
        else:
            # Fallback calculation
            self.number_of_days = (self.end_date - self.start_date).days + 1
            self.return_date = self.end_date + timedelta(days=1)
    
    def auto_assign_approvers(self):
        """Auto-assign line manager and HR representative"""
        # For 'for me' requests
        if self.employee == self.requester.employee if hasattr(self.requester, 'employee') else None:
            if not self.line_manager and self.employee.line_manager:
                self.line_manager = self.employee.line_manager
        
        # For manager creating request for their employee
        else:
            # Skip line manager approval if manager is creating for their employee
            # Go directly to HR
            self.line_manager = None
        
        # Assign HR representative
        if not self.hr_representative:
            settings = VacationSetting.get_active_settings()
            if settings and settings.default_hr_representative:
                self.hr_representative = settings.default_hr_representative
    
    def can_be_edited(self):
        """Check if request can be edited"""
        if self.request_type == 'IMMEDIATE':
            return self.status in ['DRAFT']
        
        # For scheduled requests
        if self.status not in ['DRAFT']:
            return False
        
        settings = VacationSetting.get_active_settings()
        if settings:
            return self.edit_count < settings.max_schedule_edits
        
        return self.edit_count < 3  # Default max edits
    
    def submit_request(self, user):
        """Submit request for approval"""
        if self.status != 'DRAFT':
            raise ValidationError("Only draft requests can be submitted")
        
        # Check if employee has sufficient balance for immediate requests
        if self.request_type == 'IMMEDIATE':
            balance = self.get_employee_balance()
            if balance and not balance.can_request_days(self.number_of_days):
                settings = VacationSetting.get_active_settings()
                if not settings or not settings.allow_negative_balance:
                    raise ValidationError("Insufficient vacation balance")
        
        # Set status to in progress first
        self.status = 'IN_PROGRESS'
        
        # Determine approval workflow
        # Check if requester is manager creating for their employee
        is_manager_request = (
            hasattr(user, 'employee') and 
            self.employee.line_manager == user.employee if hasattr(user, 'employee') else False
        )
        
        if is_manager_request:
            # Manager creating for employee - skip line manager approval
            if self.hr_representative:
                self.status = 'PENDING_HR'
            else:
                self.status = 'APPROVED'  # Auto-approve if no HR
        else:
            # Regular employee request
            if self.line_manager:
                self.status = 'PENDING_LINE_MANAGER'
            elif self.hr_representative:
                self.status = 'PENDING_HR'
            else:
                self.status = 'APPROVED'  # Auto-approve if no approvers
        
        self.save()
        
        # Reserve days for scheduled requests
        if self.request_type == 'SCHEDULED':
            balance = self.get_employee_balance()
            if balance:
                balance.reserve_days(self.number_of_days)
    
    def approve_by_line_manager(self, user, comment=''):
        """Approve request by line manager"""
        if self.status != 'PENDING_LINE_MANAGER':
            raise ValidationError("Request is not pending line manager approval")
        
        self.line_manager_approved_at = timezone.now()
        self.line_manager_approved_by = user
        self.line_manager_comment = comment
        
        # Move to next approval stage
        if self.hr_representative:
            self.status = 'PENDING_HR'
        else:
            self.status = 'APPROVED'
        
        self.save()
    
    def reject_by_line_manager(self, user, reason):
        """Reject request by line manager"""
        if self.status != 'PENDING_LINE_MANAGER':
            raise ValidationError("Request is not pending line manager approval")
        
        self.status = 'REJECTED_LINE_MANAGER'
        self.rejected_at = timezone.now()
        self.rejected_by = user
        self.rejection_reason = reason
        self.save()
        
        # Unreserve days if scheduled
        if self.request_type == 'SCHEDULED':
            balance = self.get_employee_balance()
            if balance:
                balance.unreserve_days(self.number_of_days)
    
    def approve_by_hr(self, user, comment=''):
        """Approve request by HR"""
        if self.status != 'PENDING_HR':
            raise ValidationError("Request is not pending HR approval")
        
        self.hr_approved_at = timezone.now()
        self.hr_approved_by = user
        self.hr_comment = comment
        self.status = 'APPROVED'
        self.save()
    
    def reject_by_hr(self, user, reason):
        """Reject request by HR"""
        if self.status != 'PENDING_HR':
            raise ValidationError("Request is not pending HR approval")
        
        self.status = 'REJECTED_HR'
        self.rejected_at = timezone.now()
        self.rejected_by = user
        self.rejection_reason = reason
        self.save()
        
        # Unreserve days if scheduled
        if self.request_type == 'SCHEDULED':
            balance = self.get_employee_balance()
            if balance:
                balance.unreserve_days(self.number_of_days)
    
    def register_vacation(self, user):
        """Register scheduled vacation as taken"""
        if self.request_type == 'SCHEDULED' and self.status == 'APPROVED':
            # This is for approved scheduled requests being registered
            balance = self.get_employee_balance()
            if balance:
                balance.use_days(self.number_of_days)
            
            self.status = 'REGISTERED'
            self.save()
            
            # Create vacation activity record
            VacationActivity.objects.create(
                vacation_request=self,
                activity_type='REGISTERED',
                description=f"Vacation registered as taken",
                performed_by=user
            )
        else:
            raise ValidationError("Only approved scheduled requests can be registered")
    
    def get_employee_balance(self):
        """Get employee's vacation balance for the request year"""
        year = self.start_date.year
        try:
            return EmployeeVacationBalance.objects.get(
                employee=self.employee,
                year=year
            )
        except EmployeeVacationBalance.DoesNotExist:
            return None
    
    def get_conflicting_requests(self):
        """Get conflicting vacation requests for team members"""
        # Get team members (same department or same line manager)
        team_members = Employee.objects.filter(
            models.Q(department=self.employee.department) | 
            models.Q(line_manager=self.employee.line_manager),
            status__affects_headcount=True,
            is_deleted=False
        ).exclude(id=self.employee.id) if self.employee.department or self.employee.line_manager else Employee.objects.none()
        
        # Find overlapping requests
        return VacationRequest.objects.filter(
            employee__in=team_members,
            status__in=['APPROVED', 'PENDING_LINE_MANAGER', 'PENDING_HR', 'SCHEDULED'],
            start_date__lte=self.end_date,
            end_date__gte=self.start_date,
            is_deleted=False
        ).exclude(id=self.id if self.id else None)
    
    def get_conflicting_schedules(self):
        """Get conflicting vacation schedules for team members"""
        # Get team members (same department or same line manager)
        team_members = Employee.objects.filter(
            models.Q(department=self.employee.department) | 
            models.Q(line_manager=self.employee.line_manager),
            status__affects_headcount=True,
            is_deleted=False
        ).exclude(id=self.employee.id) if self.employee.department or self.employee.line_manager else Employee.objects.none()
        
        # Find overlapping schedules
        return VacationSchedule.objects.filter(
            employee__in=team_members,
            status='SCHEDULED',
            start_date__lte=self.end_date,
            end_date__gte=self.start_date,
            is_deleted=False
        )

class VacationActivity(models.Model):
    """Track vacation request activities"""
    
    ACTIVITY_TYPES = [
        ('CREATED', 'Request Created'),
        ('SUBMITTED', 'Request Submitted'),
        ('APPROVED_LINE_MANAGER', 'Approved by Line Manager'),
        ('REJECTED_LINE_MANAGER', 'Rejected by Line Manager'),
        ('APPROVED_HR', 'Approved by HR'),
        ('REJECTED_HR', 'Rejected by HR'),
        ('EDITED', 'Request Edited'),
        ('CANCELLED', 'Request Cancelled'),
        ('REGISTERED', 'Vacation Registered'),
        ('SCHEDULE_CREATED', 'Schedule Created'),
        ('SCHEDULE_EDITED', 'Schedule Edited'),
    ]
    
    vacation_request = models.ForeignKey(
        VacationRequest,
        on_delete=models.CASCADE,
        related_name='activities',
        null=True,
        blank=True
    )
    vacation_schedule = models.ForeignKey(
        'VacationSchedule',
        on_delete=models.CASCADE,
        related_name='activities',
        null=True,
        blank=True
    )
    activity_type = models.CharField(max_length=30, choices=ACTIVITY_TYPES)
    description = models.TextField()
    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Vacation Activity"
        verbose_name_plural = "Vacation Activities"
    
    def __str__(self):
        if self.vacation_request:
            return f"{self.vacation_request.request_id} - {self.activity_type}"
        elif self.vacation_schedule:
            return f"Schedule {self.vacation_schedule.id} - {self.activity_type}"
        return f"{self.activity_type}"

class VacationSchedule(SoftDeleteModel):
    """Scheduled vacation entries (for planning purposes)"""
    
    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name='vacation_schedules'
    )
    vacation_type = models.ForeignKey(VacationType, on_delete=models.PROTECT)
    start_date = models.DateField()
    end_date = models.DateField()
    return_date = models.DateField(editable=False)  # Auto-calculated
    number_of_days = models.DecimalField(max_digits=5, decimal_places=1)
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=[('SCHEDULED', 'Scheduled'), ('REGISTERED', 'Registered')],
        default='SCHEDULED'
    )
    
    # Edit tracking
    edit_count = models.PositiveIntegerField(default=0)
    last_edited_at = models.DateTimeField(null=True, blank=True)
    last_edited_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='schedule_edits'
    )
    
    # Additional information
    comment = models.TextField(blank=True)
    
    # Metadata
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        ordering = ['start_date']
        verbose_name = "Vacation Schedule"
        verbose_name_plural = "Vacation Schedules"
    
    def __str__(self):
        return f"{self.employee.full_name} - {self.start_date} to {self.end_date}"
    
    def can_edit(self):
        """Check if schedule can be edited"""
        settings = VacationSetting.get_active_settings()
        max_edits = settings.max_schedule_edits if settings else 3
        return self.edit_count < max_edits and self.status == 'SCHEDULED'
    
    def save(self, *args, **kwargs):
        # Calculate number of days and return date
        settings = VacationSetting.get_active_settings()
        if settings:
            self.number_of_days = settings.calculate_working_days(
                self.start_date, 
                self.end_date
            )
            self.return_date = settings.calculate_return_date(self.end_date)
        else:
            self.number_of_days = (self.end_date - self.start_date).days + 1
            self.return_date = self.end_date + timedelta(days=1)
        
        super().save(*args, **kwargs)
        
        # Update employee balance when saving schedule
        if self.status == 'SCHEDULED':
            balance = self.get_employee_balance()
            if balance:
                # Calculate if we need to update scheduled days
                old_instance = VacationSchedule.objects.filter(id=self.id).first() if self.id else None
                if old_instance:
                    # Update: unreserve old days and reserve new days
                    difference = self.number_of_days - old_instance.number_of_days
                    if difference != 0:
                        if difference > 0:
                            balance.reserve_days(difference)
                        else:
                            balance.unreserve_days(abs(difference))
                else:
                    # New schedule: reserve days
                    balance.reserve_days(self.number_of_days)
    
    def get_employee_balance(self):
        """Get employee's vacation balance for the schedule year"""
        year = self.start_date.year
        try:
            return EmployeeVacationBalance.objects.get(
                employee=self.employee,
                year=year
            )
        except EmployeeVacationBalance.DoesNotExist:
            return None
    
    def get_conflicting_schedules(self):
        """Get conflicting vacation schedules for team members"""
        # Get team members (same department or same line manager)
        team_members = Employee.objects.filter(
            models.Q(department=self.employee.department) | 
            models.Q(line_manager=self.employee.line_manager),
            status__affects_headcount=True,
            is_deleted=False
        ).exclude(id=self.employee.id) if self.employee.department or self.employee.line_manager else Employee.objects.none()
        
        # Find overlapping schedules
        return VacationSchedule.objects.filter(
            employee__in=team_members,
            status='SCHEDULED',
            start_date__lte=self.end_date,
            end_date__gte=self.start_date,
            is_deleted=False
        ).exclude(id=self.id if self.id else None)