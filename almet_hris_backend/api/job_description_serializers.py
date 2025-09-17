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

class JobDescriptionCreateUpdateSerializer(serializers.ModelSerializer):
    """ENHANCED: Manual employee selection for multiple matches"""
    
    # Keep all existing fields...
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
    
    # NEW: Manual employee selection fields
    selected_employee_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        help_text="List of specific employee IDs to create job descriptions for (when multiple employees match)"
    )
    
    # Response fields
    created_job_descriptions = serializers.SerializerMethodField()
    total_employees_assigned = serializers.SerializerMethodField()
    requires_employee_selection = serializers.SerializerMethodField()
    
    class Meta:
        model = JobDescription
        fields = [
            'id', 'job_title', 'job_purpose', 'business_function', 'department',
            'unit', 'job_function', 'position_group', 'grading_level',
            'sections', 'required_skills_data', 'behavioral_competencies_data',
            'business_resources_ids', 'access_rights_ids', 'company_benefits_ids',
            'selected_employee_ids',
            'created_job_descriptions', 'total_employees_assigned', 'requires_employee_selection'
        ]
        read_only_fields = ['id', 'assigned_employee', 'reports_to']
    
    def get_created_job_descriptions(self, obj):
        """Return list of created job descriptions"""
        if hasattr(obj, '_created_job_descriptions'):
            return [
                {
                    'id': str(jd.id),
                    'job_title': jd.job_title,
                    'employee_name': jd.assigned_employee.full_name,
                    'employee_id': jd.assigned_employee.employee_id,
                    'manager_name': jd.reports_to.full_name if jd.reports_to else None
                }
                for jd in obj._created_job_descriptions
            ]
        return []
    
    def get_total_employees_assigned(self, obj):
        """Return total number of employees assigned"""
        if hasattr(obj, '_created_job_descriptions'):
            return len(obj._created_job_descriptions)
        return 1
    
    def get_requires_employee_selection(self, obj):
        """Return whether employee selection is required"""
        return getattr(obj, '_requires_employee_selection', False)
    
    def validate_selected_employee_ids(self, value):
        """Validate selected employee IDs"""
        if value:
            # Check if all provided IDs exist and are active
            existing_count = Employee.objects.filter(
                id__in=value, 
                is_deleted=False
            ).count()
            
            if existing_count != len(value):
                raise serializers.ValidationError("Some employee IDs do not exist or are inactive")
        
        return value
    
    def create(self, validated_data):
        """ENHANCED: Create with manual employee selection logic"""
        
        # Extract nested data
        sections_data = validated_data.pop('sections', [])
        skills_data = validated_data.pop('required_skills_data', [])
        competencies_data = validated_data.pop('behavioral_competencies_data', [])
        business_resources_ids = validated_data.pop('business_resources_ids', [])
        access_rights_ids = validated_data.pop('access_rights_ids', [])
        company_benefits_ids = validated_data.pop('company_benefits_ids', [])
        selected_employee_ids = validated_data.pop('selected_employee_ids', [])
        
        logger.info(f"Creating job description - Selected employee IDs: {selected_employee_ids}")
        
        with transaction.atomic():
            
            # Get all employees matching criteria
            eligible_employees = JobDescription.get_eligible_employees_with_priority(
                job_title=validated_data['job_title'],
                business_function_id=validated_data['business_function'].id,
                department_id=validated_data['department'].id,
                unit_id=validated_data['unit'].id if validated_data.get('unit') else None,
                job_function_id=validated_data['job_function'].id,
                position_group_id=validated_data['position_group'].id,
                grading_level=validated_data['grading_level']
            )
            
            logger.info(f"Found {eligible_employees.count()} eligible employees")
            
            if not eligible_employees.exists():
                raise serializers.ValidationError({
                    'employee_assignment': "No employees found matching the specified criteria",
                    'criteria': {
                        'job_title': validated_data['job_title'],
                        'business_function': validated_data['business_function'].name,
                        'department': validated_data['department'].name,
                        'unit': validated_data['unit'].name if validated_data.get('unit') else 'Any',
                        'job_function': validated_data['job_function'].name,
                        'position_group': validated_data['position_group'].name,
                        'grading_level': validated_data['grading_level']
                    }
                })
            
            # MAIN LOGIC: Determine assignment strategy
            if eligible_employees.count() == 1:
                # CASE 1: Only one employee matches - auto assign
                employees_to_assign = [eligible_employees.first()]
                logger.info(f"Single employee found - auto-assigning to: {employees_to_assign[0].full_name}")
                
            elif selected_employee_ids:
                # CASE 2: Multiple employees match but user selected specific ones
                selected_employees = eligible_employees.filter(id__in=selected_employee_ids)
                
                if not selected_employees.exists():
                    raise serializers.ValidationError({
                        'selected_employee_ids': 'None of the selected employees match the job criteria'
                    })
                
                employees_to_assign = list(selected_employees)
                logger.info(f"User selected {len(employees_to_assign)} employees from {eligible_employees.count()} eligible")
                
            else:
                # CASE 3: Multiple employees match but no selection made - return error with options
                employees_serializer = EmployeeBasicSerializer(eligible_employees[:20], many=True)
                
                raise serializers.ValidationError({
                    'requires_employee_selection': True,
                    'message': f'Found {eligible_employees.count()} employees matching criteria. Please select which employees to assign.',
                    'eligible_employees': employees_serializer.data,
                    'instruction': 'Use the "selected_employee_ids" field to specify which employees should get job descriptions',
                    'eligible_count': eligible_employees.count()
                })
            
            # Create job descriptions for selected employees
            created_job_descriptions = []
            
            for index, employee in enumerate(employees_to_assign):
                logger.info(f"Creating job description {index + 1}/{len(employees_to_assign)} for: {employee.full_name}")
                
                # Prepare data for this employee
                jd_data = validated_data.copy()
                jd_data['assigned_employee'] = employee
                
                # Create main job description
                job_description = JobDescription.objects.create(**jd_data)
                
                # Create all related objects
                self._create_job_description_components(
                    job_description, sections_data, skills_data, competencies_data,
                    business_resources_ids, access_rights_ids, company_benefits_ids
                )
                
                # Activity logging
                employee_info = job_description.get_employee_info()
                description = f"Job description created for {job_description.job_title} - Assigned to {employee_info['name']}"
                
                if len(employees_to_assign) > 1:
                    description += f" (Selected {index + 1}/{len(employees_to_assign)})"
                
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
                        'assignment_method': 'auto_single' if len(employees_to_assign) == 1 else 'manual_selected',
                        'selection_info': {
                            'eligible_employees_count': eligible_employees.count(),
                            'selected_employees_count': len(employees_to_assign),
                            'was_auto_assigned': len(employees_to_assign) == 1 and not selected_employee_ids,
                            'was_manually_selected': bool(selected_employee_ids)
                        },
                        'organizational_criteria': {
                            'job_title': validated_data['job_title'],
                            'business_function': validated_data['business_function'].name,
                            'department': validated_data['department'].name,
                            'unit': validated_data['unit'].name if validated_data.get('unit') else None,
                            'job_function': validated_data['job_function'].name,
                            'position_group': validated_data['position_group'].name,
                            'grading_level': validated_data['grading_level']
                        }
                    }
                )
                
                created_job_descriptions.append(job_description)
                logger.info(f"Successfully created job description {job_description.id} for {employee.full_name}")
            
            # Summary logging
            logger.info(f"Job description creation completed: {len(created_job_descriptions)} job descriptions created")
            
            # For response, return the first created job description but attach info about all
            primary_job_description = created_job_descriptions[0]
            primary_job_description._created_job_descriptions = created_job_descriptions
            
            return primary_job_description
    
    def _create_job_description_components(self, job_description, sections_data, skills_data, 
                                         competencies_data, business_resources_ids, 
                                         access_rights_ids, company_benefits_ids):
        """Helper method to create all job description components"""
        
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
            'id', 'job_title', 'business_function_name', 'department_name','job_purpose',
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

