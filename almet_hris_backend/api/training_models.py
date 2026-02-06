# api/training_models.py
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from .models import Employee, SoftDeleteModel



# api/training_request_models.py
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from .models import Employee, SoftDeleteModel


class TrainingRequest(SoftDeleteModel):
    """Training Request Model with approval workflow"""
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending Manager Approval'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('COMPLETED', 'Completed'),
    ]
    
    # Request ID (Auto-generated)
    request_id = models.CharField(max_length=50, unique=True, editable=False)
    
    # Requester Information
    requester = models.ForeignKey(
        Employee, 
        on_delete=models.CASCADE, 
        related_name='training_requests_made'
    )
    
    # Training Program Details
    training_title = models.CharField(max_length=300)
    purpose_justification = models.TextField(
        help_text="Explain why this training is needed"
    )
    training_provider = models.CharField(
        max_length=200, 
        blank=True,
        help_text="Training provider/organization (if known)"
    )
    preferred_dates_start = models.DateField(
        null=True, 
        blank=True,
        help_text="Preferred start date"
    )
    preferred_dates_end = models.DateField(
        null=True, 
        blank=True,
        help_text="Preferred end date"
    )
    duration = models.CharField(
        max_length=100,
        help_text="e.g., '3 days', '2 weeks', '1 month'"
    )
    location = models.CharField(
        max_length=200,
        help_text="Training location (city, online, etc.)"
    )
    estimated_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Estimated cost in currency"
    )
    
    # Learning Objectives
    learning_objectives = models.TextField(
        help_text="What will participants learn?"
    )
    
    # Expected Benefits
    expected_benefits = models.TextField(
        help_text="How will this training benefit the organization?"
    )
    
    # Status & Approval
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING'
    )
    
    # Manager Approval
    manager = models.ForeignKey(
        Employee,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='training_requests_to_approve',
        help_text="Manager who will approve this request (line_manager)"
    )
    manager_comments = models.TextField(
        blank=True,
        help_text="Manager's comments on the request"
    )
    approved_rejected_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date when manager/admin approved/rejected"
    )
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_training_requests',
        help_text="User who approved/rejected (manager or admin)"
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='training_requests_created'
    )
    
    def save(self, *args, **kwargs):
        if not self.request_id:
            # Auto-generate request ID
            last_request = TrainingRequest.objects.all().order_by('-id').first()
            if last_request and last_request.request_id:
                try:
                    last_num = int(last_request.request_id.replace('TRQ', ''))
                    new_num = last_num + 1
                except:
                    new_num = 1
            else:
                new_num = 1
            self.request_id = f'TRQ{new_num:04d}'
        
        super().save(*args, **kwargs)
    
    def approve(self, user, comments=''):
        """Approve training request (Manager or Admin)"""
        if self.status != 'PENDING':
            raise ValueError("Request is not pending approval")
        
        self.status = 'APPROVED'
        self.manager_comments = comments
        self.approved_rejected_date = timezone.now()
        self.approved_by = user
        self.save()
        
        # Send notification to requester
        self._send_requester_notification('approved')
        
        # Send notification to HR
        self._send_hr_notification()
        
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Training request approved: {self.request_id}")
    
    def reject(self, user, comments=''):
        """Reject training request (Manager or Admin)"""
        if self.status != 'PENDING':
            raise ValueError("Request is not pending approval")
        
        self.status = 'REJECTED'
        self.manager_comments = comments
        self.approved_rejected_date = timezone.now()
        self.approved_by = user
        self.save()
        
        # Send notification to requester
        self._send_requester_notification('rejected')
        
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Training request rejected: {self.request_id}")
    
    def _send_requester_notification(self, notification_type):
        """Send notification to requester"""
        from .system_email_service import system_email_service
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            if not self.requester.email:
                return
            
            if notification_type == 'approved':
                subject = f"Training Request Approved - {self.training_title}"
                body = f"""
                <html>
                <body style="font-family: Arial, sans-serif;">
                    <h2 style="color: #10B981;">Training Request Approved ✅</h2>
                    
                    <p>Dear {self.requester.first_name},</p>
                    
                    <p>Your training request has been approved!</p>
                    
                    <div style="background-color: #D1FAE5; padding: 15px; border-radius: 5px; margin: 15px 0; border-left: 4px solid #10B981;">
                        <p><strong>Request ID:</strong> {self.request_id}</p>
                        <p><strong>Training:</strong> {self.training_title}</p>
                        <p><strong>Location:</strong> {self.location}</p>
                        <p><strong>Duration:</strong> {self.duration}</p>
                        <p><strong>Estimated Cost:</strong> ${self.estimated_cost}</p>
                    </div>
                    
                    {f'<p><strong>Comments:</strong><br>{self.manager_comments}</p>' if self.manager_comments else ''}
                    
                    <p>HR will contact you regarding the next steps.</p>
                </body>
                </html>
                """
            else:  # rejected
                subject = f"Training Request Not Approved - {self.training_title}"
                body = f"""
                <html>
                <body style="font-family: Arial, sans-serif;">
                    <h2 style="color: #EF4444;">Training Request Not Approved ❌</h2>
                    
                    <p>Dear {self.requester.first_name},</p>
                    
                    <p>Unfortunately, your training request was not approved.</p>
                    
                    <div style="background-color: #FEE2E2; padding: 15px; border-radius: 5px; margin: 15px 0; border-left: 4px solid #EF4444;">
                        <p><strong>Request ID:</strong> {self.request_id}</p>
                        <p><strong>Training:</strong> {self.training_title}</p>
                    </div>
                    
                    {f'<p><strong>Reason:</strong><br>{self.manager_comments}</p>' if self.manager_comments else ''}
                    
                    <p>Please contact your manager for more information.</p>
                </body>
                </html>
                """
            
            system_email_service.send_email_as_system(
                from_email="myalmet@almettrading.com",
                to_email=self.requester.email,
                subject=subject,
                body_html=body
            )
        except Exception as e:
            logger.error(f"Error sending requester notification: {e}")
    
    def _send_hr_notification(self):
        """Send notification to HR when request is approved"""
        from .system_email_service import system_email_service
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            # Get all HR/Admin users
            from .role_models import EmployeeRole
            hr_roles = EmployeeRole.objects.filter(
                role__name__icontains='Admin',
                role__is_active=True,
                is_active=True,
                employee__is_deleted=False
            ).select_related('employee')
            
            hr_emails = [role.employee.email for role in hr_roles if role.employee.email]
            
            if not hr_emails:
                logger.warning("No HR emails found for training request notification")
                return
            
            subject = f"Training Request Approved - {self.requester.full_name}"
            
            body = f"""
            <html>
            <body style="font-family: Arial, sans-serif;">
                <h2 style="color: #3B82F6;">Training Request Approved - Action Required</h2>
                
                <p>Dear HR Team,</p>
                
                <p>A training request has been approved and requires your attention:</p>
                
                <div style="background-color: #DBEAFE; padding: 15px; border-radius: 5px; margin: 15px 0; border-left: 4px solid #3B82F6;">
                    <p><strong>Request ID:</strong> {self.request_id}</p>
                    <p><strong>Employee:</strong> {self.requester.full_name} ({self.requester.employee_id})</p>
                    <p><strong>Position:</strong> {self.requester.job_title}</p>
                    <p><strong>Department:</strong> {self.requester.department.name}</p>
                    <p><strong>Training:</strong> {self.training_title}</p>
                    <p><strong>Provider:</strong> {self.training_provider or 'Not specified'}</p>
                    <p><strong>Location:</strong> {self.location}</p>
                    <p><strong>Duration:</strong> {self.duration}</p>
                    <p><strong>Estimated Cost:</strong> ${self.estimated_cost}</p>
                </div>
                
                <h3>Training Details:</h3>
                <p><strong>Learning Objectives:</strong><br>{self.learning_objectives}</p>
                <p><strong>Expected Benefits:</strong><br>{self.expected_benefits}</p>
                
                {f'<p><strong>Manager Comments:</strong><br>{self.manager_comments}</p>' if self.manager_comments else ''}
                
                <p>Please proceed with arranging this training.</p>
            </body>
            </html>
            """
            
            system_email_service.send_email_as_system(
                from_email="myalmet@almettrading.com",
                to_email=hr_emails,
                subject=subject,
                body_html=body
            )
            
            logger.info(f"HR notification sent for training request: {self.request_id}")
            
        except Exception as e:
            logger.error(f"Error sending HR notification: {e}")
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Training Request'
        verbose_name_plural = 'Training Requests'
    
    def __str__(self):
        return f"{self.request_id} - {self.training_title}"


