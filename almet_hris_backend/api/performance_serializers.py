# api/performance_serializers.py

from rest_framework import serializers
from django.db import transaction
from .performance_models import *
from .models import Employee
from .competency_models import BehavioralCompetency, BehavioralCompetencyGroup  # CHANGED
from .competency_assessment_models import PositionBehavioralAssessment  # ADDED


class PerformanceYearSerializer(serializers.ModelSerializer):
    current_period = serializers.SerializerMethodField()
    
    class Meta:
        model = PerformanceYear
        fields = '__all__'
    
    def get_current_period(self, obj):
        return obj.get_current_period()


class PerformanceWeightConfigSerializer(serializers.ModelSerializer):
    position_group_name = serializers.CharField(source='position_group.get_name_display', read_only=True)
    
    class Meta:
        model = PerformanceWeightConfig
        fields = '__all__'


class GoalLimitConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = GoalLimitConfig
        fields = '__all__'


class DepartmentObjectiveSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source='department.name', read_only=True)
    
    class Meta:
        model = DepartmentObjective
        fields = '__all__'


class EvaluationScaleSerializer(serializers.ModelSerializer):
    class Meta:
        model = EvaluationScale
        fields = '__all__'


class EvaluationTargetConfigSerializer(serializers.ModelSerializer):
    """UPDATED: Removed competency_score_target"""
    class Meta:
        model = EvaluationTargetConfig
        fields = '__all__'


class ObjectiveStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = ObjectiveStatus
        fields = '__all__'


class BehavioralCompetencyGroupWithCompetenciesSerializer(serializers.ModelSerializer):
    """NEW: Behavioral Competency Group with Competencies for performance"""
    competencies = serializers.SerializerMethodField()
    
    class Meta:
        model = BehavioralCompetencyGroup
        fields = ['id', 'name', 'competencies']
    
    def get_competencies(self, obj):
        competencies = obj.competencies.all()
        return [{'id': c.id, 'name': c.name} for c in competencies]


class EmployeeObjectiveSerializer(serializers.ModelSerializer):
    linked_department_objective_title = serializers.CharField(
        source='linked_department_objective.title', 
        read_only=True,
        allow_null=True
    )
    status_label = serializers.CharField(source='status.label', read_only=True)
    status_value = serializers.CharField(source='status.value', read_only=True)
    end_year_rating_name = serializers.CharField(source='end_year_rating.name', read_only=True, allow_null=True)
    end_year_rating_value = serializers.IntegerField(source='end_year_rating.value', read_only=True, allow_null=True)
    
    class Meta:
        model = EmployeeObjective
        fields = '__all__'


class EmployeeCompetencyRatingSerializer(serializers.ModelSerializer):
    """
    UPDATED: Now uses Behavioral Competency instead of Skill
    """
    competency_name = serializers.CharField(source='behavioral_competency.name', read_only=True)
    competency_group = serializers.CharField(source='behavioral_competency.group.name', read_only=True)
    end_year_rating_name = serializers.CharField(source='end_year_rating.name', read_only=True, allow_null=True)
    end_year_rating_value = serializers.IntegerField(source='end_year_rating.value', read_only=True, allow_null=True)
    
    # NEW: Show required level and gap
    actual_value = serializers.IntegerField(read_only=True)
    gap = serializers.IntegerField(read_only=True)
    gap_status = serializers.SerializerMethodField()
    
    class Meta:
        model = EmployeeCompetencyRating
        fields = '__all__'
    
    def get_gap_status(self, obj):
        """Get gap status: exceeds, meets, below"""
        gap = obj.gap
        if gap > 0:
            return 'exceeds'
        elif gap == 0:
            return 'meets'
        else:
            return 'below'


class DevelopmentNeedSerializer(serializers.ModelSerializer):
    class Meta:
        model = DevelopmentNeed
        fields = '__all__'


class PerformanceCommentSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    replies = serializers.SerializerMethodField()
    
    class Meta:
        model = PerformanceComment
        fields = '__all__'
    
    def get_replies(self, obj):
        if obj.replies.exists():
            return PerformanceCommentSerializer(obj.replies.all(), many=True).data
        return []


