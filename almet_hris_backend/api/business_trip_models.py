# api/business_trip_models.py
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import MinValueValidator
from .models import Employee, SoftDeleteModel
import uuid

class TravelType(SoftDeleteModel):
    """Travel type configuration (Domestic, Overseas, etc.)"""
    name = models.CharField(max_length=50, unique=True)
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']
        verbose_name = "Travel Type"
        verbose_name_plural = "Travel Types"

class TransportType(SoftDeleteModel):
    """Transport type configuration (Taxi, Train, Airplane, etc.)"""
    name = models.CharField(max_length=50, unique=True)
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']
        verbose_name = "Transport Type"
        verbose_name_plural = "Transport Types"

class TripPurpose(SoftDeleteModel):
    """Trip purpose configuration (Conference, Meeting, Training, etc.)"""
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=30, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']
        verbose_name = "Trip Purpose"
        verbose_name_plural = "Trip Purposes"

class ApprovalWorkflow(SoftDeleteModel):
    """Approval workflow configuration"""
    APPROVAL_STEP_CHOICES = [
        ('LINE_MANAGER', 'Line Manager'),
        ('FINANCE_PAYROLL', 'Finance/Payroll'),
        ('HR', 'HR'),
        ('CHRO', 'CHRO'),
        ('CEO', 'CEO'),
        ('CUSTOM', 'Custom')
    ]

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    
    # Workflow conditions
    applies_to_domestic = models.BooleanField(default=True)
    applies_to_overseas = models.BooleanField(default=True)
    min_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    max_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']
        verbose_name = "Approval Workflow"
        verbose_name_plural = "Approval Workflows"

class ApprovalStep(SoftDeleteModel):
    """Individual steps in approval workflow"""
    workflow = models.ForeignKey(ApprovalWorkflow, on_delete=models.CASCADE, related_name='steps')
    step_type = models.CharField(max_length=20, choices=ApprovalWorkflow.APPROVAL_STEP_CHOICES)
    step_order = models.PositiveIntegerField()
    step_name = models.CharField(max_length=100)
    is_required = models.BooleanField(default=True)
    can_edit_amount = models.BooleanField(default=False)
    requires_amount_entry = models.BooleanField(default=False)
    
    # Auto-assignment rules
    auto_assign_to_line_manager = models.BooleanField(default=False)
    specific_approver = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.workflow.name} - Step {self.step_order}: {self.step_name}"

    class Meta:
        ordering = ['workflow', 'step_order']
        unique_together = ['workflow', 'step_order']
        verbose_name = "Approval Step"
        verbose_name_plural = "Approval Steps"

