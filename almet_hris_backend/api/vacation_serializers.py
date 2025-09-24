# api/vacation_serializers.py - Separated Settings Serializers

from rest_framework import serializers
from .vacation_models import *
from .models import Employee

# ============= SEPARATED SETTINGS SERIALIZERS =============

class ProductionCalendarSerializer(serializers.Serializer):
    """Production Calendar serializer"""
    non_working_days = serializers.ListField(
        child=serializers.DateField(),
        help_text="Qeyri-iş günlərinin siyahısı YYYY-MM-DD formatında"
    )
    
    def validate_non_working_days(self, value):
        """Tarixlərin düzgünlüyünü yoxla"""
        if not isinstance(value, list):
            raise serializers.ValidationError("Non working days siyahı olmalıdır")
        
        # Duplicate tarixlər yoxla
        if len(value) != len(set(value)):
            raise serializers.ValidationError("Təkrarlanan tarixlər var")
        
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
    """Complete Vacation Settings serializer (if still needed)"""
    class Meta:
        model = VacationSetting
        fields = ['id', 'non_working_days', 'default_hr_representative', 'allow_negative_balance', 
                  'max_schedule_edits', 'notification_days_before', 'notification_frequency', 'is_active']


class VacationTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = VacationType
        fields = ['id', 'name', 'code', 'description', 'color', 'is_active']


class NotificationTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationTemplate
        fields = ['id', 'request_type', 'stage', 'subject', 'body', 'is_active']


# ============= BALANCE =============
class EmployeeVacationBalanceSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    total_balance = serializers.ReadOnlyField()
    remaining_balance = serializers.ReadOnlyField()
    should_be_planned = serializers.ReadOnlyField()
    
    class Meta:
        model = EmployeeVacationBalance
        fields = ['id', 'employee', 'employee_name', 'year', 'start_balance', 'yearly_balance', 
                  'used_days', 'scheduled_days', 'total_balance', 'remaining_balance', 'should_be_planned']


# ============= REQUEST =============
class VacationRequestListSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    vacation_type_name = serializers.CharField(source='vacation_type.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = VacationRequest
        fields = ['id', 'request_id', 'employee_name', 'vacation_type_name', 'start_date', 'end_date', 
                  'number_of_days', 'status', 'status_display', 'created_at']


class VacationRequestDetailSerializer(serializers.ModelSerializer):
    employee_info = serializers.SerializerMethodField()
    vacation_type_detail = VacationTypeSerializer(source='vacation_type', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = VacationRequest
        fields = ['id', 'request_id', 'employee_info', 'vacation_type_detail', 'start_date', 'end_date', 
                  'return_date', 'number_of_days', 'comment', 'status', 'status_display',
                  'line_manager_comment', 'hr_comment', 'rejection_reason', 'created_at']
    
    def get_employee_info(self, obj):
        return {
            'name': obj.employee.full_name,
            'department': obj.employee.department.name if obj.employee.department else None,
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
    vacation_type_name = serializers.CharField(source='vacation_type.name', read_only=True)
    can_edit = serializers.SerializerMethodField()
    
    class Meta:
        model = VacationSchedule
        fields = ['id', 'employee_name', 'vacation_type_name', 'start_date', 'end_date', 'return_date',
                  'number_of_days', 'status', 'edit_count', 'can_edit', 'comment', 'created_at']
    
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
        
        return data