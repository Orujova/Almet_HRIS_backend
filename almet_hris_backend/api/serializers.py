# api/serializers.py - ENHANCED: Complete Employee Management with Grading Integration

from rest_framework import serializers
from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone
from datetime import date, timedelta
from .models import (
    Employee, BusinessFunction, Department, Unit, JobFunction,
    PositionGroup, EmployeeTag, EmployeeStatus, EmployeeDocument,
    VacantPosition, EmployeeActivity, HeadcountSummary
)
import logging

logger = logging.getLogger(__name__)

class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'full_name']
        read_only_fields = ['id', 'username']
    
    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip()

class BusinessFunctionSerializer(serializers.ModelSerializer):
    employee_count = serializers.SerializerMethodField()
    
    class Meta:
        model = BusinessFunction
        fields = ['id', 'name', 'code', 'description', 'is_active', 'employee_count', 'created_at']
    
    def get_employee_count(self, obj):
        return obj.employees.filter(status__affects_headcount=True).count()

class DepartmentSerializer(serializers.ModelSerializer):
    business_function_name = serializers.CharField(source='business_function.name', read_only=True)
    business_function_code = serializers.CharField(source='business_function.code', read_only=True)
    head_name = serializers.CharField(source='head_of_department.full_name', read_only=True)
    employee_count = serializers.SerializerMethodField()
    unit_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Department
        fields = [
            'id', 'name', 'business_function', 'business_function_name', 
            'business_function_code', 'head_of_department', 'head_name', 
            'is_active', 'employee_count', 'unit_count', 'created_at'
        ]
    
    def get_employee_count(self, obj):
        return obj.employees.filter(status__affects_headcount=True).count()
    
    def get_unit_count(self, obj):
        return obj.units.filter(is_active=True).count()

class UnitSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source='department.name', read_only=True)
    business_function_name = serializers.CharField(source='department.business_function.name', read_only=True)
    unit_head_name = serializers.CharField(source='unit_head.full_name', read_only=True)
    employee_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Unit
        fields = [
            'id', 'name', 'department', 'department_name',
            'business_function_name', 'unit_head', 'unit_head_name',
            'is_active', 'employee_count', 'created_at'
        ]
    
    def get_employee_count(self, obj):
        return obj.employees.filter(status__affects_headcount=True).count()

class JobFunctionSerializer(serializers.ModelSerializer):
    employee_count = serializers.SerializerMethodField()
    
    class Meta:
        model = JobFunction
        fields = ['id', 'name', 'description', 'is_active', 'employee_count', 'created_at']
    
    def get_employee_count(self, obj):
        return obj.employees.filter(status__affects_headcount=True).count()

# Enhanced Position Group Serializer with Grading Integration
class PositionGroupSerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(source='get_name_display', read_only=True)
    grading_levels = serializers.SerializerMethodField()
    employee_count = serializers.SerializerMethodField()
    grading_shorthand = serializers.CharField(read_only=True)
    
    class Meta:
        model = PositionGroup
        fields = [
            'id', 'name', 'display_name', 'hierarchy_level', 'grading_shorthand',
            'grading_levels', 'is_active', 'employee_count', 'created_at'
        ]
    
    def get_grading_levels(self, obj):
        """Get grading level options for this position"""
        return obj.get_grading_levels()
    
    def get_employee_count(self, obj):
        return obj.employees.filter(status__affects_headcount=True).count()

# Employee Tag Serializer
class EmployeeTagSerializer(serializers.ModelSerializer):
    employee_count = serializers.SerializerMethodField()
    
    class Meta:
        model = EmployeeTag
        fields = ['id', 'name', 'tag_type', 'color', 'is_active', 'employee_count', 'created_at']
    
    def get_employee_count(self, obj):
        return obj.employees.filter(status__affects_headcount=True).count()

