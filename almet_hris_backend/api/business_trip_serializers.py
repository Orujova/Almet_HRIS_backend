# api/business_trip_serializers.py
from rest_framework import serializers
from django.contrib.auth.models import User
from django.utils import timezone
from django.db import transaction
from .models import Employee
from .business_trip_models import (
    TravelType, TransportType, TripPurpose, ApprovalWorkflow, ApprovalStep,
    BusinessTripRequest, TripSchedule, TripHotel, TripApproval
)

class TravelTypeSerializer(serializers.ModelSerializer):
    """Serializer for Travel Type configuration"""
    
    class Meta:
        model = TravelType
        fields = ['id', 'name', 'description', 'is_active']

class TransportTypeSerializer(serializers.ModelSerializer):
    """Serializer for Transport Type configuration"""
    
    class Meta:
        model = TransportType
        fields = ['id', 'name',  'description', 'is_active']

class TripPurposeSerializer(serializers.ModelSerializer):
    """Serializer for Trip Purpose configuration"""
    
    class Meta:
        model = TripPurpose
        fields = ['id', 'name',  'description', 'is_active']

class ApprovalStepSerializer(serializers.ModelSerializer):
    """Serializer for Approval Steps"""
    specific_approver_name = serializers.CharField(source='specific_approver.full_name', read_only=True)
    
    class Meta:
        model = ApprovalStep
        fields = [
            'id', 'step_type', 'step_order', 'step_name', 'is_required',
            'can_edit_amount', 'requires_amount_entry', 'auto_assign_to_line_manager',
            'specific_approver', 'specific_approver_name'
        ]

class ApprovalWorkflowSerializer(serializers.ModelSerializer):
    """Serializer for Approval Workflows"""
    steps = ApprovalStepSerializer(many=True, read_only=True)
    
    class Meta:
        model = ApprovalWorkflow
        fields = [
            'id', 'name', 'description', 'is_active', 'is_default',
            'applies_to_domestic', 'applies_to_overseas', 'min_amount', 'max_amount',
            'steps'
        ]

class TripScheduleSerializer(serializers.ModelSerializer):
    """Serializer for Trip Schedule entries"""
    
    class Meta:
        model = TripSchedule
        fields = [
            'id', 'date', 'from_location', 'to_location', 'order', 'notes'
        ]

class TripHotelSerializer(serializers.ModelSerializer):
    """Serializer for Trip Hotel entries"""
    nights_count = serializers.ReadOnlyField()
    
    class Meta:
        model = TripHotel
        fields = [
            'id', 'hotel_name', 'check_in_date', 'check_out_date',
            'location', 'contact_info', 'notes', 'nights_count'
        ]

class TripApprovalSerializer(serializers.ModelSerializer):
    """Serializer for Trip Approvals"""
    approver_name = serializers.CharField(source='approver.full_name', read_only=True)
    approver_employee_id = serializers.CharField(source='approver.employee_id', read_only=True)
    step_name = serializers.CharField(source='approval_step.step_name', read_only=True)
    step_type = serializers.CharField(source='approval_step.step_type', read_only=True)
    
    class Meta:
        model = TripApproval
        fields = [
            'id', 'approval_step', 'approver', 'approver_name', 'approver_employee_id',
            'step_name', 'step_type', 'decision', 'amount', 'notes', 'created_at'
        ]

class BusinessTripRequestListSerializer(serializers.ModelSerializer):
    """Serializer for Business Trip Request list view"""
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    employee_id = serializers.CharField(source='employee.employee_id', read_only=True)
    requested_by_name = serializers.CharField(source='requested_by.full_name', read_only=True)
    travel_type_name = serializers.CharField(source='travel_type.name', read_only=True)
    transport_type_name = serializers.CharField(source='transport_type.name', read_only=True)
    purpose_name = serializers.CharField(source='purpose.name', read_only=True)
    duration_days = serializers.ReadOnlyField()
    
    # Current approver info
    current_approver_name = serializers.SerializerMethodField()
    
    class Meta:
        model = BusinessTripRequest
        fields = [
            'id', 'request_id', 'requester_type', 'employee', 'employee_name', 'employee_id',
            'requested_by', 'requested_by_name', 'travel_type_name', 'transport_type_name',
            'purpose_name', 'start_date', 'end_date', 'duration_days', 'status',
            'estimated_amount', 'approved_amount', 'current_approver_name', 'notes',
            'submitted_at', 'completed_at', 'created_at'
        ]

    def get_current_approver_name(self, obj):
        current_approver = obj.get_current_approver()
        return current_approver.full_name if current_approver else None

