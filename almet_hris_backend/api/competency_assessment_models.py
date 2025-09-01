# api/competency_assessment_models.py

from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.core.exceptions import ValidationError
import uuid
import logging

from .models import Employee, PositionGroup
from .competency_models import Skill, BehavioralCompetency
from .job_description_models import JobDescription

logger = logging.getLogger(__name__)

class CoreCompetencyScale(models.Model):
    """Core Competency Assessment Scale Definition"""
    scale = models.IntegerField(unique=True, help_text="Scale number/level")
    description = models.TextField(help_text="Description of this scale")
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        ordering = ['scale']
        db_table = 'competency_core_scales'
    
    def __str__(self):
        return f"Scale {self.scale}: {self.description[:50]}..."


class BehavioralScale(models.Model):
    """Behavioral Competency Scale Definition"""
    scale = models.IntegerField(unique=True, help_text="Scale number/level")
    description = models.TextField(help_text="Description of this scale")
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        ordering = ['scale']
        db_table = 'competency_behavioral_scales'
    
    def __str__(self):
        return f"Scale {self.scale}: {self.description[:50]}..."


class LetterGradeMapping(models.Model):
    """Letter grade mappings for behavioral assessments"""
    letter_grade = models.CharField(max_length=10, unique=True)
    min_percentage = models.IntegerField(help_text="Minimum percentage for this grade")
    max_percentage = models.IntegerField(help_text="Maximum percentage for this grade")
    description = models.CharField(max_length=200, blank=True)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-min_percentage']
        db_table = 'competency_letter_grades'
    
    def __str__(self):
        return f"{self.letter_grade} ({self.min_percentage}-{self.max_percentage}%)"
    
    @classmethod
    def get_letter_grade(cls, percentage):
        """Get letter grade for given percentage"""
        try:
            # Round percentage to 2 decimal places to avoid floating point issues
            percentage = round(float(percentage), 2)
            
            # Find grade where percentage falls within range
            grade = cls.objects.filter(
                min_percentage__lte=percentage,
                max_percentage__gte=percentage,
                is_active=True
            ).first()
            
            if grade:
                return grade.letter_grade
            
            # If no exact match, find closest grade
            # Check if percentage is above highest grade
            highest_grade = cls.objects.filter(is_active=True).order_by('-max_percentage').first()
            if highest_grade and percentage > highest_grade.max_percentage:
                return highest_grade.letter_grade
            
            # Check if percentage is below lowest grade
            lowest_grade = cls.objects.filter(is_active=True).order_by('min_percentage').first()
            if lowest_grade and percentage < lowest_grade.min_percentage:
                return lowest_grade.letter_grade
            
            return 'N/A'
            
        except (ValueError, TypeError):
            return 'N/A'
    
    def clean(self):
        """Validate that min_percentage <= max_percentage"""
        if self.min_percentage > self.max_percentage:
            raise ValidationError("Minimum percentage must be less than or equal to maximum percentage")
        
        # Check for overlaps with existing grades (excluding self)
        overlapping = LetterGradeMapping.objects.filter(is_active=True)
        if self.pk:
            overlapping = overlapping.exclude(pk=self.pk)
        
        for grade in overlapping:
            # Check if ranges overlap
            ranges_overlap = not (
                self.max_percentage < grade.min_percentage or 
                self.min_percentage > grade.max_percentage
            )
            
            if ranges_overlap:
                raise ValidationError(
                    f"Percentage range {self.min_percentage}-{self.max_percentage}% overlaps "
                    f"with existing grade '{grade.letter_grade}' ({grade.min_percentage}-{grade.max_percentage}%)"
                )
    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