# Employee Status Serializer with Enhanced Features
class EmployeeStatusSerializer(serializers.ModelSerializer):
    employee_count = serializers.SerializerMethodField()
    
    class Meta:
        model = EmployeeStatus
        fields = [
            'id', 'name', 'status_type', 'color', 'affects_headcount', 
            'allows_org_chart', 'is_active', 'employee_count', 'created_at',
            'onboarding_duration', 'probation_duration_3m', 'probation_duration_6m',
            'probation_duration_1y', 'probation_duration_2y', 'probation_duration_3y',
            'probation_duration_permanent'
        ]
    
    def get_employee_count(self, obj):
        return obj.employees.count()

# Vacant Position Serializers
class VacantPositionListSerializer(serializers.ModelSerializer):
    business_function_name = serializers.CharField(source='business_function.name', read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True)
    unit_name = serializers.CharField(source='unit.name', read_only=True)
    job_function_name = serializers.CharField(source='job_function.name', read_only=True)
    position_group_name = serializers.CharField(source='position_group.get_name_display', read_only=True)
    reporting_to_name = serializers.CharField(source='reporting_to.full_name', read_only=True)
    filled_by_name = serializers.CharField(source='filled_by.full_name', read_only=True)
    days_open = serializers.SerializerMethodField()
    
    class Meta:
        model = VacantPosition
        fields = [
            'id', 'position_id', 'title', 'business_function_name', 'department_name',
            'unit_name', 'job_function_name', 'position_group_name', 'vacancy_type',
            'urgency', 'expected_start_date', 'reporting_to_name', 'is_filled',
            'filled_by_name', 'filled_date', 'days_open', 'created_at'
        ]
    
    def get_days_open(self, obj):
        if obj.is_filled and obj.filled_date:
            delta = obj.filled_date - obj.created_at.date()
        else:
            delta = timezone.now().date() - obj.created_at.date()
        return delta.days

class VacantPositionDetailSerializer(serializers.ModelSerializer):
    business_function_name = serializers.CharField(source='business_function.name', read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True)
    unit_name = serializers.CharField(source='unit.name', read_only=True)
    job_function_name = serializers.CharField(source='job_function.name', read_only=True)
    position_group_name = serializers.CharField(source='position_group.get_name_display', read_only=True)
    reporting_to_name = serializers.CharField(source='reporting_to.full_name', read_only=True)
    filled_by_name = serializers.CharField(source='filled_by.full_name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    
    class Meta:
        model = VacantPosition
        fields = '__all__'

class VacantPositionCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = VacantPosition
        exclude = ['filled_by', 'filled_date', 'is_filled']
    
    def create(self, validated_data):
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)

# Employee Document Serializer
class EmployeeDocumentSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.CharField(source='uploaded_by.username', read_only=True)
    file_size_display = serializers.SerializerMethodField()
    
    class Meta:
        model = EmployeeDocument
        fields = [
            'id', 'name', 'document_type', 'file_path', 'file_size',
            'file_size_display', 'mime_type', 'uploaded_at', 'uploaded_by_name'
        ]
    
    def get_file_size_display(self, obj):
        if obj.file_size:
            if obj.file_size < 1024:
                return f"{obj.file_size} B"
            elif obj.file_size < 1024 * 1024:
                return f"{obj.file_size / 1024:.1f} KB"
            else:
                return f"{obj.file_size / (1024 * 1024):.1f} MB"
        return "Unknown"

# Employee Activity Serializer
class EmployeeActivitySerializer(serializers.ModelSerializer):
    performed_by_name = serializers.CharField(source='performed_by.username', read_only=True)
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    
    class Meta:
        model = EmployeeActivity
        fields = [
            'id', 'employee', 'employee_name', 'activity_type', 'description',
            'performed_by', 'performed_by_name', 'metadata', 'created_at'
        ]

