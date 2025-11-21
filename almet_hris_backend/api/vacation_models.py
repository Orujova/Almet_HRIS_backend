# api/vacation_models.py - Enhanced and Fixed

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.exceptions import ValidationError
from datetime import date, timedelta
from .models import Employee, SoftDeleteModel
import uuid

class VacationSetting(SoftDeleteModel):
    """Vacation sistem parametrləri"""
    
    # Production Calendar - qeyri-iş günlərinin siyahısı
    non_working_days = models.JSONField(
        default=list, 
        help_text="Qeyri-iş günləri JSON formatında: [{'date': '2025-01-01', 'name': 'New Year'}, ...]"
    )
    
    # Default HR
    default_hr_representative = models.ForeignKey(
        Employee, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='hr_settings',
        help_text="Default HR nümayəndəsi"
    )
    
    # Settings
    allow_negative_balance = models.BooleanField(
        default=False, 
        help_text="Balans 0 olduqda request yaratmağa icazə ver"
    )
    max_schedule_edits = models.PositiveIntegerField(
        default=3, 
        help_text="Schedule neçə dəfə edit oluna bilər"
    )
    
    # Notifications
    notification_days_before = models.PositiveIntegerField(
        default=7,
        help_text="Məzuniyyət başlamazdan neçə gün əvvəl bildiriş göndər"
    )
    notification_frequency = models.PositiveIntegerField(
        default=2,
        help_text="Bildirişi neçə dəfə göndər"
    )
    
    # System fields
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='vacation_settings_updates')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Vacation Setting"
        verbose_name_plural = "Vacation Settings"
        db_table = 'vacation_settings'
    
    def __str__(self):
        return f"Vacation Settings - Active: {self.is_active}"
    
    @classmethod
    def get_active(cls):
        """Aktiv settingi qaytarır"""
        return cls.objects.filter(is_active=True, is_deleted=False).first()
    
    def clean(self):
        """Validation - yalnız bir aktiv setting ola bilər"""
        if self.is_active:
            existing = VacationSetting.objects.filter(
                is_active=True, 
                is_deleted=False
            ).exclude(pk=self.pk)
            if existing.exists():
                raise ValidationError("Yalnız bir aktiv vacation setting ola bilər")
    
    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
    
    def is_working_day(self, check_date):
        """Verilən tarixi iş günü olub-olmadığını yoxlayır
        
        ✅ Həftəsonu günləri (Saturday, Sunday) də iş günü sayılır
        ❌ Yalnız non_working_days siyahısındakı günlər istisna edilir
        """
        # Non-working days yoxla
        date_str = check_date.strftime('%Y-%m-%d')
        for holiday in self.non_working_days:
            if isinstance(holiday, dict) and holiday.get('date') == date_str:
                return False
            elif isinstance(holiday, str) and holiday == date_str:
                return False
        
        return True  # Həftəsonu da daxil olmaqla bütün günlər iş günüdür
    
    def calculate_working_days(self, start, end):
        """İki tarix arasındakı iş günlərinin sayını hesablayır"""
        if start > end:
            return 0
            
        days = 0
        current = start
        while current <= end:
            if self.is_working_day(current):
                days += 1
            current += timedelta(days=1)
        return days
    
    def calculate_return_date(self, end_date):
        """Məzuniyyət bitdikdən sonra ilk iş gününü hesablayır"""
        ret = end_date + timedelta(days=1)
        while not self.is_working_day(ret):
            ret += timedelta(days=1)
        return ret


class VacationType(SoftDeleteModel):
    """Məzuniyyət növləri - Annual, Sick, Personal"""
    
    name = models.CharField(max_length=100, unique=True, help_text="Məzuniyyət növü adı")
    description = models.TextField(blank=True, help_text="Təsvir")
    
    # System fields
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='vacation_type_updates')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Vacation Type"
        verbose_name_plural = "Vacation Types"
        db_table = 'vacation_types'
        ordering = ['name']
    
    def __str__(self):
        return self.name


