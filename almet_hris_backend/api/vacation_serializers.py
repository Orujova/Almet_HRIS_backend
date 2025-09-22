# api/vacation_serializers.py - Updated Vacation Management System Serializers

from rest_framework import serializers
from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone
from datetime import date, timedelta
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError
from .vacation_models import (
    VacationSetting, VacationType, EmployeeVacationBalance,
    VacationRequest, VacationActivity, VacationSchedule
)
from .models import Employee
from .serializers import EmployeeListSerializer
import logging

logger = logging.getLogger(__name__)

class VacationSettingSerializer(serializers.ModelSerializer):
    """Serializer for vacation settings"""
    
    default_hr_name = serializers.CharField(
        source='default_hr_representative.full_name', 
        read_only=True
    )
    total_non_working_days = serializers.SerializerMethodField()
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    
    class Meta:
        model = VacationSetting
        fields = [
            'id', 'non_working_days', 'default_hr_representative', 'default_hr_name',
            'allow_negative_balance', 'max_schedule_edits', 
            'notification_days_before', 'notification_frequency',
            'total_non_working_days', 'is_active', 'created_at', 'updated_at',
            'created_by_name'
        ]
    
    def get_total_non_working_days(self, obj):
        """Get total number of non-working days configured"""
        return len(obj.non_working_days) if obj.non_working_days else 0
    
    def validate_default_hr_representative(self, value):
        """Validate HR representative is valid"""
        if value and value.department and 'HR' not in value.department.name.upper():
            logger.warning(f"Employee {value.full_name} is not from HR department but assigned as HR representative")
        return value

class VacationTypeSerializer(serializers.ModelSerializer):
    """Serializer for vacation types"""
    
    vacation_requests_count = serializers.SerializerMethodField()
    
    class Meta:
        model = VacationType
        fields = [
            'id', 'name', 'code', 'description', 'requires_approval',
            'affects_balance', 'max_consecutive_days', 'color',
            'is_active', 'vacation_requests_count', 'created_at', 'updated_at'
        ]
    
    def get_vacation_requests_count(self, obj):
        """Get count of vacation requests for this type"""
        return obj.vacationrequest_set.count()

class EmployeeVacationBalanceSerializer(serializers.ModelSerializer):
    """Serializer for employee vacation balances"""
    
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    employee_id = serializers.CharField(source='employee.employee_id', read_only=True)
    department_name = serializers.CharField(source='employee.department.name', read_only=True)
    business_function_name = serializers.CharField(source='employee.business_function.name', read_only=True)
    unit_name = serializers.CharField(source='employee.unit.name', read_only=True)
    job_function_name = serializers.CharField(source='employee.job_function.name', read_only=True)
    phone_number = serializers.CharField(source='employee.phone', read_only=True)
    
    # Calculated fields
    total_balance = serializers.ReadOnlyField()
    remaining_balance = serializers.ReadOnlyField()
    should_be_planned = serializers.ReadOnlyField()
    
    # Balance status
    balance_status = serializers.SerializerMethodField()
    
    class Meta:
        model = EmployeeVacationBalance
        fields = [
            'id', 'employee', 'employee_name', 'employee_id', 'department_name',
            'business_function_name', 'unit_name', 'job_function_name', 'phone_number',
            'year', 'start_balance', 'yearly_balance', 'used_days', 'scheduled_days',
            'total_balance', 'remaining_balance', 'should_be_planned',
            'balance_status', 'created_at', 'updated_at'
        ]
    
    def get_balance_status(self, obj):
        """Get balance status indicator"""
        remaining = obj.remaining_balance
        if remaining < 0:
            return 'negative'
        elif remaining < 5:
            return 'low'
        elif remaining > obj.yearly_balance * 0.8:
            return 'high'
        else:
            return 'normal'

