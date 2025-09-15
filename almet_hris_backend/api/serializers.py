# api/serializers.py - ENHANCED: Complete Employee Management with Contract Status Management

from rest_framework import serializers
from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone
from datetime import date, timedelta
from .models import (
    Employee, BusinessFunction, Department, Unit, JobFunction,
    PositionGroup, EmployeeTag, EmployeeStatus, EmployeeDocument,
    VacantPosition, EmployeeActivity,  ContractTypeConfig
)
import logging
import os
from django.db import models 
logger = logging.getLogger(__name__)
from .job_description_models import JobDescription

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
        fields = ['id', 'name', 'code',  'is_active', 'employee_count', 'created_at']
    
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
        fields = ['id', 'name',  'is_active', 'employee_count', 'created_at']
    
    def get_employee_count(self, obj):
        return obj.employees.filter(status__affects_headcount=True).count()

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

class EmployeeTagSerializer(serializers.ModelSerializer):
    employee_count = serializers.SerializerMethodField()
    
    class Meta:
        model = EmployeeTag
        fields = ['id', 'name',  'color', 'is_active', 'employee_count', 'created_at']
    
    def get_employee_count(self, obj):
        return obj.employees.filter(status__affects_headcount=True).count()

class EmployeeStatusSerializer(serializers.ModelSerializer):
    employee_count = serializers.SerializerMethodField()
    auto_transition_to_name = serializers.CharField(source='auto_transition_to.name', read_only=True)
    
    class Meta:
        model = EmployeeStatus
        fields = [
            'id', 'name', 'status_type', 'color', 'description', 'order', 
            'affects_headcount', 'allows_org_chart', 
            'auto_transition_enabled', 'auto_transition_days', 'auto_transition_to', 'auto_transition_to_name',
            'is_transitional', 'transition_priority',
            'send_notifications', 'notification_template',
            'is_system_status', 'is_default_for_new_employees',
            'is_active', 'employee_count', 'created_at'
        ]
    
    def get_employee_count(self, obj):
        return obj.employees.count()

class ContractTypeConfigSerializer(serializers.ModelSerializer):
    total_days_until_active = serializers.SerializerMethodField()
    employee_count = serializers.SerializerMethodField()
    
    class Meta:
        model = ContractTypeConfig
        fields = [
            'id', 'contract_type', 'display_name', 
            'onboarding_days', 'probation_days', 'total_days_until_active',
            'enable_auto_transitions', 'transition_to_inactive_on_end',
            'notify_days_before_end', 'employee_count', 'is_active', 'created_at'
        ]
    
    def get_total_days_until_active(self, obj):
        return obj.get_total_days_until_active()
    
    def get_employee_count(self, obj):
        return Employee.objects.filter(contract_duration=obj.contract_type).count()

class VacantPositionCreateSerializer(serializers.ModelSerializer):
    """Enhanced serializer for creating vacant positions with business function based position_id"""
    
    # Auto-generate position_id preview like employee_id
    position_id_preview = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = VacantPosition
        fields = [
            # Required organizational fields
            'business_function', 'department', 'unit', 'job_function', 
            'position_group', 'job_title', 'grading_level',
            
            # Management
            'reporting_to',
            
            # Configuration
            'is_visible_in_org_chart', 'include_in_headcount',
            
            # Additional info
            'notes',
            
            # Read-only fields
            'position_id_preview', 'id', 'created_at', 'updated_at'
        ]
        read_only_fields = ['position_id', 'created_at', 'updated_at']
    
    def get_position_id_preview(self, obj):
        """Preview what position ID will be generated"""
        if hasattr(obj, 'business_function') and obj.business_function:
            return VacantPosition.get_next_position_id_preview(obj.business_function.id)
        return None
    
    def create(self, validated_data):
        # position_id will be auto-generated in model save() method
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)

class VacantPositionListSerializer(serializers.ModelSerializer):
    """ENHANCED: List serializer with employee-like fields and business function based ID"""
    business_function_name = serializers.CharField(source='business_function.name', read_only=True)
    business_function_code = serializers.CharField(source='business_function.code', read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True)
    unit_name = serializers.CharField(source='unit.name', read_only=True)
    job_function_name = serializers.CharField(source='job_function.name', read_only=True)
    position_group_name = serializers.CharField(source='position_group.get_name_display', read_only=True)
    position_group_level = serializers.IntegerField(source='position_group.hierarchy_level', read_only=True)
    reporting_to_name = serializers.CharField(source='reporting_to.full_name', read_only=True)
    reporting_to_hc_number = serializers.CharField(source='reporting_to.employee_id', read_only=True)
    filled_by_name = serializers.CharField(source='filled_by_employee.full_name', read_only=True)
    
    # ENHANCED: Employee-like fields for unified display (using position_id as employee_id)
    
    employee_id = serializers.CharField(source='position_id', read_only=True)  # position_id acts as employee_id
    job_title = serializers.CharField()
    status_name = serializers.CharField(source='vacancy_status.name', read_only=True)
    status_color = serializers.CharField(source='vacancy_status.color', read_only=True)
 
    
    # ENHANCED: Mark as vacancy for frontend identification
    is_vacancy = serializers.SerializerMethodField()

    
    class Meta:
        model = VacantPosition
        fields = [
            # Employee-like fields for unified display
            'id', 'employee_id',  'job_title', 'business_function_name', 'business_function_code',
            'department_name', 'unit_name', 'job_function_name', 'position_group_name', 'position_group_level',
            'grading_level',  'status_name', 'status_color',
            'reporting_to_name', 'reporting_to_hc_number', 'is_visible_in_org_chart',
            'is_filled', 'filled_by_name', 'filled_date', 'include_in_headcount',
            'is_vacancy',  'created_at', 'updated_at',
            
            # Original vacancy fields
            'position_id',  'notes'
        ]
    
    def get_grading_display(self, obj):
        if obj.grading_level:
            parts = obj.grading_level.split('_')
            if len(parts) == 2:
                position_short, level = parts
                return f"{position_short}-{level}"
        return "No Grade"
    
    def get_is_vacancy(self, obj):
        return True

