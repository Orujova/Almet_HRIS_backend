# api/serializers.py

from rest_framework import serializers
from django.contrib.auth.models import User
from .models import (
    Employee, BusinessFunction, Department, Unit, JobFunction, 
    PositionGroup, EmployeeTag, EmployeeDocument, EmployeeStatus,
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

# Reference Models Serializers with CRUD
class BusinessFunctionSerializer(serializers.ModelSerializer):
    class Meta:
        model = BusinessFunction
        fields = ['id', 'name', 'code', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

class DepartmentSerializer(serializers.ModelSerializer):
    business_function_name = serializers.CharField(source='business_function.name', read_only=True)
    
    class Meta:
        model = Department
        fields = ['id', 'name', 'business_function', 'business_function_name', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

class UnitSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source='department.name', read_only=True)
    business_function_name = serializers.CharField(source='department.business_function.name', read_only=True)
    
    class Meta:
        model = Unit
        fields = ['id', 'name', 'department', 'department_name', 'business_function_name', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

class JobFunctionSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobFunction
        fields = ['id', 'name', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

class PositionGroupSerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(source='get_name_display', read_only=True)
    
    class Meta:
        model = PositionGroup
        fields = ['id', 'name', 'display_name', 'hierarchy_level', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

class EmployeeTagSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmployeeTag
        fields = ['id', 'name', 'tag_type', 'color', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

class EmployeeStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmployeeStatus
        fields = ['id', 'name', 'color', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

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
    line_manager_name = serializers.CharField(source='line_manager.full_name', read_only=True)
    line_manager_hc_number = serializers.CharField(source='line_manager.employee_id', read_only=True)
    status_name = serializers.CharField(source='status.name', read_only=True)
    tag_names = serializers.SerializerMethodField()
    
    class Meta:
        model = Employee
        fields = [
            'id', 'employee_id', 'name', 'email', 'date_of_birth', 'gender', 'phone', 
            'business_function_name', 'department_name', 'unit_name', 
            'job_function_name', 'job_title', 'position_group_name', 'grade',
            'start_date', 'end_date', 'line_manager_name', 
            'line_manager_hc_number', 'status_name', 'tag_names'
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
    status = EmployeeStatusSerializer(read_only=True)
    line_manager = serializers.SerializerMethodField()
    direct_reports = serializers.SerializerMethodField()
    tags = EmployeeTagSerializer(many=True, read_only=True)
    documents = EmployeeDocumentSerializer(many=True, read_only=True)
    recent_activities = serializers.SerializerMethodField()
    
    class Meta:
        model = Employee
        fields = [
            'id', 'employee_id', 'user', 'name', 'date_of_birth', 'gender', 'address', 
            'phone', 'emergency_contact', 'profile_image', 'business_function', 
            'department', 'unit', 'job_function', 'job_title', 'position_group', 
            'grade', 'start_date', 'end_date', 'line_manager', 
            'direct_reports', 'status', 'tags', 
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
        reports = obj.direct_reports.filter(status__name='ACTIVE')
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
    
    # Documents for upload during creation/update
    documents = serializers.ListField(
        child=serializers.DictField(),
        write_only=True,
        required=False,
        allow_empty=True,
        help_text="List of documents to upload. Each document should have: name, document_type, file_path"
    )
    
    # Unit və Line Manager optional edin
    unit = serializers.PrimaryKeyRelatedField(
        queryset=Unit.objects.all(),
        required=False,
        allow_null=True
    )
    
    line_manager = serializers.PrimaryKeyRelatedField(
        queryset=Employee.objects.all(),
        required=False,
        allow_null=True
    )
    
    class Meta:
        model = Employee
        fields = [
            'employee_id', 'first_name', 'last_name', 'email', 'date_of_birth', 
            'gender', 'address', 'phone', 'emergency_contact', 'profile_image',
            'business_function', 'department', 'unit', 'job_function', 
            'job_title', 'position_group', 'grade', 'start_date', 
            'end_date', 'line_manager', 'status', 'tag_ids', 'notes', 'documents'
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
    
    def validate_documents(self, value):
        """Validate document data"""
        if not value:
            return value
            
        valid_document_types = [choice[0] for choice in EmployeeDocument.DOCUMENT_TYPES]
        
        for doc in value:
            # Check required fields
            if not all(key in doc for key in ['name', 'document_type', 'file_path']):
                raise serializers.ValidationError(
                    "Each document must have 'name', 'document_type', and 'file_path' fields"
                )
            
            # Validate document type
            if doc['document_type'] not in valid_document_types:
                raise serializers.ValidationError(
                    f"Invalid document_type '{doc['document_type']}'. Valid types: {valid_document_types}"
                )
        
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
        
        # Extract tag IDs and documents
        tag_ids = validated_data.pop('tag_ids', [])
        documents_data = validated_data.pop('documents', [])
        
        # Create user
        user = User.objects.create_user(**user_data)
        
        # Create employee - explicit None handling üçün unit və line_manager
        unit = validated_data.pop('unit', None)
        line_manager = validated_data.pop('line_manager', None)
        
        employee = Employee.objects.create(
            user=user, 
            unit=unit,
            line_manager=line_manager,
            **validated_data
        )
        
        # Set tags
        if tag_ids:
            employee.tags.set(tag_ids)
        
        # Create documents
        if documents_data:
            self._create_documents(employee, documents_data)
        
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
        
        # Extract tag IDs and documents
        tag_ids = validated_data.pop('tag_ids', None)
        documents_data = validated_data.pop('documents', [])
        
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
        
        # Create new documents (if any)
        if documents_data:
            self._create_documents(instance, documents_data)
        
        # Log activity
        EmployeeActivity.objects.create(
            employee=instance,
            activity_type='UPDATED',
            description=f"Employee {instance.full_name} was updated",
            performed_by=self.context['request'].user if 'request' in self.context else None
        )
        
        return instance
    
    def _create_documents(self, employee, documents_data):
        """Helper method to create documents for an employee"""
        request_user = self.context.get('request').user if 'request' in self.context else None
        
        for doc_data in documents_data:
            EmployeeDocument.objects.create(
                employee=employee,
                name=doc_data['name'],
                document_type=doc_data['document_type'],
                file_path=doc_data['file_path'],
                file_size=doc_data.get('file_size'),
                mime_type=doc_data.get('mime_type'),
                uploaded_by=request_user
            )
            
            # Log document upload activity
            if request_user:
                EmployeeActivity.objects.create(
                    employee=employee,
                    activity_type='DOCUMENT_UPLOADED',
                    description=f"Document '{doc_data['name']}' was uploaded for {employee.full_name}",
                    performed_by=request_user,
                    metadata={'document_name': doc_data['name'], 'document_type': doc_data['document_type']}
                )



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
            status__name='ACTIVE', 
            is_visible_in_org_chart=True
        ).order_by('position_group__hierarchy_level', 'employee_id')
        
        return OrgChartNodeSerializer(children, many=True, context=self.context).data

# Org Chart Visibility Serializer
class EmployeeOrgChartVisibilitySerializer(serializers.ModelSerializer):
    """Serializer for updating org chart visibility"""
    
    class Meta:
        model = Employee
        fields = ['id', 'employee_id', 'is_visible_in_org_chart']
        read_only_fields = ['id', 'employee_id']
    
    def update(self, instance, validated_data):
        old_visibility = instance.is_visible_in_org_chart
        new_visibility = validated_data.get('is_visible_in_org_chart', old_visibility)
        
        instance.is_visible_in_org_chart = new_visibility
        instance.save()
        
        # Log activity if visibility changed
        if old_visibility != new_visibility:
            EmployeeActivity.objects.create(
                employee=instance,
                activity_type='ORG_CHART_VISIBILITY_CHANGED',
                description=f"Org chart visibility changed from {old_visibility} to {new_visibility} for {instance.full_name}",
                performed_by=self.context['request'].user if 'request' in self.context else None,
                metadata={'old_visibility': old_visibility, 'new_visibility': new_visibility}
            )
        
        return instance