class EmployeeInfoSerializer(serializers.ModelSerializer):
    """Serializer for employee information in vacation requests"""
    
    department_name = serializers.CharField(source='department.name', read_only=True)
    business_function_name = serializers.CharField(source='business_function.name', read_only=True)
    unit_name = serializers.CharField(source='unit.name', read_only=True)
    job_function_name = serializers.CharField(source='job_function.name', read_only=True)
    line_manager_name = serializers.CharField(source='line_manager.full_name', read_only=True)
    
    class Meta:
        model = Employee
        fields = [
            'id', 'employee_id', 'full_name', 'phone',
            'department_name', 'business_function_name', 'unit_name', 
            'job_function_name', 'line_manager_name'
        ]

class VacationRequestListSerializer(serializers.ModelSerializer):
    """List serializer for vacation requests"""
    
    employee_info = EmployeeInfoSerializer(source='employee', read_only=True)
    requester_name = serializers.CharField(source='requester.get_full_name', read_only=True)
    vacation_type_name = serializers.CharField(source='vacation_type.name', read_only=True)
    vacation_type_color = serializers.CharField(source='vacation_type.color', read_only=True)
    
    # Approval info
    line_manager_name = serializers.CharField(source='line_manager.full_name', read_only=True)
    hr_representative_name = serializers.CharField(source='hr_representative.full_name', read_only=True)
    
    # Status info
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    can_edit = serializers.SerializerMethodField()
    days_until_start = serializers.SerializerMethodField()
    
    class Meta:
        model = VacationRequest
        fields = [
            'id', 'request_id', 'employee_info', 'requester_name', 'request_type', 
            'vacation_type_name', 'vacation_type_color', 'start_date', 'end_date', 
            'return_date', 'number_of_days', 'status', 'status_display', 
            'line_manager_name', 'hr_representative_name', 'can_edit', 
            'days_until_start', 'created_at', 'updated_at'
        ]
    
    def get_can_edit(self, obj):
        """Check if request can be edited"""
        return obj.can_be_edited()
    
    def get_days_until_start(self, obj):
        """Get days until vacation starts"""
        if obj.start_date:
            delta = obj.start_date - date.today()
            return delta.days
        return None