class VacantPositionDetailSerializer(serializers.ModelSerializer):
    """FIXED: Detail serializer with proper JSON serialization"""
    
    # Use proper serialization instead of including objects directly
    business_function_detail = BusinessFunctionSerializer(source='business_function', read_only=True)
    department_detail = DepartmentSerializer(source='department', read_only=True)
    unit_detail = UnitSerializer(source='unit', read_only=True)
    job_function_detail = JobFunctionSerializer(source='job_function', read_only=True)
    position_group_detail = PositionGroupSerializer(source='position_group', read_only=True)
    status_detail = EmployeeStatusSerializer(source='vacancy_status', read_only=True)
    
    # Management details
    reporting_to_detail = serializers.SerializerMethodField()
    filled_by_detail = serializers.SerializerMethodField()
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    
    # Simple field references instead of complex objects
    business_function_name = serializers.CharField(source='business_function.name', read_only=True)
    business_function_code = serializers.CharField(source='business_function.code', read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True)
    unit_name = serializers.CharField(source='unit.name', read_only=True)
    job_function_name = serializers.CharField(source='job_function.name', read_only=True)
    position_group_name = serializers.CharField(source='position_group.get_name_display', read_only=True)
    status_name = serializers.CharField(source='vacancy_status.name', read_only=True)
    status_color = serializers.CharField(source='vacancy_status.color', read_only=True)
    
    # Employee-like conversion - FIXED to avoid BusinessFunction object serialization
    as_employee_data = serializers.SerializerMethodField()
    

    next_position_id_would_be = serializers.SerializerMethodField()
    
    class Meta:
        model = VacantPosition
        fields = [
            # Basic info
            'id', 'position_id', 'job_title', 'grading_level', 'display_name',
            'is_filled', 'filled_date', 'include_in_headcount', 'is_visible_in_org_chart',
            'notes', 'created_at', 'updated_at',
            
            # Simple name fields (JSON serializable)
            'business_function_name', 'business_function_code', 'department_name', 
            'unit_name', 'job_function_name', 'position_group_name',
            'status_name', 'status_color',
            
            # Detailed objects (properly serialized)
            'business_function_detail', 'department_detail', 'unit_detail',
            'job_function_detail', 'position_group_detail', 'status_detail',
            
            # Management
            'reporting_to_detail', 'filled_by_detail', 'created_by_name',
            
            # Complex fields
            'as_employee_data',  'next_position_id_would_be'
        ]
    
    def get_reporting_to_detail(self, obj):
        if obj.reporting_to:
            return {
                'id': obj.reporting_to.id,
                'employee_id': obj.reporting_to.employee_id,
                'name': obj.reporting_to.full_name,
                'job_title': obj.reporting_to.job_title,
                'email': obj.reporting_to.user.email if obj.reporting_to.user else None
            }
        return None
    
    def get_filled_by_detail(self, obj):
        if obj.filled_by_employee:
            return {
                'id': obj.filled_by_employee.id,
                'employee_id': obj.filled_by_employee.employee_id,
                'name': obj.filled_by_employee.full_name,
                'job_title': obj.filled_by_employee.job_title,
                'email': obj.filled_by_employee.user.email if obj.filled_by_employee.user else None
            }
        return None
    
    def get_as_employee_data(self, obj):
        """Get vacancy data in employee-like format - FIXED"""
        return {
            'id': f"vacancy_{obj.id}",
            'employee_id': obj.position_id,
            'name': obj.display_name,
            'full_name': None,
            'email': None,
            'job_title': obj.job_title,
            
            # Use simple string references instead of objects
            'business_function_name': obj.business_function.name if obj.business_function else 'N/A',
            'business_function_code': obj.business_function.code if obj.business_function else 'N/A',
            'department_name': obj.department.name if obj.department else 'N/A',
            'unit_name': obj.unit.name if obj.unit else None,
            'job_function_name': obj.job_function.name if obj.job_function else 'N/A',
            'position_group_name': obj.position_group.get_name_display() if obj.position_group else 'N/A',
            'grading_level': obj.grading_level,
            
            'status_name': obj.vacancy_status.name if obj.vacancy_status else 'VACANT',
            'status_color': obj.vacancy_status.color if obj.vacancy_status else '#F97316',
            'line_manager_name': obj.reporting_to.full_name if obj.reporting_to else None,
            'line_manager_hc_number': obj.reporting_to.employee_id if obj.reporting_to else None,
            'is_visible_in_org_chart': obj.is_visible_in_org_chart,
            'is_vacancy': True,
            'created_at': obj.created_at,
            'notes': obj.notes,
            'filled_by': obj.filled_by_employee.full_name if obj.filled_by_employee else None,
            'vacancy_details': {
                'internal_id': obj.id,
                'position_id': obj.position_id,
                'include_in_headcount': obj.include_in_headcount,
                'is_filled': obj.is_filled,
                'filled_date': obj.filled_date,
                'business_function_based_id': True
            }
        }
    
    
    def get_next_position_id_would_be(self, obj):
        """Show what the next position ID would be for this business function"""
        if obj.business_function:
            return VacantPosition.get_next_position_id_preview(obj.business_function.id)
        return None

class VacancyToEmployeeConversionSerializer(serializers.Serializer):
    """Serializer for converting vacancy to employee"""
    
    # Required employee data
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)  
    email = serializers.EmailField()
    start_date = serializers.DateField()
    contract_duration = serializers.CharField(max_length=50, default='PERMANENT')
    
    # Personal data - ALL OPTIONAL
    father_name = serializers.CharField(max_length=200, required=False, allow_blank=True)
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    gender = serializers.ChoiceField(choices=Employee.GENDER_CHOICES, required=False, allow_null=True)
    address = serializers.CharField(required=False, allow_blank=True)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    emergency_contact = serializers.CharField(required=False, allow_blank=True)
    
    # Employment details - OPTIONAL
    end_date = serializers.DateField(required=False, allow_null=True)
    contract_start_date = serializers.DateField(required=False, allow_null=True)
    
    # File uploads - OPTIONAL
    document = serializers.FileField(required=False)
    profile_photo = serializers.ImageField(required=False)
    document_type = serializers.ChoiceField(
        choices=EmployeeDocument.DOCUMENT_TYPES, 
        required=False, 
        default='OTHER'
    )
    document_name = serializers.CharField(max_length=255, required=False)
    
    # Additional - OPTIONAL
    tag_ids = serializers.ListField(child=serializers.IntegerField(), required=False, default=list)
    
    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email already exists.")
        return value
    
    def validate_contract_duration(self, value):
        """Validate that contract duration exists in configurations"""
        try:
            ContractTypeConfig.objects.get(contract_type=value, is_active=True)
        except ContractTypeConfig.DoesNotExist:
            available_choices = list(ContractTypeConfig.objects.filter(is_active=True).values_list('contract_type', flat=True))
            if not available_choices:
                ContractTypeConfig.get_or_create_defaults()
                available_choices = list(ContractTypeConfig.objects.filter(is_active=True).values_list('contract_type', flat=True))
            
            raise serializers.ValidationError(
                f"Invalid contract duration '{value}'. Available choices: {', '.join(available_choices)}"
            )
        return value
    
    def create(self, validated_data):
        """Convert vacancy to employee"""
        # Get vacancy from context instead of validated_data
        vacancy = self.context['vacancy']
        
        tag_ids = validated_data.pop('tag_ids', [])
        document = validated_data.pop('document', None)
        profile_photo = validated_data.pop('profile_photo', None)
        document_type = validated_data.pop('document_type', 'OTHER')
        document_name = validated_data.pop('document_name', '')
        
        with transaction.atomic():
            # Create user
            user = User.objects.create_user(
                username=validated_data['email'],
                email=validated_data['email'],
                first_name=validated_data['first_name'],
                last_name=validated_data['last_name']
            )
            
            # Create employee with vacancy data
            employee = Employee.objects.create(
                user=user,
                # Personal information
                date_of_birth=validated_data.get('date_of_birth'),
                gender=validated_data.get('gender'),
                father_name=validated_data.get('father_name', ''),
                address=validated_data.get('address', ''),
                phone=validated_data.get('phone', ''),
                emergency_contact=validated_data.get('emergency_contact', ''),
                
                # Copy organizational structure from vacancy
                business_function=vacancy.business_function,
                department=vacancy.department,
                unit=vacancy.unit,
                job_function=vacancy.job_function,
                job_title=vacancy.job_title,
                position_group=vacancy.position_group,
                grading_level=vacancy.grading_level,
                
                # Employment details
                start_date=validated_data['start_date'],
                end_date=validated_data.get('end_date'),
                contract_duration=validated_data['contract_duration'],
                contract_start_date=validated_data.get('contract_start_date') or validated_data['start_date'],
                
                # Management
                line_manager=vacancy.reporting_to,
                
                # Configuration
                is_visible_in_org_chart=vacancy.is_visible_in_org_chart,
                original_vacancy=vacancy,
                created_by=self.context['request'].user
            )
            
            # Handle profile photo
            if profile_photo:
                employee.profile_image = profile_photo
                employee.save()
            
            # Add tags
            if tag_ids:
                valid_tags = EmployeeTag.objects.filter(id__in=tag_ids, is_active=True)
                employee.tags.set(valid_tags)
            
            # Handle document upload
            if document:
                doc_name = document_name or document.name
                EmployeeDocument.objects.create(
                    employee=employee,
                    name=doc_name,
                    document_type=document_type,
                    document_file=document,
                    uploaded_by=self.context['request'].user,
                    document_status='ACTIVE',
                    version=1,
                    is_current_version=True
                )
            
            # Mark vacancy as filled
            vacancy.mark_as_filled(employee)
            
            # Log activity
            EmployeeActivity.objects.create(
                employee=employee,
                activity_type='CREATED',
                description=f"Employee {employee.full_name} created from vacancy {vacancy.position_id}",
                performed_by=self.context['request'].user,
                metadata={
                    'converted_from_vacancy': True,
                    'vacancy_id': vacancy.id,
                    'vacancy_position_id': vacancy.position_id
                }
            )
            
            return employee
class EmployeeDocumentSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.CharField(source='uploaded_by.username', read_only=True)
    file_size_display = serializers.CharField(source='get_file_size_display', read_only=True)
    is_image = serializers.BooleanField(read_only=True)
    is_pdf = serializers.BooleanField(read_only=True)
    file_url = serializers.SerializerMethodField()
    version_info = serializers.SerializerMethodField()
    
    class Meta:
        model = EmployeeDocument
        fields = [
            'id', 'name', 'document_type', 'document_status', 'document_file', 'file_url',
            'version', 'is_current_version', 'version_info',
            'file_size', 'file_size_display', 'mime_type', 'original_filename',
            'description', 'expiry_date', 'is_confidential', 'is_required',
            'uploaded_at', 'uploaded_by_name', 'download_count', 'last_accessed',
            'is_image', 'is_pdf', 'is_deleted'
        ]
        read_only_fields = [
            'id', 'version', 'file_size', 'mime_type', 'original_filename', 
            'uploaded_at', 'download_count', 'last_accessed', 'is_current_version'
        ]
    
    def get_file_url(self, obj):
        if obj.document_file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.document_file.url)
        return None
    
    def get_version_info(self, obj):
        """Get version history information"""
        version_history = obj.get_version_history()
        return {
            'current_version': obj.version,
            'is_current': obj.is_current_version,
            'total_versions': version_history.count(),
            'has_previous': obj.get_previous_version() is not None,
            'has_next': obj.get_next_version() is not None
        }