class PerformanceActivityLogSerializer(serializers.ModelSerializer):
    performed_by_name = serializers.CharField(source='performed_by.get_full_name', read_only=True)
    
    class Meta:
        model = PerformanceActivityLog
        fields = '__all__'


class EmployeePerformanceListSerializer(serializers.ModelSerializer):
    """Simplified serializer for list view"""
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    employee_id = serializers.CharField(source='employee.employee_id', read_only=True)
    employee_job_title = serializers.CharField(source='employee.job_title', read_only=True)
    employee_department = serializers.CharField(source='employee.department.name', read_only=True)
    year = serializers.IntegerField(source='performance_year.year', read_only=True)
    
    objectives_count = serializers.SerializerMethodField()
    competencies_count = serializers.SerializerMethodField()
    
    # Draft status indicators
    has_objectives_draft = serializers.SerializerMethodField()
    has_competencies_draft = serializers.SerializerMethodField()
    has_mid_year_draft = serializers.SerializerMethodField()
    has_end_year_draft = serializers.SerializerMethodField()
    has_dev_needs_draft = serializers.SerializerMethodField()
    
    class Meta:
        model = EmployeePerformance
        fields = [
            'id', 'employee', 'employee_name', 'employee_id', 'employee_job_title', 'employee_department',
            'year', 'approval_status',
            'objectives_count', 'competencies_count',
            'objectives_employee_submitted', 'objectives_employee_approved', 'objectives_manager_approved',
            'mid_year_completed', 'end_year_completed',
            'final_employee_approved', 'final_manager_approved',
            'overall_weighted_percentage', 'final_rating',
            'competencies_letter_grade',  # NEW
            'has_objectives_draft', 'has_competencies_draft', 'has_mid_year_draft', 
            'has_end_year_draft', 'has_dev_needs_draft',
            'created_at', 'updated_at'
        ]
    
    def get_objectives_count(self, obj):
        return obj.objectives.filter(is_cancelled=False).count()
    
    def get_competencies_count(self, obj):
        return obj.competency_ratings.count()
    
    def get_has_objectives_draft(self, obj):
        return obj.objectives_draft_saved_date is not None
    
    def get_has_competencies_draft(self, obj):
        return obj.competencies_draft_saved_date is not None
    
    def get_has_mid_year_draft(self, obj):
        return obj.mid_year_employee_draft_saved is not None or obj.mid_year_manager_draft_saved is not None
    
    def get_has_end_year_draft(self, obj):
        return obj.end_year_employee_draft_saved is not None or obj.end_year_manager_draft_saved is not None
    
    def get_has_dev_needs_draft(self, obj):
        return obj.development_needs_draft_saved is not None


class EmployeePerformanceDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer with all related data"""
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    employee_id = serializers.CharField(source='employee.employee_id', read_only=True)
    employee_job_title = serializers.CharField(source='employee.job_title', read_only=True)
    employee_department = serializers.CharField(source='employee.department.name', read_only=True)
    employee_position_group = serializers.CharField(
        source='employee.position_group.get_name_display', 
        read_only=True
    )
    employee_grade_level = serializers.CharField(source='employee.grading_level', read_only=True)  # NEW
    line_manager_name = serializers.CharField(source='employee.line_manager.full_name', read_only=True, allow_null=True)
    
    year = serializers.IntegerField(source='performance_year.year', read_only=True)
    current_period = serializers.CharField(source='performance_year.get_current_period', read_only=True)
    
    objectives = EmployeeObjectiveSerializer(many=True, read_only=True)
    competency_ratings = EmployeeCompetencyRatingSerializer(many=True, read_only=True)
    development_needs = DevelopmentNeedSerializer(many=True, read_only=True)
    comments = PerformanceCommentSerializer(many=True, read_only=True)
    activity_logs = PerformanceActivityLogSerializer(many=True, read_only=True)
    
    # Weight configuration
    weight_config = serializers.SerializerMethodField()
    
    # Evaluation targets
    evaluation_targets = serializers.SerializerMethodField()
    
    # Goal limits
    goal_limits = serializers.SerializerMethodField()
    
    # NEW: Group competency scores breakdown
    group_scores_breakdown = serializers.SerializerMethodField()
    
    class Meta:
        model = EmployeePerformance
        fields = '__all__'
    
    def get_weight_config(self, obj):
        weight = PerformanceWeightConfig.objects.filter(
            position_group=obj.employee.position_group
        ).first()
        if weight:
            return {
                'objectives_weight': weight.objectives_weight,
                'competencies_weight': weight.competencies_weight
            }
        return None
    
    def get_evaluation_targets(self, obj):
        config = EvaluationTargetConfig.get_active_config()
        return {
            'objective_score_target': config.objective_score_target,
            # competency_score_target removed
        }
    
    def get_goal_limits(self, obj):
        config = GoalLimitConfig.get_active_config()
        return {
            'min_goals': config.min_goals,
            'max_goals': config.max_goals
        }
    
    def get_group_scores_breakdown(self, obj):
        """Get detailed breakdown of competency scores by group"""
        return obj.group_competency_scores


class EmployeePerformanceCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating performance with nested data"""
    objectives_data = serializers.ListField(write_only=True, required=False)
    competency_ratings_data = serializers.ListField(write_only=True, required=False)
    development_needs_data = serializers.ListField(write_only=True, required=False)
    
    class Meta:
        model = EmployeePerformance
        fields = [
            'id', 'employee', 'performance_year', 'approval_status',
            'mid_year_employee_comment', 'mid_year_manager_comment',
            'end_year_employee_comment', 'end_year_manager_comment',
            'objectives_data', 'competency_ratings_data', 'development_needs_data'
        ]
        read_only_fields = ['id']
    
    def create(self, validated_data):
        objectives_data = validated_data.pop('objectives_data', [])
        competency_ratings_data = validated_data.pop('competency_ratings_data', [])
        development_needs_data = validated_data.pop('development_needs_data', [])
        
        with transaction.atomic():
            # Create performance record
            performance = EmployeePerformance.objects.create(**validated_data)
            
            # Create objectives
            for idx, obj_data in enumerate(objectives_data):
                EmployeeObjective.objects.create(
                    performance=performance,
                    display_order=idx,
                    **obj_data
                )
            
            # Create competency ratings
            for comp_data in competency_ratings_data:
                EmployeeCompetencyRating.objects.create(
                    performance=performance,
                    **comp_data
                )
            
            # Create development needs
            for dev_data in development_needs_data:
                DevelopmentNeed.objects.create(
                    performance=performance,
                    **dev_data
                )
            
            # Log activity
            PerformanceActivityLog.objects.create(
                performance=performance,
                action='CREATED',
                description=f'Performance record created for {performance.employee.full_name}',
                performed_by=self.context['request'].user if 'request' in self.context else None
            )
            
            return performance
    
    def update(self, instance, validated_data):
        objectives_data = validated_data.pop('objectives_data', None)
        competency_ratings_data = validated_data.pop('competency_ratings_data', None)
        development_needs_data = validated_data.pop('development_needs_data', None)
        
        with transaction.atomic():
            # Update performance fields
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()
            
            # Update objectives if provided
            if objectives_data is not None:
                updated_ids = []
                for idx, obj_data in enumerate(objectives_data):
                    obj_id = obj_data.pop('id', None)
                    if obj_id:
                        EmployeeObjective.objects.filter(id=obj_id, performance=instance).update(
                            display_order=idx, **obj_data
                        )
                        updated_ids.append(obj_id)
                    else:
                        new_obj = EmployeeObjective.objects.create(
                            performance=instance,
                            display_order=idx,
                            **obj_data
                        )
                        updated_ids.append(new_obj.id)
                
                instance.objectives.exclude(id__in=updated_ids).delete()
            
            # Update competency ratings if provided
            if competency_ratings_data is not None:
                for comp_data in competency_ratings_data:
                    comp_id = comp_data.pop('id', None)
                    behavioral_competency_id = comp_data.get('behavioral_competency')
                    
                    if comp_id:
                        EmployeeCompetencyRating.objects.filter(
                            id=comp_id, 
                            performance=instance
                        ).update(**comp_data)
                    else:
                        EmployeeCompetencyRating.objects.update_or_create(
                            performance=instance,
                            behavioral_competency_id=behavioral_competency_id,
                            defaults=comp_data
                        )
            
            # Update development needs if provided
            if development_needs_data is not None:
                updated_dev_ids = []
                for dev_data in development_needs_data:
                    dev_id = dev_data.pop('id', None)
                    if dev_id:
                        DevelopmentNeed.objects.filter(id=dev_id, performance=instance).update(**dev_data)
                        updated_dev_ids.append(dev_id)
                    else:
                        new_dev = DevelopmentNeed.objects.create(performance=instance, **dev_data)
                        updated_dev_ids.append(new_dev.id)
                
                instance.development_needs.exclude(id__in=updated_dev_ids).delete()
            
            # Recalculate scores if end-year ratings provided
            if competency_ratings_data or objectives_data:
                instance.calculate_scores()
            
            # Log activity
            PerformanceActivityLog.objects.create(
                performance=instance,
                action='UPDATED',
                description=f'Performance record updated for {instance.employee.full_name}',
                performed_by=self.context['request'].user if 'request' in self.context else None
            )
            
            return instance


class PerformanceNotificationTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = PerformanceNotificationTemplate
        fields = '__all__'


class PerformanceDashboardSerializer(serializers.Serializer):
    """Serializer for dashboard statistics"""
    total_employees = serializers.IntegerField()
    objectives_completed = serializers.IntegerField()
    mid_year_completed = serializers.IntegerField()
    end_year_completed = serializers.IntegerField()
    
    current_period = serializers.CharField()
    year = serializers.IntegerField()
    
    timeline = serializers.DictField()
    by_department = serializers.ListField()
    recent_activities = serializers.ListField()
    
    # Additional stats
    pending_employee_approval = serializers.IntegerField()
    pending_manager_approval = serializers.IntegerField()
    need_clarification = serializers.IntegerField()


class PerformanceInitializeSerializer(serializers.Serializer):
    """
    UPDATED: Initializing performance now loads behavioral competencies from position assessment
    """
    employee = serializers.PrimaryKeyRelatedField(queryset=Employee.objects.all())
    performance_year = serializers.PrimaryKeyRelatedField(queryset=PerformanceYear.objects.all())
    
    def validate(self, data):
        """Validate that employee has a matching position behavioral assessment"""
        employee = data['employee']
        
        # Check if position behavioral assessment exists
        position_assessment = PositionBehavioralAssessment.objects.filter(
            position_group=employee.position_group,
            job_title=employee.job_title,
            grade_levels__contains=[employee.grading_level],
            is_active=True
        ).first()
        
        if not position_assessment:
            raise serializers.ValidationError(
                f"No behavioral assessment template found for {employee.job_title} "
                f"(Grade {employee.grading_level}). Please create position assessment first."
            )
        
        data['position_assessment'] = position_assessment
        return data
    
    def create(self, validated_data):
        employee = validated_data['employee']
        performance_year = validated_data['performance_year']
        position_assessment = validated_data['position_assessment']
        
        # Check if already exists
        existing = EmployeePerformance.objects.filter(
            employee=employee,
            performance_year=performance_year
        ).first()
        
        if existing:
            return existing
        
        with transaction.atomic():
            # Create performance record
            performance = EmployeePerformance.objects.create(
                employee=employee,
                performance_year=performance_year,
                approval_status='DRAFT'
            )
            
            # Auto-create competency ratings from position behavioral assessment
            position_ratings = position_assessment.competency_ratings.all()
            for position_rating in position_ratings:
                EmployeeCompetencyRating.objects.create(
                    performance=performance,
                    behavioral_competency=position_rating.behavioral_competency,
                    required_level=position_rating.required_level
                )
            
            # Log activity
            PerformanceActivityLog.objects.create(
                performance=performance,
                action='INITIALIZED',
                description=f'Performance initialized for {employee.full_name} - {performance_year.year} '
                           f'with {position_ratings.count()} behavioral competencies from position assessment',
                performed_by=self.context.get('request').user if self.context.get('request') else None
            )
            
            return performance