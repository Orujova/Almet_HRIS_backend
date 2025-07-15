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
        fields = ['id', 'name', 'tag_type', 'color', 'is_active', 'employee_count', 'created_at']
    
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

class DocumentUploadSerializer(serializers.Serializer):
    """File upload serializer - Fixed version handling"""
    employee_id = serializers.IntegerField(
        help_text="Employee ID to associate document with"
    )
    name = serializers.CharField(
        max_length=255,
        help_text="Document name or title"
    )
    document_type = serializers.ChoiceField(
        choices=EmployeeDocument.DOCUMENT_TYPES,
        default='OTHER',
        help_text="Type of document being uploaded"
    )
    document_file = serializers.FileField(
        help_text="Document file to upload (PDF, DOC, DOCX, JPG, PNG, etc.)"
    )
    description = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Optional document description"
    )
    expiry_date = serializers.DateField(
        required=False,
        allow_null=True,
        help_text="Document expiry date (YYYY-MM-DD format)"
    )
    is_confidential = serializers.BooleanField(
        default=False,
        help_text="Mark document as confidential"
    )
    is_required = serializers.BooleanField(
        default=False,
        help_text="Mark document as required"
    )
    replace_existing = serializers.BooleanField(
        default=False,
        help_text="Replace existing document with same name and type"
    )
    
    def validate_employee_id(self, value):
        try:
            Employee.objects.get(id=value)
        except Employee.DoesNotExist:
            raise serializers.ValidationError("Employee not found.")
        return value
    
    def validate_document_file(self, value):
        # File size validation (50MB max)
        if value.size > 50 * 1024 * 1024:
            raise serializers.ValidationError("File size cannot exceed 50MB.")
        
        # File type validation
        allowed_types = [
            'application/pdf', 'application/msword', 
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'image/jpeg', 'image/png', 'image/gif', 'image/bmp',
            'text/plain', 'application/vnd.ms-excel',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        ]
        
        import mimetypes
        file_type, _ = mimetypes.guess_type(value.name)
        
        if file_type and file_type not in allowed_types:
            raise serializers.ValidationError(f"File type {file_type} is not allowed.")
        
        return value
    
    def create(self, validated_data):
        employee_id = validated_data.pop('employee_id')
        replace_existing = validated_data.pop('replace_existing', False)
        
        employee = Employee.objects.get(id=employee_id)
        validated_data['employee'] = employee
        validated_data['uploaded_by'] = self.context['request'].user
        
        # Set default status
        validated_data['document_status'] = 'ACTIVE'
        
        # FIXED: Handle existing documents and versioning properly
        if replace_existing:
            # Check for existing documents with same name and type
            existing_docs = EmployeeDocument.objects.filter(
                employee=employee,
                name=validated_data['name'],
                document_type=validated_data['document_type'],
                is_deleted=False
            ).order_by('-version')
            
            if existing_docs.exists():
                # Mark existing documents as not current
                existing_docs.update(is_current_version=False)
                
                # Set version number
                latest_version = existing_docs.first().version
                validated_data['version'] = latest_version + 1
                
                # Set the latest document as replaced by the new one
                latest_doc = existing_docs.first()
                validated_data['_replace_document_id'] = latest_doc.id
            else:
                validated_data['version'] = 1
        else:
            # For new documents, check if same name+type already exists
            existing_count = EmployeeDocument.objects.filter(
                employee=employee,
                name=validated_data['name'],
                document_type=validated_data['document_type'],
                is_deleted=False
            ).count()
            
            if existing_count > 0:
                # Auto-increment the name to make it unique
                base_name = validated_data['name']
                counter = 1
                while EmployeeDocument.objects.filter(
                    employee=employee,
                    name=f"{base_name} ({counter})",
                    document_type=validated_data['document_type'],
                    is_deleted=False
                ).exists():
                    counter += 1
                
                validated_data['name'] = f"{base_name} ({counter})"
            
            validated_data['version'] = 1
        
        # Ensure is_current_version is True for new uploads
        validated_data['is_current_version'] = True
        
        # Create the document
        document = EmployeeDocument.objects.create(**validated_data)
        
        # Handle replacement relationship
        if replace_existing and '_replace_document_id' in validated_data:
            try:
                replaced_doc = EmployeeDocument.objects.get(id=validated_data['_replace_document_id'])
                replaced_doc.replaced_by = document
                replaced_doc.save()
            except EmployeeDocument.DoesNotExist:
                pass
        
        return document
    