class ProfileImageUploadSerializer(serializers.Serializer):
    employee_id = serializers.IntegerField()
    profile_image = serializers.ImageField()
    
    def validate_employee_id(self, value):
        try:
            Employee.objects.get(id=value)
        except Employee.DoesNotExist:
            raise serializers.ValidationError("Employee not found.")
        return value
    
    def validate_profile_image(self, value):
        # Image size validation (10MB max)
        if value.size > 10 * 1024 * 1024:
            raise serializers.ValidationError("Image size cannot exceed 10MB.")
        
        # Image format validation
        allowed_formats = ['JPEG', 'PNG', 'GIF', 'BMP']
        
        try:
            from PIL import Image
            img = Image.open(value)
            if img.format not in allowed_formats:
                raise serializers.ValidationError(f"Image format {img.format} is not allowed.")
        except Exception as e:
            raise serializers.ValidationError("Invalid image file.")
        
        return value
    
    def save(self):
        employee_id = self.validated_data['employee_id']
        profile_image = self.validated_data['profile_image']
        
        employee = Employee.objects.get(id=employee_id)
        
        # Delete old profile image if exists
        if employee.profile_image:
            try:
                # Check if it's a FieldFile with a path
                if hasattr(employee.profile_image, 'path'):
                    old_image_path = employee.profile_image.path
                    if os.path.exists(old_image_path):
                        os.remove(old_image_path)
            except Exception as e:
                # Log error but don't fail
                logger.warning(f"Could not delete old profile image: {e}")
        
        # Save the new profile image
        employee.profile_image = profile_image
        employee.save()
        
        # Log activity
        EmployeeActivity.objects.create(
            employee=employee,
            activity_type='PROFILE_UPDATED',
            description="Profile image updated",
            performed_by=self.context['request'].user,
            metadata={'action': 'profile_image_upload'}
        )
        
        return employee

class ProfileImageDeleteSerializer(serializers.Serializer):
    employee_id = serializers.IntegerField()
    
    def validate_employee_id(self, value):
        try:
            employee = Employee.objects.get(id=value)
            if not employee.profile_image:
                raise serializers.ValidationError("Employee has no profile image to delete.")
        except Employee.DoesNotExist:
            raise serializers.ValidationError("Employee not found.")
        return value
    
    def save(self):
        employee_id = self.validated_data['employee_id']
        employee = Employee.objects.get(id=employee_id)
        
        # Delete image file safely
        if employee.profile_image:
            try:
                if hasattr(employee.profile_image, 'path'):
                    old_image_path = employee.profile_image.path
                    if os.path.exists(old_image_path):
                        os.remove(old_image_path)
            except Exception as e:
                logger.warning(f"Could not delete profile image file: {e}")
        
        # Clear the field
        employee.profile_image = None
        employee.save()
        
        # Log activity
        EmployeeActivity.objects.create(
            employee=employee,
            activity_type='PROFILE_UPDATED',
            description="Profile image deleted",
            performed_by=self.context['request'].user,
            metadata={'action': 'profile_image_delete'}
        )
        
        return employee

class EmployeeActivitySerializer(serializers.ModelSerializer):
    performed_by_name = serializers.CharField(source='performed_by.username', read_only=True)
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    
    class Meta:
        model = EmployeeActivity
        fields = [
            'id', 'employee', 'employee_name', 'activity_type', 'description',
            'performed_by', 'performed_by_name', 'metadata', 'created_at'
        ]

class EmployeeListSerializer(serializers.ModelSerializer):
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
   
    
    direct_reports_count = serializers.SerializerMethodField()
    status_needs_update = serializers.SerializerMethodField()
    profile_image_url = serializers.SerializerMethodField()
    is_vacancy = serializers.SerializerMethodField()
    
    def get_is_vacancy(self, obj):
        return False  # This is for actual employees
    class Meta:
        model = Employee
        fields = [
            'id', 'employee_id', 'name', 'email','father_name', 'date_of_birth', 'gender',  'phone',
            'business_function_name', 'business_function_code', 'department_name', 'unit_name',
            'job_function_name', 'job_title', 'position_group_name', 'position_group_level',
            'grading_level',  'start_date', 'end_date',
            'contract_duration', 'contract_duration_display', 'contract_start_date', 'contract_end_date',
            'contract_extensions', 'last_extension_date',  
            'line_manager_name', 'line_manager_hc_number', 'status_name', 'status_color',
            'tag_names', 'years_of_service', 'current_status_display', 'is_visible_in_org_chart',
            'direct_reports_count', 'status_needs_update', 'created_at', 'updated_at','profile_image_url','is_deleted','is_vacancy',
        ]
    
    def get_profile_image_url(self, obj):
        """Get profile image URL safely"""
        if obj.profile_image:
            try:
                if hasattr(obj.profile_image, 'url'):
                    request = self.context.get('request')
                    if request:
                        return request.build_absolute_uri(obj.profile_image.url)
                    return obj.profile_image.url
            except Exception as e:
                # Log error but don't fail serialization
                logger.warning(f"Could not get profile image URL for employee {obj.employee_id}: {e}")
        return None
    
    def get_tag_names(self, obj):
        return [
            {
                'id': tag.id,
                'name': tag.name,
                'color': tag.color,
                
            }
            for tag in obj.tags.filter(is_active=True)
        ]
    
    def get_direct_reports_count(self, obj):
        return obj.get_direct_reports_count()
    
    def get_status_needs_update(self, obj):
        """Check if employee status needs updating based on contract"""
        try:
            preview = obj.get_status_preview()
            return preview['needs_update']
        except:
            return False

