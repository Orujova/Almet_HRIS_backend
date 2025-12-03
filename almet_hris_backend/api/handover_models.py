# api/handover_models.py
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.exceptions import ValidationError
from .models import Employee, SoftDeleteModel
from datetime import date, timedelta
import os

class HandoverType(SoftDeleteModel):
    """Handover növləri - Məzuniyyət, Ezamiyyət, İstefa, Digər"""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='handover_type_updates')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']
        verbose_name = "Handover Type"
        verbose_name_plural = "Handover Types"
        db_table = 'handover_types'


class HandoverRequest(SoftDeleteModel):
    """Əsas Handover Request modeli"""
    
    STATUS_CHOICES = [
        ('CREATED', 'Created'),
        ('SIGNED_BY_HANDING_OVER', 'Signed by Handing Over'),
        ('SIGNED_BY_TAKING_OVER', 'Signed by Taking Over'),
        ('APPROVED_BY_LINE_MANAGER', 'Approved by Line Manager'),
        ('REJECTED', 'Rejected'),
        ('NEED_CLARIFICATION', 'Need Clarification'),
        ('RESUBMITTED', 'Resubmitted'),
        ('TAKEN_OVER', 'Taken Over'),
        ('TAKEN_BACK', 'Taken Back'),
    ]
    
    # Request identification
    request_id = models.CharField(max_length=20, unique=True, editable=False)
    
    # Employees
    handing_over_employee = models.ForeignKey(
        Employee, 
        on_delete=models.CASCADE, 
        related_name='handovers_given'
    )
    taking_over_employee = models.ForeignKey(
        Employee, 
        on_delete=models.CASCADE, 
        related_name='handovers_received'
    )
    
    # Handover details
    handover_type = models.ForeignKey(HandoverType, on_delete=models.PROTECT)
    start_date = models.DateField()
    end_date = models.DateField()
    
    # Contacts and important info
    contacts = models.TextField(blank=True, help_text="Əlaqəli şəxslər")
    access_info = models.TextField(blank=True, help_text="Giriş məlumatları")
    documents_info = models.TextField(blank=True, help_text="Sənədlər və fayllar")
    open_issues = models.TextField(blank=True, help_text="Açıq məsələlər")
    notes = models.TextField(blank=True, help_text="Əlavə qeydlər")
    
    # Approvers
    line_manager = models.ForeignKey(
        Employee, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='handovers_to_approve'
    )
    
    # Status
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='CREATED')
    
    # Handing Over signatures
    ho_signed = models.BooleanField(default=False)
    ho_signed_date = models.DateTimeField(null=True, blank=True)
    ho_signed_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='ho_signatures'
    )
    
    # Taking Over signatures
    to_signed = models.BooleanField(default=False)
    to_signed_date = models.DateTimeField(null=True, blank=True)
    to_signed_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='to_signatures'
    )
    
    # Line Manager Approval
    lm_approved = models.BooleanField(default=False)
    lm_approved_date = models.DateTimeField(null=True, blank=True)
    lm_approved_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='lm_handover_approvals'
    )
    lm_comment = models.TextField(blank=True)
    lm_clarification_comment = models.TextField(blank=True)
    
    # Rejection
    rejected_at = models.DateTimeField(null=True, blank=True)
    rejected_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='handover_rejections'
    )
    rejection_reason = models.TextField(blank=True)
    
    # Takeover
    taken_over = models.BooleanField(default=False)
    taken_over_date = models.DateTimeField(null=True, blank=True)
    taken_back = models.BooleanField(default=False)
    taken_back_date = models.DateTimeField(null=True, blank=True)
    
    # System fields
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Handover Request"
        verbose_name_plural = "Handover Requests"
        db_table = 'handover_requests'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.request_id} - {self.handing_over_employee.full_name} → {self.taking_over_employee.full_name}"
    
    def clean(self):
        """Validation"""
        if self.start_date and self.end_date and self.start_date >= self.end_date:
            raise ValidationError("End date must be after start date")
        
        if self.handing_over_employee == self.taking_over_employee:
            raise ValidationError("Təhvil verən və təhvil alan eyni şəxs ola bilməz")
    
    def save(self, *args, **kwargs):
        # Generate request ID
        if not self.request_id:
            year = timezone.now().year
            last = HandoverRequest.objects.filter(
                request_id__startswith=f'HO{year}'
            ).order_by('-request_id').first()
            num = int(last.request_id[6:]) + 1 if last else 1
            self.request_id = f'HO{year}{num:04d}'
        
        # Auto-assign line manager
        if not self.line_manager and self.handing_over_employee.line_manager:
            # Əgər requester özü manager-dirsə, LM-i atla
            requester_emp = getattr(self.created_by, 'employee', None) if self.created_by else None
            if not (requester_emp and self.handing_over_employee.line_manager == requester_emp):
                self.line_manager = self.handing_over_employee.line_manager
        
        self.clean()
        super().save(*args, **kwargs)
    
    def sign_by_handing_over(self, user):
        """Təhvil verən imzalayır"""
        self.ho_signed = True
        self.ho_signed_date = timezone.now()
        self.ho_signed_by = user
        self.status = 'SIGNED_BY_HANDING_OVER'
        self.save()
        
        # Log activity
        self.log_activity(
            user=user,
            action='Təhvil verən tərəfindən imzalandı',
            comment='Handover imzalandı.'
        )
    
    def sign_by_taking_over(self, user):
        """Təhvil alan imzalayır"""
        if not self.ho_signed:
            raise ValidationError("Əvvəlcə təhvil verən imzalamalıdır")
        
        self.to_signed = True
        self.to_signed_date = timezone.now()
        self.to_signed_by = user
        self.status = 'SIGNED_BY_TAKING_OVER'
        self.save()
        
        # Log activity
        self.log_activity(
            user=user,
            action='Təhvil alan tərəfindən imzalandı',
            comment='Təhvil alan imzalandı.'
        )
    
    def approve_by_line_manager(self, user, comment=''):
        """Line Manager təsdiq edir"""
        if not self.to_signed:
            raise ValidationError("Əvvəlcə hər iki tərəf imzalamalıdır")
        
        self.lm_approved = True
        self.lm_approved_date = timezone.now()
        self.lm_approved_by = user
        self.lm_comment = comment
        self.status = 'APPROVED_BY_LINE_MANAGER'
        self.save()
        
        # Log activity
        self.log_activity(
            user=user,
            action='Line Manager tərəfindən təsdiqləndi',
            comment=comment or 'Təsdiq edildi.'
        )
    
    def reject_by_line_manager(self, user, reason):
        """Line Manager reject edir"""
        if not reason:
            raise ValidationError("Rədd səbəbi qeyd edilməlidir")
        
        self.status = 'REJECTED'
        self.rejected_at = timezone.now()
        self.rejected_by = user
        self.rejection_reason = reason
        self.save()
        
        # Log activity
        self.log_activity(
            user=user,
            action='Rədd edildi',
            comment=reason
        )
    
    def request_clarification(self, user, clarification_comment):
        """Line Manager aydınlaşdırma tələb edir"""
        if not clarification_comment:
            raise ValidationError("Aydınlaşdırma mətni qeyd edilməlidir")
        
        self.status = 'NEED_CLARIFICATION'
        self.lm_clarification_comment = clarification_comment
        self.save()
        
        # Log activity
        self.log_activity(
            user=user,
            action='Aydınlaşdırma tələb edildi',
            comment=clarification_comment
        )
    
    def resubmit_after_clarification(self, user, response_comment):
        """Təhvil verən aydınlaşdırmadan sonra yenidən göndərir"""
        if self.status != 'NEED_CLARIFICATION':
            raise ValidationError("Status 'Need Clarification' olmalıdır")
        
        if not response_comment:
            raise ValidationError("Aydınlaşdırmaya cavab qeyd edilməlidir")
        
        self.status = 'SIGNED_BY_TAKING_OVER'  # LM-ə yenidən göndər
        self.lm_clarification_comment = ''  # Clear old clarification
        self.save()
        
        # Log activity
        self.log_activity(
            user=user,
            action='Aydınlaşdırmadan sonra yenidən göndərildi',
            comment=response_comment
        )
    
    def takeover(self, user, comment=''):
        """Təhvil alan təhvil alır (Approved statusundan sonra)"""
        if self.status != 'APPROVED_BY_LINE_MANAGER':
            raise ValidationError("Status 'Approved by Line Manager' olmalıdır")
        
        self.taken_over = True
        self.taken_over_date = timezone.now()
        self.status = 'TAKEN_OVER'
        self.save()
        
        # Log activity
        self.log_activity(
            user=user,
            action='Handover təhvil alındı',
            comment=comment or 'Təhvil alındı.'
        )
    
    def takeback(self, user, comment=''):
        """Təhvil verən geri götürür"""
        if self.status != 'TAKEN_OVER':
            raise ValidationError("Status 'Taken Over' olmalıdır")
        
        self.taken_back = True
        self.taken_back_date = timezone.now()
        self.status = 'TAKEN_BACK'
        self.save()
        
        # Log activity
        self.log_activity(
            user=user,
            action='Handover geri götürüldü',
            comment=comment or 'Geri götürüldü.'
        )
    
    def log_activity(self, user, action, comment=''):
        """Activity log-a əlavə et"""
        HandoverActivity.objects.create(
            handover=self,
            actor=user,
            action=action,
            comment=comment,
            status=self.status
        )


