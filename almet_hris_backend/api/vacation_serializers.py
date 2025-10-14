# api/vacation_serializers.py - Enhanced Serializers

from rest_framework import serializers
from .vacation_models import *
from .models import Employee

# ============= SEPARATED SETTINGS SERIALIZERS =============

class ProductionCalendarSerializer(serializers.Serializer):
    """Production Calendar serializer with name support"""
    non_working_days = serializers.ListField(
        child=serializers.DictField(
            child=serializers.CharField(),
            required=True
        ),
        help_text="Qeyri-iş günlərinin siyahısı [{'date': 'YYYY-MM-DD', 'name': 'Holiday Name'}, ...]"
    )
    
    def validate_non_working_days(self, value):
        """Tarixlərin düzgünlüyünü yoxla"""
        if not isinstance(value, list):
            raise serializers.ValidationError("Non working days siyahı olmalıdır")
        
        dates_seen = set()
        for item in value:
            if not isinstance(item, dict):
                raise serializers.ValidationError("Hər element dict formatında olmalıdır")
            
            if 'date' not in item:
                raise serializers.ValidationError("Date field mütləqdir")
            
            if 'name' not in item:
                item['name'] = ''  # Default empty name
            
            # Date formatını yoxla
            try:
                from datetime import datetime
                datetime.strptime(item['date'], '%Y-%m-%d')
            except ValueError:
                raise serializers.ValidationError(f"Date format səhvdir: {item['date']}. YYYY-MM-DD istifadə edin")
            
            # Duplicate yoxla
            if item['date'] in dates_seen:
                raise serializers.ValidationError(f"Təkrarlanan tarix: {item['date']}")
            dates_seen.add(item['date'])
        
        return value


class GeneralVacationSettingsSerializer(serializers.Serializer):
    """General Vacation Settings serializer"""
    allow_negative_balance = serializers.BooleanField(
        required=False,
        help_text="Balans 0 olduqda request yaratmağa icazə ver"
    )
    max_schedule_edits = serializers.IntegerField(
        required=False,
        min_value=0,
        help_text="Schedule neçə dəfə edit oluna bilər"
    )
    notification_days_before = serializers.IntegerField(
        required=False,
        min_value=1,
        help_text="Məzuniyyət başlamazdan neçə gün əvvəl bildiriş göndər"
    )
    notification_frequency = serializers.IntegerField(
        required=False,
        min_value=1,
        help_text="Bildirişi neçə dəfə göndər"
    )


class HRRepresentativeSerializer(serializers.Serializer):
    """HR Representative serializer"""
    default_hr_representative_id = serializers.IntegerField(
        help_text="Default HR nümayəndəsi Employee ID"
    )
    
    def validate_default_hr_representative_id(self, value):
        """HR employee mövcudluğunu yoxla"""
        try:
            employee = Employee.objects.get(id=value, is_deleted=False)
            # Optional: HR department yoxla
            if employee.department and 'HR' not in employee.department.name.upper():
                raise serializers.ValidationError("Seçilən işçi HR departamentində deyil")
            return value
        except Employee.DoesNotExist:
            raise serializers.ValidationError("HR nümayəndəsi tapılmadı")


class HRRepresentativeDetailSerializer(serializers.ModelSerializer):
    """HR Representative detail serializer"""
    department_name = serializers.CharField(source='department.name', read_only=True)
    is_default = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = Employee
        fields = ['id', 'full_name', 'email', 'phone', 'department_name', 'is_default']


# ============= EXISTING SERIALIZERS =============

class VacationSettingSerializer(serializers.ModelSerializer):
    """Complete Vacation Settings serializer"""
    class Meta:
        model = VacationSetting
        fields = ['id', 'non_working_days', 'default_hr_representative', 'allow_negative_balance', 
                  'max_schedule_edits', 'notification_days_before', 'notification_frequency', 'is_active']
        read_only_fields = ['created_by', 'updated_by']


class VacationTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = VacationType
        fields = ['id', 'name', 'description', 'is_active']
        read_only_fields = ['created_by', 'updated_by']





