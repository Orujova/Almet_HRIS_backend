# api/job_description_serializers.py

from rest_framework import serializers
from .job_description_models import (
    JobDescription, JobDescriptionSection, JobDescriptionSkill,
    JobDescriptionBehavioralCompetency, JobBusinessResource, AccessMatrix,
    CompanyBenefit, JobDescriptionBusinessResource, JobDescriptionAccessMatrix,
    JobDescriptionCompanyBenefit, JobDescriptionActivity
)
from .models import BusinessFunction, Department, Unit, PositionGroup, Employee
from .competency_models import Skill, BehavioralCompetency
from django.contrib.auth.models import User


# Base serializers for related models
class BusinessFunctionBasicSerializer(serializers.ModelSerializer):
    class Meta:
        model = BusinessFunction
        fields = ['id', 'name', 'code']


class DepartmentBasicSerializer(serializers.ModelSerializer):
    business_function = BusinessFunctionBasicSerializer(read_only=True)
    
    class Meta:
        model = Department
        fields = ['id', 'name', 'business_function']


class UnitBasicSerializer(serializers.ModelSerializer):
    department = DepartmentBasicSerializer(read_only=True)
    
    class Meta:
        model = Unit
        fields = ['id', 'name', 'department']


class PositionGroupBasicSerializer(serializers.ModelSerializer):
    class Meta:
        model = PositionGroup
        fields = ['id', 'name', 'hierarchy_level', 'grading_shorthand']


class EmployeeBasicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Employee
        fields = ['id', 'employee_id', 'full_name', 'job_title', ]


class UserBasicSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name',]


# Competency serializers
class SkillBasicSerializer(serializers.ModelSerializer):
    group_name = serializers.CharField(source='group.name', read_only=True)
    
    class Meta:
        model = Skill
        fields = ['id', 'name', 'group_name']


class BehavioralCompetencyBasicSerializer(serializers.ModelSerializer):
    group_name = serializers.CharField(source='group.name', read_only=True)
    
    class Meta:
        model = BehavioralCompetency
        fields = ['id', 'name', 'group_name']


# Extra table serializers
class JobBusinessResourceSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    
    class Meta:
        model = JobBusinessResource
        fields = [
            'id', 'name', 'description', 'category', 'is_active',
            'created_at', 'created_by', 'created_by_name'
        ]
        read_only_fields = ['created_at', 'created_by']


class AccessMatrixSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    
    class Meta:
        model = AccessMatrix
        fields = [
            'id', 'name', 'description', 'access_level', 'is_active',
            'created_at', 'created_by', 'created_by_name'
        ]
        read_only_fields = ['created_at', 'created_by']


class CompanyBenefitSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    
    class Meta:
        model = CompanyBenefit
        fields = [
            'id', 'name', 'description', 'benefit_type', 'is_active',
            'created_at', 'created_by', 'created_by_name'
        ]
        read_only_fields = ['created_at', 'created_by']


# Job Description component serializers
class JobDescriptionSectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobDescriptionSection
        fields = ['id', 'section_type', 'title', 'content', 'order']


class JobDescriptionSkillSerializer(serializers.ModelSerializer):
    skill_detail = SkillBasicSerializer(source='skill', read_only=True)
    
    class Meta:
        model = JobDescriptionSkill
        fields = ['id', 'skill', 'skill_detail', 'proficiency_level', 'is_mandatory']


class JobDescriptionBehavioralCompetencySerializer(serializers.ModelSerializer):
    competency_detail = BehavioralCompetencyBasicSerializer(source='competency', read_only=True)
    
    class Meta:
        model = JobDescriptionBehavioralCompetency
        fields = ['id', 'competency', 'competency_detail', 'proficiency_level', 'is_mandatory']


class JobDescriptionBusinessResourceSerializer(serializers.ModelSerializer):
    resource_detail = JobBusinessResourceSerializer(source='resource', read_only=True)
    
    class Meta:
        model = JobDescriptionBusinessResource
        fields = ['id', 'resource', 'resource_detail']