class BusinessTripRequest(SoftDeleteModel):
    """Main business trip request model"""
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('SUBMITTED', 'Submitted'),
        ('IN_PROGRESS', 'In Progress'),
        ('PENDING_LINE_MANAGER', 'Pending Line Manager'),
        ('PENDING_FINANCE', 'Pending Finance/Payroll'),
        ('PENDING_HR', 'Pending HR'),
        ('PENDING_CHRO', 'Pending CHRO'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('CANCELLED', 'Cancelled'),
        ('COMPLETED', 'Completed'),
    ]

    REQUESTER_TYPE_CHOICES = [
        ('FOR_ME', 'For Me'),
        ('FOR_EMPLOYEE', 'For My Employee'),
    ]

    # Request identification
    request_id = models.CharField(max_length=20, unique=True, editable=False)
    
    # Requester information
    requester_type = models.CharField(max_length=15, choices=REQUESTER_TYPE_CHOICES, default='FOR_ME')
    requested_by = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name='trip_requests_made')
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name='trip_requests')
    
    # Travel details
    travel_type = models.ForeignKey(TravelType, on_delete=models.PROTECT)
    transport_type = models.ForeignKey(TransportType, on_delete=models.PROTECT)
    purpose = models.ForeignKey(TripPurpose, on_delete=models.PROTECT)
    
    # Dates
    start_date = models.DateField()
    end_date = models.DateField()
    
    # Status and workflow
    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default='DRAFT')
    workflow = models.ForeignKey(ApprovalWorkflow, on_delete=models.PROTECT, null=True, blank=True)
    current_step = models.ForeignKey(ApprovalStep, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Financial information
    estimated_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    approved_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Approvers
    line_manager = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True, related_name='trip_requests_as_line_manager')
    finance_approver = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True, related_name='trip_requests_as_finance')
    hr_approver = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True, related_name='trip_requests_as_hr')
    
    # Additional information
    notes = models.TextField(blank=True)
    rejection_reason = models.TextField(blank=True)
    
    # Notification settings
    phone_number = models.CharField(max_length=20, blank=True)  # For SMS notifications
    send_sms_reminders = models.BooleanField(default=True)
    
    # Timestamps
    submitted_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.request_id:
            self.request_id = self.generate_request_id()
        
        # Auto-assign workflow if not set
        if not self.workflow:
            self.workflow = self.get_applicable_workflow()
        
        # Auto-assign line manager if not set and requester_type is FOR_ME
        if self.requester_type == 'FOR_ME' and not self.line_manager:
            self.line_manager = self.employee.line_manager
        
        # Auto-assign phone number from employee if not set
        if not self.phone_number and self.employee.phone:
            self.phone_number = self.employee.phone
        
        super().save(*args, **kwargs)

    def generate_request_id(self):
        """Generate unique request ID"""
        year = timezone.now().year
        month = timezone.now().month
        
        # Get count of requests this month
        count = BusinessTripRequest.objects.filter(
            created_at__year=year,
            created_at__month=month
        ).count() + 1
        
        return f"BT{year}{month:02d}{count:04d}"

    def get_applicable_workflow(self):
        """Get applicable workflow based on travel type and amount"""
        workflows = ApprovalWorkflow.objects.filter(is_active=True)
        
        # Filter by travel type
        if self.travel_type.code == 'DOMESTIC':
            workflows = workflows.filter(applies_to_domestic=True)
        elif self.travel_type.code == 'OVERSEAS':
            workflows = workflows.filter(applies_to_overseas=True)
        
        # Filter by amount if estimated
        if self.estimated_amount:
            workflows = workflows.filter(
                models.Q(min_amount__isnull=True) | models.Q(min_amount__lte=self.estimated_amount),
                models.Q(max_amount__isnull=True) | models.Q(max_amount__gte=self.estimated_amount)
            )
        
        # Return first matching workflow or default
        workflow = workflows.first()
        if not workflow:
            workflow = ApprovalWorkflow.objects.filter(is_default=True, is_active=True).first()
        
        return workflow

    def submit_request(self):
        """Submit the request and start approval workflow"""
        if self.status != 'DRAFT':
            raise ValueError("Only draft requests can be submitted")
        
        self.status = 'SUBMITTED'
        self.submitted_at = timezone.now()
        
        # Start workflow
        if self.workflow:
            first_step = self.workflow.steps.filter(is_active=True).order_by('step_order').first()
            if first_step:
                self.current_step = first_step
                self.status = self.get_status_for_step(first_step)
        
        self.save()

    def get_status_for_step(self, step):
        """Get status based on approval step"""
        status_mapping = {
            'LINE_MANAGER': 'PENDING_LINE_MANAGER',
            'FINANCE_PAYROLL': 'PENDING_FINANCE',
            'HR': 'PENDING_HR',
            'CHRO': 'PENDING_CHRO',
        }
        return status_mapping.get(step.step_type, 'IN_PROGRESS')

    def get_current_approver(self):
        """Get current approver based on current step"""
        if not self.current_step:
            return None
        
        if self.current_step.step_type == 'LINE_MANAGER':
            return self.line_manager
        elif self.current_step.step_type == 'FINANCE_PAYROLL':
            return self.finance_approver
        elif self.current_step.step_type == 'HR':
            return self.hr_approver
        elif self.current_step.specific_approver:
            return self.current_step.specific_approver
        
        return None

    def approve_current_step(self, approver, amount=None, notes=None):
        """Approve current step and move to next"""
        if self.status in ['APPROVED', 'REJECTED', 'CANCELLED']:
            raise ValueError("Request is already finalized")
        
        # Create approval record
        TripApproval.objects.create(
            trip_request=self,
            approval_step=self.current_step,
            approver=approver,
            decision='APPROVED',
            amount=amount,
            notes=notes or ''
        )
        
        # Update approved amount if provided
        if amount is not None:
            self.approved_amount = amount
        
        # Move to next step
        next_step = self.workflow.steps.filter(
            step_order__gt=self.current_step.step_order,
            is_active=True
        ).order_by('step_order').first()
        
        if next_step:
            self.current_step = next_step
            self.status = self.get_status_for_step(next_step)
        else:
            # All steps completed
            self.current_step = None
            self.status = 'APPROVED'
            self.completed_at = timezone.now()
        
        self.save()

    def reject_current_step(self, approver, reason):
        """Reject current step"""
        if self.status in ['APPROVED', 'REJECTED', 'CANCELLED']:
            raise ValueError("Request is already finalized")
        
        # Create approval record
        TripApproval.objects.create(
            trip_request=self,
            approval_step=self.current_step,
            approver=approver,
            decision='REJECTED',
            notes=reason
        )
        
        self.status = 'REJECTED'
        self.rejection_reason = reason
        self.completed_at = timezone.now()
        self.save()

    def get_timeline(self):
        """Get approval timeline for display"""
        timeline = []
        approvals = self.approvals.select_related('approval_step', 'approver').order_by('created_at')
        
        for step in self.workflow.steps.filter(is_active=True).order_by('step_order'):
            approval = approvals.filter(approval_step=step).first()
            timeline.append({
                'step_name': step.step_name,
                'step_type': step.step_type,
                'is_current': self.current_step == step if self.current_step else False,
                'is_completed': approval is not None,
                'approval': approval,
                'approver_name': approval.approver.full_name if approval else None,
                'decision': approval.decision if approval else None,
                'approved_at': approval.created_at if approval else None,
            })
        
        return timeline

    @property
    def duration_days(self):
        """Calculate trip duration in days"""
        if self.start_date and self.end_date:
            return (self.end_date - self.start_date).days + 1
        return 0

    def __str__(self):
        return f"{self.request_id} - {self.employee.full_name} ({self.get_status_display()})"

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Business Trip Request"
        verbose_name_plural = "Business Trip Requests"

