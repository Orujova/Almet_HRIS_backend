# api/performance_models.py

from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.core.exceptions import ValidationError
import uuid
import logging

from .models import Employee, PositionGroup, Department
from .competency_models import Skill, SkillGroup  # CORE COMPETENCIES

logger = logging.getLogger(__name__)


class PerformanceYear(models.Model):
    """Performance Year Configuration"""
    year = models.IntegerField(unique=True)
    is_active = models.BooleanField(default=False)
    
    # Goal Setting Period
    goal_setting_employee_start = models.DateField()
    goal_setting_employee_end = models.DateField()
    goal_setting_manager_start = models.DateField()
    goal_setting_manager_end = models.DateField()
    
    # Mid-Year Review Period
    mid_year_review_start = models.DateField()
    mid_year_review_end = models.DateField()
    
    # End-Year Review Period
    end_year_review_start = models.DateField()
    end_year_review_end = models.DateField()
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        ordering = ['-year']
        db_table = 'performance_years'
    
    def __str__(self):
        return f"Performance Year {self.year}"
    
    def get_current_period(self):
        """Get current performance period"""
        today = timezone.now().date()
        
        if self.goal_setting_employee_start <= today <= self.goal_setting_manager_end:
            return 'GOAL_SETTING'
        elif self.mid_year_review_start <= today <= self.mid_year_review_end:
            return 'MID_YEAR_REVIEW'
        elif self.end_year_review_start <= today <= self.end_year_review_end:
            return 'END_YEAR_REVIEW'
        else:
            return 'CLOSED'
    
    def save(self, *args, **kwargs):
        if self.is_active:
            PerformanceYear.objects.filter(is_active=True).exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)


class PerformanceWeightConfig(models.Model):
    """Performance Weight Configuration by Position Group"""
    position_group = models.ForeignKey(PositionGroup, on_delete=models.CASCADE)
    objectives_weight = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Objectives weight percentage"
    )
    competencies_weight = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Competencies weight percentage"
    )
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'performance_weight_configs'
        unique_together = ['position_group']
    
    def __str__(self):
        return f"{self.position_group.get_name_display()} - Obj:{self.objectives_weight}% Comp:{self.competencies_weight}%"
    
    def clean(self):
        if self.objectives_weight + self.competencies_weight != 100:
            raise ValidationError("Objectives and Competencies weights must sum to 100%")


class GoalLimitConfig(models.Model):
    """Goal Limits Configuration"""
    min_goals = models.IntegerField(default=3, validators=[MinValueValidator(1)])
    max_goals = models.IntegerField(default=7, validators=[MinValueValidator(1)])
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'performance_goal_limits'
    
    def __str__(self):
        return f"Goal Limits: {self.min_goals} - {self.max_goals}"
    
    @classmethod
    def get_active_config(cls):
        config = cls.objects.filter(is_active=True).first()
        if not config:
            config = cls.objects.create(min_goals=3, max_goals=7, is_active=True)
        return config


class DepartmentObjective(models.Model):
    """Department Level Objectives"""
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    title = models.CharField(max_length=300)
  
    weight = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Weight percentage"
    )
    

    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        db_table = 'performance_department_objectives'
        ordering = ['department', 'title']
    
    def __str__(self):
        return f"{self.department.name} - {self.title}"


class EvaluationScale(models.Model):
    """Evaluation Scale Definition"""
    name = models.CharField(max_length=10, unique=True, help_text="e.g., E++, E+, E, E-, E--")
    value = models.IntegerField(help_text="Numeric value for calculations")
    range_min = models.IntegerField(help_text="Minimum percentage")
    range_max = models.IntegerField(help_text="Maximum percentage")
  
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'performance_evaluation_scales'
        ordering = ['-range_min']
    
    def __str__(self):
        return f"{self.name} ({self.range_min}-{self.range_max}%)"
    
    @classmethod
    def get_rating_by_percentage(cls, percentage):
        try:
            return cls.objects.filter(
                range_min__lte=percentage,
                range_max__gte=percentage,
                is_active=True
            ).first()
        except:
            return None


class EvaluationTargetConfig(models.Model):
    """Evaluation Target Configuration"""
    objective_score_target = models.IntegerField(default=21)
    competency_score_target = models.IntegerField(default=25)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'performance_evaluation_targets'
    
    def __str__(self):
        return f"Targets: Obj={self.objective_score_target}, Comp={self.competency_score_target}"
    
    @classmethod
    def get_active_config(cls):
        config = cls.objects.filter(is_active=True).first()
        if not config:
            config = cls.objects.create(is_active=True)
        return config


