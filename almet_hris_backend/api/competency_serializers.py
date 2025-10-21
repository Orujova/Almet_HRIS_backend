# api/competency_serializers.py

from rest_framework import serializers
from django.contrib.auth.models import User
from .competency_models import (
    SkillGroup, Skill, BehavioralCompetencyGroup, 
    BehavioralCompetency
    
)

class SkillSerializer(serializers.ModelSerializer):
    class Meta:
        model = Skill
        fields = ['id', 'name',  'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']

class SkillCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Skill
        fields = ['group', 'name', ]

class SkillGroupSerializer(serializers.ModelSerializer):
    skills = SkillSerializer(many=True, read_only=True)
    skills_count = serializers.ReadOnlyField()
    
    class Meta:
        model = SkillGroup
        fields = ['id', 'name',  'skills', 'skills_count', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']

class SkillGroupListSerializer(serializers.ModelSerializer):
    skills_count = serializers.ReadOnlyField()
    
    class Meta:
        model = SkillGroup
        fields = ['id', 'name', 'skills_count', 'created_at', 'updated_at']

class BehavioralCompetencySerializer(serializers.ModelSerializer):
    class Meta:
        model = BehavioralCompetency
        fields = ['id', 'name',  'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']

class BehavioralCompetencyCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = BehavioralCompetency
        fields = ['group', 'name',]

class BehavioralCompetencyGroupSerializer(serializers.ModelSerializer):
    competencies = BehavioralCompetencySerializer(many=True, read_only=True)
    competencies_count = serializers.ReadOnlyField()
    
    class Meta:
        model = BehavioralCompetencyGroup
        fields = ['id', 'name',  'competencies', 'competencies_count', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']

class BehavioralCompetencyGroupListSerializer(serializers.ModelSerializer):
    competencies_count = serializers.ReadOnlyField()
    
    class Meta:
        model = BehavioralCompetencyGroup
        fields = ['id', 'name',  'competencies_count', 'created_at', 'updated_at']




# Stats üçün serializer
class CompetencyStatsSerializer(serializers.Serializer):
    total_skill_groups = serializers.IntegerField()
    total_skills = serializers.IntegerField()
    total_behavioral_groups = serializers.IntegerField()
    total_behavioral_competencies = serializers.IntegerField()