class TrainingRequestParticipant(SoftDeleteModel):
    """Training Request Participants - Only managers can add participants"""
    
    training_request = models.ForeignKey(
        TrainingRequest,
        on_delete=models.CASCADE,
        related_name='participants'
    )
    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE
    )
    
    # Metadata
    added_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True
    )
    added_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['training_request', 'employee']
        verbose_name = 'Training Request Participant'
        verbose_name_plural = 'Training Request Participants'
    
    def __str__(self):
        return f"{self.training_request.request_id} - {self.employee.full_name}"

class Training(SoftDeleteModel):
    """Əsas training modeli"""
    
    
    
    # Basic Information
    training_id = models.CharField(max_length=50, unique=True, editable=False)
    title = models.CharField(max_length=200)
    description = models.TextField()

    

    

    is_active = models.BooleanField(default=True)
    
    # Filters - Business Structure
    business_functions = models.ManyToManyField(
        'BusinessFunction', 
        blank=True,
        help_text="Specific business functions for this training"
    )
    departments = models.ManyToManyField(
        'Department', 
        blank=True,
        help_text="Specific departments for this training"
    )
    position_groups = models.ManyToManyField(
        'PositionGroup', 
        blank=True,
        help_text="Specific position groups for this training"
    )
    
    # Completion Settings
    requires_completion = models.BooleanField(default=False)
    completion_deadline_days = models.IntegerField(
        null=True, 
        blank=True,
        help_text="Days after assignment to complete"
    )
    
    # Metadata
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_trainings')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def save(self, *args, **kwargs):
        if not self.training_id:
            # Auto-generate training ID
            last_training = Training.objects.all().order_by('-id').first()
            if last_training and last_training.training_id:
                try:
                    last_num = int(last_training.training_id.replace('TRN', ''))
                    new_num = last_num + 1
                except:
                    new_num = 1
            else:
                new_num = 1
            self.training_id = f'TRN{new_num:04d}'
        
        super().save(*args, **kwargs)
    
    class Meta:
        ordering = [ '-created_at']
        verbose_name = 'Training'
        verbose_name_plural = 'Trainings'
    
    def __str__(self):
        return f"{self.training_id} - {self.title}"