# Main Employee Serializers
class EmployeeListSerializer(serializers.ModelSerializer):
    """Enhanced serializer for employee list views with grading integration"""
    name = serializers.CharField(source='full_name', read_only=True)
    email = serializers.CharField(source='user.email', read_only=True)
    business_function_name = serializers.CharField(source='business_function.name', read_only=True)
    business_function_code = serializers.CharField(source='business_function.code', read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True)
    unit_name = serializers.CharField(source='unit.name', read_only=True)
    job_function_name = serializers.CharField(source='job_function.name', read_only=True)
    position_group_name = serializers.CharField(source='position_group.get_name_display', read_only=True)
    position_group_level = serializers.IntegerField(source='position_group.hierarchy_level', read_only=True)
    line_manager_name = serializers.CharField(source='line_manager.full_name', read_only=True)
    line_manager_hc_number = serializers.CharField(source='line_manager.employee_id', read_only=True)
    status_name = serializers.CharField(source='status.name', read_only=True)
    status_color = serializers.CharField(source='status.color', read_only=True)
    tag_names = serializers.SerializerMethodField()
    years_of_service = serializers.ReadOnlyField()
    current_status_display = serializers.ReadOnlyField()
    contract_duration_display = serializers.CharField(source='get_contract_duration_display', read_only=True)
    grading_display = serializers.CharField(source='get_grading_display', read_only=True)
    contract_end_date = serializers.DateField(read_only=True)
    direct_reports_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Employee
        fields = [
            'id', 'employee_id', 'name', 'email', 'date_of_birth', 'gender', 'phone',
            'business_function_name', 'business_function_code', 'department_name', 'unit_name',
            'job_function_name', 'job_title', 'position_group_name', 'position_group_level',
            'grading_level', 'grading_display', 'start_date', 'end_date',
            'contract_duration', 'contract_duration_display', 'contract_start_date', 'contract_end_date',
            'line_manager_name', 'line_manager_hc_number', 'status_name', 'status_color',
            'tag_names', 'years_of_service', 'current_status_display', 'is_visible_in_org_chart',
            'direct_reports_count', 'created_at', 'updated_at'
        ]
    
    def get_tag_names(self, obj):
        return [
            {
                'id': tag.id,
                'name': tag.name,
                'color': tag.color,
                'type': tag.tag_type
            }
            for tag in obj.tags.filter(is_active=True)
        ]
    
    def get_direct_reports_count(self, obj):
        return obj.get_direct_reports_count()

class EmployeeDetailSerializer(serializers.ModelSerializer):
    """Detailed employee serializer for individual views"""
    name = serializers.CharField(source='full_name', read_only=True)
    email = serializers.CharField(source='user.email', read_only=True)
    first_name = serializers.CharField(source='user.first_name', read_only=True)
    last_name = serializers.CharField(source='user.last_name', read_only=True)
    
    # Related objects
    business_function_detail = BusinessFunctionSerializer(source='business_function', read_only=True)
    department_detail = DepartmentSerializer(source='department', read_only=True)
    unit_detail = UnitSerializer(source='unit', read_only=True)
    job_function_detail = JobFunctionSerializer(source='job_function', read_only=True)
    position_group_detail = PositionGroupSerializer(source='position_group', read_only=True)
    status_detail = EmployeeStatusSerializer(source='status', read_only=True)
    line_manager_detail = serializers.SerializerMethodField()
    
    # Enhanced fields
    documents = EmployeeDocumentSerializer(many=True, read_only=True)
    activities = EmployeeActivitySerializer(many=True, read_only=True)
    tag_details = EmployeeTagSerializer(source='tags', many=True, read_only=True)
    direct_reports = serializers.SerializerMethodField()
    
    # Calculated fields
    years_of_service = serializers.ReadOnlyField()
    grading_display = serializers.CharField(source='get_grading_display', read_only=True)
    contract_duration_display = serializers.CharField(source='get_contract_duration_display', read_only=True)
    
    # Vacancy information
    filled_vacancy_detail = VacantPositionListSerializer(source='filled_vacancy', read_only=True)
    
    class Meta:
        model = Employee
        fields = '__all__'
    
    def get_line_manager_detail(self, obj):
        if obj.line_manager:
            return {
                'id': obj.line_manager.id,
                'employee_id': obj.line_manager.employee_id,
                'name': obj.line_manager.full_name,
                'job_title': obj.line_manager.job_title,
                'email': obj.line_manager.user.email if obj.line_manager.user else None
            }
        return None
    
    def get_direct_reports(self, obj):
        reports = obj.direct_reports.filter(status__affects_headcount=True)[:5]  # Limit to 5
        return [
            {
                'id': emp.id,
                'employee_id': emp.employee_id,
                'name': emp.full_name,
                'job_title': emp.job_title
            }
            for emp in reports
        ]

class EmployeeCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating and updating employees with enhanced validation"""
    first_name = serializers.CharField(write_only=True)
    last_name = serializers.CharField(write_only=True)
    email = serializers.EmailField(write_only=True)
    tag_ids = serializers.ListField(child=serializers.IntegerField(), write_only=True, required=False)
    vacancy_id = serializers.IntegerField(write_only=True, required=False, help_text="Link to vacant position")
    
    class Meta:
        model = Employee
        exclude = ['user', 'full_name', 'tags', 'filled_vacancy', 'status']  # Status auto-assigned
    
    def validate_employee_id(self, value):
        if self.instance:
            # Updating existing employee
            if Employee.objects.filter(employee_id=value).exclude(id=self.instance.id).exists():
                raise serializers.ValidationError("Employee ID already exists.")
        else:
            # Creating new employee
            if Employee.objects.filter(employee_id=value).exists():
                raise serializers.ValidationError("Employee ID already exists.")
        return value
    
    def validate_email(self, value):
        if self.instance and self.instance.user:
            # Updating existing employee
            if User.objects.filter(email=value).exclude(id=self.instance.user.id).exists():
                raise serializers.ValidationError("Email already exists.")
        else:
            # Creating new employee
            if User.objects.filter(email=value).exists():
                raise serializers.ValidationError("Email already exists.")
        return value
    
    def validate_grading_level(self, value):
        """Validate grading level matches position group"""
        position_group = self.validated_data.get('position_group') or (self.instance.position_group if self.instance else None)
        if value and position_group:
            expected_prefix = position_group.grading_shorthand
            if not value.startswith(expected_prefix):
                raise serializers.ValidationError(
                    f"Grading level must start with {expected_prefix} for this position group."
                )
        return value
    
    @transaction.atomic
    def create(self, validated_data):
        # Extract user data
        first_name = validated_data.pop('first_name')
        last_name = validated_data.pop('last_name')
        email = validated_data.pop('email')
        tag_ids = validated_data.pop('tag_ids', [])
        vacancy_id = validated_data.pop('vacancy_id', None)
        
        # Create user
        user = User.objects.create_user(
            username=email,
            email=email,
            first_name=first_name,
            last_name=last_name
        )
        
        # Create employee
        validated_data['user'] = user
        if vacancy_id:
            validated_data['_vacancy_id'] = vacancy_id
        
        # Set contract_start_date to start_date if not provided
        if not validated_data.get('contract_start_date'):
            validated_data['contract_start_date'] = validated_data.get('start_date')
        
        employee = super().create(validated_data)
        
        # Add tags
        if tag_ids:
            employee.tags.set(tag_ids)
        
        # Log activity
        EmployeeActivity.objects.create(
            employee=employee,
            activity_type='CREATED',
            description=f"Employee {employee.full_name} was created",
            performed_by=self.context['request'].user
        )
        
        return employee
    
    @transaction.atomic
    def update(self, instance, validated_data):
        # Extract user data
        first_name = validated_data.pop('first_name', None)
        last_name = validated_data.pop('last_name', None)
        email = validated_data.pop('email', None)
        tag_ids = validated_data.pop('tag_ids', None)
        vacancy_id = validated_data.pop('vacancy_id', None)
        
        # Track changes for activity log
        changes = []
        
        # Update user if data provided
        if any([first_name, last_name, email]):
            user = instance.user
            if first_name and user.first_name != first_name:
                user.first_name = first_name
                changes.append(f"First name changed to {first_name}")
            if last_name and user.last_name != last_name:
                user.last_name = last_name
                changes.append(f"Last name changed to {last_name}")
            if email and user.email != email:
                user.email = email
                user.username = email
                changes.append(f"Email changed to {email}")
            user.save()
        
        # Track other significant changes
        if 'line_manager' in validated_data and validated_data['line_manager'] != instance.line_manager:
            old_manager = instance.line_manager.full_name if instance.line_manager else "None"
            new_manager = validated_data['line_manager'].full_name if validated_data['line_manager'] else "None"
            changes.append(f"Line manager changed from {old_manager} to {new_manager}")
        
        if 'position_group' in validated_data and validated_data['position_group'] != instance.position_group:
            changes.append(f"Position changed from {instance.position_group.get_name_display()} to {validated_data['position_group'].get_name_display()}")
        
        if 'grading_level' in validated_data and validated_data['grading_level'] != instance.grading_level:
            changes.append(f"Grading level changed from {instance.grading_level} to {validated_data['grading_level']}")
        
        # Update employee
        employee = super().update(instance, validated_data)
        
        # Update tags
        if tag_ids is not None:
            employee.tags.set(tag_ids)
            changes.append("Tags updated")
        
        # Link to vacancy if provided
        if vacancy_id:
            try:
                vacancy = VacantPosition.objects.get(id=vacancy_id, is_filled=False)
                vacancy.mark_as_filled(employee)
                changes.append(f"Linked to vacant position {vacancy.position_id}")
            except VacantPosition.DoesNotExist:
                pass
        
        # Log activity
        if changes:
            EmployeeActivity.objects.create(
                employee=employee,
                activity_type='UPDATED',
                description=f"Employee {employee.full_name} was updated: {'; '.join(changes)}",
                performed_by=self.context['request'].user,
                metadata={'changes': changes}
            )
        
        return employee

# Bulk Operations Serializers
class BulkEmployeeUpdateSerializer(serializers.Serializer):
    employee_ids = serializers.ListField(child=serializers.IntegerField())
    updates = serializers.DictField()
    
    def validate_employee_ids(self, value):
        if not value:
            raise serializers.ValidationError("At least one employee ID is required.")
        
        # Validate all employee IDs exist
        existing_count = Employee.objects.filter(id__in=value).count()
        if existing_count != len(value):
            raise serializers.ValidationError("Some employee IDs do not exist.")
        
        return value

# Line Manager Operations
class BulkLineManagerUpdateSerializer(serializers.Serializer):
    employee_ids = serializers.ListField(child=serializers.IntegerField())
    line_manager_id = serializers.IntegerField(allow_null=True)
    
    def validate_employee_ids(self, value):
        if not value:
            raise serializers.ValidationError("At least one employee ID is required.")
        
        existing_count = Employee.objects.filter(id__in=value).count()
        if existing_count != len(value):
            raise serializers.ValidationError("Some employee IDs do not exist.")
        
        return value
    
    def validate_line_manager_id(self, value):
        if value is not None:
            try:
                Employee.objects.get(id=value)
            except Employee.DoesNotExist:
                raise serializers.ValidationError("Line manager not found.")
        return value

class SingleLineManagerUpdateSerializer(serializers.Serializer):
    employee_id = serializers.IntegerField()
    line_manager_id = serializers.IntegerField(allow_null=True)
    
    def validate_employee_id(self, value):
        try:
            Employee.objects.get(id=value)
        except Employee.DoesNotExist:
            raise serializers.ValidationError("Employee not found.")
        return value
    
    def validate_line_manager_id(self, value):
        if value is not None:
            try:
                Employee.objects.get(id=value)
            except Employee.DoesNotExist:
                raise serializers.ValidationError("Line manager not found.")
        return value

# Tag Operations
class EmployeeTagOperationSerializer(serializers.Serializer):
    employee_id = serializers.IntegerField()
    tag_id = serializers.IntegerField()
    
    def validate_employee_id(self, value):
        try:
            Employee.objects.get(id=value)
        except Employee.DoesNotExist:
            raise serializers.ValidationError("Employee not found.")
        return value
    
    def validate_tag_id(self, value):
        try:
            EmployeeTag.objects.get(id=value)
        except EmployeeTag.DoesNotExist:
            raise serializers.ValidationError("Tag not found.")
        return value

class BulkEmployeeTagOperationSerializer(serializers.Serializer):
    employee_ids = serializers.ListField(child=serializers.IntegerField())
    tag_id = serializers.IntegerField()
    
    def validate_employee_ids(self, value):
        if not value:
            raise serializers.ValidationError("At least one employee ID is required.")
        
        existing_count = Employee.objects.filter(id__in=value).count()
        if existing_count != len(value):
            raise serializers.ValidationError("Some employee IDs do not exist.")
        
        return value
    
    def validate_tag_id(self, value):
        try:
            EmployeeTag.objects.get(id=value)
        except EmployeeTag.DoesNotExist:
            raise serializers.ValidationError("Tag not found.")
        return value

# Enhanced Grading Serializers
class EmployeeGradingUpdateSerializer(serializers.Serializer):
    """Serializer for updating employee grading information"""
    employee_id = serializers.IntegerField()
    grading_level = serializers.CharField()
    
    def validate_grading_level(self, value):
        """Validate grading level format"""
        if value and '_' not in value:
            raise serializers.ValidationError("Grading level must be in format POSITION_LEVEL (e.g., MGR_UQ)")
        return value
    
    def validate_employee_id(self, value):
        try:
            Employee.objects.get(id=value)
        except Employee.DoesNotExist:
            raise serializers.ValidationError("Employee not found.")
        return value

class EmployeeGradingListSerializer(serializers.ModelSerializer):
    """Serializer for employee grading information display"""
    name = serializers.CharField(source='full_name', read_only=True)
    position_group_name = serializers.CharField(source='position_group.get_name_display', read_only=True)
    grading_display = serializers.CharField(source='get_grading_display', read_only=True)
    available_levels = serializers.SerializerMethodField()
    
    class Meta:
        model = Employee
        fields = [
            'id', 'employee_id', 'name', 'job_title', 'position_group_name',
            'grading_level', 'grading_display', 'available_levels'
        ]
    
    def get_available_levels(self, obj):
        """Get available grading levels for this employee's position"""
        if obj.position_group:
            return obj.position_group.get_grading_levels()
        return []

