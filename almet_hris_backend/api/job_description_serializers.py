# api/job_description_serializers.py - UPDATED: Smart employee selection based on organizational hierarchy

from rest_framework import serializers
from .job_description_models import (
    JobDescription, JobDescriptionSection, JobDescriptionSkill,
    JobDescriptionBehavioralCompetency, JobBusinessResource, AccessMatrix,
    CompanyBenefit, JobDescriptionBusinessResource, JobDescriptionAccessMatrix,
    JobDescriptionCompanyBenefit, JobDescriptionActivity
)
from .models import BusinessFunction, Department, Unit, PositionGroup, Employee, JobFunction
from .competency_models import Skill, BehavioralCompetency
from django.contrib.auth.models import User

import logging
logger = logging.getLogger(__name__)
from django.db import transaction

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
    """IMPROVED: Enhanced employee serializer with comprehensive organizational details"""
    
    business_function_name = serializers.CharField(source='business_function.name', read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True)
    unit_name = serializers.CharField(source='unit.name', read_only=True)
    job_function_name = serializers.CharField(source='job_function.name', read_only=True)
    position_group_name = serializers.CharField(source='position_group.name', read_only=True)
    line_manager_name = serializers.CharField(source='line_manager.full_name', read_only=True)
    line_manager_id = serializers.IntegerField(source='line_manager.id', read_only=True)
    email = serializers.CharField(source='user.email', read_only=True)
    # Additional useful fields
    has_line_manager = serializers.SerializerMethodField()
    organizational_path = serializers.SerializerMethodField()
    matching_score = serializers.SerializerMethodField()
    
    class Meta:
        model = Employee
        fields = [
            'id', 'employee_id', 'full_name', 'job_title', 'phone', 'email',
            'business_function', 'business_function_name',
            'department', 'department_name',
            'unit', 'unit_name',
            'job_function', 'job_function_name',
            'position_group', 'position_group_name',
            'grading_level', 'line_manager', 'line_manager_name', 'line_manager_id',
            'has_line_manager', 'organizational_path', 'matching_score',
           
        ]
    
    def get_has_line_manager(self, obj):
        return obj.line_manager is not None
    
    def get_organizational_path(self, obj):
        """Get full organizational path for employee"""
        path_parts = []
        
        if obj.business_function:
            path_parts.append(obj.business_function.name)
        if obj.department:
            path_parts.append(obj.department.name)
        if obj.unit:
            path_parts.append(obj.unit.name)
        if obj.job_function:
            path_parts.append(f"Function: {obj.job_function.name}")
        if obj.position_group:
            path_parts.append(f"Grade: {obj.grading_level}")
        
        return " > ".join(path_parts)
    
    def get_matching_score(self, obj):
        """Calculate matching score based on criteria (placeholder for future enhancement)"""
        # This could be enhanced later to show how well employee matches criteria
        return 100  


class JobFunctionBasicSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobFunction
        fields = ['id', 'name']


class UserBasicSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name']


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
            'id', 'name', 'description', 'is_active',
            'created_at', 'created_by', 'created_by_name'
        ]
        read_only_fields = ['created_at', 'created_by']


class AccessMatrixSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    
    class Meta:
        model = AccessMatrix
        fields = [
            'id', 'name', 'description', 'is_active',
            'created_at', 'created_by', 'created_by_name'
        ]
        read_only_fields = ['created_at', 'created_by']


class CompanyBenefitSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    
    class Meta:
        model = CompanyBenefit
        fields = [
            'id', 'name', 'description', 'is_active',
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


# UPDATED: Main Job Description serializers
class JobDescriptionCreateUpdateSerializer(serializers.ModelSerializer):
    """IMPROVED: Serializer with automatic employee assignment based on strict criteria matching"""
    
    # Nested data for creation
    sections = serializers.ListField(
        child=serializers.DictField(),
        write_only=True,
        required=False,
        help_text="List of sections: {section_type, title, content, order}"
    )
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
    
    # ADDED: Manual employee override (optional)
    force_employee_id = serializers.IntegerField(
        write_only=True,
        required=False,
        help_text="Force assign specific employee ID (will be validated against criteria)"
    )
    
    # Read-only fields for response
    assigned_employee_details = EmployeeBasicSerializer(source='assigned_employee', read_only=True)
    reports_to_details = EmployeeBasicSerializer(source='reports_to', read_only=True)
    employee_matching_details = serializers.SerializerMethodField()
    
    class Meta:
        model = JobDescription
        fields = [
            'id', 'job_title', 'job_purpose', 'business_function', 'department',
            'unit', 'job_function', 'position_group', 'grading_level',
            'sections', 'required_skills_data', 'behavioral_competencies_data',
            'business_resources_ids', 'access_rights_ids', 'company_benefits_ids',
            'force_employee_id', 'assigned_employee_details', 'reports_to_details',
            'employee_matching_details'
        ]
        read_only_fields = ['id', 'assigned_employee', 'reports_to']
    
    def get_employee_matching_details(self, obj):
        """Get detailed matching information"""
        if hasattr(obj, 'get_employee_matching_details'):
            return obj.get_employee_matching_details()
        return None
    
    def validate_grading_level(self, value):
        """Enhanced grading level validation"""
        position_group_id = self.initial_data.get('position_group')
        if position_group_id:
            try:
                position_group = PositionGroup.objects.get(id=position_group_id)
                # Enhanced validation logic can be added here
                logger.info(f"Validating grading level {value} for position group {position_group.name}")
            except PositionGroup.DoesNotExist:
                raise serializers.ValidationError("Invalid position group")
        return value
    
    def validate(self, attrs):
        """ENHANCED: Comprehensive validation before employee assignment"""
        
        # Validate that all required organizational fields are present INCLUDING job_title
        required_fields = ['job_title', 'business_function', 'department', 'job_function', 'position_group', 'grading_level']  # ADD job_title here
        missing_fields = [field for field in required_fields if not attrs.get(field)]
        
        if missing_fields:
            raise serializers.ValidationError(
                f"Required organizational fields missing: {', '.join(missing_fields)}"
            )
        
        
        
        # Validate force_employee_id if provided
        force_employee_id = attrs.get('force_employee_id')
        if force_employee_id:
            try:
                employee = Employee.objects.get(id=force_employee_id,  )
                
                # Create temp JD for validation
                temp_jd = JobDescription()
                for field in required_fields:
                    if field in attrs:
                        setattr(temp_jd, field, attrs[field])
                
                temp_jd.assigned_employee = employee
                is_valid, validation_message = temp_jd.validate_employee_assignment()
                
                if not is_valid:
                    raise serializers.ValidationError(
                        f"Forced employee assignment failed validation: {validation_message}"
                    )
                
                logger.info(f"Force employee assignment validated: {employee.full_name}")
                
            except Employee.DoesNotExist:
                raise serializers.ValidationError(f"Employee with ID {force_employee_id} not found or inactive")
        
        return attrs
    
    def create(self, validated_data):
        """IMPROVED: Create job description with enhanced employee assignment logic"""
        
        # Extract nested data
        sections_data = validated_data.pop('sections', [])
        skills_data = validated_data.pop('required_skills_data', [])
        competencies_data = validated_data.pop('behavioral_competencies_data', [])
        business_resources_ids = validated_data.pop('business_resources_ids', [])
        access_rights_ids = validated_data.pop('access_rights_ids', [])
        company_benefits_ids = validated_data.pop('company_benefits_ids', [])
        force_employee_id = validated_data.pop('force_employee_id', None)
        
        with transaction.atomic():
            
            # ENHANCED: Employee assignment logic
            if force_employee_id:
                # Use forced employee (already validated in validate method)
                assigned_employee = Employee.objects.get(id=force_employee_id)
                logger.info(f"Using forced employee assignment: {assigned_employee.full_name}")
    
            else:
                # Automatic assignment based on criteria
                logger.info("Starting automatic employee assignment based on criteria")
                
                eligible_employees = JobDescription.get_eligible_employees_with_priority(
                    job_title=validated_data['job_title'],  # ADD THIS LINE
                    business_function_id=validated_data['business_function'].id,
                    department_id=validated_data['department'].id,
                    unit_id=validated_data['unit'].id if validated_data.get('unit') else None,
                    job_function_id=validated_data['job_function'].id,
                    position_group_id=validated_data['position_group'].id,
                    grading_level=validated_data['grading_level']
                )
                
                logger.info(f"Found {eligible_employees.count()} eligible employees")
                
                if not eligible_employees.exists():
                    # Provide detailed feedback about what criteria failed
                    criteria_info = {
                        'business_function': validated_data['business_function'].name,
                        'department': validated_data['department'].name,
                        'unit': validated_data['unit'].name if validated_data.get('unit') else 'Any',
                        'job_function': validated_data['job_function'].name,
                        'position_group': validated_data['position_group'].name,
                        'grading_level': validated_data['grading_level']
                    }
                    
                    raise serializers.ValidationError({
                        'employee_assignment': f"No employees found matching ALL specified criteria: {criteria_info}",
                        'suggestion': 'Please adjust the organizational criteria or ensure employees exist with matching profiles',
                        'criteria': criteria_info
                    })
                
                # Select the best employee (first one from ordered queryset)
                assigned_employee = eligible_employees.first()
                logger.info(f"Auto-assigned best matching employee: {assigned_employee.full_name}")
            
            # Set the assigned employee
            validated_data['assigned_employee'] = assigned_employee
            
            # Create main job description (reports_to will be auto-assigned in save method)
            job_description = JobDescription.objects.create(**validated_data)
            
            logger.info(f"Created job description: {job_description.job_title} for {assigned_employee.full_name}")
            
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
            
            # Enhanced activity logging with validation details
            employee_info = job_description.get_employee_info()
            matching_details = job_description.get_employee_matching_details()
            
            assignment_method = "Force-assigned" if force_employee_id else "Auto-assigned"
            description = f"Job description created for {job_description.job_title} - {assignment_method} to {employee_info['name']}"
            
            JobDescriptionActivity.objects.create(
                job_description=job_description,
                activity_type='CREATED',
                description=description,
                performed_by=self.context['request'].user,
                metadata={
                    'sections_count': len(sections_data),
                    'skills_count': len(skills_data),
                    'competencies_count': len(competencies_data),
                    'employee_info': employee_info,
                    'assignment_method': assignment_method.lower().replace('-', '_'),
                    'assigned_employee': employee_info['name'],
                    'assigned_manager': job_description.reports_to.full_name if job_description.reports_to else None,
                    'employee_matching_details': matching_details,
                    'eligible_employees_count': eligible_employees.count() if not force_employee_id else 1,
                    'organizational_criteria': {
                        'business_function': validated_data['business_function'].name,
                        'department': validated_data['department'].name,
                        'unit': validated_data['unit'].name if validated_data.get('unit') else None,
                        'job_function': validated_data['job_function'].name,
                        'position_group': validated_data['position_group'].name,
                        'grading_level': validated_data['grading_level']
                    }
                }
            )
            
            logger.info(f"Job description creation completed successfully: {job_description.id}")
            
            return job_description
    
    def update(self, instance, validated_data):
        """IMPROVED: Update job description with enhanced employee reassignment logic"""
        
        # Extract nested data
        sections_data = validated_data.pop('sections', None)
        skills_data = validated_data.pop('required_skills_data', None)
        competencies_data = validated_data.pop('behavioral_competencies_data', None)
        business_resources_ids = validated_data.pop('business_resources_ids', None)
        access_rights_ids = validated_data.pop('access_rights_ids', None)
        company_benefits_ids = validated_data.pop('company_benefits_ids', None)
        force_employee_id = validated_data.pop('force_employee_id', None)
        
        with transaction.atomic():
            
            # Track organizational changes
            org_fields = ['business_function', 'department', 'unit', 'job_function', 'position_group', 'grading_level']
            org_changed = any(field in validated_data for field in org_fields)
            
            old_employee = instance.assigned_employee
            old_manager = instance.reports_to
            reassignment_reason = None
            
            # ENHANCED: Employee reassignment logic
            if force_employee_id:
                # Force reassignment (already validated)
                new_employee = Employee.objects.get(id=force_employee_id)
                validated_data['assigned_employee'] = new_employee
                reassignment_reason = "Force reassignment requested"
                logger.info(f"Force reassigning employee to: {new_employee.full_name}")
                
            elif org_changed:
                # Automatic reassignment due to organizational criteria changes
                logger.info("Organizational criteria changed, checking for employee reassignment")
                
                # Get new organizational values (use new values or keep existing)
                business_function = validated_data.get('business_function', instance.business_function)
                department = validated_data.get('department', instance.department)
                unit = validated_data.get('unit', instance.unit)
                job_function = validated_data.get('job_function', instance.job_function)
                position_group = validated_data.get('position_group', instance.position_group)
                grading_level = validated_data.get('grading_level', instance.grading_level)
                
                # Check if current employee still matches new criteria
                temp_jd = JobDescription()
                temp_jd.business_function = business_function
                temp_jd.department = department
                temp_jd.unit = unit
                temp_jd.job_function = job_function
                temp_jd.position_group = position_group
                temp_jd.grading_level = grading_level
                temp_jd.assigned_employee = old_employee
                
                is_still_valid, validation_message = temp_jd.validate_employee_assignment()
                
                if not is_still_valid:
                    # Current employee no longer matches, find new one
                    logger.info(f"Current employee no longer matches criteria: {validation_message}")
                    
                    eligible_employees = JobDescription.get_eligible_employees_with_priority(
    job_title=temp_jd.job_title,  # FIX: Use the job title from temp_jd
    business_function_id=business_function.id,
    department_id=department.id,
    unit_id=unit.id if unit else None,
    job_function_id=job_function.id,
    position_group_id=position_group.id,
    grading_level=grading_level
)
                    
                    if eligible_employees.exists():
                        new_employee = eligible_employees.first()
                        validated_data['assigned_employee'] = new_employee
                        reassignment_reason = f"Organizational criteria changed, current employee no longer matches: {validation_message}"
                        logger.info(f"Auto-reassigning to new matching employee: {new_employee.full_name}")
                    else:
                        raise serializers.ValidationError({
                            'employee_assignment': 'No employees found matching the updated organizational criteria',
                            'current_employee_validation': validation_message,
                            'suggestion': 'Please adjust criteria or ensure matching employees exist'
                        })
                else:
                    logger.info("Current employee still matches updated criteria, keeping assignment")
            
            # Update main fields
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            
            instance.updated_by = self.context['request'].user
            instance.save()  # This will trigger auto-assignment of reports_to
            
            # Check what changed
            new_employee = instance.assigned_employee
            new_manager = instance.reports_to
            employee_changed = old_employee != new_employee
            manager_changed = old_manager != new_manager
            
            # Update nested relationships if provided
            if sections_data is not None:
                instance.sections.all().delete()
                for section_data in sections_data:
                    JobDescriptionSection.objects.create(
                        job_description=instance,
                        **section_data
                    )
            
            if skills_data is not None:
                instance.required_skills.all().delete()
                for skill_data in skills_data:
                    JobDescriptionSkill.objects.create(
                        job_description=instance,
                        skill_id=skill_data['skill_id'],
                        proficiency_level=skill_data.get('proficiency_level', 'INTERMEDIATE'),
                        is_mandatory=skill_data.get('is_mandatory', True)
                    )
            
            if competencies_data is not None:
                instance.behavioral_competencies.all().delete()
                for competency_data in competencies_data:
                    JobDescriptionBehavioralCompetency.objects.create(
                        job_description=instance,
                        competency_id=competency_data['competency_id'],
                        proficiency_level=competency_data.get('proficiency_level', 'INTERMEDIATE'),
                        is_mandatory=competency_data.get('is_mandatory', True)
                    )
            
            if business_resources_ids is not None:
                instance.business_resources.all().delete()
                for resource_id in business_resources_ids:
                    JobDescriptionBusinessResource.objects.create(
                        job_description=instance,
                        resource_id=resource_id
                    )
            
            if access_rights_ids is not None:
                instance.access_rights.all().delete()
                for access_id in access_rights_ids:
                    JobDescriptionAccessMatrix.objects.create(
                        job_description=instance,
                        access_matrix_id=access_id
                    )
            
            if company_benefits_ids is not None:
                instance.company_benefits.all().delete()
                for benefit_id in company_benefits_ids:
                    JobDescriptionCompanyBenefit.objects.create(
                        job_description=instance,
                        benefit_id=benefit_id
                    )
            
            # Enhanced activity logging
            updated_fields = list(validated_data.keys())
            description = f"Job description updated for {instance.job_title}"
            
            metadata = {
                'updated_fields': updated_fields,
                'organizational_changes': org_changed
            }
            
            if employee_changed:
                old_employee_name = old_employee.full_name if old_employee else 'None'
                new_employee_name = new_employee.full_name if new_employee else 'None'
                description += f" - Employee reassigned from {old_employee_name} to {new_employee_name}"
                metadata.update({
                    'employee_reassigned': True,
                    'old_employee': old_employee_name,
                    'new_employee': new_employee_name,
                    'reassignment_reason': reassignment_reason,
                    'employee_matching_details': instance.get_employee_matching_details()
                })
            
            if manager_changed:
                old_manager_name = old_manager.full_name if old_manager else 'None'
                new_manager_name = new_manager.full_name if new_manager else 'None'
                description += f" - Manager auto-updated from {old_manager_name} to {new_manager_name}"
                metadata.update({
                    'manager_auto_updated': True,
                    'old_manager': old_manager_name,
                    'new_manager': new_manager_name
                })
            
            JobDescriptionActivity.objects.create(
                job_description=instance,
                activity_type='UPDATED',
                description=description,
                performed_by=self.context['request'].user,
                metadata=metadata
            )
            
            logger.info(f"Job description update completed: {instance.id}")
            
            return instance


# IMPROVED: Enhanced eligible employees serializer
class EligibleEmployeesSerializer(serializers.Serializer):
    """IMPROVED: Serializer for getting eligible employees with enhanced validation"""
    
    business_function = serializers.IntegerField(required=True, help_text="Business Function ID (Required)")
    department = serializers.IntegerField(required=True, help_text="Department ID (Required)")
    unit = serializers.IntegerField(required=False, allow_null=True, help_text="Unit ID (Optional)")
    job_function = serializers.IntegerField(required=True, help_text="Job Function ID (Required)")
    position_group = serializers.IntegerField(required=True, help_text="Position Group ID (Required)")
    grading_level = serializers.CharField(required=True, help_text="Grading Level (Required)")
    
    def validate(self, attrs):
        """Enhanced validation with organizational structure checks"""
        
        # Validate that provided IDs exist and are active
        validation_errors = {}
        
        if 'business_function' in attrs:
            try:
                bf = BusinessFunction.objects.get(id=attrs['business_function'])
                if not bf.is_active:
                    validation_errors['business_function'] = 'Business function is not active'
            except BusinessFunction.DoesNotExist:
                validation_errors['business_function'] = 'Business function not found'
        
        if 'department' in attrs:
            try:
                dept = Department.objects.get(id=attrs['department'])
                if not dept.is_active:
                    validation_errors['department'] = 'Department is not active'
                    
                # Check if department belongs to business function
                if 'business_function' in attrs and dept.business_function_id != attrs['business_function']:
                    validation_errors['department'] = 'Department does not belong to specified business function'
                    
            except Department.DoesNotExist:
                validation_errors['department'] = 'Department not found'
        
        if 'unit' in attrs and attrs['unit']:
            try:
                unit = Unit.objects.get(id=attrs['unit'])
                if not unit.is_active:
                    validation_errors['unit'] = 'Unit is not active'
                    
                # Check if unit belongs to department
                if 'department' in attrs and unit.department_id != attrs['department']:
                    validation_errors['unit'] = 'Unit does not belong to specified department'
                    
            except Unit.DoesNotExist:
                validation_errors['unit'] = 'Unit not found'
        
        if 'job_function' in attrs:
            try:
                jf = JobFunction.objects.get(id=attrs['job_function'])
                if not jf.is_active:
                    validation_errors['job_function'] = 'Job function is not active'
            except JobFunction.DoesNotExist:
                validation_errors['job_function'] = 'Job function not found'
        
        if 'position_group' in attrs:
            try:
                pg = PositionGroup.objects.get(id=attrs['position_group'])
                if not pg.is_active:
                    validation_errors['position_group'] = 'Position group is not active'
            except PositionGroup.DoesNotExist:
                validation_errors['position_group'] = 'Position group not found'
        
        if validation_errors:
            raise serializers.ValidationError(validation_errors)
        
        return attrs


# Keep all other existing serializers unchanged (list, detail, approval, etc.)
class JobDescriptionListSerializer(serializers.ModelSerializer):
    """Serializer for job description list view with enhanced employee info"""
    
    business_function_name = serializers.CharField(source='business_function.name', read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True)
    unit_name = serializers.CharField(source='unit.name', read_only=True)
    job_function_name = serializers.CharField(source='job_function.name', read_only=True)
    position_group_name = serializers.CharField(source='position_group.name', read_only=True)
    reports_to_name = serializers.CharField(source='reports_to.full_name', read_only=True)
    employee_info = serializers.SerializerMethodField()
    manager_info = serializers.SerializerMethodField()
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    status_display = serializers.SerializerMethodField()
    employee_validation = serializers.SerializerMethodField()
    
    class Meta:
        model = JobDescription
        fields = [
            'id', 'job_title', 'business_function_name', 'department_name',
            'unit_name', 'job_function_name', 'position_group_name', 'grading_level', 
            'reports_to_name', 'employee_info', 'manager_info', 'status', 'status_display', 
            'version', 'is_active', 'created_at', 'created_by_name', 'employee_validation'
        ]
    
    def get_status_display(self, obj):
        return obj.get_status_display_with_color()
    
    def get_employee_info(self, obj):
        return obj.get_employee_info()
    
    def get_manager_info(self, obj):
        return obj.get_manager_info()
    
    def get_employee_validation(self, obj):
        """Get employee validation status"""
        if obj.assigned_employee:
            is_valid, message = obj.validate_employee_assignment()
            return {
                'is_valid': is_valid,
                'message': message[:100] + '...' if len(message) > 100 else message
            }
        return {'is_valid': False, 'message': 'No employee assigned'}


# Keep other existing serializers (DetailSerializer, ApprovalSerializer, etc.) with minor enhancements
class JobDescriptionDetailSerializer(serializers.ModelSerializer):
    """Enhanced detail serializer with employee validation info"""
    
    # Related object details
    business_function = BusinessFunctionBasicSerializer(read_only=True)
    department = DepartmentBasicSerializer(read_only=True)
    unit = UnitBasicSerializer(read_only=True)
    job_function = JobFunctionBasicSerializer(read_only=True)
    position_group = PositionGroupBasicSerializer(read_only=True)
    reports_to = EmployeeBasicSerializer(read_only=True)
    assigned_employee = EmployeeBasicSerializer(read_only=True)
    
    # Enhanced employee information
    employee_info = serializers.SerializerMethodField()
    manager_info = serializers.SerializerMethodField()
    employee_matching_details = serializers.SerializerMethodField()
    employee_validation = serializers.SerializerMethodField()
    
    # Keep all other existing fields...
    status_display = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField()
    can_approve_as_line_manager = serializers.SerializerMethodField()
    can_approve_as_employee = serializers.SerializerMethodField()
    
    class Meta:
        model = JobDescription
        fields = [
            # Basic info
            'id', 'job_title', 'job_purpose', 'grading_level', 'version', 'is_active',
            
            # Organizational structure
            'business_function', 'department', 'unit', 'job_function', 'position_group',
            
            # Enhanced employee assignment
            'assigned_employee', 'reports_to', 'employee_info', 'manager_info',
            'employee_matching_details', 'employee_validation',
            
            # Status and permissions
            'status', 'status_display', 'can_edit', 'can_approve_as_line_manager', 'can_approve_as_employee',
            
            # Metadata
            'created_at', 'updated_at'
        ]
    
    def get_status_display(self, obj):
        return obj.get_status_display_with_color()
    
    def get_employee_info(self, obj):
        return obj.get_employee_info()
    
    def get_manager_info(self, obj):
        return obj.get_manager_info()
    
    def get_employee_matching_details(self, obj):
        return obj.get_employee_matching_details()
    
    def get_employee_validation(self, obj):
        if obj.assigned_employee:
            is_valid, message = obj.validate_employee_assignment()
            return {'is_valid': is_valid, 'message': message}
        return {'is_valid': False, 'message': 'No employee assigned'}
    
    def get_can_edit(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        return (obj.status in ['DRAFT', 'REVISION_REQUIRED'] and obj.created_by == request.user)
    
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


# Export serializers
class JobDescriptionExportSerializer(serializers.Serializer):
    """Serializer for export functionality with proper UUID handling"""
    
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