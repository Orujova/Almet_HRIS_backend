# grading/models.py

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth.models import User
from django.utils import timezone
from django.contrib.postgres.fields import JSONField  # PostgreSQL specific
from django.contrib.postgres.indexes import GinIndex  # For JSON indexing
from api.models import PositionGroup
import uuid

class GradingSystem(models.Model):
    """Main grading system configuration"""
    name = models.CharField(max_length=100, unique=True, db_index=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    base_currency = models.CharField(max_length=3, default='AZN')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Grading System"
        verbose_name_plural = "Grading Systems"
        ordering = ['name']
        indexes = [
            models.Index(fields=['is_active', 'created_at']),
        ]

class SalaryGrade(models.Model):
    """Salary grade structure for each position group"""
    grading_system = models.ForeignKey(GradingSystem, on_delete=models.CASCADE, related_name='salary_grades')
    position_group = models.ForeignKey(PositionGroup, on_delete=models.CASCADE, related_name='salary_grades')
    
    # Grade range values (5 columns) - Using NUMERIC for precision
    lower_decile = models.DecimalField(max_digits=15, decimal_places=2, help_text="LD - Lower Decile")
    lower_quartile = models.DecimalField(max_digits=15, decimal_places=2, help_text="LQ - Lower Quartile") 
    median = models.DecimalField(max_digits=15, decimal_places=2, help_text="M - Median")
    upper_quartile = models.DecimalField(max_digits=15, decimal_places=2, help_text="UQ - Upper Quartile")
    upper_decile = models.DecimalField(max_digits=15, decimal_places=2, help_text="UD - Upper Decile")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.grading_system.name} - {self.position_group.get_name_display()}"

    class Meta:
        unique_together = ['grading_system', 'position_group']
        ordering = ['position_group__hierarchy_level']
        indexes = [
            models.Index(fields=['grading_system', 'position_group']),
        ]

class GrowthRate(models.Model):
    """Growth rates for vertical calculations (level to level)"""
    grading_system = models.ForeignKey(GradingSystem, on_delete=models.CASCADE, related_name='growth_rates')
    
    # Vertical growth rates (level to level)
    from_position = models.ForeignKey(PositionGroup, on_delete=models.CASCADE, related_name='vertical_growth_from')
    to_position = models.ForeignKey(PositionGroup, on_delete=models.CASCADE, related_name='vertical_growth_to')
    vertical_rate = models.DecimalField(max_digits=8, decimal_places=4, help_text="Vertical growth rate as percentage")
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.from_position.get_name_display()} → {self.to_position.get_name_display()}: {self.vertical_rate}%"

    class Meta:
        unique_together = ['grading_system', 'from_position', 'to_position']
        ordering = ['from_position__hierarchy_level']
        indexes = [
            models.Index(fields=['grading_system', 'from_position']),
        ]

class HorizontalRate(models.Model):
    """Horizontal growth rates (grade to grade within same level)"""
    GRADE_TRANSITIONS = [
        ('LD_TO_LQ', 'LD to LQ'),
        ('LQ_TO_M', 'LQ to Median'), 
        ('M_TO_UQ', 'Median to UQ'),
        ('UQ_TO_UD', 'UQ to UD'),
    ]
    
    grading_system = models.ForeignKey(GradingSystem, on_delete=models.CASCADE, related_name='horizontal_rates')
    position_group = models.ForeignKey(PositionGroup, on_delete=models.CASCADE, related_name='horizontal_rates')
    transition_type = models.CharField(max_length=10, choices=GRADE_TRANSITIONS, db_index=True)
    horizontal_rate = models.DecimalField(max_digits=8, decimal_places=4, help_text="Horizontal growth rate as percentage")
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.position_group.get_name_display()} - {self.get_transition_type_display()}: {self.horizontal_rate}%"

    class Meta:
        unique_together = ['grading_system', 'position_group', 'transition_type']
        ordering = ['position_group__hierarchy_level', 'transition_type']
        indexes = [
            models.Index(fields=['grading_system', 'position_group', 'transition_type']),
        ]

class SalaryScenario(models.Model):
    """Salary scenarios for testing different configurations"""
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('CURRENT', 'Current'),
        ('ARCHIVED', 'Archived'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    grading_system = models.ForeignKey(GradingSystem, on_delete=models.CASCADE, related_name='scenarios')
    name = models.CharField(max_length=100, db_index=True)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='DRAFT', db_index=True)
    
    # Base configuration
    base_position = models.ForeignKey(PositionGroup, on_delete=models.CASCADE, help_text="Starting position (lowest)")
    base_value = models.DecimalField(max_digits=15, decimal_places=2, help_text="Base minimum value")
    
    # Custom growth rates for this scenario - Using PostgreSQL JSONField
    custom_vertical_rates = models.JSONField(default=dict, help_text="Custom vertical rates: {from_pos_id: rate}")
    custom_horizontal_rates = models.JSONField(default=dict, help_text="Custom horizontal rates: {pos_id: {transition: rate}}")
    
    # Calculated results - Using PostgreSQL JSONField with GIN index
    calculated_grades = models.JSONField(default=dict, help_text="Calculated salary grades")
    calculation_timestamp = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    applied_at = models.DateTimeField(null=True, blank=True)
    applied_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='applied_scenarios')

    def __str__(self):
        return f"{self.name} ({self.get_status_display()})"

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['grading_system', 'status']),
            models.Index(fields=['status', 'created_at']),
            # GIN index for JSON fields (PostgreSQL specific)
            GinIndex(fields=['calculated_grades']),
            GinIndex(fields=['custom_vertical_rates']),
            GinIndex(fields=['custom_horizontal_rates']),
        ]

class ScenarioHistory(models.Model):
    """History of scenario applications"""
    scenario = models.ForeignKey(SalaryScenario, on_delete=models.CASCADE, related_name='history')
    action = models.CharField(max_length=30, db_index=True)  # CREATED, CALCULATED, APPLIED, ARCHIVED
    previous_current_scenario = models.ForeignKey(SalaryScenario, on_delete=models.SET_NULL, null=True, blank=True)
    changes_made = models.JSONField(default=dict)  # PostgreSQL JSONField
    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    def __str__(self):
        return f"{self.scenario.name} - {self.action}"

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['scenario', 'timestamp']),
            models.Index(fields=['action', 'timestamp']),
            # GIN index for JSON field
            GinIndex(fields=['changes_made']),
        ]