class VacationRequestDetailSerializer(serializers.ModelSerializer):
    """Detail serializer for vacation requests"""
    
    # Employee details
    employee_info = EmployeeInfoSerializer(source='employee', read_only=True)
    requester_detail = serializers.SerializerMethodField()
    
    # Vacation type details
    vacation_type_detail = VacationTypeSerializer(source='vacation_type', read_only=True)
    
    # Approval details
    line_manager_detail = serializers.SerializerMethodField()
    hr_representative_detail = serializers.SerializerMethodField()
    
    # Calculated fields
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    can_edit = serializers.SerializerMethodField()
    days_until_start = serializers.SerializerMethodField()
    conflicting_requests = serializers.SerializerMethodField()
    conflicting_schedules = serializers.SerializerMethodField()
    
    # Activities
    activities = serializers.SerializerMethodField()
    
    # Balance info
    employee_balance = serializers.SerializerMethodField()
    
    class Meta:
        model = VacationRequest
        fields = [
            'id', 'request_id', 'employee_info', 'requester_detail',
            'request_type', 'vacation_type_detail', 'start_date', 'end_date', 
            'return_date', 'number_of_days', 'comment',
            'line_manager_detail', 'hr_representative_detail',
            'status', 'status_display', 'can_edit', 'days_until_start',
            'line_manager_approved_at', 'line_manager_comment',
            'hr_approved_at', 'hr_comment',
            'rejected_at', 'rejection_reason',
            'edit_count', 'last_edited_at',
            'conflicting_requests', 'conflicting_schedules', 'activities', 'employee_balance',
            'created_at', 'updated_at'
        ]
    
    def get_requester_detail(self, obj):
        """Get requester details"""
        if obj.requester:
            return {
                'id': obj.requester.id,
                'username': obj.requester.username,
                'full_name': obj.requester.get_full_name(),
                'email': obj.requester.email
            }
        return None
    
    def get_line_manager_detail(self, obj):
        """Get line manager details"""
        if obj.line_manager:
            return EmployeeInfoSerializer(obj.line_manager).data
        return None
    
    def get_hr_representative_detail(self, obj):
        """Get HR representative details"""
        if obj.hr_representative:
            return EmployeeInfoSerializer(obj.hr_representative).data
        return None
    
    def get_can_edit(self, obj):
        """Check if request can be edited"""
        return obj.can_be_edited()
    
    def get_days_until_start(self, obj):
        """Get days until vacation starts"""
        if obj.start_date:
            delta = obj.start_date - date.today()
            return delta.days
        return None
    
    def get_conflicting_requests(self, obj):
        """Get conflicting vacation requests"""
        conflicting = obj.get_conflicting_requests()
        return [
            {
                'id': req.id,
                'request_id': req.request_id,
                'employee_name': req.employee.full_name,
                'start_date': req.start_date,
                'end_date': req.end_date,
                'status': req.status,
                'status_display': req.get_status_display()
            }
            for req in conflicting[:5]  # Limit to 5
        ]
    
    def get_conflicting_schedules(self, obj):
        """Get conflicting vacation schedules"""
        conflicting = obj.get_conflicting_schedules()
        return [
            {
                'id': schedule.id,
                'employee_name': schedule.employee.full_name,
                'start_date': schedule.start_date,
                'end_date': schedule.end_date,
                'vacation_type': schedule.vacation_type.name,
                'status': schedule.status
            }
            for schedule in conflicting[:5]  # Limit to 5
        ]
    
    def get_activities(self, obj):
        """Get vacation request activities"""
        activities = obj.activities.all()[:10]  # Last 10 activities
        return [
            {
                'id': activity.id,
                'activity_type': activity.activity_type,
                'description': activity.description,
                'performed_by': activity.performed_by.get_full_name() if activity.performed_by else 'System',
                'created_at': activity.created_at
            }
            for activity in activities
        ]
    
    def get_employee_balance(self, obj):
        """Get employee's vacation balance"""
        balance = obj.get_employee_balance()
        if balance:
            return EmployeeVacationBalanceSerializer(balance).data
        return None

class VacationRequestCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating vacation requests"""
    
    # Employee selection
    requester_type = serializers.ChoiceField(
        choices=[('for_me', 'For Me'), ('for_my_employee', 'For My Employee')],
        write_only=True
    )
    
    class Meta:
        model = VacationRequest
        fields = [
            'requester_type', 'employee', 'request_type', 'vacation_type',
            'start_date', 'end_date', 'comment', 'line_manager', 'hr_representative'
        ]
    
    def validate(self, data):
        """Validate vacation request data"""
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        request_type = data.get('request_type')
        
        # Validate dates
        if start_date and end_date:
            if start_date > end_date:
                raise ValidationError("Start date cannot be after end date")
            
            # For immediate requests, start date cannot be in the past
            if request_type == 'IMMEDIATE' and start_date < date.today():
                raise ValidationError("Start date cannot be in the past for immediate requests")
        
        # Validate employee selection based on requester type
        requester_type = data.get('requester_type')
        employee = data.get('employee')
        
        request = self.context.get('request')
        if request and request.user:
            try:
                user_employee = Employee.objects.get(user=request.user)
                
                if requester_type == 'for_me':
                    # User creating request for themselves
                    data['employee'] = user_employee
                elif requester_type == 'for_my_employee':
                    # Check if selected employee reports to the requesting user
                    if not employee:
                        raise ValidationError("Employee must be selected for 'for my employee' requests")
                    
                    if employee.line_manager != user_employee:
                        raise ValidationError("You can only create requests for your direct reports")
                    
            except Employee.DoesNotExist:
                raise ValidationError("User does not have an employee profile")
        
        # Validate vacation type consecutive days limit
        vacation_type = data.get('vacation_type')
        if vacation_type and vacation_type.max_consecutive_days and start_date and end_date:
            settings = VacationSetting.get_active_settings()
            if settings:
                requested_days = settings.calculate_working_days(start_date, end_date)
                if requested_days > vacation_type.max_consecutive_days:
                    raise ValidationError(
                        f"Maximum consecutive days for {vacation_type.name} is {vacation_type.max_consecutive_days}"
                    )
        
        return data
    
    def create(self, validated_data):
        """Create vacation request"""
        requester_type = validated_data.pop('requester_type')
        
        # Set requester
        validated_data['requester'] = self.context['request'].user
        
        # Create the request
        with transaction.atomic():
            vacation_request = super().create(validated_data)
            
            # Create activity log
            VacationActivity.objects.create(
                vacation_request=vacation_request,
                activity_type='CREATED',
                description=f"Vacation request created by {vacation_request.requester.get_full_name()}",
                performed_by=vacation_request.requester
            )
        
        return vacation_request

class VacationRequestUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating vacation requests"""
    
    class Meta:
        model = VacationRequest
        fields = [
            'start_date', 'end_date', 'comment', 'vacation_type'
        ]
    
    def validate(self, data):
        """Validate update data"""
        instance = self.instance
        
        # Check if request can be edited
        if not instance.can_be_edited():
            raise ValidationError("This request cannot be edited")
        
        # Validate dates
        start_date = data.get('start_date', instance.start_date)
        end_date = data.get('end_date', instance.end_date)
        
        if start_date > end_date:
            raise ValidationError("Start date cannot be after end date")
        
        # For immediate requests, start date cannot be in the past
        if instance.request_type == 'IMMEDIATE' and start_date < date.today():
            raise ValidationError("Start date cannot be in the past for immediate requests")
        
        # Validate vacation type consecutive days limit
        vacation_type = data.get('vacation_type', instance.vacation_type)
        if vacation_type and vacation_type.max_consecutive_days:
            settings = VacationSetting.get_active_settings()
            if settings:
                requested_days = settings.calculate_working_days(start_date, end_date)
                if requested_days > vacation_type.max_consecutive_days:
                    raise ValidationError(
                        f"Maximum consecutive days for {vacation_type.name} is {vacation_type.max_consecutive_days}"
                    )
        
        return data
    
    def update(self, instance, validated_data):
        """Update vacation request"""
        # Track what changed
        changes = []
        
        for field, new_value in validated_data.items():
            old_value = getattr(instance, field)
            if old_value != new_value:
                if field in ['start_date', 'end_date']:
                    changes.append(f"{field}: {old_value} → {new_value}")
                elif field == 'vacation_type':
                    changes.append(f"vacation type: {old_value.name} → {new_value.name}")
                else:
                    changes.append(f"{field}: {old_value} → {new_value}")
        
        # Update edit tracking
        instance.edit_count += 1
        instance.last_edited_at = timezone.now()
        instance.last_edited_by = self.context['request'].user
        
        # Update instance
        updated_instance = super().update(instance, validated_data)
        
        # Log activity
        if changes:
            VacationActivity.objects.create(
                vacation_request=updated_instance,
                activity_type='EDITED',
                description=f"Request edited: {'; '.join(changes)}",
                performed_by=self.context['request'].user,
                metadata={'changes': changes, 'edit_count': updated_instance.edit_count}
            )
        
        return updated_instance

class VacationApprovalSerializer(serializers.Serializer):
    """Serializer for vacation approval actions"""
    
    action = serializers.ChoiceField(choices=['approve', 'reject'])
    comment = serializers.CharField(required=False, allow_blank=True)
    reason = serializers.CharField(required=False, allow_blank=True)
    
    def validate(self, data):
        """Validate approval data"""
        if data['action'] == 'reject' and not data.get('reason'):
            raise ValidationError("Rejection reason is required when rejecting a request")
        return data

