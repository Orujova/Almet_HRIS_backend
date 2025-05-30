# api/serializers.py

from rest_framework import serializers
from django.contrib.auth.models import User
from .models import (
    Employee, BusinessFunction, Department, Unit, JobFunction, 
    PositionGroup, Office, EmployeeTag, EmployeeDocument, 
    EmployeeActivity, MicrosoftUser
)

class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'full_name']
        read_only_fields = ['id', 'username']
    
    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip()

class MicrosoftUserSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = MicrosoftUser
        fields = ['id', 'user', 'microsoft_id']
        read_only_fields = ['id', 'microsoft_id']

# Reference Models Serializers
class BusinessFunctionSerializer(serializers.ModelSerializer):
    class Meta:
        model = BusinessFunction
        fields = ['id', 'name', 'description', 'code', 'is_active']

class DepartmentSerializer(serializers.ModelSerializer):
    business_function_name = serializers.CharField(source='business_function.name', read_only=True)
    
    class Meta:
        model = Department
        fields = ['id', 'name', 'description', 'business_function', 'business_function_name', 'is_active']

class UnitSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source='department.name', read_only=True)
    
    class Meta:
        model = Unit
        fields = ['id', 'name', 'description', 'department', 'department_name', 'is_active']

class JobFunctionSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobFunction
        fields = ['id', 'name', 'description', 'is_active']

class PositionGroupSerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(source='get_name_display', read_only=True)
    
    class Meta:
        model = PositionGroup
        fields = ['id', 'name', 'display_name', 'description', 'hierarchy_level', 'is_active']

class OfficeSerializer(serializers.ModelSerializer):
    business_function_name = serializers.CharField(source='business_function.name', read_only=True)
    
    class Meta:
        model = Office
        fields = ['id', 'name', 'address', 'business_function', 'business_function_name', 'is_active']

class EmployeeTagSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmployeeTag
        fields = ['id', 'name', 'tag_type', 'color', 'description', 'is_active']

class EmployeeDocumentSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.CharField(source='uploaded_by.get_full_name', read_only=True)
    
    class Meta:
        model = EmployeeDocument
        fields = [
            'id', 'name', 'document_type', 'file_path', 'file_size', 
            'mime_type', 'uploaded_at', 'uploaded_by', 'uploaded_by_name'
        ]
        read_only_fields = ['id', 'uploaded_at', 'uploaded_by']

class EmployeeActivitySerializer(serializers.ModelSerializer):
    performed_by_name = serializers.CharField(source='performed_by.get_full_name', read_only=True)
    
    class Meta:
        model = EmployeeActivity
        fields = [
            'id', 'activity_type', 'description', 'timestamp', 
            'performed_by', 'performed_by_name', 'metadata'
        ]
        read_only_fields = ['id', 'timestamp', 'performed_by']

# Employee Serializers
class EmployeeListSerializer(serializers.ModelSerializer):
    """Simplified serializer for employee list views"""
    name = serializers.CharField(source='full_name', read_only=True)
    email = serializers.CharField(source='user.email', read_only=True)
    business_function_name = serializers.CharField(source='business_function.name', read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True)
    unit_name = serializers.CharField(source='unit.name', read_only=True)
    job_function_name = serializers.CharField(source='job_function.name', read_only=True)
    position_group_name = serializers.CharField(source='position_group.get_name_display', read_only=True)
    office_name = serializers.CharField(source='office.name', read_only=True)
    line_manager_name = serializers.CharField(source='line_manager.full_name', read_only=True)
    line_manager_hc_number = serializers.CharField(source='line_manager.employee_id', read_only=True)
    tag_names = serializers.SerializerMethodField()
    
    class Meta:
        model = Employee
        fields = [
            'id', 'employee_id', 'name', 'email', 'date_of_birth', 'phone', 
            'business_function_name', 'department_name', 'unit_name', 
            'job_function_name', 'job_title', 'position_group_name', 'grade',
            'office_name', 'start_date', 'end_date', 'line_manager_name', 
            'line_manager_hc_number', 'status', 'tag_names', 'is_visible_in_org_chart'
        ]
    
    def get_tag_names(self, obj):
        return [tag.name for tag in obj.tags.all()]

class EmployeeDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for single employee views"""
    user = UserSerializer(read_only=True)
    name = serializers.CharField(source='full_name', read_only=True)
    business_function = BusinessFunctionSerializer(read_only=True)
    department = DepartmentSerializer(read_only=True)
    unit = UnitSerializer(read_only=True)
    job_function = JobFunctionSerializer(read_only=True)
    position_group = PositionGroupSerializer(read_only=True)
    office = OfficeSerializer(read_only=True)
    line_manager = serializers.SerializerMethodField()
    direct_reports = serializers.SerializerMethodField()
    tags = EmployeeTagSerializer(many=True, read_only=True)
    documents = EmployeeDocumentSerializer(many=True, read_only=True)
    recent_activities = serializers.SerializerMethodField()
    
    class Meta:
        model = Employee
        fields = [
            'id', 'employee_id', 'user', 'name', 'date_of_birth', 'address', 
            'phone', 'emergency_contact', 'profile_image', 'business_function', 
            'department', 'unit', 'job_function', 'job_title', 'position_group', 
            'grade', 'office', 'start_date', 'end_date', 'line_manager', 
            'direct_reports', 'status', 'tags', 'is_visible_in_org_chart', 
            'notes', 'documents', 'recent_activities', 'created_at', 'updated_at'
        ]
    
    def get_line_manager(self, obj):
        if obj.line_manager:
            return {
                'id': obj.line_manager.id,
                'employee_id': obj.line_manager.employee_id,
                'name': obj.line_manager.full_name,
                'job_title': obj.line_manager.job_title
            }
        return None
    
    
    
    def get_direct_reports(self, obj):
        reports = obj.direct_reports.filter(status='ACTIVE')
        return [
            {
                'id': emp.id,
                'employee_id': emp.employee_id,
                'name': emp.full_name,
                'job_title': emp.job_title
            }
            for emp in reports
        ]
    
    def get_recent_activities(self, obj):
        activities = obj.activities.all()[:5]  # Last 5 activities
        return EmployeeActivitySerializer(activities, many=True).data

class EmployeeCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating and updating employees"""
    # User fields
    first_name = serializers.CharField(write_only=True)
    last_name = serializers.CharField(write_only=True)
    email = serializers.EmailField(write_only=True)
    
    # Tag IDs for many-to-many relationship
    tag_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False,
        allow_empty=True
    )
    
    class Meta:
        model = Employee
        fields = [
            'employee_id', 'first_name', 'last_name', 'email', 'date_of_birth', 
            'address', 'phone', 'emergency_contact', 'profile_image',
            'business_function', 'department', 'unit', 'job_function', 
            'job_title', 'position_group', 'grade', 'office', 'start_date', 
            'end_date', 'line_manager', 'status', 'tag_ids', 
            'is_visible_in_org_chart', 'notes'
        ]
    
    def validate_employee_id(self, value):
        # Check if employee_id is unique (excluding current instance for updates)
        queryset = Employee.objects.filter(employee_id=value)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError("Employee ID must be unique.")
        return value
    
    def validate_email(self, value):
        # Check if email is unique (excluding current instance for updates)
        queryset = User.objects.filter(email=value)
        if self.instance and self.instance.user:
            queryset = queryset.exclude(pk=self.instance.user.pk)
        if queryset.exists():
            raise serializers.ValidationError("Email must be unique.")
        return value
    
    def validate(self, data):
        # Validate that end_date is after start_date
        if data.get('end_date') and data.get('start_date'):
            if data['end_date'] <= data['start_date']:
                raise serializers.ValidationError("End date must be after start date.")
        
        # Validate line manager is not the employee themselves
        if self.instance and data.get('line_manager') == self.instance:
            raise serializers.ValidationError("Employee cannot be their own line manager.")
        
        return data
    
    def create(self, validated_data):
        # Extract user data
        user_data = {
            'first_name': validated_data.pop('first_name'),
            'last_name': validated_data.pop('last_name'),
            'email': validated_data.pop('email'),
            'username': validated_data['employee_id']  # Use employee_id as username
        }
        
        # Extract tag IDs
        tag_ids = validated_data.pop('tag_ids', [])
        
        # Create user
        user = User.objects.create_user(**user_data)
        
        # Create employee
        employee = Employee.objects.create(user=user, **validated_data)
        
        # Set tags
        if tag_ids:
            employee.tags.set(tag_ids)
        
        # Log activity
        EmployeeActivity.objects.create(
            employee=employee,
            activity_type='CREATED',
            description=f"Employee {employee.full_name} was created",
            performed_by=self.context['request'].user if 'request' in self.context else None
        )
        
        return employee
    
    def update(self, instance, validated_data):
        # Extract user data
        user_data = {}
        for field in ['first_name', 'last_name', 'email']:
            if field in validated_data:
                user_data[field] = validated_data.pop(field)
        
        # Extract tag IDs
        tag_ids = validated_data.pop('tag_ids', None)
        
        # Update user
        if user_data:
            for field, value in user_data.items():
                setattr(instance.user, field, value)
            instance.user.save()
        
        # Update employee
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        
        # Update tags
        if tag_ids is not None:
            instance.tags.set(tag_ids)
        
        # Log activity
        EmployeeActivity.objects.create(
            employee=instance,
            activity_type='UPDATED',
            description=f"Employee {instance.full_name} was updated",
            performed_by=self.context['request'].user if 'request' in self.context else None
        )
        
        return instance

# Organizational Structure Serializers
class OrgChartNodeSerializer(serializers.ModelSerializer):
    """Serializer for organizational chart nodes"""
    name = serializers.CharField(source='full_name', read_only=True)
    children = serializers.SerializerMethodField()
    
    class Meta:
        model = Employee
        fields = [
            'id', 'employee_id', 'name', 'job_title', 'position_group', 
            'department', 'business_function', 'profile_image', 'children'
        ]
    
    def get_children(self, obj):
        children = obj.direct_reports.filter(
            status='ACTIVE', 
            is_visible_in_org_chart=True
        ).order_by('position_group__hierarchy_level', 'employee_id')
        
        return OrgChartNodeSerializer(children, many=True, context=self.context).data