# Organizational Chart Serializers
class OrgChartNodeSerializer(serializers.ModelSerializer):
    """Serializer for organizational chart nodes"""
    name = serializers.CharField(source='full_name', read_only=True)
    children = serializers.SerializerMethodField()
    status_color = serializers.CharField(source='status.color', read_only=True)
    position_level = serializers.IntegerField(source='position_group.hierarchy_level', read_only=True)
    grading_display = serializers.CharField(source='get_grading_display', read_only=True)
    
    class Meta:
        model = Employee
        fields = [
            'id', 'employee_id', 'name', 'job_title', 'position_group', 
            'position_level', 'department', 'business_function', 'profile_image', 
            'status_color', 'grading_display', 'children'
        ]
    
    def get_children(self, obj):
        children = obj.direct_reports.filter(
            status__allows_org_chart=True,
            is_visible_in_org_chart=True,
            is_deleted=False
        ).order_by('position_group__hierarchy_level', 'employee_id')
        
        return OrgChartNodeSerializer(children, many=True, context=self.context).data

# Employee Visibility Serializer
class EmployeeOrgChartVisibilitySerializer(serializers.ModelSerializer):
    """Serializer for updating org chart visibility"""
    
    class Meta:
        model = Employee
        fields = ['id', 'employee_id', 'is_visible_in_org_chart']
        read_only_fields = ['id', 'employee_id']

