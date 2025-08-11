# api/competency_models.py

from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

class SkillGroup(models.Model):
    name = models.CharField(max_length=200, unique=True)
  
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        ordering = ['name']
        db_table = 'competency_skill_groups'
        
    def __str__(self):
        return self.name
    
    @property
    def skills_count(self):
        return self.skills.count()

class Skill(models.Model):
    group = models.ForeignKey(SkillGroup, on_delete=models.CASCADE, related_name='skills')
    name = models.CharField(max_length=200)
   
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        ordering = ['name']
        unique_together = ['group', 'name']
        db_table = 'competency_skills'
        
    def __str__(self):
        return f"{self.group.name} - {self.name}"

class BehavioralCompetencyGroup(models.Model):
    name = models.CharField(max_length=200, unique=True)
   
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        ordering = ['name']
        db_table = 'competency_behavioral_groups'
        
    def __str__(self):
        return self.name
    
    @property
    def competencies_count(self):
        return self.competencies.count()

class BehavioralCompetency(models.Model):
    group = models.ForeignKey(BehavioralCompetencyGroup, on_delete=models.CASCADE, related_name='competencies')
    name = models.CharField(max_length=200)
 
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        ordering = ['name']
        unique_together = ['group', 'name']
        db_table = 'competency_behavioral'
        
    def __str__(self):
        return f"{self.group.name} - {self.name}"
