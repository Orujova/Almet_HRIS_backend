# api/training_serializers.py
from rest_framework import serializers
from .training_models import (
 Training, TrainingMaterial, 
    TrainingAssignment, TrainingActivity
)
from .models import Employee
from django.utils import timezone
# api/training_serializers.py

# Əvvəlki import-ların sonuna əlavə et
from rest_framework import serializers

# Faylın sonuna əlavə et:


class TrainingMaterialSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()
    file_size_display = serializers.SerializerMethodField()
    uploaded_by_name = serializers.CharField(source='uploaded_by.get_full_name', read_only=True)
    
    class Meta:
        model = TrainingMaterial
        fields = [
            'id', 'title', 'material_type', 'file', 'file_url', 
            'external_link', 'file_size', 'file_size_display',
            'duration_minutes',  'is_required',
            'uploaded_by_name', 'created_at'
        ]
    
    def get_file_url(self, obj):
        if obj.file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.file.url)
        return None
    
    def get_file_size_display(self, obj):
        if obj.file_size:
            if obj.file_size < 1024:
                return f"{obj.file_size} B"
            elif obj.file_size < 1024 * 1024:
                return f"{obj.file_size / 1024:.1f} KB"
            else:
                return f"{obj.file_size / (1024 * 1024):.1f} MB"
        return "N/A"

class TrainingListSerializer(serializers.ModelSerializer):
  

    materials_count = serializers.SerializerMethodField()
    assignments_count = serializers.SerializerMethodField()
    completion_rate = serializers.SerializerMethodField()
    
    class Meta:
        model = Training
        fields = [
            'id', 'training_id', 'title', 'description',
          'training_type',
            'difficulty_level', 'estimated_duration_hours',
            'priority', 'is_active', 'materials_count',
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
        from datetime import timedelta
        
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
        return obj.training.materials.filter(is_required=True).count()
    
    def get_is_overdue(self, obj):
        return obj.is_overdue()
    
    def get_days_until_due(self, obj):
        if obj.due_date and obj.status not in ['COMPLETED', 'CANCELLED']:
            delta = (obj.due_date - timezone.now().date()).days
            return delta
        return None

class BulkTrainingAssignmentSerializer(serializers.Serializer):
    """Bulk training assignment"""
    training_id = serializers.IntegerField()
    employee_ids = serializers.ListField(
        child=serializers.IntegerField(),
        help_text="List of employee IDs to assign training"
    )
    due_date = serializers.DateField(required=False, allow_null=True)
    is_mandatory = serializers.BooleanField(default=False)
    notes = serializers.CharField(max_length=500, required=False, allow_blank=True)
    
    def validate_training_id(self, value):
        try:
            Training.objects.get(id=value, is_active=True)
        except Training.DoesNotExist:
            raise serializers.ValidationError("Training not found or inactive.")
        return value
    
    def validate_employee_ids(self, value):
        if not value:
            raise serializers.ValidationError("At least one employee ID is required.")
        
        employees = Employee.objects.filter(id__in=value, is_deleted=False)
        if employees.count() != len(value):
            raise serializers.ValidationError("Some employee IDs not found.")
        
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
    title = serializers.CharField(max_length=200, required=True)
    material_type = serializers.ChoiceField(
        choices=['PDF', 'VIDEO', 'PRESENTATION', 'DOCUMENT', 'LINK', 'OTHER'],
        required=True
    )
    file = serializers.FileField(required=False, allow_null=True)
    external_link = serializers.URLField(max_length=500, required=False, allow_blank=True, allow_null=True)
    is_required = serializers.BooleanField(default=True, required=False)

    duration_minutes = serializers.IntegerField(required=False, allow_null=True)
    
    def validate(self, data):
        """Validate that either file or external_link is provided"""
        if not data.get('file') and not data.get('external_link'):
            raise serializers.ValidationError(
                "Either 'file' or 'external_link' must be provided"
            )
        return data    