class TripSchedule(SoftDeleteModel):
    """Trip schedule/itinerary details"""
    trip_request = models.ForeignKey(BusinessTripRequest, on_delete=models.CASCADE, related_name='schedules')
    date = models.DateField()
    from_location = models.CharField(max_length=200)
    to_location = models.CharField(max_length=200)
    order = models.PositiveIntegerField(default=0)
    notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.trip_request.request_id} - {self.date}: {self.from_location} → {self.to_location}"

    class Meta:
        ordering = ['trip_request', 'date', 'order']
        verbose_name = "Trip Schedule"
        verbose_name_plural = "Trip Schedules"

class TripHotel(SoftDeleteModel):
    """Hotel accommodation details"""
    trip_request = models.ForeignKey(BusinessTripRequest, on_delete=models.CASCADE, related_name='hotels')
    hotel_name = models.CharField(max_length=200)
    check_in_date = models.DateField()
    check_out_date = models.DateField()
    location = models.CharField(max_length=200, blank=True)
    contact_info = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.trip_request.request_id} - {self.hotel_name}"

    @property
    def nights_count(self):
        """Calculate number of nights"""
        if self.check_in_date and self.check_out_date:
            return (self.check_out_date - self.check_in_date).days
        return 0

    class Meta:
        ordering = ['trip_request', 'check_in_date']
        verbose_name = "Trip Hotel"
        verbose_name_plural = "Trip Hotels"

class TripApproval(SoftDeleteModel):
    """Approval records for each step"""
    DECISION_CHOICES = [
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('PENDING', 'Pending'),
    ]

    trip_request = models.ForeignKey(BusinessTripRequest, on_delete=models.CASCADE, related_name='approvals')
    approval_step = models.ForeignKey(ApprovalStep, on_delete=models.PROTECT)
    approver = models.ForeignKey(Employee, on_delete=models.PROTECT)
    decision = models.CharField(max_length=10, choices=DECISION_CHOICES, default='PENDING')
    amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    notes = models.TextField(blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.trip_request.request_id} - {self.approval_step.step_name}: {self.get_decision_display()}"

    class Meta:
        ordering = ['trip_request', 'approval_step__step_order']
        unique_together = ['trip_request', 'approval_step']
        verbose_name = "Trip Approval"
        verbose_name_plural = "Trip Approvals"