class EmployeeVacationBalance(SoftDeleteModel):
    """İşçinin illik vacation balansı"""
    
    employee = models.ForeignKey(
        Employee, 
        on_delete=models.CASCADE, 
        related_name='vacation_balances'
    )
    year = models.PositiveIntegerField(help_text="İl (məsələn: 2025)")
    
    # Balance fields
    start_balance = models.DecimalField(
        max_digits=5, 
        decimal_places=1, 
        default=0,
        help_text="Əvvəlki ildən qalan balans"
    )
    yearly_balance = models.DecimalField(
        max_digits=5, 
        decimal_places=1, 
        default=0,
        help_text="İllik məzuniyyət balansı"
    )
    used_days = models.DecimalField(
        max_digits=5, 
        decimal_places=1, 
        default=0,
        help_text="İstifadə edilmiş günlər"
    )
    scheduled_days = models.DecimalField(
        max_digits=5, 
        decimal_places=1, 
        default=0,
        help_text="Planlaşdırılmış günlər"
    )
    
    # System fields
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Employee Vacation Balance"
        verbose_name_plural = "Employee Vacation Balances"
        unique_together = ['employee', 'year']
        db_table = 'employee_vacation_balances'
        ordering = ['-year', 'employee__full_name']
    
    def __str__(self):
        return f"{self.employee.full_name} - {self.year} - Balance: {self.total_balance}"
    
    @property
    def total_balance(self):
        """✅ FIX: Ümumi balans"""
        return float(self.start_balance) + float(self.yearly_balance)
    
    @property
    def remaining_balance(self):
        """✅ FIX: Qalan balans"""
        total = self.total_balance
        used = float(self.used_days)
        scheduled = float(self.scheduled_days)
        return total - used - scheduled
    
    @property
    def should_be_planned(self):
        """Planlaşdırılmalı olan günlər"""
        # yearly_balance-dən artıq istifadə edilmiş və planlaşdırılmış günləri çıxarırıq
        planned_and_used = float(self.scheduled_days) + float(self.used_days)
        remaining_from_yearly = max(0, float(self.yearly_balance) - planned_and_used)
        return remaining_from_yearly
    
    def clean(self):
        """Validation"""
        if self.year < 2020 or self.year > 2030:
            raise ValidationError("İl 2020-2030 aralığında olmalıdır")


