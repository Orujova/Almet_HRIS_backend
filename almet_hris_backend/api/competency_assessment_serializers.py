# api/competency_assessment_serializers.py

from rest_framework import serializers
from django.db import transaction
from django.contrib.auth.models import User
from .competency_assessment_models import (
    CoreCompetencyScale, BehavioralScale, LetterGradeMapping,
    PositionCoreAssessment, PositionCoreCompetencyRating,
    PositionBehavioralAssessment, PositionBehavioralCompetencyRating,
    EmployeeCoreAssessment, EmployeeCoreCompetencyRating,
    EmployeeBehavioralAssessment, EmployeeBehavioralCompetencyRating
)
from .competency_models import Skill, BehavioralCompetency
from .models import Employee, PositionGroup
from .job_description_models import JobDescription


# SCALE MANAGEMENT SERIALIZERS

class CoreCompetencyScaleSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    
    class Meta:
        model = CoreCompetencyScale
        fields = [
            'id', 'scale', 'description', 'is_active', 
            'created_at', 'updated_at', 'created_by', 'created_by_name'
        ]
        read_only_fields = ['created_at', 'updated_at', 'created_by']
    
    def create(self, validated_data):
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)


class BehavioralScaleSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    
    class Meta:
        model = BehavioralScale
        fields = [
            'id', 'scale', 'description', 'is_active', 
            'created_at', 'updated_at', 'created_by', 'created_by_name'
        ]
        read_only_fields = ['created_at', 'updated_at', 'created_by']
    
    def create(self, validated_data):
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)


class LetterGradeMappingSerializer(serializers.ModelSerializer):
    class Meta:
        model = LetterGradeMapping
        fields = [
            'id', 'letter_grade', 'min_percentage', 'max_percentage', 
            'description', 'is_active', 'created_at'
        ]
        read_only_fields = ['created_at']
    
    def validate(self, data):
        """Validate percentage ranges don't overlap"""
        min_pct = data.get('min_percentage')
        max_pct = data.get('max_percentage')
        
        if min_pct >= max_pct:
            raise serializers.ValidationError("Min percentage must be less than max percentage")
        
        # Check for overlaps with existing grades
        existing = LetterGradeMapping.objects.filter(is_active=True)
        if self.instance:
            existing = existing.exclude(id=self.instance.id)
        
        for grade in existing:
            # Check if ranges overlap
            ranges_overlap = not (max_pct < grade.min_percentage or min_pct > grade.max_percentage)
            
            if ranges_overlap:
                raise serializers.ValidationError(
                    f"Percentage range {min_pct}-{max_pct}% overlaps with existing grade '{grade.letter_grade}' ({grade.min_percentage}-{grade.max_percentage}%)"
                )
        
        return data


# POSITION ASSESSMENT SERIALIZERS

class PositionCoreCompetencyRatingSerializer(serializers.ModelSerializer):
    skill_name = serializers.CharField(source='skill.name', read_only=True)
    skill_group_name = serializers.CharField(source='skill.group.name', read_only=True)
    
    class Meta:
        model = PositionCoreCompetencyRating
        fields = [
            'id', 'skill', 'skill_name', 'skill_group_name', 
            'required_level', 'created_at'
        ]
        read_only_fields = ['created_at']