class BulkDocumentUploadSerializer(serializers.Serializer):
    """Bulk document upload serializer - Fixed version handling"""
    employee_id = serializers.IntegerField(
        help_text="Employee ID to upload documents for"
    )
    documents = serializers.ListField(
        child=serializers.FileField(),
        min_length=1,
        max_length=10,
        help_text="List of document files (max 10 files)"
    )
    document_type = serializers.ChoiceField(
        choices=EmployeeDocument.DOCUMENT_TYPES,
        default='OTHER',
        help_text="Document type for all uploaded files"
    )
    is_confidential = serializers.BooleanField(
        default=False,
        help_text="Mark all documents as confidential"
    )
    replace_existing = serializers.BooleanField(
        default=False,
        help_text="Replace existing documents with same names"
    )
    
    def validate_employee_id(self, value):
        try:
            Employee.objects.get(id=value)
        except Employee.DoesNotExist:
            raise serializers.ValidationError("Employee not found.")
        return value
    
    def validate_documents(self, value):
        total_size = sum(doc.size for doc in value)
        if total_size > 100 * 1024 * 1024:  # 100MB total
            raise serializers.ValidationError("Total file size cannot exceed 100MB.")
        
        for doc in value:
            if doc.size > 50 * 1024 * 1024:  # 50MB per file
                raise serializers.ValidationError(f"File {doc.name} exceeds 50MB limit.")
        
        return value