# Headcount Summary Serializer
class HeadcountSummarySerializer(serializers.ModelSerializer):
    """Serializer for headcount summaries and analytics"""
    
    class Meta:
        model = HeadcountSummary
        fields = '__all__'

# Additional Employee Serializers for specific use cases
class EmployeeMinimalSerializer(serializers.ModelSerializer):
    """Minimal employee serializer for dropdowns and references"""
    name = serializers.CharField(source='full_name', read_only=True)
    position_display = serializers.CharField(source='position_group.get_name_display', read_only=True)
    
    class Meta:
        model = Employee
        fields = ['id', 'employee_id', 'name', 'job_title', 'position_display']

class EmployeeSearchSerializer(serializers.ModelSerializer):
    """Optimized serializer for search results"""
    name = serializers.CharField(source='full_name', read_only=True)
    business_function_name = serializers.CharField(source='business_function.name', read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True)
    position_group_name = serializers.CharField(source='position_group.get_name_display', read_only=True)
    status_name = serializers.CharField(source='status.name', read_only=True)
    status_color = serializers.CharField(source='status.color', read_only=True)
    
    class Meta:
        model = Employee
        fields = [
            'id', 'employee_id', 'name', 'job_title', 'business_function_name',
            'department_name', 'position_group_name', 'status_name', 'status_color'
        ]