class PositionCoreAssessmentSerializer(serializers.ModelSerializer):
    position_group_name = serializers.CharField(source='position_group.get_name_display', read_only=True)
    competency_ratings = PositionCoreCompetencyRatingSerializer(many=True, read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    
    class Meta:
        model = PositionCoreAssessment
        fields = [
            'id', 'position_group', 'position_group_name', 'job_title', 
            'competency_ratings', 'is_active',
            'created_at', 'updated_at', 'created_by', 'created_by_name'
        ]
        read_only_fields = ['created_at', 'updated_at', 'created_by']


class PositionCoreAssessmentCreateSerializer(serializers.ModelSerializer):
    competency_ratings = serializers.ListField(
        child=serializers.DictField(),
        write_only=True,
        help_text="List of {skill_id: required_level} mappings"
    )
    
    class Meta:
        model = PositionCoreAssessment
        fields = [
            'position_group', 'job_title', 'competency_ratings'
        ]
    
    def validate_competency_ratings(self, value):
        """Validate competency ratings format"""
        if not value:
            raise serializers.ValidationError("Competency ratings are required")
        
        for rating in value:
            if 'skill_id' not in rating or 'required_level' not in rating:
                raise serializers.ValidationError(
                    "Each rating must have skill_id and required_level"
                )
            
            level = rating.get('required_level')
            if not isinstance(level, int) or level < 0 or level > 10:
                raise serializers.ValidationError(
                    "Required level must be integer between 0-10"
                )
        
        return value
    
    @transaction.atomic
    def create(self, validated_data):
        competency_ratings = validated_data.pop('competency_ratings')
        validated_data['created_by'] = self.context['request'].user
        
        position_assessment = super().create(validated_data)
        
        # Create competency ratings
        for rating_data in competency_ratings:
            PositionCoreCompetencyRating.objects.create(
                position_assessment=position_assessment,
                skill_id=rating_data['skill_id'],
                required_level=rating_data['required_level']
            )
        
        return position_assessment
    
    @transaction.atomic
    def update(self, instance, validated_data):
        """Update position assessment and its competency ratings"""
        competency_ratings = validated_data.pop('competency_ratings', None)
        
        # Update basic fields
        instance.position_group = validated_data.get('position_group', instance.position_group)
        instance.job_title = validated_data.get('job_title', instance.job_title)
        instance.save()
        
        # Update competency ratings if provided
        if competency_ratings is not None:
            # Delete existing ratings
            instance.competency_ratings.all().delete()
            
            # Create new ratings
            for rating_data in competency_ratings:
                PositionCoreCompetencyRating.objects.create(
                    position_assessment=instance,
                    skill_id=rating_data['skill_id'],
                    required_level=rating_data['required_level']
                )
        
        return instance

class PositionBehavioralCompetencyRatingSerializer(serializers.ModelSerializer):
    competency_name = serializers.CharField(source='behavioral_competency.name', read_only=True)
    competency_group_name = serializers.CharField(source='behavioral_competency.group.name', read_only=True)
    
    class Meta:
        model = PositionBehavioralCompetencyRating
        fields = [
            'id', 'behavioral_competency', 'competency_name', 'competency_group_name',
            'required_level', 'created_at'
        ]
        read_only_fields = ['created_at']


class PositionBehavioralAssessmentSerializer(serializers.ModelSerializer):
    position_group_name = serializers.CharField(source='position_group.get_name_display', read_only=True)
    competency_ratings = PositionBehavioralCompetencyRatingSerializer(many=True, read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    
    class Meta:
        model = PositionBehavioralAssessment
        fields = [
            'id', 'position_group', 'position_group_name', 'job_title',
            'competency_ratings', 'is_active',
            'created_at', 'updated_at', 'created_by', 'created_by_name'
        ]
        read_only_fields = ['created_at', 'updated_at', 'created_by']


class PositionBehavioralAssessmentCreateSerializer(serializers.ModelSerializer):
    competency_ratings = serializers.ListField(
        child=serializers.DictField(),
        write_only=True,
        help_text="List of {behavioral_competency_id: required_level} mappings"
    )
    
    class Meta:
        model = PositionBehavioralAssessment
        fields = [
            'position_group', 'job_title', 'competency_ratings'
        ]
    
    def validate_competency_ratings(self, value):
        """Validate competency ratings format"""
        if not value:
            raise serializers.ValidationError("Competency ratings are required")
        
        for rating in value:
            if 'behavioral_competency_id' not in rating or 'required_level' not in rating:
                raise serializers.ValidationError(
                    "Each rating must have behavioral_competency_id and required_level"
                )
            
            level = rating.get('required_level')
            if not isinstance(level, int) or level < 1 or level > 10:
                raise serializers.ValidationError(
                    "Required level must be integer between 1-10"
                )
        
        return value
    
    @transaction.atomic
    def create(self, validated_data):
        competency_ratings = validated_data.pop('competency_ratings')
        validated_data['created_by'] = self.context['request'].user
        
        position_assessment = super().create(validated_data)
        
        # Create competency ratings
        for rating_data in competency_ratings:
            PositionBehavioralCompetencyRating.objects.create(
                position_assessment=position_assessment,
                behavioral_competency_id=rating_data['behavioral_competency_id'],
                required_level=rating_data['required_level']
            )
        
        return position_assessment
    
    @transaction.atomic
    def update(self, instance, validated_data):
        """Update position assessment and its competency ratings"""
        competency_ratings = validated_data.pop('competency_ratings', None)
        
        # Update basic fields
        instance.position_group = validated_data.get('position_group', instance.position_group)
        instance.job_title = validated_data.get('job_title', instance.job_title)
        instance.save()
        
        # Update competency ratings if provided
        if competency_ratings is not None:
            # Delete existing ratings
            instance.competency_ratings.all().delete()
            
            # Create new ratings
            for rating_data in competency_ratings:
                PositionBehavioralCompetencyRating.objects.create(
                    position_assessment=instance,
                    behavioral_competency_id=rating_data['behavioral_competency_id'],
                    required_level=rating_data['required_level']
                )
        
        return instance
class EmployeeCoreCompetencyRatingSerializer(serializers.ModelSerializer):
    skill_name = serializers.CharField(source='skill.name', read_only=True)
    skill_group_name = serializers.CharField(source='skill.group.name', read_only=True)
    gap_color = serializers.SerializerMethodField()
    
    class Meta:
        model = EmployeeCoreCompetencyRating
        fields = [
            'id', 'skill', 'skill_name', 'skill_group_name',
            'required_level', 'actual_level', 'gap', 'gap_color', 'notes', 'created_at'
        ]
        read_only_fields = ['gap', 'created_at']
    
    def get_gap_color(self, obj):
        """Get color coding for gap analysis"""
        if obj.gap > 0:
            return '#10B981'  # Green - exceeds requirement
        elif obj.gap == 0:
            return '#6B7280'  # Gray - meets requirement
        else:
            return '#EF4444'  # Red - below requirement


class EmployeeCoreAssessmentSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    employee_id = serializers.CharField(source='employee.employee_id', read_only=True)
    position_assessment_title = serializers.CharField(source='position_assessment.job_title', read_only=True)

    competency_ratings = EmployeeCoreCompetencyRatingSerializer(many=True, read_only=True)
    
    # Status display
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    can_edit = serializers.SerializerMethodField()
    
    # Gap analysis summary
    gap_analysis = serializers.SerializerMethodField()
    
    class Meta:
        model = EmployeeCoreAssessment
        fields = [
            'id', 'employee', 'employee_name', 'employee_id',
            'position_assessment', 'position_assessment_title', 'assessment_date', 
            'status', 'status_display', 'can_edit',
            'notes',
            'total_position_score', 'total_employee_score', 'gap_score',
            'completion_percentage', 'competency_ratings', 'gap_analysis',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'total_position_score', 'total_employee_score', 'gap_score', 
            'completion_percentage', 'created_at', 'updated_at'
        ]
    
    def get_can_edit(self, obj):
        """Check if assessment can be edited (only DRAFT status)"""
        return obj.status == 'DRAFT'
    
    def get_gap_analysis(self, obj):
        """Get gap analysis summary by skill groups"""
        from collections import defaultdict
        
        ratings = obj.competency_ratings.select_related('skill__group').all()
        group_analysis = defaultdict(lambda: {
            'skills_count': 0,
            'exceeds_count': 0,
            'meets_count': 0,
            'below_count': 0,
            'total_gap': 0
        })
        
        for rating in ratings:
            group_name = rating.skill.group.name
            group_analysis[group_name]['skills_count'] += 1
            group_analysis[group_name]['total_gap'] += rating.gap
            
            if rating.gap > 0:
                group_analysis[group_name]['exceeds_count'] += 1
            elif rating.gap == 0:
                group_analysis[group_name]['meets_count'] += 1
            else:
                group_analysis[group_name]['below_count'] += 1
        
        return dict(group_analysis)


class EmployeeCoreAssessmentCreateSerializer(serializers.ModelSerializer):
    competency_ratings = serializers.ListField(
        child=serializers.DictField(),
        write_only=True,
        help_text="List of {skill_id: actual_level} mappings",
        required=False
    )
    
    # Add action_type field to handle status transitions
    action_type = serializers.ChoiceField(
        choices=[('save_draft', 'Save Draft'), ('submit', 'Submit')],
        write_only=True,
        required=False,
        default='save_draft'
    )
    
    class Meta:
        model = EmployeeCoreAssessment
        fields = [
            'employee', 'position_assessment', 'assessment_date', 
          'notes', 'competency_ratings', 'action_type'
        ]
    
    def validate(self, data):
        """Validate employee matches position assessment"""
        employee = data.get('employee')
        position_assessment = data.get('position_assessment')
        
        if employee and position_assessment:
            # Check if employee's job title matches position assessment
            if employee.job_title != position_assessment.job_title:
                raise serializers.ValidationError(
                    f"Employee job title '{employee.job_title}' doesn't match "
                    f"position assessment '{position_assessment.job_title}'"
                )
        
        return data
    
    def validate_competency_ratings(self, value):
        """Validate competency ratings format"""
        if not value:
            return value  # Allow empty for draft saves
        
        for rating in value:
            if 'skill_id' not in rating or 'actual_level' not in rating:
                raise serializers.ValidationError(
                    "Each rating must have skill_id and actual_level"
                )
            
            level = rating.get('actual_level')
            if not isinstance(level, int) or level < 0 or level > 10:
                raise serializers.ValidationError(
                    "Actual level must be integer between 0-10"
                )
        
        return value
    
    @transaction.atomic
    def create(self, validated_data):
        competency_ratings = validated_data.pop('competency_ratings', [])
        action_type = validated_data.pop('action_type', 'save_draft')
        
        # Set status based on action type
        if action_type == 'submit':
            validated_data['status'] = 'COMPLETED'
        else:
            validated_data['status'] = 'DRAFT'
        
        assessment = super().create(validated_data)
        
        # Create employee ratings if provided
        if competency_ratings:
            # Get position requirements
            position_ratings = assessment.position_assessment.competency_ratings.all()
            position_requirements = {pr.skill_id: pr.required_level for pr in position_ratings}
            
            for rating_data in competency_ratings:
                skill_id = rating_data['skill_id']
                actual_level = rating_data['actual_level']
                required_level = position_requirements.get(skill_id, 0)
                
                EmployeeCoreCompetencyRating.objects.create(
                    assessment=assessment,
                    skill_id=skill_id,
                    required_level=required_level,
                    actual_level=actual_level,
                    notes=rating_data.get('notes', '')
                )
        
        # ALWAYS calculate scores when there are ratings, regardless of status
        if competency_ratings:
            assessment.calculate_scores()
        
        return assessment
    
    @transaction.atomic
    def update(self, instance, validated_data):
        competency_ratings = validated_data.pop('competency_ratings', None)
        action_type = validated_data.pop('action_type', 'save_draft')
        
        # Handle status transitions
        if action_type == 'submit':
            validated_data['status'] = 'COMPLETED'
        elif action_type == 'save_draft':
            validated_data['status'] = 'DRAFT'
        
        # Update the assessment
        assessment = super().update(instance, validated_data)
        
        # Update competency ratings if provided
        if competency_ratings is not None:
            # Clear existing ratings
            assessment.competency_ratings.all().delete()
            
            if competency_ratings:
                # Get position requirements
                position_ratings = assessment.position_assessment.competency_ratings.all()
                position_requirements = {pr.skill_id: pr.required_level for pr in position_ratings}
                
                # Create new ratings
                for rating_data in competency_ratings:
                    skill_id = rating_data['skill_id']
                    actual_level = rating_data['actual_level']
                    required_level = position_requirements.get(skill_id, 0)
                    
                    EmployeeCoreCompetencyRating.objects.create(
                        assessment=assessment,
                        skill_id=skill_id,
                        required_level=required_level,
                        actual_level=actual_level,
                        notes=rating_data.get('notes', '')
                    )
        
        # ALWAYS calculate scores when there are ratings or when assessment has ratings
        if competency_ratings or assessment.competency_ratings.exists():
            assessment.calculate_scores()
        
        return assessment

class EmployeeBehavioralCompetencyRatingSerializer(serializers.ModelSerializer):
    competency_name = serializers.CharField(source='behavioral_competency.name', read_only=True)
    competency_group_name = serializers.CharField(source='behavioral_competency.group.name', read_only=True)
    
    class Meta:
        model = EmployeeBehavioralCompetencyRating
        fields = [
            'id', 'behavioral_competency', 'competency_name', 'competency_group_name',
            'required_level', 'actual_level', 'notes', 'created_at'
        ]
        read_only_fields = ['created_at']


class EmployeeBehavioralAssessmentSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    employee_id = serializers.CharField(source='employee.employee_id', read_only=True)
    position_assessment_title = serializers.CharField(source='position_assessment.job_title', read_only=True)

    competency_ratings = EmployeeBehavioralCompetencyRatingSerializer(many=True, read_only=True)
    
    # Status display
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    can_edit = serializers.SerializerMethodField()
    
    # Group scores with letter grades
    group_scores_display = serializers.SerializerMethodField()
    overall_grade_info = serializers.SerializerMethodField()
    
    class Meta:
        model = EmployeeBehavioralAssessment
        fields = [
            'id', 'employee', 'employee_name', 'employee_id',
            'position_assessment', 'position_assessment_title', 'assessment_date', 
            'status', 'status_display', 'can_edit',
          'notes',
            'group_scores', 'group_scores_display', 'overall_percentage', 
            'overall_letter_grade', 'overall_grade_info', 'competency_ratings',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'group_scores', 'overall_percentage', 'overall_letter_grade',
            'created_at', 'updated_at'
        ]
    
    def get_can_edit(self, obj):
        """Check if assessment can be edited (only DRAFT status)"""
        return obj.status == 'DRAFT'
    
    def get_group_scores_display(self, obj):
        """Format group scores for display"""
        display_scores = {}
        for group_name, scores in obj.group_scores.items():
            letter_grade_obj = LetterGradeMapping.objects.filter(
                letter_grade=scores['letter_grade']
            ).first()
            
            display_scores[group_name] = {
                **scores,
                'description': letter_grade_obj.description if letter_grade_obj else ''
            }
        return display_scores
    
    def get_overall_grade_info(self, obj):
        """Get overall grade information with description"""
        letter_grade_obj = LetterGradeMapping.objects.filter(
            letter_grade=obj.overall_letter_grade
        ).first()
        
        return {
            'letter_grade': obj.overall_letter_grade,
            'percentage': obj.overall_percentage,
            'description': letter_grade_obj.description if letter_grade_obj else ''
        }


class EmployeeBehavioralAssessmentCreateSerializer(serializers.ModelSerializer):
    competency_ratings = serializers.ListField(
        child=serializers.DictField(),
        write_only=True,
        help_text="List of {behavioral_competency_id: actual_level} mappings",
        required=False
    )
    
    # Add action_type field to handle status transitions
    action_type = serializers.ChoiceField(
        choices=[('save_draft', 'Save Draft'), ('submit', 'Submit')],
        write_only=True,
        required=False,
        default='save_draft'
    )
    
    class Meta:
        model = EmployeeBehavioralAssessment
        fields = [
            'employee', 'position_assessment', 'assessment_date',
           'notes', 'competency_ratings', 'action_type'
        ]
    
    def validate(self, data):
        """Validate employee matches position assessment"""
        employee = data.get('employee')
        position_assessment = data.get('position_assessment')
        
        if employee and position_assessment:
            # Check if employee's job title matches position assessment
            if employee.job_title != position_assessment.job_title:
                raise serializers.ValidationError(
                    f"Employee job title '{employee.job_title}' doesn't match "
                    f"position assessment '{position_assessment.job_title}'"
                )
        
        return data
    
    def validate_competency_ratings(self, value):
        """Validate competency ratings format"""
        if not value:
            return value  # Allow empty for draft saves
        
        for rating in value:
            if 'behavioral_competency_id' not in rating or 'actual_level' not in rating:
                raise serializers.ValidationError(
                    "Each rating must have behavioral_competency_id and actual_level"
                )
            
            level = rating.get('actual_level')
            if not isinstance(level, int) or level < 1 or level > 10:
                raise serializers.ValidationError(
                    "Actual level must be integer between 1-10"
                )
        
        return value
    
    @transaction.atomic
    def create(self, validated_data):
        competency_ratings = validated_data.pop('competency_ratings', [])
        action_type = validated_data.pop('action_type', 'save_draft')
        
        # Set status based on action type
        if action_type == 'submit':
            validated_data['status'] = 'COMPLETED'
        else:
            validated_data['status'] = 'DRAFT'
        
        assessment = super().create(validated_data)
        
        # Create employee ratings if provided
        if competency_ratings:
            # Get position requirements
            position_ratings = assessment.position_assessment.competency_ratings.all()
            position_requirements = {pr.behavioral_competency_id: pr.required_level for pr in position_ratings}
            
            for rating_data in competency_ratings:
                competency_id = rating_data['behavioral_competency_id']
                actual_level = rating_data['actual_level']
                required_level = position_requirements.get(competency_id, 1)
                
                EmployeeBehavioralCompetencyRating.objects.create(
                    assessment=assessment,
                    behavioral_competency_id=competency_id,
                    required_level=required_level,
                    actual_level=actual_level,
                    notes=rating_data.get('notes', '')
                )
        
        # Calculate scores if submitting
        if action_type == 'submit':
            assessment.calculate_scores()
        
        return assessment
    
    @transaction.atomic
    def update(self, instance, validated_data):
        competency_ratings = validated_data.pop('competency_ratings', None)
        action_type = validated_data.pop('action_type', 'save_draft')
        
        # Handle status transitions
        if action_type == 'submit':
            validated_data['status'] = 'COMPLETED'
        elif action_type == 'save_draft':
            validated_data['status'] = 'DRAFT'
        
        # Update the assessment
        assessment = super().update(instance, validated_data)
        
        # Update competency ratings if provided
        if competency_ratings is not None:
            # Clear existing ratings
            assessment.competency_ratings.all().delete()
            
            if competency_ratings:
                # Get position requirements
                position_ratings = assessment.position_assessment.competency_ratings.all()
                position_requirements = {pr.behavioral_competency_id: pr.required_level for pr in position_ratings}
                
                # Create new ratings
                for rating_data in competency_ratings:
                    competency_id = rating_data['behavioral_competency_id']
                    actual_level = rating_data['actual_level']
                    required_level = position_requirements.get(competency_id, 1)
                    
                    EmployeeBehavioralCompetencyRating.objects.create(
                        assessment=assessment,
                        behavioral_competency_id=competency_id,
                        required_level=required_level,
                        actual_level=actual_level,
                        notes=rating_data.get('notes', '')
                    )
        
        # Calculate scores if submitting or if completed
        if action_type == 'submit' or assessment.status == 'COMPLETED':
            assessment.calculate_scores()
        
        return assessment