class HandoverTask(SoftDeleteModel):
    """Handover task-ları"""
    
    TASK_STATUS_CHOICES = [
        ('NOT_STARTED', 'Başlanmayıb'),
        ('IN_PROGRESS', 'Davam edir'),
        ('COMPLETED', 'Tamamlanıb'),
        ('CANCELED', 'Ləğv edilib'),
        ('POSTPONED', 'Təxirə salınıb'),
    ]
    
    handover = models.ForeignKey(HandoverRequest, on_delete=models.CASCADE, related_name='tasks')
    description = models.TextField()
    current_status = models.CharField(max_length=20, choices=TASK_STATUS_CHOICES, default='NOT_STARTED')
    initial_comment = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.handover.request_id} - {self.description[:50]}"
    
    def update_status(self, user, new_status, comment=''):
        """Task statusunu yenilə"""
        old_status = self.current_status
        self.current_status = new_status
        self.save()
        
        # Log activity
        TaskActivity.objects.create(
            task=self,
            actor=user,
            action='Status Yeniləndi',
            old_status=old_status,
            new_status=new_status,
            comment=comment
        )
    
    class Meta:
        ordering = ['handover', 'order']
        verbose_name = "Handover Task"
        verbose_name_plural = "Handover Tasks"
        db_table = 'handover_tasks'


