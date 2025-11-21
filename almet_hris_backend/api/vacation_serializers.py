# api/vacation_serializers.py - COMPLETE FINAL VERSION

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


# ============= ATTACHMENT SERIALIZERS =============

class VacationAttachmentSerializer(serializers.ModelSerializer):
    """Vacation attachment serializer with file URLs"""
    file_url = serializers.SerializerMethodField()
    file_size_display = serializers.ReadOnlyField()
    uploaded_by_name = serializers.CharField(source='uploaded_by.get_full_name', read_only=True)
    
    class Meta:
        model = VacationAttachment
        fields = [
            'id', 'file', 'file_url', 'original_filename', 
            'file_size', 'file_size_display', 'file_type', 
            'uploaded_by_name', 'uploaded_at'
        ]
        read_only_fields = ['file_size', 'uploaded_by', 'uploaded_at']
    
    def get_file_url(self, obj):
        request = self.context.get('request')
        if obj.file and hasattr(obj.file, 'url'):
            if request:
                return request.build_absolute_uri(obj.file.url)
            return obj.file.url
        return None


# ============= BALANCE =============

# vacation_serializers.py

class EmployeeVacationBalanceSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    employee_id = serializers.CharField(source='employee.employee_id', read_only=True)
    department_name = serializers.CharField(source='employee.department.name', read_only=True)
    business_function_name = serializers.CharField(source='employee.business_function.name', read_only=True)  # ✅ YENİ
    total_balance = serializers.ReadOnlyField()
    remaining_balance = serializers.ReadOnlyField()
    should_be_planned = serializers.ReadOnlyField()
    
    class Meta:
        model = EmployeeVacationBalance
        fields = [
            'id', 'employee', 'employee_name', 'employee_id', 
            'department_name', 'business_function_name',  # ✅ YENİ
            'year', 'start_balance', 'yearly_balance', 
            'used_days', 'scheduled_days', 'total_balance', 
            'remaining_balance', 'should_be_planned', 'updated_at'
        ]


# ============= REQUEST SERIALIZERS =============

