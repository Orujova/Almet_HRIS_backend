# api/competency_admin.py

from django.contrib import admin
from .competency_models import (
    SkillGroup, Skill, BehavioralCompetencyGroup, 
    BehavioralCompetency
)

class SkillInline(admin.TabularInline):
    model = Skill
    extra = 0
    fields = ['name', 'description']

@admin.register(SkillGroup)
class SkillGroupAdmin(admin.ModelAdmin):
    list_display = ['name', 'skills_count', 'created_at', 'created_by']
    search_fields = ['name', 'description']
    list_filter = ['created_at']
    inlines = [SkillInline]
    readonly_fields = ['created_at', 'updated_at']

@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = ['name', 'group', 'created_at', 'created_by']
    list_filter = ['group', 'created_at']
    search_fields = ['name', 'description', 'group__name']
    readonly_fields = ['created_at', 'updated_at']

class BehavioralCompetencyInline(admin.TabularInline):
    model = BehavioralCompetency
    extra = 0
    fields = ['name', 'description']

@admin.register(BehavioralCompetencyGroup)
class BehavioralCompetencyGroupAdmin(admin.ModelAdmin):
    list_display = ['name', 'competencies_count', 'created_at', 'created_by']
    search_fields = ['name', 'description']
    list_filter = ['created_at']
    inlines = [BehavioralCompetencyInline]
    readonly_fields = ['created_at', 'updated_at']

@admin.register(BehavioralCompetency)
class BehavioralCompetencyAdmin(admin.ModelAdmin):
    list_display = ['name', 'group', 'created_at', 'created_by']
    list_filter = ['group', 'created_at']
    search_fields = ['name', 'description', 'group__name']
    readonly_fields = ['created_at', 'updated_at']