class DocumentReplaceSerializer(serializers.Serializer):
    """Serializer for replacing an existing document"""
    document_file = serializers.FileField(
        help_text="New document file to replace the existing one"
    )
    description = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Optional description for the new version"
    )
    
    def validate_document_file(self, value):
        # Same validation as DocumentUploadSerializer
        if value.size > 50 * 1024 * 1024:
            raise serializers.ValidationError("File size cannot exceed 50MB.")
        
        allowed_types = [
            'application/pdf', 'application/msword', 
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'image/jpeg', 'image/png', 'image/gif', 'image/bmp',
            'text/plain', 'application/vnd.ms-excel',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        ]
        
        import mimetypes
        file_type, _ = mimetypes.guess_type(value.name)
        
        if file_type and file_type not in allowed_types:
            raise serializers.ValidationError(f"File type {file_type} is not allowed.")
        
        return value

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
    grading_display = serializers.CharField(source='get_grading_display', read_only=True)
    renewal_status_display = serializers.CharField(source='get_renewal_status_display', read_only=True)
    direct_reports_count = serializers.SerializerMethodField()
    status_needs_update = serializers.SerializerMethodField()
    profile_image_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Employee
        fields = [
            'id', 'employee_id', 'name', 'email', 'date_of_birth', 'gender', 'father_name', 'phone',
            'business_function_name', 'business_function_code', 'department_name', 'unit_name',
            'job_function_name', 'job_title', 'position_group_name', 'position_group_level',
            'grading_level', 'grading_display', 'start_date', 'end_date',
            'contract_duration', 'contract_duration_display', 'contract_start_date', 'contract_end_date',
            'contract_extensions', 'last_extension_date', 'renewal_status', 'renewal_status_display',
            'line_manager_name', 'line_manager_hc_number', 'status_name', 'status_color',
            'tag_names', 'years_of_service', 'current_status_display', 'is_visible_in_org_chart',
            'direct_reports_count', 'status_needs_update', 'created_at', 'updated_at','profile_image_url',
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
                'type': tag.tag_type
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
    
    # Contract status analysis
    status_preview = serializers.SerializerMethodField()
    
    # Vacancy information
    filled_vacancy_detail = VacantPositionListSerializer(source='filled_vacancy', read_only=True)
    
    profile_image_url = serializers.SerializerMethodField()
    documents = EmployeeDocumentSerializer(many=True, read_only=True)
    documents_count = serializers.SerializerMethodField()
    class Meta:
        model = Employee
        fields = '__all__'
    
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

class EmployeeCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating and updating employees with enhanced validation"""
    first_name = serializers.CharField(write_only=True)
    last_name = serializers.CharField(write_only=True)
    email = serializers.EmailField(write_only=True)
    father_name = serializers.CharField(write_only=True, required=False, allow_blank=True)
    tag_ids = serializers.ListField(child=serializers.IntegerField(), write_only=True, required=False)
    vacancy_id = serializers.IntegerField(write_only=True, required=False, help_text="Link to vacant position")
    
    class Meta:
        model = Employee
        exclude = ['user', 'full_name', 'tags', 'filled_vacancy', 'status', 'created_by', 'updated_by']
    
    def validate_contract_duration(self, value):
        """Validate that contract duration exists in configurations"""
        try:
            if not ContractTypeConfig.objects.filter(contract_type=value, is_active=True).exists():
                # Get available choices for error message
                available_choices = list(ContractTypeConfig.objects.filter(is_active=True).values_list('contract_type', flat=True))
                if not available_choices:
                    # Create defaults if none exist
                    ContractTypeConfig.get_or_create_defaults()
                    available_choices = list(ContractTypeConfig.objects.filter(is_active=True).values_list('contract_type', flat=True))
                
                if not available_choices:
                    # Final fallback
                    available_choices = ['3_MONTHS', '6_MONTHS', '1_YEAR', '2_YEARS', '3_YEARS', 'PERMANENT']
                
                raise serializers.ValidationError(
                    f"Invalid contract duration '{value}'. Available choices: {', '.join(available_choices)}"
                )
        except ContractTypeConfig.DoesNotExist:
            # This shouldn't happen with the above code, but just in case
            pass
        
        return value
    
    
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
    
    def validate(self, data):
        """Cross-field validation including grading level"""
        # Validate grading level matches position group
        grading_level = data.get('grading_level')
        position_group = data.get('position_group')
        
        # If updating, get existing values if not provided
        if self.instance:
            if not position_group:
                position_group = self.instance.position_group
        
        if grading_level and position_group:
            expected_prefix = position_group.grading_shorthand
            if not grading_level.startswith(expected_prefix):
                raise serializers.ValidationError({
                    'grading_level': f"Grading level must start with {expected_prefix} for this position group."
                })
        
        return data
    
    @transaction.atomic
    def create(self, validated_data):
        # Extract user data
        first_name = validated_data.pop('first_name')
        last_name = validated_data.pop('last_name')
        email = validated_data.pop('email')
        father_name = validated_data.pop('father_name', '')  # NEW FIELD
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
        validated_data['created_by'] = self.context['request'].user
        
        if vacancy_id:
            validated_data['_vacancy_id'] = vacancy_id
        
        # Set contract_start_date to start_date if not provided
        if not validated_data.get('contract_start_date'):
            validated_data['contract_start_date'] = validated_data.get('start_date')
        
        # Set default values for new fields
        if 'contract_extensions' not in validated_data:
            validated_data['contract_extensions'] = 0
        if 'renewal_status' not in validated_data:
            if validated_data.get('contract_duration') == 'PERMANENT':
                validated_data['renewal_status'] = 'NOT_APPLICABLE'
            else:
                validated_data['renewal_status'] = 'PENDING'
        if 'notes' not in validated_data:
            validated_data['notes'] = ''
        if 'grading_level' not in validated_data:
            validated_data['grading_level'] = ''
        if 'father_name' not in validated_data:
            validated_data['father_name'] = father_name
        
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
        father_name = validated_data.pop('father_name', None)  # NEW FIELD
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
        
        # Update father_name if provided
        if father_name is not None and instance.father_name != father_name:
            instance.father_name = father_name
            changes.append(f"Father name changed to {father_name}")
        
        # Track other significant changes
        if 'line_manager' in validated_data and validated_data['line_manager'] != instance.line_manager:
            old_manager = instance.line_manager.full_name if instance.line_manager else "None"
            new_manager = validated_data['line_manager'].full_name if validated_data['line_manager'] else "None"
            changes.append(f"Line manager changed from {old_manager} to {new_manager}")
        
        if 'position_group' in validated_data and validated_data['position_group'] != instance.position_group:
            changes.append(f"Position changed from {instance.position_group.get_name_display()} to {validated_data['position_group'].get_name_display()}")
        
        if 'grading_level' in validated_data and validated_data['grading_level'] != instance.grading_level:
            changes.append(f"Grading level changed from {instance.grading_level} to {validated_data['grading_level']}")
        
        # Set updated_by
        validated_data['updated_by'] = self.context['request'].user
        
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

class BulkEmployeeCreateItemSerializer(serializers.Serializer):
    """Serializer for a single employee in bulk creation"""
    employee_id = serializers.CharField(max_length=50)
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    gender = serializers.ChoiceField(choices=Employee.GENDER_CHOICES, required=False, allow_null=True)
    father_name = serializers.CharField(max_length=200, required=False, allow_blank=True)  # NEW FIELD
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
    contract_duration = serializers.CharField(max_length=50, default='PERMANENT')
    contract_start_date = serializers.DateField(required=False, allow_null=True)
    line_manager_id = serializers.IntegerField(required=False, allow_null=True)  # ENHANCED FOR LINE MANAGER
    
    # Additional
    is_visible_in_org_chart = serializers.BooleanField(default=True)
    tag_ids = serializers.ListField(child=serializers.IntegerField(), required=False, default=list)
    notes = serializers.CharField(required=False, allow_blank=True)
    vacancy_id = serializers.IntegerField(required=False, allow_null=True)

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
    """Enhanced serializer for organizational chart nodes with full data"""
    name = serializers.CharField(source='full_name', read_only=True)
    children = serializers.SerializerMethodField()
    status_color = serializers.CharField(source='status.color', read_only=True)
    position_level = serializers.IntegerField(source='position_group.hierarchy_level', read_only=True)
    grading_display = serializers.CharField(source='get_grading_display', read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True)
    business_function_name = serializers.CharField(source='business_function.name', read_only=True)
    
    class Meta:
        model = Employee
        fields = [
            'id', 'employee_id', 'name', 'job_title', 'position_group', 
            'position_level', 'department', 'department_name', 
            'business_function', 'business_function_name', 'profile_image', 
            'status_color', 'grading_display', 'children'
        ]
    
    def get_children(self, obj):
        """Get direct reports as children"""
        children = obj.direct_reports.filter(
            status__allows_org_chart=True,
            is_visible_in_org_chart=True,
            is_deleted=False
        ).select_related(
            'status', 'position_group', 'department', 'business_function'
        ).order_by('position_group__hierarchy_level', 'full_name')
        
        return OrgChartNodeSerializer(children, many=True, context=self.context).data

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

class BulkSoftDeleteSerializer(serializers.Serializer):
    """Bulk soft delete employees"""
    employee_ids = serializers.ListField(
        child=serializers.IntegerField(),
        help_text="List of employee IDs to soft delete"
    )
    
    def validate_employee_ids(self, value):
        if not value:
            raise serializers.ValidationError("At least one employee ID is required.")
        
        existing_count = Employee.objects.filter(id__in=value, is_deleted=False).count()
        if existing_count != len(value):
            raise serializers.ValidationError("Some employee IDs do not exist or are already deleted.")
        
        return value

class BulkRestoreSerializer(serializers.Serializer):
    """Bulk restore soft-deleted employees"""
    employee_ids = serializers.ListField(
        child=serializers.IntegerField(),
        help_text="List of employee IDs to restore"
    )
    
    def validate_employee_ids(self, value):
        if not value:
            raise serializers.ValidationError("At least one employee ID is required.")
        
        existing_count = Employee.all_objects.filter(id__in=value, is_deleted=True).count()
        if existing_count != len(value):
            raise serializers.ValidationError("Some employee IDs do not exist or are not deleted.")
        
        return value

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