class JobDescriptionAccessMatrixSerializer(serializers.ModelSerializer):
    access_detail = AccessMatrixSerializer(source='access_matrix', read_only=True)
    
    class Meta:
        model = JobDescriptionAccessMatrix
        fields = ['id', 'access_matrix', 'access_detail']


class JobDescriptionCompanyBenefitSerializer(serializers.ModelSerializer):
    benefit_detail = CompanyBenefitSerializer(source='benefit', read_only=True)
    
    class Meta:
        model = JobDescriptionCompanyBenefit
        fields = ['id', 'benefit', 'benefit_detail']


class JobDescriptionActivitySerializer(serializers.ModelSerializer):
    performed_by_detail = UserBasicSerializer(source='performed_by', read_only=True)
    
    class Meta:
        model = JobDescriptionActivity
        fields = [
            'id', 'activity_type', 'description', 'performed_by', 
            'performed_by_detail', 'performed_at', 'metadata'
        ]


# Main Job Description serializers
class JobDescriptionListSerializer(serializers.ModelSerializer):
    """Serializer for job description list view"""
    
    business_function_name = serializers.CharField(source='business_function.name', read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True)
    unit_name = serializers.CharField(source='unit.name', read_only=True)
    position_group_name = serializers.CharField(source='position_group.get_name_display', read_only=True)
    reports_to_name = serializers.CharField(source='reports_to.full_name', read_only=True)
    employee_info = serializers.SerializerMethodField()
    manager_info = serializers.SerializerMethodField()
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    status_display = serializers.SerializerMethodField()
    
    class Meta:
        model = JobDescription
        fields = [
            'id', 'job_title', 'business_function_name', 'department_name',
            'unit_name', 'position_group_name', 'grading_level', 'reports_to_name',
            'employee_info', 'manager_info', 'status', 'status_display', 'version', 'is_active',
            'created_at', 'created_by_name'
        ]
    
    def get_status_display(self, obj):
        return obj.get_status_display_with_color()
    
    def get_employee_info(self, obj):
        return obj.get_employee_info()
    
    def get_can_approve_as_employee(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        
        return obj.can_be_approved_by_employee(request.user)
    
    def get_employee_info(self, obj):
        return obj.get_employee_info()
    
    def get_manager_info(self, obj):
        return obj.get_manager_info()


class JobDescriptionDetailSerializer(serializers.ModelSerializer):
    """Serializer for job description detail view"""
    
    # Related object details
    business_function = BusinessFunctionBasicSerializer(read_only=True)
    department = DepartmentBasicSerializer(read_only=True)
    unit = UnitBasicSerializer(read_only=True)
    position_group = PositionGroupBasicSerializer(read_only=True)
    reports_to = EmployeeBasicSerializer(read_only=True)
    assigned_employee = EmployeeBasicSerializer(read_only=True)
    
    # Employee and manager info
    employee_info = serializers.SerializerMethodField()
    manager_info = serializers.SerializerMethodField()
    
    # User details
    created_by_detail = UserBasicSerializer(source='created_by', read_only=True)
    updated_by_detail = UserBasicSerializer(source='updated_by', read_only=True)
    line_manager_approved_by_detail = UserBasicSerializer(source='line_manager_approved_by', read_only=True)
    employee_approved_by_detail = UserBasicSerializer(source='employee_approved_by', read_only=True)
    
    # Related components
    sections = JobDescriptionSectionSerializer(many=True, read_only=True)
    required_skills = JobDescriptionSkillSerializer(many=True, read_only=True)
    behavioral_competencies = JobDescriptionBehavioralCompetencySerializer(many=True, read_only=True)
    business_resources = JobDescriptionBusinessResourceSerializer(many=True, read_only=True)
    access_rights = JobDescriptionAccessMatrixSerializer(many=True, read_only=True)
    company_benefits = JobDescriptionCompanyBenefitSerializer(many=True, read_only=True)
    
    # Status display
    status_display = serializers.SerializerMethodField()
    
    # Signature URLs
    line_manager_signature_url = serializers.SerializerMethodField()
    employee_signature_url = serializers.SerializerMethodField()
    
    # Permissions
    can_edit = serializers.SerializerMethodField()
    can_approve_as_line_manager = serializers.SerializerMethodField()
    can_approve_as_employee = serializers.SerializerMethodField()
    
    class Meta:
        model = JobDescription
        fields = [
            # Basic info
            'id', 'job_title', 'job_purpose', 'grading_level', 'version', 'is_active',
            
            # Organizational structure
            'business_function', 'department', 'unit', 'position_group', 'reports_to',
            
            # Employee assignment (existing or manual)
            'assigned_employee', 'manual_employee_name', 'manual_employee_phone',
            'employee_info', 'manager_info',
            
            # Status and approval
            'status', 'status_display',
            'line_manager_approved_by', 'line_manager_approved_by_detail', 'line_manager_approved_at', 'line_manager_comments',
            'employee_approved_by', 'employee_approved_by_detail', 'employee_approved_at', 'employee_comments',
            
            # Signatures
            'line_manager_signature', 'line_manager_signature_url',
            'employee_signature', 'employee_signature_url',
            
            # Metadata
            'created_by', 'created_by_detail', 'created_at',
            'updated_by', 'updated_by_detail', 'updated_at',
            
            # Related components
            'sections', 'required_skills', 'behavioral_competencies',
            'business_resources', 'access_rights', 'company_benefits',
            
            # Permissions
            'can_edit', 'can_approve_as_line_manager', 'can_approve_as_employee'
        ]
    
    def get_status_display(self, obj):
        return obj.get_status_display_with_color()
    
    def get_line_manager_signature_url(self, obj):
        if obj.line_manager_signature:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.line_manager_signature.url)
        return None
    
    def get_employee_signature_url(self, obj):
        if obj.employee_signature:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.employee_signature.url)
        return None
    
    def get_can_edit(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        
        # Can edit if status is DRAFT or REVISION_REQUIRED and user is creator
        return (obj.status in ['DRAFT', 'REVISION_REQUIRED'] and 
                obj.created_by == request.user)
    
    def get_can_approve_as_line_manager(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        
        return obj.can_be_approved_by_line_manager(request.user)
    
    def get_can_approve_as_employee(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        
        return obj.can_be_approved_by_employee(request.user)
    
    def get_employee_info(self, obj):
        return obj.get_employee_info()
    
    def get_manager_info(self, obj):
        return obj.get_manager_info()

class JobDescriptionCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating and updating job descriptions"""
    
    # Nested data for creation
    sections = JobDescriptionSectionSerializer(many=True, required=False)
    required_skills_data = serializers.ListField(
        child=serializers.DictField(),
        write_only=True,
        required=False,
        help_text="List of {skill_id, proficiency_level, is_mandatory}"
    )
    behavioral_competencies_data = serializers.ListField(
        child=serializers.DictField(),
        write_only=True,
        required=False,
        help_text="List of {competency_id, proficiency_level, is_mandatory}"
    )
    business_resources_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False
    )
    access_rights_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False
    )
    company_benefits_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False
    )
    
    class Meta:
        model = JobDescription
        fields = [
            'id', 'job_title', 'job_purpose', 'business_function', 'department',
            'unit', 'position_group', 'grading_level', 'reports_to',
            'assigned_employee', 'manual_employee_name',  'manual_employee_phone',
            'sections', 'required_skills_data', 'behavioral_competencies_data',
            'business_resources_ids', 'access_rights_ids', 'company_benefits_ids'
        ]
        read_only_fields = ['id']
    
    def validate_grading_level(self, value):
        """Validate grading level against position group"""
        position_group_id = self.initial_data.get('position_group')
        if position_group_id:
            try:
                position_group = PositionGroup.objects.get(id=position_group_id)
                valid_levels = [level['code'] for level in position_group.get_grading_levels()]
                if value not in valid_levels:
                    raise serializers.ValidationError(
                        f"Invalid grading level '{value}' for position group '{position_group.name}'. "
                        f"Valid levels: {', '.join(valid_levels)}"
                    )
            except PositionGroup.DoesNotExist:
                raise serializers.ValidationError("Invalid position group")
        return value
    
    def validate_department(self, value):
        """Validate department belongs to business function"""
        business_function_id = self.initial_data.get('business_function')
        if business_function_id and value:
            if value.business_function.id != int(business_function_id):
                raise serializers.ValidationError(
                    "Department must belong to the selected business function"
                )
        return value
    
    def validate(self, attrs):
        """Validate employee assignment - either existing employee or manual entry"""
        assigned_employee = attrs.get('assigned_employee')
        manual_employee_name = attrs.get('manual_employee_name')
        
        if not assigned_employee and not manual_employee_name:
            raise serializers.ValidationError(
                "Either assign an existing employee or provide manual employee information"
            )
        
        if assigned_employee and manual_employee_name:
            raise serializers.ValidationError(
                "Cannot assign both existing employee and manual employee information"
            )
        
        # If manual employee, name is required
        if manual_employee_name and not manual_employee_name.strip():
            raise serializers.ValidationError(
                "Manual employee name is required when not assigning existing employee"
            )
        
        return attrs
    
    def validate_unit(self, value):
        """Validate unit belongs to department"""
        department_id = self.initial_data.get('department')
        if department_id and value:
            if value.department.id != int(department_id):
                raise serializers.ValidationError(
                    "Unit must belong to the selected department"
                )
        return value
    
    def create(self, validated_data):
        """Create job description with all related components"""
        from django.db import transaction
        
        # Extract nested data
        sections_data = validated_data.pop('sections', [])
        skills_data = validated_data.pop('required_skills_data', [])
        competencies_data = validated_data.pop('behavioral_competencies_data', [])
        business_resources_ids = validated_data.pop('business_resources_ids', [])
        access_rights_ids = validated_data.pop('access_rights_ids', [])
        company_benefits_ids = validated_data.pop('company_benefits_ids', [])
        
        with transaction.atomic():
            # Create main job description
            job_description = JobDescription.objects.create(**validated_data)
            
            # Create sections
            for section_data in sections_data:
                JobDescriptionSection.objects.create(
                    job_description=job_description,
                    **section_data
                )
            
            # Create skills
            for skill_data in skills_data:
                JobDescriptionSkill.objects.create(
                    job_description=job_description,
                    skill_id=skill_data['skill_id'],
                    proficiency_level=skill_data.get('proficiency_level', 'INTERMEDIATE'),
                    is_mandatory=skill_data.get('is_mandatory', True)
                )
            
            # Create behavioral competencies
            for competency_data in competencies_data:
                JobDescriptionBehavioralCompetency.objects.create(
                    job_description=job_description,
                    competency_id=competency_data['competency_id'],
                    proficiency_level=competency_data.get('proficiency_level', 'INTERMEDIATE'),
                    is_mandatory=competency_data.get('is_mandatory', True)
                )
            
            # Create business resources links
            for resource_id in business_resources_ids:
                JobDescriptionBusinessResource.objects.create(
                    job_description=job_description,
                    resource_id=resource_id
                )
            
            # Create access rights links
            for access_id in access_rights_ids:
                JobDescriptionAccessMatrix.objects.create(
                    job_description=job_description,
                    access_matrix_id=access_id
                )
            
            # Create company benefits links
            for benefit_id in company_benefits_ids:
                JobDescriptionCompanyBenefit.objects.create(
                    job_description=job_description,
                    benefit_id=benefit_id
                )
            
            # Log creation activity
            JobDescriptionActivity.objects.create(
                job_description=job_description,
                activity_type='CREATED',
                description=f"Job description created for {job_description.job_title}",
                performed_by=self.context['request'].user,
                metadata={
                    'sections_count': len(sections_data),
                    'skills_count': len(skills_data),
                    'competencies_count': len(competencies_data)
                }
            )
            
            return job_description
    
    def update(self, instance, validated_data):
        """Update job description with all related components"""
        from django.db import transaction
        
        # Extract nested data
        sections_data = validated_data.pop('sections', None)
        skills_data = validated_data.pop('required_skills_data', None)
        competencies_data = validated_data.pop('behavioral_competencies_data', None)
        business_resources_ids = validated_data.pop('business_resources_ids', None)
        access_rights_ids = validated_data.pop('access_rights_ids', None)
        company_benefits_ids = validated_data.pop('company_benefits_ids', None)
        
        with transaction.atomic():
            # Update main fields
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            
            instance.updated_by = self.context['request'].user
            instance.save()
            
            # Update sections if provided
            if sections_data is not None:
                instance.sections.all().delete()
                for section_data in sections_data:
                    JobDescriptionSection.objects.create(
                        job_description=instance,
                        **section_data
                    )
            
            # Update skills if provided
            if skills_data is not None:
                instance.required_skills.all().delete()
                for skill_data in skills_data:
                    JobDescriptionSkill.objects.create(
                        job_description=instance,
                        skill_id=skill_data['skill_id'],
                        proficiency_level=skill_data.get('proficiency_level', 'INTERMEDIATE'),
                        is_mandatory=skill_data.get('is_mandatory', True)
                    )
            
            # Update behavioral competencies if provided
            if competencies_data is not None:
                instance.behavioral_competencies.all().delete()
                for competency_data in competencies_data:
                    JobDescriptionBehavioralCompetency.objects.create(
                        job_description=instance,
                        competency_id=competency_data['competency_id'],
                        proficiency_level=competency_data.get('proficiency_level', 'INTERMEDIATE'),
                        is_mandatory=competency_data.get('is_mandatory', True)
                    )
            
            # Update business resources if provided
            if business_resources_ids is not None:
                instance.business_resources.all().delete()
                for resource_id in business_resources_ids:
                    JobDescriptionBusinessResource.objects.create(
                        job_description=instance,
                        resource_id=resource_id
                    )
            
            # Update access rights if provided
            if access_rights_ids is not None:
                instance.access_rights.all().delete()
                for access_id in access_rights_ids:
                    JobDescriptionAccessMatrix.objects.create(
                        job_description=instance,
                        access_matrix_id=access_id
                    )
            
            # Update company benefits if provided
            if company_benefits_ids is not None:
                instance.company_benefits.all().delete()
                for benefit_id in company_benefits_ids:
                    JobDescriptionCompanyBenefit.objects.create(
                        job_description=instance,
                        benefit_id=benefit_id
                    )
            
            # Log update activity
            JobDescriptionActivity.objects.create(
                job_description=instance,
                activity_type='UPDATED',
                description=f"Job description updated for {instance.job_title}",
                performed_by=self.context['request'].user,
                metadata={'updated_fields': list(validated_data.keys())}
            )
            
            return instance


# Approval serializers
class JobDescriptionApprovalSerializer(serializers.Serializer):
    """Serializer for approval actions"""
    
    comments = serializers.CharField(required=False, allow_blank=True)
    signature = serializers.FileField(required=False, allow_null=True)
    
    def validate_signature(self, value):
        """Validate signature file"""
        if value:
            # Check file size (max 2MB)
            if value.size > 2 * 1024 * 1024:
                raise serializers.ValidationError("Signature file must be less than 2MB")
            
            # Check file type
            allowed_types = ['image/png', 'image/jpeg', 'image/jpg', 'application/pdf']
            if value.content_type not in allowed_types:
                raise serializers.ValidationError(
                    "Invalid file type. Allowed types: PNG, JPEG, PDF"
                )
        
        return value


class JobDescriptionRejectionSerializer(serializers.Serializer):
    """Serializer for rejection actions"""
    
    reason = serializers.CharField(required=True, min_length=10)


class JobDescriptionSubmissionSerializer(serializers.Serializer):
    """Serializer for submitting job description for approval"""
    
    submit_to_line_manager = serializers.BooleanField(default=True)
    comments = serializers.CharField(required=False, allow_blank=True)


# Bulk operation serializers
class BulkJobDescriptionStatusUpdateSerializer(serializers.Serializer):
    """Serializer for bulk status updates"""
    
    job_description_ids = serializers.ListField(
        child=serializers.UUIDField(),
        min_length=1
    )
    action = serializers.ChoiceField(choices=[
        ('submit_for_approval', 'Submit for Approval'),
        ('withdraw', 'Withdraw from Approval'),
        ('archive', 'Archive'),
        ('activate', 'Activate')
    ])
    comments = serializers.CharField(required=False, allow_blank=True)


# Statistics serializers
class JobDescriptionStatsSerializer(serializers.Serializer):
    """Serializer for job description statistics"""
    
    total_job_descriptions = serializers.IntegerField()
    by_status = serializers.DictField()
    by_department = serializers.DictField()
    by_position_group = serializers.DictField()
    pending_approvals = serializers.IntegerField()
    recent_activities = serializers.ListField()
    approval_workflow_stats = serializers.DictField()


# Filter serializers
class JobDescriptionFilterSerializer(serializers.Serializer):
    """Serializer for advanced filtering"""
    
    search = serializers.CharField(required=False)
    business_function = serializers.ListField(
        child=serializers.IntegerField(),
        required=False
    )
    department = serializers.ListField(
        child=serializers.IntegerField(),
        required=False
    )
    status = serializers.ListField(
        child=serializers.CharField(),
        required=False
    )
    position_group = serializers.ListField(
        child=serializers.IntegerField(),
        required=False
    )
    created_date_from = serializers.DateField(required=False)
    created_date_to = serializers.DateField(required=False)
    pending_approval_for_user = serializers.BooleanField(required=False)


# Export serializers
class JobDescriptionExportSerializer(serializers.Serializer):
    """FIXED: Serializer for export functionality with proper UUID handling"""
    
    job_description_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        allow_empty=True,
        help_text="List of job description UUIDs to export. If empty, exports all filtered results."
    )
    export_format = serializers.ChoiceField(
        choices=[('pdf', 'PDF'), ('excel', 'Excel'), ('word', 'Word')],
        default='pdf'
    )
    include_signatures = serializers.BooleanField(default=True)
    include_activities = serializers.BooleanField(default=False)
    
    def validate_job_description_ids(self, value):
        """Validate that job description IDs exist"""
        if value:
            # Check if all provided UUIDs exist
            existing_count = JobDescription.objects.filter(id__in=value).count()
            if existing_count != len(value):
                raise serializers.ValidationError("Some job description IDs do not exist")
        return value
    
    
    # job_description_serializers.py - ADD THESE SERIALIZERS

class JobDescriptionSubmissionSerializer(serializers.Serializer):
    """Serializer for submitting job description for approval"""
    
    submit_to_line_manager = serializers.BooleanField(default=True)
    comments = serializers.CharField(required=False, allow_blank=True)


class JobDescriptionApprovalSerializer(serializers.Serializer):
    """Serializer for approval actions"""
    
    comments = serializers.CharField(required=False, allow_blank=True)
    signature = serializers.FileField(required=False, allow_null=True)
    
    def validate_signature(self, value):
        """Validate signature file"""
        if value:
            # Check file size (max 5MB)
            if value.size > 5 * 1024 * 1024:
                raise serializers.ValidationError("Signature file must be less than 5MB")
            
            # Check file type
            allowed_types = ['image/png', 'image/jpeg', 'image/jpg', 'application/pdf']
            if value.content_type not in allowed_types:
                raise serializers.ValidationError(
                    "Invalid file type. Allowed types: PNG, JPEG, PDF"
                )
        
        return value


class JobDescriptionRejectionSerializer(serializers.Serializer):
    """Serializer for rejection actions"""
    
    reason = serializers.CharField(required=True, min_length=10)
    
    def validate_reason(self, value):
        if len(value.strip()) < 10:
            raise serializers.ValidationError("Rejection reason must be at least 10 characters long")
        return value.strip()