class ObjectiveStatus(models.Model):
    """Objective Status Types"""
    label = models.CharField(max_length=50, unique=True)
  
  
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'performance_objective_statuses'
     
    
    def __str__(self):
        return self.label


class EmployeePerformance(models.Model):
    """Employee Performance Record"""
    APPROVAL_STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('PENDING_EMPLOYEE_APPROVAL', 'Pending Employee Approval'),
        ('PENDING_MANAGER_APPROVAL', 'Pending Manager Approval'),
        ('NEED_CLARIFICATION', 'Need Clarification'),
        ('APPROVED', 'Approved'),
        ('COMPLETED', 'Completed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='performances')
    performance_year = models.ForeignKey(PerformanceYear, on_delete=models.CASCADE)
    
    # Approval workflow
    approval_status = models.CharField(max_length=30, choices=APPROVAL_STATUS_CHOICES, default='DRAFT')
    
    # Objective Setting
    objectives_set_date = models.DateTimeField(null=True, blank=True)
    objectives_employee_submitted = models.BooleanField(default=False)
    objectives_employee_approved = models.BooleanField(default=False)
    objectives_manager_approved = models.BooleanField(default=False)
    objectives_deadline = models.DateField(null=True, blank=True)
    
    # Mid-Year Review
    mid_year_employee_comment = models.TextField(blank=True)
    mid_year_employee_submitted = models.DateTimeField(null=True, blank=True)
    mid_year_manager_comment = models.TextField(blank=True)
    mid_year_manager_submitted = models.DateTimeField(null=True, blank=True)
    mid_year_completed = models.BooleanField(default=False)
    
    # End-Year Review
    end_year_employee_comment = models.TextField(blank=True)
    end_year_employee_submitted = models.DateTimeField(null=True, blank=True)
    end_year_manager_comment = models.TextField(blank=True)
    end_year_manager_submitted = models.DateTimeField(null=True, blank=True)
    end_year_completed = models.BooleanField(default=False)
    
    # Final employee approval of performance result
    final_employee_approved = models.BooleanField(default=False)
    final_employee_approval_date = models.DateTimeField(null=True, blank=True)
    final_manager_approved = models.BooleanField(default=False)
    final_manager_approval_date = models.DateTimeField(null=True, blank=True)
    
    # Final Scores
    total_objectives_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    objectives_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    total_competencies_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    competencies_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    overall_weighted_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    final_rating = models.CharField(max_length=10, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_performances')
    
    class Meta:
        db_table = 'employee_performances'
        unique_together = ['employee', 'performance_year']
        ordering = ['-performance_year__year', 'employee__employee_id']
    
    def __str__(self):
        return f"{self.employee.full_name} - {self.performance_year.year}"
    
    def calculate_scores(self):
        """Calculate all performance scores"""
        eval_target = EvaluationTargetConfig.get_active_config()
        weight_config = PerformanceWeightConfig.objects.filter(
            position_group=self.employee.position_group
        ).first()
        
        if not weight_config:
            logger.warning(f"No weight config for {self.employee.position_group}")
            return
        
        # Calculate objectives score
        objectives = self.objectives.filter(is_cancelled=False)
        obj_score = sum([
            (obj.end_year_rating.value if obj.end_year_rating else 0) * 
            (obj.weight / 100) * 
            (eval_target.objective_score_target / 5)
            for obj in objectives
        ])
        
        self.total_objectives_score = round(obj_score, 2)
        self.objectives_percentage = round(
            (self.total_objectives_score / eval_target.objective_score_target) * 100, 2
        ) if eval_target.objective_score_target > 0 else 0
        
        # Calculate competencies score
        competencies = self.competency_ratings.all()
        comp_score = sum([
            comp.end_year_rating.value if comp.end_year_rating else 0
            for comp in competencies
        ])
        
        self.total_competencies_score = round(comp_score, 2)
        self.competencies_percentage = round(
            (self.total_competencies_score / eval_target.competency_score_target) * 100, 2
        ) if eval_target.competency_score_target > 0 else 0
        
        # Calculate overall weighted percentage
        self.overall_weighted_percentage = round(
            (self.objectives_percentage * weight_config.objectives_weight / 100) +
            (self.competencies_percentage * weight_config.competencies_weight / 100),
            2
        )
        
        # Determine final rating
        rating = EvaluationScale.get_rating_by_percentage(self.overall_weighted_percentage)
        self.final_rating = rating.name if rating else 'N/A'
        
        self.save()


class EmployeeObjective(models.Model):
    """Employee Objectives"""
    performance = models.ForeignKey(EmployeePerformance, on_delete=models.CASCADE, related_name='objectives')
    
    title = models.CharField(max_length=300)
    description = models.TextField()
    linked_department_objective = models.ForeignKey(
        DepartmentObjective, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True
    )
    
    weight = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Weight percentage"
    )
    
    # Progress tracking
    progress = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    status = models.ForeignKey(ObjectiveStatus, on_delete=models.PROTECT)
    
    # End-year evaluation
    end_year_rating = models.ForeignKey(
        EvaluationScale, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='objective_ratings'
    )
    calculated_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Manager can cancel/add mid-year
    is_cancelled = models.BooleanField(default=False)
    cancelled_date = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.TextField(blank=True)
    added_mid_year = models.BooleanField(default=False)
    
    display_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'employee_objectives'
        ordering = ['performance', 'display_order']
    
    def __str__(self):
        return f"{self.performance.employee.full_name} - {self.title}"


class EmployeeCompetencyRating(models.Model):
    """Employee Competency Ratings - Uses CORE Competencies (Skill)"""
    performance = models.ForeignKey(
        EmployeePerformance, 
        on_delete=models.CASCADE, 
        related_name='competency_ratings'
    )
    competency = models.ForeignKey(Skill, on_delete=models.CASCADE)  # CORE COMPETENCY
    
    # End-year rating
    end_year_rating = models.ForeignKey(
        EvaluationScale,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='competency_ratings'
    )
    
    notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'employee_competency_ratings'
        unique_together = ['performance', 'competency']
        ordering = ['competency__group', 'competency__name']
    
    def __str__(self):
        return f"{self.performance.employee.full_name} - {self.competency.name}"


class DevelopmentNeed(models.Model):
    """Development Needs (for competencies with E-- or E-)"""
    performance = models.ForeignKey(
        EmployeePerformance,
        on_delete=models.CASCADE,
        related_name='development_needs'
    )
    competency_gap = models.CharField(max_length=200, help_text="Competency name with gap")
    development_activity = models.TextField(help_text="Planned development activity")
    
    progress = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    comment = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'employee_development_needs'
        ordering = ['performance', 'competency_gap']
    
    def __str__(self):
        return f"{self.performance.employee.full_name} - {self.competency_gap}"


class PerformanceComment(models.Model):
    """Comments and Clarifications"""
    COMMENT_TYPE_CHOICES = [
        ('OBJECTIVE_CLARIFICATION', 'Objective Clarification'),
        ('FINAL_CLARIFICATION', 'Final Performance Clarification'),
        ('GENERAL_NOTE', 'General Note'),
    ]
    
    performance = models.ForeignKey(
        EmployeePerformance,
        on_delete=models.CASCADE,
        related_name='comments'
    )
    
    comment_type = models.CharField(max_length=30, choices=COMMENT_TYPE_CHOICES)
    content = models.TextField()
    
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Parent comment for threading
    parent_comment = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='replies'
    )
    
    class Meta:
        db_table = 'performance_comments'
        ordering = ['created_at']
    
    def __str__(self):
        return f"{self.performance.employee.full_name} - {self.comment_type}"