class TrainingMaterial(SoftDeleteModel):
    """Training materials (PDF, video, etc.)"""
    
    training = models.ForeignKey(
        Training, 
        on_delete=models.CASCADE, 
        related_name='materials'
    )
    
    # File upload
    file = models.FileField(
        upload_to='training_materials/%Y/%m/',
        null=True,
        blank=True,
        help_text="Upload file for PDF, Video, etc."
    )
    
    # Metadata
    file_size = models.BigIntegerField(
        null=True, 
        blank=True, 
        help_text="File size in bytes"
    )
    
    uploaded_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['training', 'created_at']
        verbose_name = 'Training Material'
        verbose_name_plural = 'Training Materials'
    
    def __str__(self):
        filename = self.file.name.split('/')[-1] if self.file else 'No file'
        return f"{self.training.training_id} - {filename}"
class TrainingAssignment(SoftDeleteModel):
    """Training assignment to employees"""
    
    STATUS_CHOICES = [
        ('ASSIGNED', 'Assigned'),
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
        ('OVERDUE', 'Overdue'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    # Assignment Details
    training = models.ForeignKey(Training, on_delete=models.CASCADE, related_name='assignments')
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='training_assignments')
    
    # Status & Dates
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ASSIGNED')
    assigned_date = models.DateTimeField(auto_now_add=True)
    due_date = models.DateField(null=True, blank=True)
    started_date = models.DateTimeField(null=True, blank=True)
    completed_date = models.DateTimeField(null=True, blank=True)
    
    # Progress Tracking
    progress_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text="Completion progress 0-100"
    )
    materials_completed = models.ManyToManyField(
        TrainingMaterial,
        blank=True,
        help_text="Materials that have been viewed/completed"
    )
    
    # Completion Details
    completion_notes = models.TextField(blank=True)
    completion_certificate_generated = models.BooleanField(default=False)
    
    # Assignment Metadata
    assigned_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True,
        related_name='assigned_trainings'
    )
    is_mandatory = models.BooleanField(
        default=False,
        help_text="Is this assignment mandatory for the employee"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-assigned_date']
        unique_together = ['training', 'employee']
        verbose_name = 'Training Assignment'
        verbose_name_plural = 'Training Assignments'
    
    def __str__(self):
        return f"{self.employee.full_name} - {self.training.title}"
    
    def calculate_progress(self):
        """Calculate progress based on completed materials"""
        if self.status == 'COMPLETED':
            return 100.0
        
        # Remove is_mandatory filter
        total_required = self.training.materials.filter(is_deleted=False).count()
        if total_required == 0:
            return 0.0
        
        # Remove is_mandatory filter
        completed = self.materials_completed.filter(is_deleted=False).count()
        progress = (completed / total_required) * 100
        
        self.progress_percentage = round(progress, 2)
        self.save(update_fields=['progress_percentage'])
        
        return self.progress_percentage
    
    def check_completion(self):
        """Check if training is completed"""
        # Remove is_mandatory filter
        total_required = self.training.materials.filter(is_deleted=False).count()
        completed = self.materials_completed.filter(is_deleted=False).count()
        
        if total_required > 0 and completed >= total_required:
            self.status = 'COMPLETED'
            self.completed_date = timezone.now()
            self.progress_percentage = 100
            self.save()
            return True
        
        return False
    def is_overdue(self):
        """Check if assignment is overdue"""
        if self.status not in ['COMPLETED', 'CANCELLED'] and self.due_date:
            return timezone.now().date() > self.due_date
        return False

class TrainingActivity(models.Model):
    """Training activity log"""
    
    ACTIVITY_TYPES = [
        ('ASSIGNED', 'Training Assigned'),
        ('STARTED', 'Training Started'),
        ('MATERIAL_VIEWED', 'Material Viewed'),
        ('PROGRESS_UPDATED', 'Progress Updated'),
        ('COMPLETED', 'Training Completed'),
        ('CANCELLED', 'Training Cancelled'),
    ]
    
    assignment = models.ForeignKey(
        TrainingAssignment, 
        on_delete=models.CASCADE, 
        related_name='activities'
    )
    activity_type = models.CharField(max_length=30, choices=ACTIVITY_TYPES)
    description = models.TextField()
    
    material = models.ForeignKey(
        TrainingMaterial,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Related material if applicable"
    )
    
    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Training Activity'
        verbose_name_plural = 'Training Activities'
    
    def __str__(self):
        return f"{self.assignment.employee.full_name} - {self.activity_type}"