# api/training_serializers.py
from rest_framework import serializers
from .training_models import (
    Training, TrainingMaterial, 
    TrainingAssignment, TrainingRequest, TrainingRequestParticipant
)
from .models import Employee
from django.utils import timezone


class TrainingRequestParticipantSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    employee_id_display = serializers.CharField(source='employee.employee_id', read_only=True)
    position = serializers.CharField(source='employee.position_display', read_only=True)
    email = serializers.EmailField(source='employee.email', read_only=True)
    
    class Meta:
        model = TrainingRequestParticipant
        fields = [
            'id', 'employee', 'employee_name', 'employee_id_display',
            'position', 'email', 'added_at'
        ]


class TrainingRequestListSerializer(serializers.ModelSerializer):
    requester_name = serializers.CharField(source='requester.full_name', read_only=True)
    requester_id = serializers.CharField(source='requester.employee_id', read_only=True)
    manager_name = serializers.CharField(source='manager.full_name', read_only=True)
    participants_count = serializers.SerializerMethodField()
    
    class Meta:
        model = TrainingRequest
        fields = [
            'id', 'request_id', 'training_title', 'status',
            'requester_name', 'requester_id', 'manager_name',
            'estimated_cost', 'location', 'created_at',
            'participants_count', 'preferred_dates_start'
        ]
    
    def get_participants_count(self, obj):
        return obj.participants.filter(is_deleted=False).count()


class TrainingRequestDetailSerializer(serializers.ModelSerializer):
    requester_name = serializers.CharField(source='requester.full_name', read_only=True)
    requester_id = serializers.CharField(source='requester.employee_id', read_only=True)
    requester_position = serializers.CharField(source='requester.position_display', read_only=True)
    requester_department = serializers.CharField(source='requester.department.name', read_only=True)
    requester_email = serializers.EmailField(source='requester.email', read_only=True)
    
    manager_name = serializers.CharField(source='manager.full_name', read_only=True)
    manager_email = serializers.EmailField(source='manager.email', read_only=True)
    
    participants = TrainingRequestParticipantSerializer(many=True, read_only=True)
    participants_data = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False,
        help_text="List of employee IDs to add as participants"
    )
    
    class Meta:
        model = TrainingRequest
        fields = '__all__'
        read_only_fields = ['request_id', 'requester', 'manager', 'created_at', 'updated_at', 'created_by']  # 👈 BURDA ƏLAVƏ ET
    
    def create(self, validated_data):
        participants_data = validated_data.pop('participants_data', [])
        request_obj = TrainingRequest.objects.create(**validated_data)
        
        # Add participants if provided (only for managers)
        if participants_data:
            for employee_id in participants_data:
                try:
                    employee = Employee.objects.get(id=employee_id, is_deleted=False)
                    TrainingRequestParticipant.objects.create(
                        training_request=request_obj,
                        employee=employee,
                        added_by=self.context['request'].user
                    )
                except Employee.DoesNotExist:
                    pass
        
        return request_obj
    
    def update(self, instance, validated_data):
        participants_data = validated_data.pop('participants_data', None)
        
        # Update training request fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Update participants if provided
        if participants_data is not None:
            # Remove existing participants
            instance.participants.all().delete()
            
            # Add new participants
            for employee_id in participants_data:
                try:
                    employee = Employee.objects.get(id=employee_id, is_deleted=False)
                    TrainingRequestParticipant.objects.create(
                        training_request=instance,
                        employee=employee,
                        added_by=self.context['request'].user
                    )
                except Employee.DoesNotExist:
                    pass
        
        return instance


class TrainingRequestCreateSerializer(serializers.Serializer):
    """Serializer for creating training request - no requester/manager needed"""
    training_title = serializers.CharField(max_length=300)
    purpose_justification = serializers.CharField()
    training_provider = serializers.CharField(max_length=200, required=False, allow_blank=True)
    preferred_dates_start = serializers.DateField(required=False, allow_null=True)
    preferred_dates_end = serializers.DateField(required=False, allow_null=True)
    duration = serializers.CharField(max_length=100)
    location = serializers.CharField(max_length=200)
    estimated_cost = serializers.DecimalField(max_digits=10, decimal_places=2)
    learning_objectives = serializers.CharField()
    expected_benefits = serializers.CharField()
    participants_data = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        help_text="List of employee IDs (only for managers)"
    )
    
    def validate(self, data):
        # Validate dates
        if data.get('preferred_dates_start') and data.get('preferred_dates_end'):
            if data['preferred_dates_start'] > data['preferred_dates_end']:
                raise serializers.ValidationError(
                    "Start date must be before end date"
                )
        return data