class PerformanceNotificationTemplate(models.Model):
    """Notification Templates"""
    TRIGGER_TYPE_CHOICES = [
        ('GOAL_SETTING_START', 'Goal Setting Period Started'),
        ('MID_YEAR_START', 'Mid-Year Review Started'),
        ('MID_YEAR_END', 'Mid-Year Review Ending'),
        ('END_YEAR_START', 'End-Year Review Started'),
        ('END_YEAR_END', 'End-Year Review Ending'),
        ('FINAL_SCORE_PUBLISHED', 'Final Score Published'),
    ]
    
    trigger_type = models.CharField(max_length=30, choices=TRIGGER_TYPE_CHOICES, unique=True)
    subject = models.CharField(max_length=200)
    message_template = models.TextField(
        help_text="Use {{employee_name}}, {{year}}, {{deadline}} as placeholders"
    )
    
    days_before = models.IntegerField(
        default=0,
        help_text="Days before deadline to send notification"
    )
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'performance_notification_templates'
    
    def __str__(self):
        return f"{self.get_trigger_type_display()}"


class PerformanceActivityLog(models.Model):
    """Activity Log for Performance Records"""
    performance = models.ForeignKey(
        EmployeePerformance,
        on_delete=models.CASCADE,
        related_name='activity_logs'
    )
    
    action = models.CharField(max_length=100)
    description = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)
    
    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'performance_activity_logs'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.performance.employee.full_name} - {self.action}"