class BusinessTripRequestDetailSerializer(serializers.ModelSerializer):
    """Serializer for Business Trip Request detail view"""
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    employee_id = serializers.CharField(source='employee.employee_id', read_only=True)
    employee_job_function = serializers.CharField(source='employee.job_function.name', read_only=True)
    employee_department = serializers.CharField(source='employee.department.name', read_only=True)
    employee_unit = serializers.CharField(source='employee.unit.name', read_only=True)
   
    employee_business_function = serializers.CharField(source='employee.business_function.name', read_only=True)
    employee_phone = serializers.CharField(source='employee.phone', read_only=True)
    
    requested_by_name = serializers.CharField(source='requested_by.full_name', read_only=True)
    travel_type_name = serializers.CharField(source='travel_type.name', read_only=True)
    transport_type_name = serializers.CharField(source='transport_type.name', read_only=True)
    purpose_name = serializers.CharField(source='purpose.name', read_only=True)
    
    line_manager_name = serializers.CharField(source='line_manager.full_name', read_only=True)
    finance_approver_name = serializers.CharField(source='finance_approver.full_name', read_only=True)
    hr_approver_name = serializers.CharField(source='hr_approver.full_name', read_only=True)
    
    duration_days = serializers.ReadOnlyField()
    
    # Related data
    schedules = TripScheduleSerializer(many=True, read_only=True)
    hotels = TripHotelSerializer(many=True, read_only=True)
    approvals = TripApprovalSerializer(many=True, read_only=True)
    
    # Timeline and workflow info
    timeline = serializers.SerializerMethodField()
    current_approver = serializers.SerializerMethodField()
    workflow_info = serializers.SerializerMethodField()
    
    class Meta:
        model = BusinessTripRequest
        fields = [
            'id', 'request_id', 'requester_type', 'employee', 'employee_name', 'employee_id',
            'employee_job_function', 'employee_department', 'employee_unit', 'employee_phone','employee_business_function',
            'requested_by', 'requested_by_name', 'travel_type', 'travel_type_name',
            'transport_type', 'transport_type_name', 'purpose', 'purpose_name',
            'start_date', 'end_date', 'duration_days', 'status', 'workflow',
            'estimated_amount', 'approved_amount', 'line_manager', 'line_manager_name',
            'finance_approver', 'finance_approver_name', 'hr_approver', 'hr_approver_name',
            'phone_number', 'send_sms_reminders', 'notes', 'rejection_reason',
            'schedules', 'hotels', 'approvals', 'timeline', 'current_approver',
            'workflow_info', 'submitted_at', 'completed_at', 'created_at', 'updated_at'
        ]

    def get_timeline(self, obj):
        if obj.workflow:
            return obj.get_timeline()
        return []

    def get_current_approver(self, obj):
        current_approver = obj.get_current_approver()
        if current_approver:
            return {
                'id': current_approver.id,
                'name': current_approver.full_name,
                'employee_id': current_approver.employee_id,
                'email': current_approver.user.email if current_approver.user else None
            }
        return None

    def get_workflow_info(self, obj):
        if obj.workflow:
            return {
                'id': obj.workflow.id,
                'name': obj.workflow.name,
                'description': obj.workflow.description,
                'total_steps': obj.workflow.steps.filter(is_active=True).count(),
                'current_step_order': obj.current_step.step_order if obj.current_step else None,
                'current_step_name': obj.current_step.step_name if obj.current_step else None
            }
        return None

class BusinessTripRequestCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating Business Trip Requests"""
    schedules_data = TripScheduleSerializer(many=True, write_only=True)
    hotels_data = TripHotelSerializer(many=True, write_only=True)
    
    class Meta:
        model = BusinessTripRequest
        fields = [
            'requester_type', 'employee', 'travel_type', 'transport_type', 'purpose',
            'start_date', 'end_date', 'estimated_amount', 'line_manager',
            'finance_approver', 'hr_approver', 'phone_number', 'send_sms_reminders',
            'notes', 'schedules_data', 'hotels_data'
        ]

    def validate(self, data):
        """Validate request data"""
        # Validate dates
        if data['start_date'] >= data['end_date']:
            raise serializers.ValidationError("End date must be after start date")
        
        # Validate schedules
        schedules_data = data.get('schedules_data', [])
        if not schedules_data:
            raise serializers.ValidationError("At least one schedule entry is required")
        
        # Validate schedule dates are within trip period
        for schedule in schedules_data:
            if schedule['date'] < data['start_date'] or schedule['date'] > data['end_date']:
                raise serializers.ValidationError(
                    f"Schedule date {schedule['date']} is outside trip period"
                )
        
        # Validate hotels if provided
        hotels_data = data.get('hotels_data', [])
        for hotel in hotels_data:
            if hotel['check_in_date'] > hotel['check_out_date']:
                raise serializers.ValidationError(
                    f"Hotel check-out date must be after check-in date for {hotel['hotel_name']}"
                )
        
        # Auto-assign line manager if requester_type is FOR_ME
        request = self.context.get('request')
        if request and data.get('requester_type') == 'FOR_ME':
            try:
                employee_profile = Employee.objects.get(user=request.user)
                data['employee'] = employee_profile
                if not data.get('line_manager') and employee_profile.line_manager:
                    data['line_manager'] = employee_profile.line_manager
                if not data.get('phone_number') and employee_profile.phone:
                    data['phone_number'] = employee_profile.phone
            except Employee.DoesNotExist:
                raise serializers.ValidationError("Employee profile not found for current user")
        
        return data

    def create(self, validated_data):
        """Create trip request with schedules and hotels"""
        schedules_data = validated_data.pop('schedules_data', [])
        hotels_data = validated_data.pop('hotels_data', [])
        
        # Set requested_by to current user's employee profile
        request = self.context.get('request')
        if request:
            try:
                requested_by = Employee.objects.get(user=request.user)
                validated_data['requested_by'] = requested_by
            except Employee.DoesNotExist:
                raise serializers.ValidationError("Employee profile not found for current user")
        
        with transaction.atomic():
            # Create trip request
            trip_request = BusinessTripRequest.objects.create(**validated_data)
            
            # Create schedules
            for i, schedule_data in enumerate(schedules_data):
                schedule_data['order'] = i + 1
                TripSchedule.objects.create(trip_request=trip_request, **schedule_data)
            
            # Create hotels
            for hotel_data in hotels_data:
                TripHotel.objects.create(trip_request=trip_request, **hotel_data)
        
        return trip_request

class BusinessTripRequestUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating Business Trip Requests"""
    schedules_data = TripScheduleSerializer(many=True, write_only=True, required=False)
    hotels_data = TripHotelSerializer(many=True, write_only=True, required=False)
    
    class Meta:
        model = BusinessTripRequest
        fields = [
            'travel_type', 'transport_type', 'purpose', 'start_date', 'end_date',
            'estimated_amount', 'finance_approver', 'hr_approver', 'phone_number',
            'send_sms_reminders', 'notes', 'schedules_data', 'hotels_data'
        ]

    def validate(self, data):
        """Validate update data"""
        # Only allow updates if request is in draft status
        if self.instance.status != 'DRAFT':
            raise serializers.ValidationError("Only draft requests can be updated")
        
        # Validate dates if provided
        start_date = data.get('start_date', self.instance.start_date)
        end_date = data.get('end_date', self.instance.end_date)
        
        if start_date >= end_date:
            raise serializers.ValidationError("End date must be after start date")
        
        return data

    def update(self, instance, validated_data):
        """Update trip request with schedules and hotels"""
        schedules_data = validated_data.pop('schedules_data', None)
        hotels_data = validated_data.pop('hotels_data', None)
        
        with transaction.atomic():
            # Update trip request
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()
            
            # Update schedules if provided
            if schedules_data is not None:
                # Delete existing schedules
                instance.schedules.all().delete()
                
                # Create new schedules
                for i, schedule_data in enumerate(schedules_data):
                    schedule_data['order'] = i + 1
                    TripSchedule.objects.create(trip_request=instance, **schedule_data)
            
            # Update hotels if provided
            if hotels_data is not None:
                # Delete existing hotels
                instance.hotels.all().delete()
                
                # Create new hotels
                for hotel_data in hotels_data:
                    TripHotel.objects.create(trip_request=instance, **hotel_data)
        
        return instance