# Contract Expiry Serializer
class ContractExpirySerializer(serializers.ModelSerializer):
    """Serializer for contract expiry tracking"""
    name = serializers.CharField(source='full_name', read_only=True)
    business_function_name = serializers.CharField(source='business_function.name', read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True)
    position_group_name = serializers.CharField(source='position_group.get_name_display', read_only=True)
    days_until_expiry = serializers.SerializerMethodField()
    
    class Meta:
        model = Employee
        fields = [
            'id', 'employee_id', 'name', 'job_title', 'business_function_name',
            'department_name', 'position_group_name', 'contract_duration',
            'contract_end_date', 'days_until_expiry'
        ]
    
    def get_days_until_expiry(self, obj):
        if obj.contract_end_date:
            delta = obj.contract_end_date - date.today()
            return delta.days
        return None

# Soft Delete Operations
class SoftDeleteSerializer(serializers.Serializer):
    employee_ids = serializers.ListField(child=serializers.IntegerField())
    
    def validate_employee_ids(self, value):
        if not value:
            raise serializers.ValidationError("At least one employee ID is required.")
        
        # Use all_objects to include soft-deleted employees for validation
        existing_count = Employee.all_objects.filter(id__in=value, is_deleted=False).count()
        if existing_count != len(value):
            raise serializers.ValidationError("Some employee IDs do not exist or are already deleted.")
        
        return value

class RestoreEmployeeSerializer(serializers.Serializer):
    employee_ids = serializers.ListField(child=serializers.IntegerField())
    
    def validate_employee_ids(self, value):
        if not value:
            raise serializers.ValidationError("At least one employee ID is required.")
        
        # Check that all employees exist and are soft-deleted
        existing_count = Employee.all_objects.filter(id__in=value, is_deleted=True).count()
        if existing_count != len(value):
            raise serializers.ValidationError("Some employee IDs do not exist or are not deleted.")
        
        return value

# Export Serializer for selected data
class EmployeeExportSerializer(serializers.Serializer):
    employee_ids = serializers.ListField(
        child=serializers.IntegerField(), 
        required=False,
        help_text="List of employee IDs to export. If empty, exports filtered results."
    )
    export_format = serializers.ChoiceField(
        choices=[('csv', 'CSV'), ('excel', 'Excel')],
        default='excel'
    )
    include_fields = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        help_text="List of fields to include in export"
    )

# Status Management Serializers
class EmployeeStatusUpdateSerializer(serializers.Serializer):
    employee_ids = serializers.ListField(child=serializers.IntegerField())
    status_id = serializers.IntegerField()
    
    def validate_employee_ids(self, value):
        if not value:
            raise serializers.ValidationError("At least one employee ID is required.")
        
        existing_count = Employee.objects.filter(id__in=value).count()
        if existing_count != len(value):
            raise serializers.ValidationError("Some employee IDs do not exist.")
        
        return value
    
    def validate_status_id(self, value):
        try:
            EmployeeStatus.objects.get(id=value)
        except EmployeeStatus.DoesNotExist:
            raise serializers.ValidationError("Status not found.")
        return value

class AutoStatusUpdateSerializer(serializers.Serializer):
    employee_ids = serializers.ListField(
        child=serializers.IntegerField(), 
        required=False,
        help_text="Employee IDs to update. If empty, updates all employees."
    )
    force_update = serializers.BooleanField(
        default=False,
        help_text="Force update even if status appears correct"
    )