class TrainingRequestApprovalSerializer(serializers.Serializer):
    """Serializer for manager approving/rejecting request"""
    status = serializers.ChoiceField(choices=['APPROVED', 'REJECTED'])
    manager_comments = serializers.CharField(required=False, allow_blank=True)
    
    def validate_status(self, value):
        if value not in ['APPROVED', 'REJECTED']:
            raise serializers.ValidationError("Status must be APPROVED or REJECTED")
        return value

class TrainingMaterialSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()
    file_size_display = serializers.SerializerMethodField()
    uploaded_by_name = serializers.CharField(source='uploaded_by.get_full_name', read_only=True)
    
    class Meta:
        model = TrainingMaterial
        fields = [
            'id', 'file', 'file_url', 
             'file_size', 'file_size_display',
            'uploaded_by_name', 'created_at'
        ]
    
    def get_file_url(self, obj):
        if obj.file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.file.url)
        return None
    
    def get_file_size_display(self, obj):
        """Display file size or link info"""
        parts = []
        
        # Add file size if file exists
        if obj.file and obj.file_size:
            if obj.file_size < 1024:
                parts.append(f"{obj.file_size} B")
            elif obj.file_size < 1024 * 1024:
                parts.append(f"{obj.file_size / 1024:.1f} KB")
            else:
                parts.append(f"{obj.file_size / (1024 * 1024):.1f} MB")
        
     
        
        return " • ".join(parts) if parts else None


class TrainingMaterialCreateSerializer(serializers.Serializer):
    """Serializer for creating training materials within training creation"""

    file = serializers.FileField(required=False, allow_null=True)


    def validate(self, data):
        if not data.get('file') :
            raise serializers.ValidationError(
                "Either 'file'  must be provided"
            )
        return data


class TrainingListSerializer(serializers.ModelSerializer):
    materials_count = serializers.SerializerMethodField()
    assignments_count = serializers.SerializerMethodField()
    completion_rate = serializers.SerializerMethodField()
    
    class Meta:
        model = Training
        fields = [
            'id', 'training_id', 'title', 'description',
            'is_active', 'materials_count',
            'assignments_count', 'completion_rate', 
            'requires_completion', 'created_at'
        ]
    
    def get_materials_count(self, obj):
        return obj.materials.filter(is_deleted=False).count()
    
    def get_assignments_count(self, obj):
        return obj.assignments.filter(is_deleted=False).count()
    
    def get_completion_rate(self, obj):
        total = obj.assignments.filter(is_deleted=False).count()
        if total == 0:
            return 0
        completed = obj.assignments.filter(status='COMPLETED', is_deleted=False).count()
        return round((completed / total) * 100, 2)


class TrainingDetailSerializer(serializers.ModelSerializer):
    materials = TrainingMaterialSerializer(many=True, read_only=True)
    materials_data = TrainingMaterialCreateSerializer(many=True, write_only=True, required=False)
    
    # Organizational filters
    business_function_names = serializers.SerializerMethodField()
    department_names = serializers.SerializerMethodField()
    position_group_names = serializers.SerializerMethodField()
    
    # Statistics
    total_assignments = serializers.SerializerMethodField()
    completed_assignments = serializers.SerializerMethodField()
    in_progress_assignments = serializers.SerializerMethodField()
    overdue_assignments = serializers.SerializerMethodField()
    completion_rate = serializers.SerializerMethodField()
    average_completion_time = serializers.SerializerMethodField()
    
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    
    class Meta:
        model = Training
        fields = '__all__'
        extra_kwargs = {
            'materials_data': {'write_only': True}
        }
    
    def create(self, validated_data):
        materials_data = validated_data.pop('materials_data', [])
        training = Training.objects.create(**validated_data)
        
        # Create materials
        for material_data in materials_data:
            material = TrainingMaterial.objects.create(
                training=training,
                uploaded_by=self.context['request'].user,
                **material_data
            )
            if material.file:
                material.file_size = material.file.size
                material.save()
        
        return training
    
    def update(self, instance, validated_data):
        materials_data = validated_data.pop('materials_data', None)
        
        # Update training fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Update materials if provided
        if materials_data is not None:
            for material_data in materials_data:
                material = TrainingMaterial.objects.create(
                    training=instance,
                    uploaded_by=self.context['request'].user,
                    **material_data
                )
                if material.file:
                    material.file_size = material.file.size
                    material.save()
        
        return instance
    
    def get_business_function_names(self, obj):
        return [bf.name for bf in obj.business_functions.all()]
    
    def get_department_names(self, obj):
        return [dept.name for dept in obj.departments.all()]
    
    def get_position_group_names(self, obj):
        return [pg.get_name_display() for pg in obj.position_groups.all()]
    
    def get_total_assignments(self, obj):
        return obj.assignments.filter(is_deleted=False).count()
    
    def get_completed_assignments(self, obj):
        return obj.assignments.filter(status='COMPLETED', is_deleted=False).count()
    
    def get_in_progress_assignments(self, obj):
        return obj.assignments.filter(status='IN_PROGRESS', is_deleted=False).count()
    
    def get_overdue_assignments(self, obj):
        return obj.assignments.filter(status='OVERDUE', is_deleted=False).count()
    
    def get_completion_rate(self, obj):
        total = self.get_total_assignments(obj)
        if total == 0:
            return 0
        completed = self.get_completed_assignments(obj)
        return round((completed / total) * 100, 2)
    
    def get_average_completion_time(self, obj):
        from django.db.models import Avg, F, ExpressionWrapper, fields
        
        completed = obj.assignments.filter(
            status='COMPLETED',
            is_deleted=False,
            completed_date__isnull=False
        )
        
        if not completed.exists():
            return None
        
        avg_delta = completed.annotate(
            completion_time=ExpressionWrapper(
                F('completed_date') - F('assigned_date'),
                output_field=fields.DurationField()
            )
        ).aggregate(avg_time=Avg('completion_time'))
        
        if avg_delta['avg_time']:
            days = avg_delta['avg_time'].days
            return f"{days} days"
        
        return None