# ============= BALANCE =============
class EmployeeVacationBalanceSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    employee_id = serializers.CharField(source='employee.employee_id', read_only=True)
    department_name = serializers.CharField(source='employee.department.name', read_only=True)
    total_balance = serializers.ReadOnlyField()
    remaining_balance = serializers.ReadOnlyField()
    should_be_planned = serializers.ReadOnlyField()
    
    class Meta:
        model = EmployeeVacationBalance
        fields = ['id', 'employee', 'employee_name', 'employee_id', 'department_name', 'year', 
                  'start_balance', 'yearly_balance', 'used_days', 'scheduled_days', 'total_balance', 
                  'remaining_balance', 'should_be_planned', 'updated_at']


# ============= REQUEST =============
class VacationRequestListSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    employee_id = serializers.CharField(source='employee.employee_id', read_only=True)
    department_name = serializers.CharField(source='employee.department.name', read_only=True)
    vacation_type_name = serializers.CharField(source='vacation_type.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = VacationRequest
        fields = ['id', 'request_id', 'employee_name', 'employee_id', 'department_name', 
                  'vacation_type_name', 'start_date', 'end_date', 'return_date', 'number_of_days', 
                  'status', 'status_display', 'comment', 'created_at']


class VacationRequestDetailSerializer(serializers.ModelSerializer):
    employee_info = serializers.SerializerMethodField()
    vacation_type_detail = VacationTypeSerializer(source='vacation_type', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    line_manager_name = serializers.CharField(source='line_manager.full_name', read_only=True)
    hr_representative_name = serializers.CharField(source='hr_representative.full_name', read_only=True)
    
    class Meta:
        model = VacationRequest
        fields = ['id', 'request_id', 'employee_info', 'vacation_type_detail', 'start_date', 'end_date', 
                  'return_date', 'number_of_days', 'comment', 'status', 'status_display',
                  'line_manager_name', 'line_manager_comment', 'line_manager_approved_at',
                  'hr_representative_name', 'hr_comment', 'hr_approved_at',
                  'rejection_reason', 'rejected_at', 'created_at']
    
    def get_employee_info(self, obj):
        return {
            'id': obj.employee.id,
            'name': obj.employee.full_name,
            'employee_id': getattr(obj.employee, 'employee_id', ''),
            'department': obj.employee.department.name if obj.employee.department else None,
            'business_function': obj.employee.business_function.name if obj.employee.business_function else None,
            'phone': obj.employee.phone
        }


class EmployeeManualSerializer(serializers.Serializer):
    """Manual employee məlumatları üçün"""
    name = serializers.CharField(max_length=200)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    department = serializers.CharField(max_length=100, required=False, allow_blank=True)
    business_function = serializers.CharField(max_length=100, required=False, allow_blank=True)
    unit = serializers.CharField(max_length=100, required=False, allow_blank=True)
    job_function = serializers.CharField(max_length=100, required=False, allow_blank=True)


class VacationRequestCreateSerializer(serializers.Serializer):
    requester_type = serializers.ChoiceField(choices=['for_me', 'for_my_employee'])
    employee_id = serializers.IntegerField(required=False)
    employee_manual = EmployeeManualSerializer(required=False)
    vacation_type_id = serializers.IntegerField()
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    comment = serializers.CharField(required=False, allow_blank=True)
    hr_representative_id = serializers.IntegerField(required=False)
    
    def validate(self, data):
        # Əgər for_my_employee seçilibsə, employee_id və ya employee_manual olmalıdır
        if data['requester_type'] == 'for_my_employee':
            if not data.get('employee_id') and not data.get('employee_manual'):
                raise serializers.ValidationError(
                    "For my employee seçildikdə employee_id və ya employee_manual məlumatları lazımdır"
                )
        
        # Tarixləri yoxla
        if data['start_date'] >= data['end_date']:
            raise serializers.ValidationError("End date start date-dən böyük olmalıdır")
        
        # Vacation type mövcudluğu
        try:
            VacationType.objects.get(id=data['vacation_type_id'], is_active=True, is_deleted=False)
        except VacationType.DoesNotExist:
            raise serializers.ValidationError("Vacation type tapılmadı və ya aktiv deyil")
        
        return data


class VacationApprovalSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=['approve', 'reject'])
    comment = serializers.CharField(required=False, allow_blank=True)
    reason = serializers.CharField(required=False, allow_blank=True)
    
    def validate(self, data):
        if data['action'] == 'reject' and not data.get('reason'):
            raise serializers.ValidationError("Reject edərkən səbəb mütləqdir")
        return data


# ============= SCHEDULE =============
class VacationScheduleSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    employee_id = serializers.CharField(source='employee.employee_id', read_only=True)
    department_name = serializers.CharField(source='employee.department.name', read_only=True)
    vacation_type_name = serializers.CharField(source='vacation_type.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    can_edit = serializers.SerializerMethodField()
    
    class Meta:
        model = VacationSchedule
        fields = ['id', 'employee_name', 'employee_id', 'department_name', 'vacation_type_name', 
                  'start_date', 'end_date', 'return_date', 'number_of_days', 'status', 'status_display',
                  'edit_count', 'can_edit', 'comment', 'created_at']
    
    def get_can_edit(self, obj):
        return obj.can_edit()


class VacationScheduleCreateSerializer(serializers.Serializer):
    requester_type = serializers.ChoiceField(choices=['for_me', 'for_my_employee'])
    employee_id = serializers.IntegerField(required=False)
    employee_manual = EmployeeManualSerializer(required=False)
    vacation_type_id = serializers.IntegerField()
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    comment = serializers.CharField(required=False, allow_blank=True)
    
    def validate(self, data):
        # Əgər for_my_employee seçilibsə, employee_id və ya employee_manual olmalıdır
        if data['requester_type'] == 'for_my_employee':
            if not data.get('employee_id') and not data.get('employee_manual'):
                raise serializers.ValidationError(
                    "For my employee seçildikdə employee_id və ya employee_manual məlumatları lazımdır"
                )
        
        # Tarixləri yoxla
        if data['start_date'] >= data['end_date']:
            raise serializers.ValidationError("End date start date-dən böyük olmalıdır")
        
        # Vacation type mövcudluğu
        try:
            VacationType.objects.get(id=data['vacation_type_id'], is_active=True, is_deleted=False)
        except VacationType.DoesNotExist:
            raise serializers.ValidationError("Vacation type tapılmadı və ya aktiv deyil")
        
        return data


class VacationScheduleEditSerializer(serializers.ModelSerializer):
    class Meta:
        model = VacationSchedule
        fields = ['vacation_type', 'start_date', 'end_date', 'comment']
    
    def validate(self, data):
        if 'start_date' in data and 'end_date' in data:
            if data['start_date'] >= data['end_date']:
                raise serializers.ValidationError("End date start date-dən böyük olmalıdır")
        return data


# ============= EMPLOYEE SEARCH =============
class EmployeeSearchSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source='department.name', read_only=True)
    business_function_name = serializers.CharField(source='business_function.name', read_only=True)
    unit_name = serializers.CharField(source='unit.name', read_only=True)
    job_function_name = serializers.CharField(source='job_function.name', read_only=True)
    
    class Meta:
        model = Employee
        fields = ['id', 'full_name', 'employee_id', 'phone', 'department_name', 
                  'business_function_name', 'unit_name', 'job_function_name']

class VacationAttachmentSerializer(serializers.ModelSerializer):
    """
    Serializer for VacationAttachment model
    Displays file information for vacation requests
    """
    
    # Read-only fields with custom display
    uploaded_by_name = serializers.SerializerMethodField()
    uploaded_by_email = serializers.SerializerMethodField()
    file_url = serializers.SerializerMethodField()
    file_size_display = serializers.SerializerMethodField()
    
    class Meta:
        model = VacationAttachment
        fields = [
            'id',
            'vacation_request',
            'file',
            'file_url',
            'original_filename',
            'file_size',
            'file_size_display',
            'file_type',
            'uploaded_by',
            'uploaded_by_name',
            'uploaded_by_email',
            'uploaded_at',
            'is_deleted'
        ]
        read_only_fields = [
            'id',
            'uploaded_at',
            'uploaded_by',
            'file_size',
            'file_type'
        ]
    
    def get_uploaded_by_name(self, obj):
        """Get full name of uploader"""
        if obj.uploaded_by:
            return obj.uploaded_by.get_full_name() or obj.uploaded_by.username
        return None
    
    def get_uploaded_by_email(self, obj):
        """Get email of uploader"""
        if obj.uploaded_by:
            return obj.uploaded_by.email
        return None
    
    def get_file_url(self, obj):
        """Get full URL for file download"""
        if obj.file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.file.url)
            return obj.file.url
        return None
    
    def get_file_size_display(self, obj):
        """Convert file size to human-readable format"""
        if not obj.file_size:
            return "0 B"
        
        size = obj.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} TB"