class VacationRequestListSerializer(serializers.ModelSerializer):
    """List serializer for vacation requests"""
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    employee_id = serializers.CharField(source='employee.employee_id', read_only=True)
    department_name = serializers.CharField(source='employee.department.name', read_only=True)
    vacation_type_name = serializers.CharField(source='vacation_type.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    attachments_count = serializers.SerializerMethodField()
    
    class Meta:
        model = VacationRequest
        fields = [
            'id', 'request_id', 'employee_name', 'employee_id', 'department_name', 
            'vacation_type_name', 'start_date', 'end_date', 'return_date', 'number_of_days', 
            'status', 'status_display', 'comment', 'attachments_count', 'created_at'
        ]
    
    def get_attachments_count(self, obj):
        return obj.attachments.filter(is_deleted=False).count()


class VacationRequestDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for vacation requests with all information"""
    employee_info = serializers.SerializerMethodField()
    vacation_type_detail = VacationTypeSerializer(source='vacation_type', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    line_manager_name = serializers.CharField(source='line_manager.full_name', read_only=True)
    hr_representative_name = serializers.CharField(source='hr_representative.full_name', read_only=True)
    attachments = serializers.SerializerMethodField()
    
    class Meta:
        model = VacationRequest
        fields = [
            'id', 'request_id', 'employee_info', 'vacation_type_detail', 
            'start_date', 'end_date', 'return_date', 'number_of_days', 
            'comment', 'status', 'status_display',
            'line_manager_name', 'line_manager_comment', 'line_manager_approved_at',
            'hr_representative_name', 'hr_comment', 'hr_approved_at',
            'rejection_reason', 'rejected_at', 
            'attachments', 'created_at', 'updated_at'
        ]
    
    def get_employee_info(self, obj):
        return {
            'id': obj.employee.id,
            'name': obj.employee.full_name,
            'employee_id': getattr(obj.employee, 'employee_id', ''),
            'department': obj.employee.department.name if obj.employee.department else None,
            'business_function': obj.employee.business_function.name if obj.employee.business_function else None,
            'unit': obj.employee.unit.name if obj.employee.unit else None,
            'job_function': obj.employee.job_function.name if obj.employee.job_function else None,
            'phone': obj.employee.phone
        }
    
    def get_attachments(self, obj):
        attachments = obj.attachments.filter(is_deleted=False).order_by('-uploaded_at')
        return VacationAttachmentSerializer(
            attachments,
            many=True,
            context=self.context
        ).data


class EmployeeManualSerializer(serializers.Serializer):
    """Manual employee məlumatları üçün"""
    name = serializers.CharField(max_length=200)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    department = serializers.CharField(max_length=100, required=False, allow_blank=True)
    business_function = serializers.CharField(max_length=100, required=False, allow_blank=True)
    unit = serializers.CharField(max_length=100, required=False, allow_blank=True)
    job_function = serializers.CharField(max_length=100, required=False, allow_blank=True)


class VacationRequestCreateSerializer(serializers.Serializer):
    """Serializer for creating vacation requests"""
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
    """Serializer for approval/rejection actions"""
    action = serializers.ChoiceField(choices=['approve', 'reject'])
    comment = serializers.CharField(required=False, allow_blank=True)
    reason = serializers.CharField(required=False, allow_blank=True)
    
    def validate(self, data):
        if data['action'] == 'reject' and not data.get('reason'):
            raise serializers.ValidationError("Reject edərkən səbəb mütləqdir")
        return data


# ============= SCHEDULE SERIALIZERS =============

class VacationScheduleSerializer(serializers.ModelSerializer):
    """List serializer for vacation schedules"""
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    employee_id = serializers.CharField(source='employee.employee_id', read_only=True)
    department_name = serializers.CharField(source='employee.department.name', read_only=True)
    vacation_type_name = serializers.CharField(source='vacation_type.name', read_only=True)
    vacation_type_detail = VacationTypeSerializer(source='vacation_type', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    can_edit = serializers.SerializerMethodField()
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    last_edited_by_name = serializers.CharField(source='last_edited_by.get_full_name', read_only=True)
    
    class Meta:
        model = VacationSchedule
        fields = [
            'id', 'employee_name', 'employee_id', 'department_name', 
            'vacation_type_name', 'vacation_type_detail',
            'start_date', 'end_date', 'return_date', 'number_of_days', 
            'status', 'status_display',
            'edit_count', 'can_edit', 
            'created_by_name', 'last_edited_by_name',
            'last_edited_at',
            'comment', 'created_at', 'updated_at'
        ]
    
    def get_can_edit(self, obj):
        return obj.can_edit()


class VacationScheduleDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for vacation schedule with all information"""
    employee_info = serializers.SerializerMethodField()
    vacation_type_detail = VacationTypeSerializer(source='vacation_type', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    can_edit = serializers.SerializerMethodField()
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    created_by_email = serializers.CharField(source='created_by.email', read_only=True)
    last_edited_by_name = serializers.CharField(source='last_edited_by.get_full_name', read_only=True)
    edit_history = serializers.SerializerMethodField()
    
    class Meta:
        model = VacationSchedule
        fields = [
            'id', 'employee_info', 'vacation_type_detail', 
            'start_date', 'end_date', 'return_date', 'number_of_days',
            'status', 'status_display', 'comment',
            'edit_count', 'can_edit', 'edit_history',
            'created_by_name', 'created_by_email',
            'last_edited_by_name', 'last_edited_at',
            'created_at', 'updated_at'
        ]
    
    def get_employee_info(self, obj):
        return {
            'id': obj.employee.id,
            'name': obj.employee.full_name,
            'employee_id': getattr(obj.employee, 'employee_id', ''),
            'department': obj.employee.department.name if obj.employee.department else None,
            'business_function': obj.employee.business_function.name if obj.employee.business_function else None,
            'unit': obj.employee.unit.name if obj.employee.unit else None,
            'job_function': obj.employee.job_function.name if obj.employee.job_function else None,
            'phone': obj.employee.phone
        }
    
    def get_can_edit(self, obj):
        return obj.can_edit()
    
    def get_edit_history(self, obj):
        settings = VacationSetting.get_active()
        max_edits = settings.max_schedule_edits if settings else 3
        
        return {
            'current_edits': obj.edit_count,
            'max_edits_allowed': max_edits,
            'remaining_edits': max(0, max_edits - obj.edit_count),
            'can_still_edit': obj.can_edit(),
            'last_edited_by': obj.last_edited_by.get_full_name() if obj.last_edited_by else None,
            'last_edited_at': obj.last_edited_at
        }


class VacationScheduleCreateSerializer(serializers.Serializer):
    """Serializer for creating vacation schedules"""
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
    """Serializer for editing vacation schedules"""
    class Meta:
        model = VacationSchedule
        fields = ['vacation_type', 'start_date', 'end_date', 'comment']
    
    def validate(self, data):
        if 'start_date' in data and 'end_date' in data:
            if data['start_date'] >= data['end_date']:
                raise serializers.ValidationError("End date start date-dən böyük olmalıdır")
        return data