class PositionCoreAssessment(models.Model):
    """Position-specific Core Competency Assessment Template"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Position details
    position_group = models.ForeignKey(PositionGroup, on_delete=models.CASCADE)
    job_title = models.CharField(max_length=200)
    
    # Status
    is_active = models.BooleanField(default=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        db_table = 'position_core_assessments'
        unique_together = ['position_group', 'job_title']
    
    def __str__(self):
        return f"{self.job_title} - Core Assessment"


class PositionCoreCompetencyRating(models.Model):
    """Individual competency ratings within position assessment"""
    position_assessment = models.ForeignKey(
        PositionCoreAssessment, 
        on_delete=models.CASCADE,
        related_name='competency_ratings'
    )
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE)
    required_level = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        help_text="Required proficiency level for this position"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'position_core_ratings'
        unique_together = ['position_assessment', 'skill']
    
    def __str__(self):
        return f"{self.position_assessment.job_title} - {self.skill.name}: {self.required_level}"


class PositionBehavioralAssessment(models.Model):
    """Position-specific Behavioral Competency Assessment Template"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Position details
    position_group = models.ForeignKey(PositionGroup, on_delete=models.CASCADE)
    job_title = models.CharField(max_length=200)
    
    # Status
    is_active = models.BooleanField(default=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        db_table = 'position_behavioral_assessments'
        unique_together = ['position_group', 'job_title']
    
    def __str__(self):
        return f"{self.job_title} - Behavioral Assessment"


class PositionBehavioralCompetencyRating(models.Model):
    """Individual behavioral competency ratings within position assessment"""
    position_assessment = models.ForeignKey(
        PositionBehavioralAssessment,
        on_delete=models.CASCADE,
        related_name='competency_ratings'
    )
    behavioral_competency = models.ForeignKey(BehavioralCompetency, on_delete=models.CASCADE)
    required_level = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="Required behavioral competency level"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'position_behavioral_ratings'
        unique_together = ['position_assessment', 'behavioral_competency']
    
    def __str__(self):
        return f"{self.position_assessment.job_title} - {self.behavioral_competency.name}: {self.required_level}"


class EmployeeCoreAssessment(models.Model):
    """Employee Core Competency Assessment"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Assessment details
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='core_assessments')
    position_assessment = models.ForeignKey(PositionCoreAssessment, on_delete=models.CASCADE)
    assessment_date = models.DateField(default=timezone.now)
    
    # Status with proper choices
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('COMPLETED', 'Completed'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    
    # Assessment metadata
    assessed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    notes = models.TextField(blank=True)
    
    # Calculated scores
    total_position_score = models.IntegerField(default=0, help_text="Total required score for position")
    total_employee_score = models.IntegerField(default=0, help_text="Total employee actual score")
    gap_score = models.IntegerField(default=0, help_text="Gap between required and actual")
    completion_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'employee_core_assessments'
        ordering = ['-created_at']
    
    def calculate_scores(self):
        """Calculate assessment scores and gaps"""
        ratings = self.competency_ratings.all()
        
        total_position = sum(r.required_level for r in ratings)
        total_employee = sum(r.actual_level for r in ratings)
        gap = total_employee - total_position
        
        self.total_position_score = total_position
        self.total_employee_score = total_employee
        self.gap_score = gap
        
        if total_position > 0:
            self.completion_percentage = (total_employee / total_position) * 100
        
        self.save()
    
    def can_edit(self):
        """Check if assessment can be edited"""
        return self.status == 'DRAFT'
    
    def save(self, *args, **kwargs):
        """Override save to handle status transitions"""
        # Only check for old instance if this is an update (not a create)
        if self.pk:
            try:
                # Check if status is changing from COMPLETED to DRAFT
                old_instance = EmployeeCoreAssessment.objects.get(pk=self.pk)
                if old_instance.status == 'COMPLETED' and self.status == 'DRAFT':
                    logger.info(f"Core assessment {self.pk} reopened for editing")
            except EmployeeCoreAssessment.DoesNotExist:
                # This shouldn't happen, but if it does, just continue
                pass
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.employee.full_name} - Core Assessment ({self.assessment_date})"


class EmployeeCoreCompetencyRating(models.Model):
    """Individual competency rating within employee assessment"""
    assessment = models.ForeignKey(
        EmployeeCoreAssessment,
        on_delete=models.CASCADE,
        related_name='competency_ratings'
    )
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE)
    required_level = models.IntegerField(validators=[MinValueValidator(0), MaxValueValidator(10)])
    actual_level = models.IntegerField(validators=[MinValueValidator(0), MaxValueValidator(10)])
    gap = models.IntegerField(default=0, help_text="Actual - Required")
    notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    def save(self, *args, **kwargs):
        self.gap = self.actual_level - self.required_level
        super().save(*args, **kwargs)
    
    class Meta:
        db_table = 'employee_core_ratings'
        unique_together = ['assessment', 'skill']
    
    def __str__(self):
        return f"{self.assessment.employee.full_name} - {self.skill.name}: {self.actual_level}/{self.required_level}"


class EmployeeBehavioralAssessment(models.Model):
    """Employee Behavioral Competency Assessment"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Assessment details
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='behavioral_assessments')
    position_assessment = models.ForeignKey(PositionBehavioralAssessment, on_delete=models.CASCADE)
    assessment_date = models.DateField(default=timezone.now)
    
    # Status with proper choices
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('COMPLETED', 'Completed'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    
    # Assessment metadata
    assessed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    notes = models.TextField(blank=True)
    
    # Calculated scores by group
    group_scores = models.JSONField(
        default=dict,
        help_text="Scores by competency group: {group_name: {position_total, employee_total, percentage, letter_grade}}"
    )
    
    # Overall score
    overall_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    overall_letter_grade = models.CharField(max_length=10, default='N/A')
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'employee_behavioral_assessments'
        ordering = ['-created_at']
    
    def calculate_scores(self):
        """Calculate behavioral assessment scores by group"""
        from django.db.models import Sum
        from collections import defaultdict
        
        ratings = self.competency_ratings.select_related('behavioral_competency__group').all()
        
        # Group ratings by competency group
        group_data = defaultdict(lambda: {'position_total': 0, 'employee_total': 0, 'count': 0})
        
        for rating in ratings:
            group_name = rating.behavioral_competency.group.name
            group_data[group_name]['position_total'] += rating.required_level
            group_data[group_name]['employee_total'] += rating.actual_level
            group_data[group_name]['count'] += 1
        
        # Calculate percentages and letter grades
        group_scores = {}
        total_percentage = 0
        group_count = len(group_data)
        
        for group_name, data in group_data.items():
            if data['position_total'] > 0:
                percentage = (data['employee_total'] / data['position_total']) * 100
            else:
                percentage = 0
            
            letter_grade = LetterGradeMapping.get_letter_grade(percentage)
            
            group_scores[group_name] = {
                'position_total': data['position_total'],
                'employee_total': data['employee_total'],
                'percentage': round(percentage, 2),
                'letter_grade': letter_grade
            }
            
            total_percentage += percentage
        
        # Calculate overall scores
        if group_count > 0:
            self.overall_percentage = round(total_percentage / group_count, 2)
        else:
            self.overall_percentage = 0
        
        self.overall_letter_grade = LetterGradeMapping.get_letter_grade(self.overall_percentage)
        self.group_scores = group_scores
        
        self.save()
    
    def can_edit(self):
        """Check if assessment can be edited"""
        return self.status == 'DRAFT'
    
    def save(self, *args, **kwargs):
        """Override save to handle status transitions"""
        # Only check for old instance if this is an update (not a create)
        if self.pk:
            try:
                # Check if status is changing from COMPLETED to DRAFT
                old_instance = EmployeeBehavioralAssessment.objects.get(pk=self.pk)
                if old_instance.status == 'COMPLETED' and self.status == 'DRAFT':
                    logger.info(f"Behavioral assessment {self.pk} reopened for editing")
            except EmployeeBehavioralAssessment.DoesNotExist:
                # This shouldn't happen, but if it does, just continue
                pass
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.employee.full_name} - Behavioral Assessment ({self.assessment_date})"


# Core Assessment model-də də eyni problem ola bilər, onu da düzəltək:

class EmployeeBehavioralCompetencyRating(models.Model):
    """Individual behavioral competency rating within employee assessment"""
    assessment = models.ForeignKey(
        EmployeeBehavioralAssessment,
        on_delete=models.CASCADE,
        related_name='competency_ratings'
    )
    behavioral_competency = models.ForeignKey(BehavioralCompetency, on_delete=models.CASCADE)
    required_level = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(10)])
    actual_level = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(10)])
    notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'employee_behavioral_ratings'
        unique_together = ['assessment', 'behavioral_competency']
    
    def __str__(self):
        return f"{self.assessment.employee.full_name} - {self.behavioral_competency.name}: {self.actual_level}/{self.required_level}"