class VacationAttachmentUploadSerializer(serializers.Serializer):
    """
    Serializer for uploading files to vacation requests
    Validates file type, size, and other constraints
    """
    
    file = serializers.FileField(required=True)
    
    # Allowed file types
    ALLOWED_EXTENSIONS = ['pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx', 'xls', 'xlsx']
    ALLOWED_CONTENT_TYPES = [
        'application/pdf',
        'image/jpeg',
        'image/jpg',
        'image/png',
        'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'application/vnd.ms-excel',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    ]
    
    # Maximum file size: 10MB
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB in bytes
    
    def validate_file(self, value):
        """
        Validate uploaded file
        - Check file extension
        - Check file size
        - Check content type
        """
        
        # Check file extension
        file_extension = value.name.split('.')[-1].lower()
        if file_extension not in self.ALLOWED_EXTENSIONS:
            raise serializers.ValidationError(
                f"File type '.{file_extension}' is not allowed. "
                f"Allowed types: {', '.join(self.ALLOWED_EXTENSIONS)}"
            )
        
        # Check file size
        if value.size > self.MAX_FILE_SIZE:
            max_size_mb = self.MAX_FILE_SIZE / (1024 * 1024)
            actual_size_mb = value.size / (1024 * 1024)
            raise serializers.ValidationError(
                f"File size ({actual_size_mb:.2f}MB) exceeds maximum allowed size ({max_size_mb}MB)"
            )
        
        # Check content type
        if value.content_type not in self.ALLOWED_CONTENT_TYPES:
            raise serializers.ValidationError(
                f"File content type '{value.content_type}' is not allowed"
            )
        
        return value


class VacationAttachmentListSerializer(serializers.ModelSerializer):
    """
    Simplified serializer for listing attachments
    Used in vacation request list views
    """
    
    uploaded_by_name = serializers.SerializerMethodField()
    file_size_display = serializers.SerializerMethodField()
    
    class Meta:
        model = VacationAttachment
        fields = [
            'id',
            'original_filename',
            'file_size_display',
            'file_type',
            'uploaded_by_name',
            'uploaded_at'
        ]
    
    def get_uploaded_by_name(self, obj):
        """Get name of uploader"""
        if obj.uploaded_by:
            return obj.uploaded_by.get_full_name() or obj.uploaded_by.username
        return "Unknown"
    
    def get_file_size_display(self, obj):
        """Convert file size to human-readable format"""
        if not obj.file_size:
            return "0 B"
        
        size = obj.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} TB"
# ============= COMBINED RECORDS =============
class VacationRecordSerializer(serializers.Serializer):
    """Unified serializer for both requests and schedules"""
    id = serializers.IntegerField()
    type = serializers.CharField()  # 'request' or 'schedule'
    request_id = serializers.CharField()
    vacation_type = serializers.CharField()
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    return_date = serializers.DateField(required=False, allow_null=True)
    days = serializers.DecimalField(max_digits=5, decimal_places=1)
    status = serializers.CharField()
    comment = serializers.CharField(required=False, allow_blank=True)
    created_at = serializers.DateTimeField()
    
    # Schedule specific fields
    can_edit = serializers.BooleanField(required=False)
    edit_count = serializers.IntegerField(required=False)