class EmployeeDetailSerializer(serializers.ModelSerializer):
    """UPDATED: Job Description integration əlavə olundu"""
     
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
    contract_duration_display = serializers.CharField(source='get_contract_duration_display', read_only=True)
    
    # Contract status analysis
    status_preview = serializers.SerializerMethodField()
    
    # Vacancy information
    original_vacancy_detail = VacantPositionListSerializer(source='original_vacancy', read_only=True)
    
    profile_image_url = serializers.SerializerMethodField()
    documents_count = serializers.SerializerMethodField()
    
    # JOB DESCRIPTION INTEGRATION - YENİ SAHƏLƏR
    job_descriptions = serializers.SerializerMethodField()
    job_descriptions_count = serializers.SerializerMethodField()
    pending_job_description_approvals = serializers.SerializerMethodField()
    
    # For managers - team member job descriptions
    team_job_descriptions = serializers.SerializerMethodField()
    team_pending_approvals = serializers.SerializerMethodField()
    
    assigned_assets = serializers.SerializerMethodField()
    pending_asset_approvals = serializers.SerializerMethodField()
    assets_summary = serializers.SerializerMethodField()
    
    class Meta:
        model = Employee
        fields = '__all__'
    
    
    
    
    
    def get_assigned_assets(self, obj):
        """Get all assets assigned to this employee with clarification info"""
        try:
            from .asset_models import Asset
            assets = Asset.objects.filter(
                assigned_to=obj
            ).select_related('category').order_by('-created_at')
            
            assets_data = []
            for asset in assets:
                asset_info = {
                    'id': str(asset.id),
                    'asset_name': asset.asset_name,
                    'category': asset.category.name if asset.category else None,
                    'serial_number': asset.serial_number,
                    'status': asset.status,
                    'status_display': asset.get_status_display(),
                    'status_color': asset.get_status_display_with_color()['color'],
                    'purchase_date': asset.purchase_date,
                    'created_at': asset.created_at,
                    
                    # Action permissions
                    'can_accept': asset.status == 'ASSIGNED',
                    'can_request_clarification': asset.status in ['ASSIGNED', 'NEED_CLARIFICATION'],
                    
                    # Assignment details
                    'assignment_date': None,
                    'days_assigned': 0,
                    
                    # YENİ: Clarification information
                    'clarification_info': self._get_asset_clarification_info(asset)
                }
                
                # Get assignment details
                current_assignment = asset.assignments.filter(check_in_date__isnull=True).first()
                if current_assignment:
                    asset_info['assignment_date'] = current_assignment.check_out_date
                    asset_info['days_assigned'] = current_assignment.get_duration_days()
                
                assets_data.append(asset_info)
            
            return assets_data
        except Exception as e:
            logger.error(f"Error getting assigned assets for employee {obj.employee_id}: {e}")
            return []

    def _get_asset_clarification_info(self, asset):
        """Get clarification information for asset"""
        try:
            # Əgər asset model-də clarification field-ləri varsa
            if hasattr(asset, 'clarification_requested_reason'):
                if asset.status == 'NEED_CLARIFICATION' or asset.clarification_requested_reason:
                    return {
                        'has_clarification': True,
                        'requested_reason': asset.clarification_requested_reason,
                        'requested_at': asset.clarification_requested_at,
                        'requested_by': asset.clarification_requested_by.get_full_name() if asset.clarification_requested_by else None,
                        'response': asset.clarification_response,
                        'provided_at': asset.clarification_provided_at,
                        'provided_by': asset.clarification_provided_by.get_full_name() if asset.clarification_provided_by else None,
                        'has_response': bool(asset.clarification_response),
                        'is_pending': asset.status == 'NEED_CLARIFICATION' and not asset.clarification_response,
                        'status': 'pending' if asset.status == 'NEED_CLARIFICATION' and not asset.clarification_response else 'resolved'
                    }
            
            # Əgər model field-ləri yoxdursa, activity-lərindən məlumat al
            return self._get_clarification_from_activities(asset)
            
        except Exception as e:
            logger.error(f"Error getting clarification info for asset {asset.id}: {e}")
            return {'has_clarification': False}
    
    def _get_clarification_from_activities(self, asset):
        """Get clarification info from asset activities if model fields don't exist"""
        try:
            from .asset_models import AssetActivity
            
            # Get latest clarification request
            clarification_request = AssetActivity.objects.filter(
                asset=asset,
                activity_type='CLARIFICATION_REQUESTED'
            ).order_by('-performed_at').first()
            
            # Get latest clarification response
            clarification_response = AssetActivity.objects.filter(
                asset=asset,
                activity_type='CLARIFICATION_PROVIDED'
            ).order_by('-performed_at').first()
            
            if clarification_request:
                # Extract reason from description or metadata
                reason = ''
                if clarification_request.metadata and 'clarification_reason' in clarification_request.metadata:
                    reason = clarification_request.metadata['clarification_reason']
                else:
                    # Extract from description
                    desc = clarification_request.description
                    if 'Clarification requested by' in desc and ':' in desc:
                        reason = desc.split(':', 1)[1].strip()
                
                response_text = ''
                if clarification_response and clarification_response.metadata and 'clarification_response' in clarification_response.metadata:
                    response_text = clarification_response.metadata['clarification_response']
                
                return {
                    'has_clarification': True,
                    'requested_reason': reason,
                    'requested_at': clarification_request.performed_at,
                    'requested_by': clarification_request.performed_by.get_full_name() if clarification_request.performed_by else None,
                    'response': response_text,
                    'provided_at': clarification_response.performed_at if clarification_response else None,
                    'provided_by': clarification_response.performed_by.get_full_name() if clarification_response and clarification_response.performed_by else None,
                    'has_response': bool(clarification_response),
                    'is_pending': asset.status == 'NEED_CLARIFICATION' and not clarification_response,
                    'status': 'pending' if asset.status == 'NEED_CLARIFICATION' and not clarification_response else 'resolved'
                }
            
            return {'has_clarification': False}
            
        except Exception as e:
            logger.error(f"Error getting clarification from activities for asset {asset.id}: {e}")
            return {'has_clarification': False}
    
    def get_pending_asset_approvals(self, obj):
        """Get assets pending employee approval"""
        try:
            from .asset_models import Asset
            pending_assets = Asset.objects.filter(
                assigned_to=obj,
                status='ASSIGNED'
            ).select_related('category')
            
            return [
                {
                    'id': str(asset.id),
                    'asset_name': asset.asset_name,
                    'category': asset.category.name if asset.category else None,
                    'serial_number': asset.serial_number,
                    'status': asset.status,
                    'status_display': asset.get_status_display(),
                    'status_color': asset.get_status_display_with_color()['color'],
                    'assignment_date': asset.assignments.filter(
                        check_in_date__isnull=True
                    ).first().check_out_date if asset.assignments.filter(
                        check_in_date__isnull=True
                    ).exists() else None,
                    'urgency': 'high' if (timezone.now().date() - (
                        asset.assignments.filter(check_in_date__isnull=True).first().check_out_date 
                        if asset.assignments.filter(check_in_date__isnull=True).exists() else timezone.now().date()
                    )).days > 3 else 'normal'
                }
                for asset in pending_assets
            ]
        except Exception as e:
            logger.error(f"Error getting pending asset approvals for employee {obj.employee_id}: {e}")
            return []
    
    def get_assets_summary(self, obj):
        """Get asset assignment summary for employee"""
        try:
            from .asset_models import Asset
            all_assets = Asset.objects.filter(assigned_to=obj)
            
            return {
                'total_assigned': all_assets.count(),
                'pending_approval': all_assets.filter(status='ASSIGNED').count(),
                'in_use': all_assets.filter(status='IN_USE').count(),
                'need_clarification': all_assets.filter(status='NEED_CLARIFICATION').count(),
                'has_pending_approvals': all_assets.filter(status='ASSIGNED').exists()
            }
        except Exception as e:
            logger.error(f"Error getting assets summary for employee {obj.employee_id}: {e}")
            return {
                'total_assigned': 0,
                'pending_approval': 0,
                'in_use': 0,
                'need_clarification': 0,
                'has_pending_approvals': False
            }
    
    
    def get_profile_image_url(self, obj):
        """Get profile image URL safely"""
        if obj.profile_image:
            try:
                if hasattr(obj.profile_image, 'url'):
                    request = self.context.get('request')
                    if request:
                        return request.build_absolute_uri(obj.profile_image.url)
                    return obj.profile_image.url
            except Exception as e:
                logger.warning(f"Could not get profile image URL for employee {obj.employee_id}: {e}")
        return None
    
    def get_documents_count(self, obj):
        return obj.documents.filter(is_deleted=False).count()
    
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
    
    def get_status_preview(self, obj):
        """Get status preview for this employee"""
        try:
            return obj.get_status_preview()
        except:
            return None
    
    def get_job_descriptions(self, obj):
        """Get job descriptions assigned to this employee"""
        try:
            # DƏYİŞİKLİK: request_user dəyişənini təyin et
            request_user = self.context.get('request').user if self.context.get('request') else None
            
            job_descriptions = JobDescription.objects.filter(
                assigned_employee=obj
            ).select_related(
                'business_function', 'department', 'job_function', 'position_group', 'reports_to', 'created_by'
            ).order_by('-created_at')[:10]  # Son 10 job description
            
            # DƏYİŞİKLİK: List comprehension əvəzinə explicit loop və düzgün dəyişən adı
            result = []
            for jd in job_descriptions:  # DƏYİŞİKLİK: pending_team_jds əvəzinə job_descriptions
                result.append({
                    'id': str(jd.id),
                    'job_title': jd.job_title,
                    'status': jd.status,
                    'status_display': jd.get_status_display(),
                    'status_color': jd.get_status_display_with_color()['color'],
                    'created_at': jd.created_at,
                    'version': jd.version,
                    'can_approve': jd.can_be_approved_by_employee(request_user) if request_user else False,  # DƏYİŞİKLİK: employee üçün düzgün metod
                    'business_function': jd.business_function.name if jd.business_function else None,
                    'department': jd.department.name if jd.department else None,
                    'job_function': jd.job_function.name if jd.job_function else None,
                    'reports_to_name': jd.reports_to.full_name if jd.reports_to else None,
                    'urgency': 'high' if (timezone.now() - jd.created_at).days > 7 else 'normal'
                })
            
            return result
        except Exception as e:
            logger.error(f"Error getting job descriptions for employee {obj.employee_id}: {e}")
            return []
        
    def get_job_descriptions_count(self, obj):
        """Get total count of job descriptions for this employee"""
        try:
            return JobDescription.objects.filter(assigned_employee=obj).count()
        except:
            return 0
    
    def get_pending_job_description_approvals(self, obj):
        """Get job descriptions pending employee approval"""
        try:
            if not self.context.get('request') or not self.context.get('request').user:
                return []
            
            request_user = self.context.get('request').user
            pending_jds = JobDescription.objects.filter(
                assigned_employee=obj,
                status='PENDING_EMPLOYEE'
            ).select_related('business_function', 'department', 'reports_to')
            
            return [
                {
                    'id': str(jd.id),
                    'job_title': jd.job_title,
                    'status': jd.status,
                    'status_display': jd.get_status_display(),
                    'status_color': jd.get_status_display_with_color()['color'],
                    'created_at': jd.created_at,
                    'version': jd.version,
                    'can_approve': jd.can_be_approved_by_employee(request_user),
                    'business_function': jd.business_function.name if jd.business_function else None,
                    'department': jd.department.name if jd.department else None,
                    'reports_to_name': jd.reports_to.full_name if jd.reports_to else None,
                    'urgency': 'high' if (timezone.now() - jd.created_at).days > 7 else 'normal',
                    'days_pending': (timezone.now() - jd.created_at).days
                }
                for jd in pending_jds
            ]
        except Exception as e:
            logger.error(f"Error getting pending job descriptions for employee {obj.employee_id}: {e}")
            return []
    


    def get_team_job_descriptions(self, obj):
        """Get job descriptions for direct reports (for managers)"""
        try:
            if not self.context.get('request') or not self.context.get('request').user:
                return []
            
            # DƏYİŞİKLİK: request_user dəyişənini təyin et
            request_user = self.context.get('request').user
            
            # Get job descriptions where this employee is the reports_to manager
            team_jds = JobDescription.objects.filter(
                reports_to=obj
            ).select_related(
                'assigned_employee', 'business_function', 'department', 'job_function', 'created_by'
            ).order_by('-created_at')[:10]
            
            # DƏYİŞİKLİK: List comprehension əvəzinə explicit loop
            result = []
            for jd in team_jds:
                result.append({
                    'id': str(jd.id),
                    'job_title': jd.job_title,
                    'status': jd.status,
                    'status_display': jd.get_status_display(),
                    'status_color': jd.get_status_display_with_color()['color'],
                    'created_at': jd.created_at,
                    'version': jd.version,
                    'employee_name': jd.get_employee_info()['name'] if jd.get_employee_info() else 'Unknown',
                    'employee_id': jd.assigned_employee.employee_id if jd.assigned_employee else None,
                    'can_approve': jd.can_be_approved_by_line_manager(request_user),  # DƏYİŞİKLİK: təyin edilmiş dəyişən
                    'business_function': jd.business_function.name if jd.business_function else None,
                    'department': jd.department.name if jd.department else None,
                    'job_function': jd.job_function.name if jd.job_function else None,
                    'days_since_created': (timezone.now() - jd.created_at).days,
                    'is_vacant_position': not jd.assigned_employee
                })
            
            return result
        except Exception as e:
            logger.error(f"Error getting team job descriptions for manager {obj.employee_id}: {e}")
            return []
    
    
    
    def get_team_pending_approvals(self, obj):
        """Get job descriptions pending line manager approval for this manager"""
        try:
            if not self.context.get('request') or not self.context.get('request').user:
                return []
            
            # DƏYİŞİKLİK: request_user dəyişənini təyin et
            request_user = self.context.get('request').user
            # DƏYİŞİKLİK: pending_team_jds dəyişənini təyin et
            pending_team_jds = JobDescription.objects.filter(
                reports_to=obj,
                status='PENDING_LINE_MANAGER'
            ).select_related('assigned_employee', 'business_function', 'department', 'job_function')
            
            # DƏYİŞİKLİK: List comprehension əvəzinə explicit loop
            result = []
            for jd in pending_team_jds:
                result.append({
                    'id': str(jd.id),
                    'job_title': jd.job_title,
                    'status': jd.status,
                    'status_display': jd.get_status_display(),
                    'status_color': jd.get_status_display_with_color()['color'],
                    'created_at': jd.created_at,
                    'version': jd.version,
                    'employee_name': jd.get_employee_info()['name'] if jd.get_employee_info() else 'Vacant Position',
                    'employee_id': jd.assigned_employee.employee_id if jd.assigned_employee else None,
                    'can_approve': jd.can_be_approved_by_line_manager(request_user),  # DƏYİŞİKLİK: təyin edilmiş dəyişən
                    'business_function': jd.business_function.name if jd.business_function else None,
                    'department': jd.department.name if jd.department else None,
                    'job_function': jd.job_function.name if jd.job_function else None,
                    'urgency': 'critical' if (timezone.now() - jd.created_at).days > 14 else ('high' if (timezone.now() - jd.created_at).days > 7 else 'normal'),
                    'days_pending': (timezone.now() - jd.created_at).days,
                    'is_vacant_position': not jd.assigned_employee
                })
            
            return result
        except Exception as e:
            logger.error(f"Error getting pending team job descriptions for manager {obj.employee_id}: {e}")
            return []