class TripApprovalActionSerializer(serializers.Serializer):
    """Serializer for trip approval actions"""
    ACTION_CHOICES = [
        ('APPROVE', 'Approve'),
        ('REJECT', 'Reject'),
    ]
    
    action = serializers.ChoiceField(choices=ACTION_CHOICES)
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    
    def validate(self, data):
        """Validate approval action"""
        action = data['action']
        
        if action == 'REJECT' and not data.get('notes'):
            raise serializers.ValidationError("Notes are required for rejection")
        
        return data

class TripStatisticsSerializer(serializers.Serializer):
    """Serializer for trip statistics"""
    pending_requests = serializers.IntegerField()
    approved_trips = serializers.IntegerField()
    total_days_this_year = serializers.IntegerField()
    upcoming_trips = serializers.IntegerField()
    
    # Breakdown by status
    by_status = serializers.DictField()
    
    # Breakdown by travel type
    by_travel_type = serializers.DictField()
    
    # Recent activity
    recent_submissions = serializers.IntegerField()
    recent_approvals = serializers.IntegerField()

class EmployeeOptionSerializer(serializers.ModelSerializer):
    """Simplified employee serializer for dropdown options"""
    
    class Meta:
        model = Employee
        fields = ['id', 'employee_id', 'job_function',"phone" ,'full_name', 'job_title', 'department']
        
    department = serializers.CharField(source='department.name', read_only=True)

class PendingApprovalSerializer(serializers.ModelSerializer):
    """Serializer for pending approvals view"""
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    employee_id = serializers.CharField(source='employee.employee_id', read_only=True)
    travel_type_name = serializers.CharField(source='travel_type.name', read_only=True)
    timeline = serializers.SerializerMethodField()
    current_step_info = serializers.SerializerMethodField()
    can_approve = serializers.SerializerMethodField()
    
    class Meta:
        model = BusinessTripRequest
        fields = [
            'id', 'request_id', 'employee_name', 'employee_id', 'travel_type_name',
            'start_date', 'end_date', 'status', 'estimated_amount', 'approved_amount',
            'timeline', 'current_step_info', 'can_approve', 'submitted_at'
        ]

    def get_timeline(self, obj):
        if obj.workflow:
            timeline = []
            for step in obj.workflow.steps.filter(is_active=True).order_by('step_order'):
                approval = obj.approvals.filter(approval_step=step).first()
                timeline.append({
                    'step_name': step.step_name,
                    'is_current': obj.current_step == step if obj.current_step else False,
                    'is_completed': approval is not None,
                    'decision': approval.decision if approval else None
                })
            return timeline
        return []

    def get_current_step_info(self, obj):
        if obj.current_step:
            return {
                'step_name': obj.current_step.step_name,
                'step_type': obj.current_step.step_type,
                'can_edit_amount': obj.current_step.can_edit_amount,
                'requires_amount_entry': obj.current_step.requires_amount_entry
            }
        return None

    def get_can_approve(self, obj):
        """Check if current user can approve this request"""
        request = self.context.get('request')
        if not request or not request.user:
            return False
        
        try:
            current_employee = Employee.objects.get(user=request.user)
            current_approver = obj.get_current_approver()
            return current_approver == current_employee
        except Employee.DoesNotExist:
            return False