class TaskActivity(models.Model):
    """Task activity log"""
    task = models.ForeignKey(HandoverTask, on_delete=models.CASCADE, related_name='activity_log')
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=100)
    old_status = models.CharField(max_length=20, blank=True)
    new_status = models.CharField(max_length=20, blank=True)
    comment = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['timestamp']
        verbose_name = "Task Activity"
        verbose_name_plural = "Task Activities"
        db_table = 'task_activities'
    
    def __str__(self):
        return f"{self.task.handover.request_id} - {self.action} - {self.timestamp}"


class HandoverImportantDate(SoftDeleteModel):
    """Mühüm tarixlər"""
    handover = models.ForeignKey(HandoverRequest, on_delete=models.CASCADE, related_name='important_dates')
    date = models.DateField()
    description = models.CharField(max_length=500)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['handover', 'date']
        verbose_name = "Important Date"
        verbose_name_plural = "Important Dates"
        db_table = 'handover_important_dates'
    
    def __str__(self):
        return f"{self.handover.request_id} - {self.date}: {self.description}"


class HandoverActivity(models.Model):
    """Handover activity log"""
    handover = models.ForeignKey(HandoverRequest, on_delete=models.CASCADE, related_name='activity_log')
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=200)
    comment = models.TextField(blank=True)
    status = models.CharField(max_length=30, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['timestamp']
        verbose_name = "Handover Activity"
        verbose_name_plural = "Handover Activities"
        db_table = 'handover_activities'
    
    def __str__(self):
        return f"{self.handover.request_id} - {self.action} - {self.timestamp}"


def handover_attachment_path(instance, filename):
    """Generate upload path for handover attachments"""
    year = instance.handover.created_at.year
    request_id = instance.handover.request_id
    return f'handovers/{year}/{request_id}/{filename}'


class HandoverAttachment(SoftDeleteModel):
    """File attachments for handover requests"""
    handover = models.ForeignKey(
        HandoverRequest, 
        on_delete=models.CASCADE, 
        related_name='attachments'
    )
    file = models.FileField(upload_to=handover_attachment_path)
    original_filename = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField(help_text="File size in bytes")
    file_type = models.CharField(max_length=100, blank=True)
    
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Handover Attachment"
        verbose_name_plural = "Handover Attachments"
        db_table = 'handover_attachments'
        ordering = ['-uploaded_at']
    
    def __str__(self):
        return f"{self.handover.request_id} - {self.original_filename}"
    
    @property
    def file_size_display(self):
        """Human readable file size"""
        size = self.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"
    
    def delete(self, *args, **kwargs):
        """Delete file from storage when model is deleted"""
        if self.file:
            if os.path.isfile(self.file.path):
                os.remove(self.file.path)
        super().delete(*args, **kwargs)