class EmployeeJobDescriptionSerializer(serializers.ModelSerializer):
    """Simple job description serializer for employee views"""
    
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    status_color = serializers.SerializerMethodField()
    business_function_name = serializers.CharField(source='business_function.name', read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True)
    job_function_name = serializers.CharField(source='job_function.name', read_only=True)  # YENİ
    reports_to_name = serializers.CharField(source='reports_to.full_name', read_only=True)
    can_approve = serializers.SerializerMethodField()
    employee_info = serializers.SerializerMethodField()
    days_since_created = serializers.SerializerMethodField()
    
    class Meta:
        model = JobDescription
        fields = [
            'id', 'job_title', 'job_purpose', 'status', 'status_display', 'status_color',
            'version', 'created_at', 'updated_at', 'business_function_name', 'department_name',
            'job_function_name', 'reports_to_name', 'can_approve', 'employee_info', 'days_since_created',
            'line_manager_approved_at', 'employee_approved_at'
        ]
    
    def get_status_color(self, obj):
        return obj.get_status_display_with_color()['color']
    
    def get_can_approve(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        return obj.can_be_approved_by_employee(request.user)
    
    def get_employee_info(self, obj):
        return obj.get_employee_info()
    
    def get_days_since_created(self, obj):
        return (timezone.now() - obj.created_at).days



class BulkSoftDeleteSerializer(serializers.Serializer):
    """Simple serializer for bulk soft delete operations"""
    employee_ids = serializers.ListField(
        child=serializers.IntegerField(),
        help_text="List of employee IDs to soft delete"
    )
    reason = serializers.CharField(
        max_length=500,
        required=False,
        default="Bulk restructuring",
        help_text="Reason for bulk deletion"
    )
    
    def validate_employee_ids(self, value):
        if not value:
            raise serializers.ValidationError("At least one employee ID is required.")
        
        employees = Employee.objects.filter(id__in=value, is_deleted=False)
        if employees.count() != len(value):
            raise serializers.ValidationError("Some employee IDs were not found or already deleted.")
        
        return value

class BulkHardDeleteSerializer(serializers.Serializer):
    """Simple serializer for bulk hard delete operations"""
    employee_ids = serializers.ListField(
        child=serializers.IntegerField(),
        help_text="List of employee IDs to hard delete"
    )
    confirm_hard_delete = serializers.BooleanField(
        help_text="Confirmation flag (must be true)"
    )
    notes = serializers.CharField(
        max_length=1000,
        required=False,
        help_text="Additional notes about deletion"
    )
    
    def validate_employee_ids(self, value):
        if not value:
            raise serializers.ValidationError("At least one employee ID is required.")
        
        employees = Employee.objects.filter(id__in=value)
        if employees.count() != len(value):
            raise serializers.ValidationError("Some employee IDs were not found.")
        
        return value
    
    def validate_confirm_hard_delete(self, value):
        if not value:
            raise serializers.ValidationError("confirm_hard_delete must be true for hard deletion.")
        return value

class HardDeleteSerializer(serializers.Serializer):
    """Simple serializer for single employee hard delete"""
    employee_id = serializers.IntegerField(help_text="Employee ID to hard delete")
    confirm_hard_delete = serializers.BooleanField(help_text="Confirmation flag (must be true)")
    notes = serializers.CharField(
        max_length=1000,
        required=False,
        help_text="Additional notes about deletion"
    )
    
    def validate_employee_id(self, value):
        try:
            Employee.objects.get(id=value)
        except Employee.DoesNotExist:
            raise serializers.ValidationError("Employee not found.")
        return value
    
    def validate_confirm_hard_delete(self, value):
        if not value:
            raise serializers.ValidationError("confirm_hard_delete must be true for hard deletion.")
        return value

class ManagerJobDescriptionSerializer(serializers.ModelSerializer):
    """Job description serializer for manager views (team members)"""
    
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    status_color = serializers.SerializerMethodField()
    business_function_name = serializers.CharField(source='business_function.name', read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True)
    job_function_name = serializers.CharField(source='job_function.name', read_only=True)  # YENİ
    employee_info = serializers.SerializerMethodField()
    can_approve = serializers.SerializerMethodField()
    days_since_created = serializers.SerializerMethodField()
    urgency_level = serializers.SerializerMethodField()
    
    class Meta:
        model = JobDescription
        fields = [
            'id', 'job_title', 'job_purpose', 'status', 'status_display', 'status_color',
            'version', 'created_at', 'updated_at', 'business_function_name', 'department_name',
            'job_function_name', 'employee_info', 'can_approve', 'days_since_created', 'urgency_level',
            'line_manager_approved_at', 'employee_approved_at'
        ]
    
    def get_status_color(self, obj):
        return obj.get_status_display_with_color()['color']
    
    def get_can_approve(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        return obj.can_be_approved_by_line_manager(request.user)
    
    def get_employee_info(self, obj):
        return obj.get_employee_info()
    
    def get_days_since_created(self, obj):
        return (timezone.now() - obj.created_at).days
    
    def get_urgency_level(self, obj):
        days = (timezone.now() - obj.created_at).days
        if days > 14:
            return 'critical'
        elif days > 7:
            return 'high'
        else:
            return 'normal'
class EmployeeCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating and updating employees with auto-generated employee_id"""
    
    # User fields (write-only for creation)
    first_name = serializers.CharField(write_only=True, max_length=150)
    last_name = serializers.CharField(write_only=True, max_length=150)
    email = serializers.EmailField(write_only=True)
    
    # Optional personal fields
    father_name = serializers.CharField(write_only=True, required=False, allow_blank=True, max_length=200)
    tag_ids = serializers.ListField(child=serializers.IntegerField(), write_only=True, required=False)
    vacancy_id = serializers.IntegerField(write_only=True, required=False, help_text="Link to vacant position")
    
    # File upload fields
    document = serializers.FileField(write_only=True, required=False, help_text="Employee document file")
    profile_photo = serializers.ImageField(write_only=True, required=False, help_text="Employee profile photo")
    document_type = serializers.ChoiceField(
        choices=EmployeeDocument.DOCUMENT_TYPES,
        write_only=True, 
        required=False, 
        default='OTHER'
    )
    document_name = serializers.CharField(write_only=True, required=False, max_length=255)
    
    # Preview field (read-only) - shows what the employee_id will be
    employee_id_preview = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = Employee
        # COMPLETELY EXCLUDE employee_id from all operations
        exclude = [
            'employee_id',  # This is the key fix - completely exclude from serializer
            'user', 
            'full_name', 
            'tags', 
            'original_vacancy', 
            'status', 
            'created_by', 
            'updated_by', 
            'profile_image'
        ]
        read_only_fields = [
            'contract_extensions', 
            'last_extension_date', 
            'deleted_by', 
            'deleted_at', 
            'is_deleted',
            'contract_end_date', 
            'created_at', 
            'updated_at'
        ]
    
    def get_employee_id_preview(self, obj):
        """Preview what employee ID will be generated"""
        if hasattr(obj, 'business_function') and obj.business_function:
            try:
                business_code = obj.business_function.code
                
                # Get next number for this business function
                last_employee = Employee.all_objects.filter(
                    employee_id__startswith=business_code
                ).order_by('-employee_id').first()
                
                if last_employee:
                    try:
                        last_number = int(last_employee.employee_id[len(business_code):])
                        next_number = last_number + 1
                    except (ValueError, IndexError):
                        next_number = 1
                else:
                    next_number = 1
                
                return f"{business_code}{next_number}"
            except:
                return None
        return None
    
    def validate(self, data):
        """Custom validation - ensure business function is provided"""
        # Business function is required for auto-generating employee_id
        if not data.get('business_function'):
            raise serializers.ValidationError({
                'business_function': 'Business function is required for generating employee ID'
            })
        
        return data
    
    def validate_email(self, value):
        """Validate email uniqueness"""
        if self.instance and self.instance.user:
            # Updating existing employee
            if User.objects.filter(email=value).exclude(id=self.instance.user.id).exists():
                raise serializers.ValidationError("Email already exists.")
        else:
            # Creating new employee
            if User.objects.filter(email=value).exists():
                raise serializers.ValidationError("Email already exists.")
        return value
    
    @transaction.atomic
    def create(self, validated_data):
        # Extract user data
        first_name = validated_data.pop('first_name')
        last_name = validated_data.pop('last_name')
        email = validated_data.pop('email')
        father_name = validated_data.pop('father_name', '')
        tag_ids = validated_data.pop('tag_ids', [])
        vacancy_id = validated_data.pop('vacancy_id', None)
        
        # Extract file data
        document = validated_data.pop('document', None)
        profile_photo = validated_data.pop('profile_photo', None)
        document_type = validated_data.pop('document_type', 'OTHER')
        document_name = validated_data.pop('document_name', '')
        
        # Create user
        user = User.objects.create_user(
            username=email,  # Use email as username
            email=email,
            first_name=first_name,
            last_name=last_name
        )
        
        # Create employee (employee_id will be auto-generated in model save())
        validated_data['user'] = user
        validated_data['created_by'] = self.context['request'].user
        
        # Set profile photo if provided
        if profile_photo:
            validated_data['profile_image'] = profile_photo
        
        # Set vacancy link if provided
        if vacancy_id:
            validated_data['_vacancy_id'] = vacancy_id
        
        # Set contract_start_date to start_date if not provided
        if not validated_data.get('contract_start_date'):
            validated_data['contract_start_date'] = validated_data.get('start_date')
        
        # Set default values for required fields
        if 'contract_extensions' not in validated_data:
            validated_data['contract_extensions'] = 0
        if 'notes' not in validated_data:
            validated_data['notes'] = ''
        if 'grading_level' not in validated_data:
            validated_data['grading_level'] = ''
        if 'father_name' not in validated_data:
            validated_data['father_name'] = father_name
        
        # Create the employee (employee_id auto-generated)
        employee = super().create(validated_data)
        
        # Add tags
        if tag_ids:
            employee.tags.set(tag_ids)
        
        # Handle document upload
        if document:
            doc_name = document_name or document.name
            EmployeeDocument.objects.create(
                employee=employee,
                name=doc_name,
                document_type=document_type,
                document_file=document,
                uploaded_by=self.context['request'].user,
                document_status='ACTIVE',
                version=1,
                is_current_version=True
            )
        
        # Log activity
        activity_description = f"Employee {employee.full_name} created with auto-generated ID {employee.employee_id}"
        if document:
            activity_description += f" with document '{doc_name}'"
        if profile_photo:
            activity_description += " with profile photo"
        
        EmployeeActivity.objects.create(
            employee=employee,
            activity_type='CREATED',
            description=activity_description,
            performed_by=self.context['request'].user,
            metadata={
                'auto_generated_employee_id': employee.employee_id,
                'has_document': bool(document),
                'has_profile_photo': bool(profile_photo),
                'document_type': document_type if document else None
            }
        )
        
        return employee
    
    @transaction.atomic
    def update(self, instance, validated_data):
        # Extract user data
        first_name = validated_data.pop('first_name', None)
        last_name = validated_data.pop('last_name', None)
        email = validated_data.pop('email', None)
        father_name = validated_data.pop('father_name', None)
        tag_ids = validated_data.pop('tag_ids', None)
        vacancy_id = validated_data.pop('vacancy_id', None)
        
        # Extract file data
        document = validated_data.pop('document', None)
        profile_photo = validated_data.pop('profile_photo', None)
        document_type = validated_data.pop('document_type', 'OTHER')
        document_name = validated_data.pop('document_name', '')
        
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
                user.username = email  # Update username to match email
                changes.append(f"Email changed to {email}")
            user.save()
        
        # Update profile photo if provided
        if profile_photo:
            if instance.profile_image:
                try:
                    if hasattr(instance.profile_image, 'path'):
                        import os
                        old_image_path = instance.profile_image.path
                        if os.path.exists(old_image_path):
                            os.remove(old_image_path)
                except Exception as e:
                    logger.warning(f"Could not delete old profile image: {e}")
            
            instance.profile_image = profile_photo
            changes.append("Profile photo updated")
        
        # Update father_name if provided
        if father_name is not None and instance.father_name != father_name:
            instance.father_name = father_name
            changes.append(f"Father name changed to {father_name}")
        
        # Set updated_by
        validated_data['updated_by'] = self.context['request'].user
        
        # Update employee (employee_id should NOT be changed)
        employee = super().update(instance, validated_data)
        
        # Update tags
        if tag_ids is not None:
            employee.tags.set(tag_ids)
            changes.append("Tags updated")
        
        # Handle document upload
        if document:
            doc_name = document_name or document.name
            EmployeeDocument.objects.create(
                employee=employee,
                name=doc_name,
                document_type=document_type,
                document_file=document,
                uploaded_by=self.context['request'].user,
                document_status='ACTIVE',
                version=1,
                is_current_version=True
            )
            changes.append(f"Document '{doc_name}' uploaded")
        
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
                description=f"Employee {employee.full_name} updated: {'; '.join(changes)}",
                performed_by=self.context['request'].user,
                metadata={
                    'changes': changes,
                    'has_new_document': bool(document),
                    'has_new_profile_photo': bool(profile_photo),
                    'employee_id_unchanged': employee.employee_id  # Log that ID wasn't changed
                }
            )
        
        return employee

class BulkEmployeeCreateItemSerializer(serializers.Serializer):
    """Serializer for a single employee in bulk creation"""
    employee_id = serializers.CharField(max_length=50)
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    gender = serializers.ChoiceField(choices=Employee.GENDER_CHOICES, required=False, allow_null=True)
    father_name = serializers.CharField(max_length=200, required=False, allow_blank=True)
    address = serializers.CharField(required=False, allow_blank=True)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    emergency_contact = serializers.CharField(required=False, allow_blank=True)
    
    # Job Information
    business_function_id = serializers.IntegerField()
    department_id = serializers.IntegerField()
    unit_id = serializers.IntegerField(required=False, allow_null=True)
    job_function_id = serializers.IntegerField()
    job_title = serializers.CharField(max_length=200)
    position_group_id = serializers.IntegerField()
    grading_level = serializers.CharField(max_length=15, required=False, allow_blank=True)
    
    # Employment Details
    start_date = serializers.DateField()
    # FIXED: Use CharField instead of ChoiceField for dynamic contract types
    contract_duration = serializers.CharField(max_length=50, default='PERMANENT')
    contract_start_date = serializers.DateField(required=False, allow_null=True)
    line_manager_id = serializers.IntegerField(required=False, allow_null=True)
    
    # Additional
    is_visible_in_org_chart = serializers.BooleanField(default=True)
    tag_ids = serializers.ListField(child=serializers.IntegerField(), required=False, default=list)
    notes = serializers.CharField(required=False, allow_blank=True)
    vacancy_id = serializers.IntegerField(required=False, allow_null=True)
    
    def validate_contract_duration(self, value):
        """Validate that contract duration exists in configurations"""
        try:
            ContractTypeConfig.objects.get(contract_type=value, is_active=True)
        except ContractTypeConfig.DoesNotExist:
            # Get available choices for error message
            available_choices = list(ContractTypeConfig.objects.filter(is_active=True).values_list('contract_type', flat=True))
            raise serializers.ValidationError(
                f"Invalid contract duration '{value}'. Available choices: {', '.join(available_choices)}"
            )
        return value

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

class BulkLineManagerAssignmentSerializer(serializers.Serializer):
    """Bulk line manager assignment using employee IDs"""
    employee_ids = serializers.ListField(
        child=serializers.IntegerField(),
        help_text="List of employee IDs to update"
    )
    line_manager_id = serializers.IntegerField(
        allow_null=True,
        help_text="Line manager employee ID (null to remove line manager)"
    )
    
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

class SingleLineManagerAssignmentSerializer(serializers.Serializer):
    """Single employee line manager assignment"""
    employee_id = serializers.IntegerField(help_text="Employee ID")
    line_manager_id = serializers.IntegerField(
        allow_null=True,
        help_text="Line manager employee ID (null to remove line manager)"
    )
    
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

class BulkEmployeeTagUpdateSerializer(serializers.Serializer):
    """Simple bulk tag operations using employee IDs"""
    employee_ids = serializers.ListField(
        child=serializers.IntegerField(),
        help_text="List of employee IDs to update"
    )
    tag_id = serializers.IntegerField(help_text="Tag ID to add or remove")
    
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

class SingleEmployeeTagUpdateSerializer(serializers.Serializer):
    """Single employee tag operations"""
    employee_id = serializers.IntegerField(help_text="Employee ID")
    tag_id = serializers.IntegerField(help_text="Tag ID to add or remove")
    
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

class BulkEmployeeGradingUpdateSerializer(serializers.Serializer):
    """Serializer for bulk updating employee grades"""
    updates = serializers.ListField(
        child=EmployeeGradingUpdateSerializer(),
        help_text="List of employee grading updates",
        allow_empty=False
    )
    
    def validate_updates(self, value):
        if not value:
            raise serializers.ValidationError("At least one update is required")
        return value

class OrgChartNodeSerializer(serializers.ModelSerializer):
    """FINAL FIXED: Enhanced serializer for organizational chart nodes"""
    
    # Basic employee info for org chart
    name = serializers.CharField(source='full_name', read_only=True)
    title = serializers.CharField(source='job_title', read_only=True)
    avatar = serializers.SerializerMethodField()
    
    # Organizational info
    department = serializers.CharField(source='department.name', read_only=True)
    unit = serializers.SerializerMethodField()
    business_function = serializers.CharField(source='business_function.name', read_only=True)
    position_group = serializers.CharField(source='position_group.get_name_display', read_only=True)
    
    # Contact info
    email = serializers.CharField(source='user.email', read_only=True)
    phone = serializers.SerializerMethodField()
    
    # Hierarchy info
    line_manager_id = serializers.CharField(source='line_manager.employee_id', read_only=True)
    direct_reports = serializers.SerializerMethodField()
    direct_reports_details = serializers.SerializerMethodField()  # NEW: Detailed direct reports
    
    # Visual info
    status_color = serializers.CharField(source='status.color', read_only=True)
    profile_image_url = serializers.SerializerMethodField()
    
    # Additional calculated fields
    level_to_ceo = serializers.SerializerMethodField()
    total_subordinates = serializers.SerializerMethodField()
    colleagues_in_unit = serializers.SerializerMethodField()
    colleagues_in_business_function = serializers.SerializerMethodField()
    manager_info = serializers.SerializerMethodField()
    
    # Employee details
    employee_details = serializers.SerializerMethodField()
    
    class Meta:
        model = Employee
        fields = [
            # Org chart essentials
            'employee_id', 'name', 'title', 'avatar',
            'department', 'unit', 'business_function', 'position_group',
            'email', 'phone',
            'line_manager_id', 'direct_reports', 'direct_reports_details', 'status_color',
            'profile_image_url',
            
            # Calculated metrics
            'level_to_ceo', 'total_subordinates', 
            'colleagues_in_unit', 'colleagues_in_business_function',
            'manager_info', 'employee_details'
        ]
    
    def get_avatar(self, obj):
        """Generate avatar initials safely"""
        try:
            if not obj.full_name:
                return 'NA'
            
            words = obj.full_name.strip().split()
            if len(words) >= 2:
                return f"{words[0][0]}{words[1][0]}".upper()
            elif len(words) == 1:
                return words[0][:2].upper()
            return 'NA'
        except Exception:
            return 'NA'
    
    
    def get_unit(self, obj):
        """FIXED: Get unit name properly or department name as fallback"""
        try:
            if obj.unit and obj.unit.name:
                return obj.unit.name
            
            return 'N/A'
        except Exception:
            return 'N/A'
    
    def get_phone(self, obj):
        """Get phone or default"""
        return obj.phone or '+994 50 xxx xxxx'
    
    def get_direct_reports(self, obj):
        """Get number of direct reports safely"""
        try:
            return Employee.objects.filter(
                line_manager=obj,
                status__allows_org_chart=True,
                is_deleted=False
            ).count()
        except Exception:
            return 0
    
    def get_direct_reports_details(self, obj):
        """NEW: Get detailed information about direct reports"""
        try:
            direct_reports = Employee.objects.filter(
                line_manager=obj,
                status__allows_org_chart=True,
                is_deleted=False
            ).select_related('user', 'department', 'position_group', 'status')
            
            reports_data = []
            for report in direct_reports:
                report_data = {
                    'id': report.id,
                    'employee_id': report.employee_id,
                    'name': report.full_name,
                    'title': report.job_title,
                    'department': report.department.name if report.department else 'N/A',
                    'unit': report.unit.name if report.unit else None,
                    'position_group': report.position_group.get_name_display() if report.position_group else 'N/A',
                    'email': report.user.email if report.user else 'N/A',
                    'avatar': self.get_avatar(report),
                    'status_color': report.status.color if report.status else '#6B7280',
                    'profile_image_url': self._get_safe_profile_image_url(report)
                }
                reports_data.append(report_data)
            
            return reports_data
        except Exception:
            return []
    
    def _get_safe_profile_image_url(self, employee):
        """Get profile image URL safely for any employee"""
        try:
            if employee.profile_image and hasattr(employee.profile_image, 'url'):
                request = self.context.get('request')
                if request:
                    return request.build_absolute_uri(employee.profile_image.url)
                return employee.profile_image.url
        except Exception:
            pass
        return None
    
    def get_profile_image_url(self, obj):
        """Get profile image URL safely"""
        return self._get_safe_profile_image_url(obj)
    
    def get_level_to_ceo(self, obj):
        """FIXED: Calculate level to CEO with recursion protection"""
        try:
            level = 0
            current = obj
            visited = set()
            
            while current and current.line_manager and current.id not in visited:
                visited.add(current.id)
                current = current.line_manager
                level += 1
                
                if level > 10:  # Prevent infinite loops
                    break
            
            return level
        except Exception:
            return 0
    
    def get_total_subordinates(self, obj):
        """FIXED: Calculate total subordinates with recursion protection"""
        try:
            def count_subordinates_safe(employee, visited=None):
                if visited is None:
                    visited = set()
                
                if employee.id in visited:
                    return 0
                
                visited.add(employee.id)
                
                direct_reports = Employee.objects.filter(
                    line_manager=employee,
                    status__allows_org_chart=True,
                    is_deleted=False
                )
                
                total = direct_reports.count()
                for report in direct_reports:
                    if report.id not in visited:
                        total += count_subordinates_safe(report, visited.copy())
                
                return total
            
            return count_subordinates_safe(obj)
        except Exception:
            return 0
    
    def get_colleagues_in_unit(self, obj):
        """Get colleagues in same unit safely"""
        try:
            if not obj.unit:
                return 0
            
            return Employee.objects.filter(
                unit=obj.unit,
                status__allows_org_chart=True,
                is_deleted=False
            ).exclude(id=obj.id).count()
        except Exception:
            return 0
    
    def get_colleagues_in_business_function(self, obj):
        """Get colleagues in same business function safely"""
        try:
            if not obj.business_function:
                return 0
            
            return Employee.objects.filter(
                business_function=obj.business_function,
                status__allows_org_chart=True,
                is_deleted=False
            ).exclude(id=obj.id).count()
        except Exception:
            return 0
    
    def get_manager_info(self, obj):
        """Get manager information safely"""
        try:
            if not obj.line_manager:
                return None
            
            manager = obj.line_manager
            return {
                'id': manager.employee_id,
                'name': manager.full_name,
                'title': manager.job_title,
                'department': manager.department.name if manager.department else 'N/A',
                'avatar': self.get_avatar(manager),
                'email': manager.user.email if manager.user else None,
                'profile_image_url': self._get_safe_profile_image_url(manager)
            }
        except Exception:
            return None
    
    def get_employee_details(self, obj):
        """Get additional employee details safely"""
        try:
            # FIXED: Safe grading display - only from employee_details
            grading_display = 'No Grade'
            if obj.grading_level:
                parts = obj.grading_level.split('_')
                if len(parts) == 2:
                    position_short, level = parts
                    grading_display = f"{position_short}-{level}"
                else:
                    grading_display = obj.grading_level
            elif obj.position_group:
                grading_display = f"{obj.position_group.grading_shorthand}-M"
            
            # FIXED: Safe contract duration
            contract_duration = obj.contract_duration
            try:
                if hasattr(obj, 'get_contract_duration_display'):
                    contract_duration = obj.get_contract_duration_display()
            except:
                pass
            
            return {
                'internal_id': obj.id,
                'start_date': obj.start_date,
                'contract_duration': contract_duration,
                'years_of_service': obj.years_of_service,
                'grading_display': grading_display,  # ONLY grading info here
                'tags': [
                    {'name': tag.name, 'color': tag.color, } 
                    for tag in obj.tags.filter(is_active=True)
                ],
                'is_visible_in_org_chart': obj.is_visible_in_org_chart,
                'created_at': obj.created_at,
                'updated_at': obj.updated_at
            }
        except Exception as e:
            # Return basic details if there's any error
            return {
                'internal_id': obj.id,
                'start_date': obj.start_date,
                'contract_duration': getattr(obj, 'contract_duration', 'N/A'),
                'years_of_service': getattr(obj, 'years_of_service', 0),
                'grading_display': 'No Grade',
                'tags': [],
                'is_visible_in_org_chart': getattr(obj, 'is_visible_in_org_chart', True),
                'created_at': getattr(obj, 'created_at', None),
                'updated_at': getattr(obj, 'updated_at', None)
            }

class ContractExpirySerializer(serializers.ModelSerializer):
    """Serializer for contract expiry tracking"""
    name = serializers.CharField(source='full_name', read_only=True)
    business_function_name = serializers.CharField(source='business_function.name', read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True)
    position_group_name = serializers.CharField(source='position_group.get_name_display', read_only=True)
    days_until_expiry = serializers.SerializerMethodField()
    status_needs_update = serializers.SerializerMethodField()
    
    class Meta:
        model = Employee
        fields = [
            'id', 'employee_id', 'name', 'job_title', 'business_function_name',
            'department_name', 'position_group_name', 'contract_duration',
            'contract_end_date', 'days_until_expiry', 'status_needs_update'
        ]
    
    def get_days_until_expiry(self, obj):
        if obj.contract_end_date:
            delta = obj.contract_end_date - date.today()
            return delta.days
        return None
    
    def get_status_needs_update(self, obj):
        try:
            preview = obj.get_status_preview()
            return preview['needs_update']
        except:
            return False

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

class ContractExtensionSerializer(serializers.Serializer):
    """Contract extension for single employee - WITHOUT extension_months"""
    employee_id = serializers.IntegerField(help_text="Employee ID")
    new_contract_type = serializers.CharField(
        max_length=50,
        help_text="New contract type (required)"
    )
    new_start_date = serializers.DateField(
        help_text="New contract start date (required)"
    )
    reason = serializers.CharField(
        max_length=500,
        required=False,
        help_text="Reason for contract change"
    )
    
    def validate_employee_id(self, value):
        try:
            Employee.objects.get(id=value)
        except Employee.DoesNotExist:
            raise serializers.ValidationError("Employee not found.")
        return value
    
    def validate_new_contract_type(self, value):
        try:
            ContractTypeConfig.objects.get(contract_type=value, is_active=True)
        except ContractTypeConfig.DoesNotExist:
            available_choices = list(ContractTypeConfig.objects.filter(is_active=True).values_list('contract_type', flat=True))
            raise serializers.ValidationError(
                f"Invalid contract type '{value}'. Available choices: {', '.join(available_choices)}"
            )
        return value

class BulkContractExtensionSerializer(serializers.Serializer):
    """Bulk contract extension - WITHOUT extension_months"""
    employee_ids = serializers.ListField(
        child=serializers.IntegerField(),
        help_text="List of employee IDs to update contracts"
    )
    new_contract_type = serializers.CharField(
        max_length=50,
        help_text="New contract type for all employees (required)"
    )
    new_start_date = serializers.DateField(
        help_text="New contract start date for all employees (required)"
    )
    reason = serializers.CharField(
        max_length=500,
        required=False,
        help_text="Reason for contract change"
    )
    
    def validate_employee_ids(self, value):
        if not value:
            raise serializers.ValidationError("At least one employee ID is required.")
        
        employees = Employee.objects.filter(id__in=value)
        if employees.count() != len(value):
            raise serializers.ValidationError("Some employee IDs do not exist.")
        
        return value
    
    def validate_new_contract_type(self, value):
        try:
            ContractTypeConfig.objects.get(contract_type=value, is_active=True)
        except ContractTypeConfig.DoesNotExist:
            available_choices = list(ContractTypeConfig.objects.filter(is_active=True).values_list('contract_type', flat=True))
            raise serializers.ValidationError(
                f"Invalid contract type '{value}'. Available choices: {', '.join(available_choices)}"
            )
        return value

                    
                    