class VacationRequest(SoftDeleteModel):
    """Vacation Request - Immediate approval tələb edənlər"""
    
    REQUEST_TYPE_CHOICES = [
        ('IMMEDIATE', 'Immediate'),
        ('SCHEDULING', 'Scheduling'),
    ]
    
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('IN_PROGRESS', 'In Progress'),
        ('PENDING_LINE_MANAGER', 'Pending Line Manager'),
        ('PENDING_HR', 'Pending HR'),
        ('APPROVED', 'Approved'),
        ('REJECTED_LINE_MANAGER', 'Rejected by Line Manager'),
        ('REJECTED_HR', 'Rejected by HR'),
    ]
    
    # Request identification
    request_id = models.CharField(max_length=50, unique=True, editable=False)
    
    # Employee and requester
    employee = models.ForeignKey(
        Employee, 
        on_delete=models.CASCADE, 
        related_name='vacation_requests'
    )
    requester = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='created_vacation_requests'
    )
    
    # Request details
    request_type = models.CharField(max_length=20, choices=REQUEST_TYPE_CHOICES, default='IMMEDIATE')
    vacation_type = models.ForeignKey(VacationType, on_delete=models.PROTECT)
    
    # Dates
    start_date = models.DateField()
    end_date = models.DateField()
    return_date = models.DateField(editable=False, null=True, blank=True)
    number_of_days = models.DecimalField(max_digits=5, decimal_places=1, editable=False, default=0)
    comment = models.TextField(blank=True, help_text="İşçinin şərhi")
    
    # Approvers
    line_manager = models.ForeignKey(
        Employee, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='requests_to_approve'
    )
    hr_representative = models.ForeignKey(
        Employee, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='requests_hr'
    )
    
    # Status
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='DRAFT')
    
    # Line Manager Approval
    line_manager_approved_at = models.DateTimeField(null=True, blank=True)
    line_manager_approved_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='lm_approvals'
    )
    line_manager_comment = models.TextField(blank=True)
    
    # HR Approval
    hr_approved_at = models.DateTimeField(null=True, blank=True)
    hr_approved_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='hr_approvals'
    )
    hr_comment = models.TextField(blank=True)
    
    # Rejection
    rejected_at = models.DateTimeField(null=True, blank=True)
    rejected_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='rejections'
    )
    rejection_reason = models.TextField(blank=True)
    
    # System fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Vacation Request"
        verbose_name_plural = "Vacation Requests"
        db_table = 'vacation_requests'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.request_id} - {self.employee.full_name} - {self.vacation_type.name}"
    
    def check_date_conflicts(self):
        """
        Eyni employee üçün kəsişən tarixlərdə request/schedule olub-olmadığını yoxla
        Returns: (has_conflict, conflicting_records)
        """
        # Mövcud approved/pending requestlər
        conflicting_requests = VacationRequest.objects.filter(
            employee=self.employee,
            is_deleted=False,
            status__in=['PENDING_LINE_MANAGER', 'PENDING_HR', 'APPROVED']
        ).filter(
            start_date__lte=self.end_date,
            end_date__gte=self.start_date
        ).exclude(pk=self.pk)
        
        # Scheduled schedules
        conflicting_schedules = VacationSchedule.objects.filter(
            employee=self.employee,
            is_deleted=False,
            status='SCHEDULED'
        ).filter(
            start_date__lte=self.end_date,
            end_date__gte=self.start_date
        )
        
        conflicts = []
        
        for req in conflicting_requests:
            conflicts.append({
                'type': 'request',
                'id': req.request_id,
                'start_date': req.start_date,
                'end_date': req.end_date,
                'vacation_type': req.vacation_type.name,
                'status': req.get_status_display()
            })
        
        for sch in conflicting_schedules:
            conflicts.append({
                'type': 'schedule',
                'id': f'SCH{sch.id}',
                'start_date': sch.start_date,
                'end_date': sch.end_date,
                'vacation_type': sch.vacation_type.name,
                'status': sch.get_status_display()
            })
        
        return len(conflicts) > 0, conflicts
    
    def clean(self):
        """Validation"""
        if self.start_date and self.end_date and self.start_date >= self.end_date:
            raise ValidationError("End date start date-dən böyük olmalıdır")
        
        # ✅ Kəsişmə yoxla
        has_conflict, conflicts = self.check_date_conflicts()
        if has_conflict:
            conflict_details = ", ".join([
                f"{c['id']} ({c['start_date']} - {c['end_date']})" 
                for c in conflicts
            ])
            raise ValidationError(
                f"Bu tarixlərdə artıq vacation var: {conflict_details}"
            )
    
    def save(self, *args, **kwargs):
        # Generate request ID
        if not self.request_id:
            year = timezone.now().year
            last = VacationRequest.objects.filter(
                request_id__startswith=f'VR{year}'
            ).order_by('-request_id').first()
            num = int(last.request_id[6:]) + 1 if last else 1
            self.request_id = f'VR{year}{num:04d}'
        
        # Calculate working days and return date
        settings = VacationSetting.get_active()
        if settings and self.start_date and self.end_date:
            self.number_of_days = settings.calculate_working_days(self.start_date, self.end_date)
            self.return_date = settings.calculate_return_date(self.end_date)
        
        # Auto-assign approvers
        if not self.line_manager and self.employee.line_manager:
            # Əgər manager öz işçisi üçün yaradırsa - line manager atla
            requester_emp = getattr(self.requester, 'employee', None)
            if not (requester_emp and self.employee.line_manager == requester_emp):
                self.line_manager = self.employee.line_manager
        
        if not self.hr_representative and settings:
            self.hr_representative = settings.default_hr_representative
        
        self.clean()
        super().save(*args, **kwargs)
    
    def submit_request(self, user):
        """Submit for approval"""
        requester_emp = getattr(user, 'employee', None)
        is_manager_request = requester_emp and self.employee.line_manager == requester_emp
        
        if is_manager_request:
            # Manager öz işçisi üçün request edir - HR-a göndər
            self.status = 'PENDING_HR' if self.hr_representative else 'APPROVED'
        else:
            # Normal işçi request edir - Line Manager-ə göndər
            self.status = 'PENDING_LINE_MANAGER' if self.line_manager else ('PENDING_HR' if self.hr_representative else 'APPROVED')
        
        self.save()
    
    def approve_by_line_manager(self, user, comment=''):
        """Line Manager təsdiq edir"""
        self.line_manager_approved_at = timezone.now()
        self.line_manager_approved_by = user
        self.line_manager_comment = comment
        self.status = 'PENDING_HR' if self.hr_representative else 'APPROVED'
        self.save()
        
        # Əgər tam təsdiq olubsa balansı yenilə
        if self.status == 'APPROVED':
            self._update_balance()
    
    def reject_by_line_manager(self, user, reason):
        """Line Manager reject edir"""
        self.status = 'REJECTED_LINE_MANAGER'
        self.rejected_at = timezone.now()
        self.rejected_by = user
        self.rejection_reason = reason
        self.save()
    
    def approve_by_hr(self, user, comment=''):
        """HR təsdiq edir"""
        self.hr_approved_at = timezone.now()
        self.hr_approved_by = user
        self.hr_comment = comment
        self.status = 'APPROVED'
        self.save()
        
        # Balansı yenilə
        self._update_balance()
    
    def reject_by_hr(self, user, reason):
        """HR reject edir"""
        self.status = 'REJECTED_HR'
        self.rejected_at = timezone.now()
        self.rejected_by = user
        self.rejection_reason = reason
        self.save()
    
    def _update_balance(self):
        """Approved olduqda balansı yenilə"""
        balance, created = EmployeeVacationBalance.objects.get_or_create(
            employee=self.employee,
            year=self.start_date.year,
          
        )
        balance.used_days += self.number_of_days
        balance.save()