class TrainingAssignmentSerializer(serializers.ModelSerializer):
    training_title = serializers.CharField(source='training.title', read_only=True)
    training_id = serializers.CharField(source='training.training_id', read_only=True)
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    employee_id = serializers.CharField(source='employee.employee_id', read_only=True)
    assigned_by_name = serializers.CharField(source='assigned_by.get_full_name', read_only=True)
    
    materials_completed_count = serializers.SerializerMethodField()
    total_materials = serializers.SerializerMethodField()
    is_overdue = serializers.SerializerMethodField()
    days_until_due = serializers.SerializerMethodField()
    
    class Meta:
        model = TrainingAssignment
        fields = [
            'id', 'training', 'training_title', 'training_id',
            'employee', 'employee_name', 'employee_id',
            'status', 'assigned_date', 'due_date', 'started_date',
            'completed_date', 'progress_percentage', 'is_mandatory',
            'materials_completed_count', 'total_materials',
            'is_overdue', 'days_until_due', 'assigned_by_name',
            'completion_notes', 'created_at', 'updated_at'
        ]
    
    def get_materials_completed_count(self, obj):
        return obj.materials_completed.count()
    
    def get_total_materials(self, obj):
        # is_mandatory filter-i SİLDİK
        return obj.training.materials.filter(is_deleted=False).count()
    
    def get_is_overdue(self, obj):
        return obj.is_overdue()
    
    def get_days_until_due(self, obj):
        if obj.due_date and obj.status not in ['COMPLETED', 'CANCELLED']:
            delta = (obj.due_date - timezone.now().date()).days
            return delta
        return None


class BulkTrainingAssignmentSerializer(serializers.Serializer):
    """Bulk training assignment - multiple trainings to multiple employees"""
    training_ids = serializers.ListField(
        child=serializers.IntegerField(),
        help_text="List of training IDs to assign"
    )
    employee_ids = serializers.ListField(
        child=serializers.IntegerField(),
        help_text="List of employee IDs to assign trainings"
    )
    due_date = serializers.DateField(required=False, allow_null=True)
    is_mandatory = serializers.BooleanField(default=False)
    notes = serializers.CharField(max_length=500, required=False, allow_blank=True)
    
    def validate_training_ids(self, value):
        if not value:
            raise serializers.ValidationError("At least one training ID is required.")
        return value
    
    def validate_employee_ids(self, value):
        if not value:
            raise serializers.ValidationError("At least one employee ID is required.")
        return value


class TrainingAssignByTrainingSerializer(serializers.Serializer):
    """Assign one training to multiple employees"""
    training_id = serializers.IntegerField()
    employee_ids = serializers.ListField(child=serializers.IntegerField())
    due_date = serializers.DateField(required=False, allow_null=True)
    is_mandatory = serializers.BooleanField(default=False)


class TrainingAssignToEmployeeSerializer(serializers.Serializer):
    """Assign multiple trainings to one employee"""
    employee_id = serializers.IntegerField()
    training_ids = serializers.ListField(child=serializers.IntegerField())
    due_date = serializers.DateField(required=False, allow_null=True)
    is_mandatory = serializers.BooleanField(default=False)


class TrainingMaterialUploadSerializer(serializers.Serializer):
    """Serializer for uploading training materials"""
    file = serializers.FileField(required=False, allow_null=True)

    
    def validate(self, data):
        """Validate that either filenk is provided"""
        if not data.get('file'):
            raise serializers.ValidationError(
                "Either 'file'  must be provided"
            )
        return data