class TripNotification(SoftDeleteModel):
    """Notification log for trip requests"""
    NOTIFICATION_TYPE_CHOICES = [
        ('EMAIL', 'Email'),
        ('SMS', 'SMS'),
        ('SYSTEM', 'System Notification'),
    ]

    NOTIFICATION_TEMPLATE_CHOICES = [
        ('TRIP_SUBMITTED', 'Trip Request Submitted'),
        ('APPROVAL_PENDING', 'Approval Pending'),
        ('TRIP_APPROVED', 'Trip Request Approved'),
        ('TRIP_REJECTED', 'Trip Request Rejected'),
        ('TRIP_REMINDER', 'Trip Reminder'),
        ('AMOUNT_UPDATED', 'Trip Amount Updated'),
    ]

    trip_request = models.ForeignKey(BusinessTripRequest, on_delete=models.CASCADE, related_name='notifications')
    recipient = models.ForeignKey(Employee, on_delete=models.CASCADE)
    notification_type = models.CharField(max_length=10, choices=NOTIFICATION_TYPE_CHOICES)
    template = models.CharField(max_length=20, choices=NOTIFICATION_TEMPLATE_CHOICES)
    
    subject = models.CharField(max_length=200)
    message = models.TextField()
    
    # Delivery status
    is_sent = models.BooleanField(default=False)
    sent_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.trip_request.request_id} - {self.get_template_display()} to {self.recipient.full_name}"

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Trip Notification"
        verbose_name_plural = "Trip Notifications"

# Create default data function
def create_default_trip_settings():
    """Create default travel types, transport types, and purposes"""
    
    # Travel Types
    travel_types = [
        ('DOMESTIC', 'Domestic'),
        ('OVERSEAS', 'Overseas'),
    ]
    
    for code, name in travel_types:
        TravelType.objects.get_or_create(
            code=code,
            defaults={'name': name, 'is_active': True}
        )
    
    # Transport Types
    transport_types = [
        ('TAXI', 'Taxi'),
        ('PRIVATE_CAR', 'Private Car'),
        ('CORPORATE_CAR', 'Corporate Car'),
        ('TRAIN', 'Train'),
        ('AIRPLANE', 'Airplane'),
    ]
    
    for code, name in transport_types:
        TransportType.objects.get_or_create(
            code=code,
            defaults={'name': name, 'is_active': True}
        )
    
    # Trip Purposes
    purposes = [
        ('CONFERENCE', 'Conference'),
        ('MEETING', 'Meeting'),
        ('TRAINING', 'Training'),
        ('SITE_VISIT', 'Site Visit'),
        ('CLIENT_VISIT', 'Client Visit'),
        ('OTHER', 'Other'),
    ]
    
    for code, name in purposes:
        TripPurpose.objects.get_or_create(
            code=code,
            defaults={'name': name, 'is_active': True}
        )
    
    # Default Approval Workflow
    workflow, created = ApprovalWorkflow.objects.get_or_create(
        name='Standard Approval Process',
        defaults={
            'description': 'Standard 3-step approval process for business trips',
            'is_active': True,
            'is_default': True,
            'applies_to_domestic': True,
            'applies_to_overseas': True
        }
    )
    
    if created:
        # Create approval steps
        steps = [
            ('LINE_MANAGER', 'Line Manager', 1, False, False),
            ('FINANCE_PAYROLL', 'Finance/Payroll', 2, True, True),
            ('HR', 'HR', 3, False, False),
        ]
        
        for step_type, step_name, order, can_edit_amount, requires_amount in steps:
            ApprovalStep.objects.create(
                workflow=workflow,
                step_type=step_type,
                step_name=step_name,
                step_order=order,
                is_required=True,
                can_edit_amount=can_edit_amount,
                requires_amount_entry=requires_amount
            )