class VacationSchedule(SoftDeleteModel):
    """Vacation Schedule - Planlaşdırma (təsdiq tələb etmir)"""
    
    STATUS_CHOICES = [
        ('SCHEDULED', 'Scheduled'),
        ('REGISTERED', 'Registered'),
    ]
    
    employee = models.ForeignKey(
        Employee, 
        on_delete=models.CASCADE, 
        related_name='schedules'
    )
    vacation_type = models.ForeignKey(VacationType, on_delete=models.PROTECT)
    
    # Dates
    start_date = models.DateField()
    end_date = models.DateField()
    return_date = models.DateField(editable=False, null=True, blank=True)
    number_of_days = models.DecimalField(max_digits=5, decimal_places=1, default=0)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='SCHEDULED')
    
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
    
    comment = models.TextField(blank=True)
    
    # System fields
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Vacation Schedule"
        verbose_name_plural = "Vacation Schedules"
        db_table = 'vacation_schedules'
        ordering = ['-start_date']
    
    def __str__(self):
        return f"{self.employee.full_name} - {self.vacation_type.name} - {self.start_date} to {self.end_date}"
    
    def check_date_conflicts(self):
        """
        Eyni employee üçün kəsişən tarixlərdə request/schedule olub-olmadığını yoxla
        Returns: (has_conflict, conflicting_records)
        """
        # Mövcud approved/pending requestlər
        conflicting_requests = VacationRequest.objects.filter(
            employee=self.employee,
            is_deleted=False,
            status__in=['PENDING_LINE_MANAGER', 'PENDING_HR', 'APPROVED']
        ).filter(
            start_date__lte=self.end_date,
            end_date__gte=self.start_date
        )
        
        # Başqa scheduled schedules
        conflicting_schedules = VacationSchedule.objects.filter(
            employee=self.employee,
            is_deleted=False,
            status='SCHEDULED'
        ).filter(
            start_date__lte=self.end_date,
            end_date__gte=self.start_date
        ).exclude(pk=self.pk)
        
        conflicts = []
        
        for req in conflicting_requests:
            conflicts.append({
                'type': 'request',
                'id': req.request_id,
                'start_date': req.start_date,
                'end_date': req.end_date,
                'vacation_type': req.vacation_type.name,
                'status': req.get_status_display()
            })
        
        for sch in conflicting_schedules:
            conflicts.append({
                'type': 'schedule',
                'id': f'SCH{sch.id}',
                'start_date': sch.start_date,
                'end_date': sch.end_date,
                'vacation_type': sch.vacation_type.name,
                'status': sch.get_status_display()
            })
        
        return len(conflicts) > 0, conflicts
    
    def clean(self):
        """Validation"""
        if self.start_date and self.end_date and self.start_date >= self.end_date:
            raise ValidationError("End date start date-dən böyük olmalıdır")
        
        # ✅ Kəsişmə yoxla
        has_conflict, conflicts = self.check_date_conflicts()
        if has_conflict:
            conflict_details = ", ".join([
                f"{c['id']} ({c['start_date']} - {c['end_date']})" 
                for c in conflicts
            ])
            raise ValidationError(
                f"Bu tarixlərdə artıq vacation var: {conflict_details}"
            )
    
    def save(self, *args, **kwargs):
        # Calculate working days and return date
        settings = VacationSetting.get_active()
        if settings and self.start_date and self.end_date:
            self.number_of_days = settings.calculate_working_days(self.start_date, self.end_date)
            self.return_date = settings.calculate_return_date(self.end_date)
        
        is_new = not self.pk
        self.clean()
        super().save(*args, **kwargs)
        
        # ✅ FIX: Yeni schedule yaradıldıqda scheduled_days artır
        if is_new and self.status == 'SCHEDULED':
            self._update_scheduled_balance(add=True)
    
    def register_as_taken(self, user):
        """Schedule-i registered et"""
        if self.status != 'SCHEDULED':
            return
        
        # Get or create balance
        balance, created = EmployeeVacationBalance.objects.get_or_create(
            employee=self.employee, 
            year=self.start_date.year,
            defaults={
                'start_balance': 0,
                'yearly_balance': 28,
                'updated_by': user
            }
        )
        
        # DÜZƏLTMƏ: Scheduled-dən sil, used-ə əlavə et
        balance.scheduled_days = max(0, float(balance.scheduled_days) - float(self.number_of_days))
        balance.used_days = float(balance.used_days) + float(self.number_of_days)
        balance.updated_by = user
        balance.save()
        
        # Status dəyiş
        self.status = 'REGISTERED'
        self.save()
    
    def _update_scheduled_balance(self, add=True):
        """Scheduled balansı yenilə"""
        balance, created = EmployeeVacationBalance.objects.get_or_create(
            employee=self.employee,
            year=self.start_date.year,
           
        )
        
        if add:
            balance.scheduled_days += self.number_of_days
        else:
            balance.scheduled_days = max(0, balance.scheduled_days - self.number_of_days)
        
        balance.save()
    
    def can_edit(self):
        """Edit edilə bilərmi?"""
        if self.status != 'SCHEDULED':
            return False
        
        settings = VacationSetting.get_active()
        max_edits = settings.max_schedule_edits if settings else 3
        return self.edit_count < max_edits

def vacation_attachment_path(instance, filename):
    """Generate upload path for vacation attachments"""
    # vacation/2025/VR202500001/filename.pdf
    year = instance.vacation_request.created_at.year
    request_id = instance.vacation_request.request_id
    return f'vacation/{year}/{request_id}/{filename}'


class VacationAttachment(SoftDeleteModel):
    """File attachments for vacation requests"""
    vacation_request = models.ForeignKey(
        VacationRequest, 
        on_delete=models.CASCADE, 
        related_name='attachments'
    )
    file = models.FileField(upload_to=vacation_attachment_path)
    original_filename = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField(help_text="File size in bytes")
    file_type = models.CharField(max_length=100, blank=True)
    
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Vacation Attachment"
        verbose_name_plural = "Vacation Attachments"
        db_table = 'vacation_attachments'
        ordering = ['-uploaded_at']
    
    def __str__(self):
        return f"{self.vacation_request.request_id} - {self.original_filename}"
    
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
            import os
            if os.path.isfile(self.file.path):
                os.remove(self.file.path)
        super().delete(*args, **kwargs)