class VacationScheduleSerializer(serializers.ModelSerializer):
    """Serializer for vacation schedules"""
    
    employee_info = EmployeeInfoSerializer(source='employee', read_only=True)
    vacation_type_name = serializers.CharField(source='vacation_type.name', read_only=True)
    vacation_type_color = serializers.CharField(source='vacation_type.color', read_only=True)
    
    can_edit = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    conflicting_schedules = serializers.SerializerMethodField()
    
    class Meta:
        model = VacationSchedule
        fields = [
            'id', 'employee_info', 'vacation_type', 'vacation_type_name', 'vacation_type_color',
            'start_date', 'end_date', 'return_date', 'number_of_days',
            'status', 'status_display', 'can_edit', 'edit_count',
            'comment', 'notes', 'conflicting_schedules', 'created_at', 'updated_at'
        ]
    
    def get_can_edit(self, obj):
        """Check if schedule can be edited"""
        return obj.can_edit()
    
    def get_conflicting_schedules(self, obj):
        """Get conflicting schedules for this schedule"""
        conflicting = obj.get_conflicting_schedules()
        return [
            {
                'id': schedule.id,
                'employee_name': schedule.employee.full_name,
                'start_date': schedule.start_date,
                'end_date': schedule.end_date,
                'vacation_type': schedule.vacation_type.name
            }
            for schedule in conflicting[:5]  # Limit to 5
        ]

class VacationScheduleCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating vacation schedules"""
    
    # Employee selection
    requester_type = serializers.ChoiceField(
        choices=[('for_me', 'For Me'), ('for_my_employee', 'For My Employee')],
        write_only=True,
        required=False
    )
    
    class Meta:
        model = VacationSchedule
        fields = [
            'requester_type', 'employee', 'vacation_type', 'start_date', 
            'end_date', 'comment', 'notes'
        ]
    
    def validate(self, data):
        """Validate schedule data"""
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        
        # Validate dates
        if start_date and end_date:
            if start_date > end_date:
                raise ValidationError("Start date cannot be after end date")
        
        # Validate employee selection based on requester type
        requester_type = data.get('requester_type')
        employee = data.get('employee')
        
        request = self.context.get('request')
        if request and request.user and requester_type:
            try:
                user_employee = Employee.objects.get(user=request.user)
                
                if requester_type == 'for_me':
                    # User creating schedule for themselves
                    data['employee'] = user_employee
                elif requester_type == 'for_my_employee':
                    # Check if selected employee reports to the requesting user
                    if not employee:
                        raise ValidationError("Employee must be selected for 'for my employee' schedules")
                    
                    if employee.line_manager != user_employee:
                        raise ValidationError("You can only create schedules for your direct reports")
                    
            except Employee.DoesNotExist:
                raise ValidationError("User does not have an employee profile")
        
        # Check if employee has sufficient balance
        if start_date and end_date and employee:
            balance = EmployeeVacationBalance.objects.filter(
                employee=employee,
                year=start_date.year
            ).first()
            
            if balance:
                settings = VacationSetting.get_active_settings()
                if settings:
                    requested_days = settings.calculate_working_days(start_date, end_date)
                    if not balance.can_request_days(requested_days):
                        if not settings.allow_negative_balance:
                            raise ValidationError(
                                f"Insufficient vacation balance. Remaining: {balance.remaining_balance}, Requested: {requested_days}"
                            )
        
        return data
    
    def create(self, validated_data):
        """Create vacation schedule"""
        # Remove requester_type from validated_data
        validated_data.pop('requester_type', None)
        
        # Create the schedule
        with transaction.atomic():
            schedule = super().create(validated_data)
            
            # Create activity log
            VacationActivity.objects.create(
                vacation_schedule=schedule,
                activity_type='SCHEDULE_CREATED',
                description=f"Vacation schedule created by {self.context['request'].user.get_full_name()}",
                performed_by=self.context['request'].user
            )
        
        return schedule

class VacationStatisticsSerializer(serializers.Serializer):
    """Serializer for vacation statistics"""
    
    total_requests = serializers.IntegerField()
    pending_requests = serializers.IntegerField()
    approved_requests = serializers.IntegerField()
    rejected_requests = serializers.IntegerField()
    
    # By status breakdown
    status_breakdown = serializers.DictField()
    
    # By type breakdown
    type_breakdown = serializers.DictField()
    
    # Monthly trends
    monthly_trends = serializers.ListField()
    
    # Balance statistics
    balance_stats = serializers.DictField()

class BulkVacationBalanceSerializer(serializers.Serializer):
    """Serializer for bulk vacation balance upload"""
    
    file = serializers.FileField()
    year = serializers.IntegerField()
    
    def validate_year(self, value):
        """Validate year"""
        current_year = date.today().year
        if value < current_year - 1 or value > current_year + 2:
            raise ValidationError("Year must be within reasonable range")
        return value
    
    def validate_file(self, value):
        """Validate uploaded file"""
        if not value.name.endswith(('.xlsx', '.xls')):
            raise ValidationError("File must be Excel format (.xlsx or .xls)")
        
        if value.size > 10 * 1024 * 1024:  # 10MB limit
            raise ValidationError("File size cannot exceed 10MB")
        
        return value

class VacationExportSerializer(serializers.Serializer):
    """Serializer for vacation data export"""
    
    export_type = serializers.ChoiceField(
        choices=[
            ('requests', 'Vacation Requests'),
            ('balances', 'Vacation Balances'),
            ('schedules', 'Vacation Schedules')
        ]
    )
    format = serializers.ChoiceField(
        choices=[('excel', 'Excel'), ('csv', 'CSV')],
        default='excel'
    )
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)
    year = serializers.IntegerField(required=False)
    department_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False
    )
    employee_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False
    )
    
    def validate(self, data):
        """Validate export parameters"""
        date_from = data.get('date_from')
        date_to = data.get('date_to')
        
        if date_from and date_to and date_from > date_to:
            raise ValidationError("Date from cannot be after date to")
        
        return data

class MyVacationSummarySerializer(serializers.Serializer):
    """Serializer for employee's vacation summary"""
    
    # Current balance
    current_balance = EmployeeVacationBalanceSerializer()
    
    # Recent requests
    recent_requests = VacationRequestListSerializer(many=True)
    
    # Upcoming schedules
    upcoming_schedules = VacationScheduleSerializer(many=True)
    
    # Pending approvals (if manager)
    pending_approvals = VacationRequestListSerializer(many=True)
    
    # Statistics
    stats = serializers.DictField()

class TeamVacationOverviewSerializer(serializers.Serializer):
    """Serializer for team vacation overview (for managers)"""
    
    # Team members
    team_members = EmployeeListSerializer(many=True)
    
    # Team vacation requests
    team_requests = VacationRequestListSerializer(many=True)
    
    # Team schedules
    team_schedules = VacationScheduleSerializer(many=True)
    
    # Conflicts and overlaps
    conflicts = serializers.ListField()
    
    # Team statistics
    team_stats = serializers.DictField()

class VacationDashboardSerializer(serializers.Serializer):
    """Serializer for vacation dashboard data"""
    
    # Balance information (5 stat cards)
    balance = serializers.DictField()
    
    # Pending approvals count
    pending_approvals_count = serializers.IntegerField()
    
    # Upcoming schedules count
    upcoming_schedules_count = serializers.IntegerField()
    
    # Recent activity
    recent_activity = serializers.ListField(required=False)

class VacationApprovalHistorySerializer(serializers.Serializer):
    """Serializer for vacation approval history"""
    
    request_id = serializers.CharField()
    employee_name = serializers.CharField()
    vacation_type = serializers.CharField()
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    status = serializers.CharField()
    approved_by = serializers.CharField()
    approved_at = serializers.DateTimeField()
    comments = serializers.CharField()