class JobDescriptionDetailSerializer(serializers.ModelSerializer):
    """Enhanced detail serializer with all nested data and employee validation info"""
    
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
    
    # NEW: Nested detailed data - READ-ONLY for detail view
    sections = JobDescriptionSectionSerializer(many=True, read_only=True)
    required_skills = JobDescriptionSkillSerializer(many=True, read_only=True)
    behavioral_competencies = JobDescriptionBehavioralCompetencySerializer(many=True, read_only=True)
    business_resources = JobDescriptionBusinessResourceSerializer(many=True, read_only=True)
    access_rights = JobDescriptionAccessMatrixSerializer(many=True, read_only=True)
    company_benefits = JobDescriptionCompanyBenefitSerializer(many=True, read_only=True)
    
    # Approval and user information
    created_by_detail = UserBasicSerializer(source='created_by', read_only=True)
    updated_by_detail = UserBasicSerializer(source='updated_by', read_only=True)
    line_manager_approved_by_detail = UserBasicSerializer(source='line_manager_approved_by', read_only=True)
    employee_approved_by_detail = UserBasicSerializer(source='employee_approved_by', read_only=True)
    
    # Status and permissions
    status_display = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField()
    can_approve_as_line_manager = serializers.SerializerMethodField()
    can_approve_as_employee = serializers.SerializerMethodField()
    can_submit_for_approval = serializers.SerializerMethodField()
    can_request_revision = serializers.SerializerMethodField()
    
    # Summary counts for quick overview
    sections_count = serializers.SerializerMethodField()
    skills_count = serializers.SerializerMethodField()
    competencies_count = serializers.SerializerMethodField()
    resources_count = serializers.SerializerMethodField()
    
    # Approval workflow info
    approval_workflow_status = serializers.SerializerMethodField()
    next_approval_step = serializers.SerializerMethodField()
    
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
            
            # NEW: Complete nested data
            'sections', 'required_skills', 'behavioral_competencies',
            'business_resources', 'access_rights', 'company_benefits',
            
            # Summary counts
            'sections_count', 'skills_count', 'competencies_count', 'resources_count',
            
            # Status and permissions
            'status', 'status_display', 'can_edit', 'can_approve_as_line_manager', 
            'can_approve_as_employee', 'can_submit_for_approval', 'can_request_revision',
            
            # Approval workflow
            'approval_workflow_status', 'next_approval_step',
            
            # Approval details
            'line_manager_approved_by_detail', 'line_manager_approved_at', 'line_manager_comments',
            'employee_approved_by_detail', 'employee_approved_at', 'employee_comments',
            
            # User details
            'created_by_detail', 'updated_by_detail',
            
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
    
    # Permission methods
    def get_can_edit(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        return (obj.status in ['DRAFT', 'REVISION_REQUIRED'] and 
                (obj.created_by == request.user or request.user.is_staff))
    
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
    
    def get_can_submit_for_approval(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        return (obj.status in ['DRAFT', 'REVISION_REQUIRED'] and 
                (obj.created_by == request.user or request.user.is_staff) and
                obj.assigned_employee and obj.reports_to)
    
    def get_can_request_revision(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        return (obj.status in ['PENDING_LINE_MANAGER', 'PENDING_EMPLOYEE'] and
                (obj.can_be_approved_by_line_manager(request.user) or
                 obj.can_be_approved_by_employee(request.user)))
    
    # Summary count methods
    def get_sections_count(self, obj):
        return obj.sections.count() if hasattr(obj, 'sections') else 0
    
    def get_skills_count(self, obj):
        return obj.required_skills.count() if hasattr(obj, 'required_skills') else 0
    
    def get_competencies_count(self, obj):
        return obj.behavioral_competencies.count() if hasattr(obj, 'behavioral_competencies') else 0
    
    def get_resources_count(self, obj):
        business_resources = obj.business_resources.count() if hasattr(obj, 'business_resources') else 0
        access_rights = obj.access_rights.count() if hasattr(obj, 'access_rights') else 0
        company_benefits = obj.company_benefits.count() if hasattr(obj, 'company_benefits') else 0
        return business_resources + access_rights + company_benefits
    
    # Approval workflow methods
    def get_approval_workflow_status(self, obj):
        """Get detailed approval workflow status"""
        workflow_steps = []
        
        # Step 1: Creation
        workflow_steps.append({
            'step': 'created',
            'label': 'Job Description Created',
            'status': 'completed',
            'completed_by': obj.created_by.get_full_name() if obj.created_by else 'System',
            'completed_at': obj.created_at.isoformat() if obj.created_at else None,
            'icon': 'create'
        })
        
        # Step 2: Line Manager Approval
        if obj.status in ['PENDING_LINE_MANAGER', 'PENDING_EMPLOYEE', 'APPROVED']:
            lm_status = 'completed' if obj.line_manager_approved_at else 'pending'
            workflow_steps.append({
                'step': 'line_manager_approval',
                'label': 'Line Manager Approval',
                'status': lm_status,
                'completed_by': obj.line_manager_approved_by.get_full_name() if obj.line_manager_approved_by else None,
                'completed_at': obj.line_manager_approved_at.isoformat() if obj.line_manager_approved_at else None,
                'pending_with': obj.reports_to.full_name if obj.reports_to and lm_status == 'pending' else None,
                'comments': obj.line_manager_comments if obj.line_manager_comments else None,
                'icon': 'supervisor_account'
            })
        
        # Step 3: Employee Approval
        if obj.status in ['PENDING_EMPLOYEE', 'APPROVED']:
            emp_status = 'completed' if obj.employee_approved_at else 'pending'
            workflow_steps.append({
                'step': 'employee_approval',
                'label': 'Employee Approval',
                'status': emp_status,
                'completed_by': obj.employee_approved_by.get_full_name() if obj.employee_approved_by else None,
                'completed_at': obj.employee_approved_at.isoformat() if obj.employee_approved_at else None,
                'pending_with': obj.assigned_employee.full_name if obj.assigned_employee and emp_status == 'pending' else None,
                'comments': obj.employee_comments if obj.employee_comments else None,
                'icon': 'person'
            })
        
        # Special statuses
        if obj.status == 'REJECTED':
            workflow_steps.append({
                'step': 'rejected',
                'label': 'Rejected',
                'status': 'rejected',
                'icon': 'cancel'
            })
        elif obj.status == 'REVISION_REQUIRED':
            workflow_steps.append({
                'step': 'revision_required',
                'label': 'Revision Required',
                'status': 'revision_required',
                'icon': 'edit'
            })
        
        return {
            'current_status': obj.status,
            'current_status_display': obj.get_status_display(),
            'workflow_steps': workflow_steps,
            'progress_percentage': self._calculate_progress_percentage(obj),
            'is_complete': obj.status == 'APPROVED'
        }
    
    def _calculate_progress_percentage(self, obj):
        """Calculate workflow progress percentage"""
        if obj.status == 'DRAFT':
            return 25
        elif obj.status == 'PENDING_LINE_MANAGER':
            return 50
        elif obj.status == 'PENDING_EMPLOYEE':
            return 75
        elif obj.status == 'APPROVED':
            return 100
        elif obj.status in ['REJECTED', 'REVISION_REQUIRED']:
            return 25  # Back to beginning essentially
        return 0
    
    def get_next_approval_step(self, obj):
        """Get information about next approval step"""
        if obj.status == 'DRAFT':
            return {
                'action': 'submit_for_approval',
                'label': 'Submit for Approval',
                'description': 'Submit to line manager for review',
                'next_approver': obj.reports_to.full_name if obj.reports_to else 'No manager assigned'
            }
        elif obj.status == 'PENDING_LINE_MANAGER':
            return {
                'action': 'line_manager_approval',
                'label': 'Waiting for Line Manager',
                'description': 'Pending line manager approval',
                'next_approver': obj.reports_to.full_name if obj.reports_to else 'No manager assigned'
            }
        elif obj.status == 'PENDING_EMPLOYEE':
            return {
                'action': 'employee_approval',
                'label': 'Waiting for Employee',
                'description': 'Pending employee approval',
                'next_approver': obj.assigned_employee.full_name if obj.assigned_employee else 'No employee assigned'
            }
        elif obj.status == 'APPROVED':
            return {
                'action': 'completed',
                'label': 'Fully Approved',
                'description': 'Job description is fully approved',
                'next_approver': None
            }
        elif obj.status == 'REVISION_REQUIRED':
            return {
                'action': 'revise_and_resubmit',
                'label': 'Revision Required',
                'description': 'Please revise and resubmit',
                'next_approver': obj.created_by.get_full_name() if obj.created_by else 'Creator'
            }
        elif obj.status == 'REJECTED':
            return {
                'action': 'rejected',
                'label': 'Rejected',
                'description': 'Job description was rejected',
                'next_approver': None
            }
        
        return None
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