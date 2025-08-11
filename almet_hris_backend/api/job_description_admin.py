# api/job_description_admin.py

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .job_description_models import (
    JobDescription, JobDescriptionSection, JobDescriptionSkill,
    JobDescriptionBehavioralCompetency, JobBusinessResource, AccessMatrix,
    CompanyBenefit, JobDescriptionBusinessResource, JobDescriptionAccessMatrix,
    JobDescriptionCompanyBenefit, JobDescriptionActivity
)


class JobDescriptionSectionInline(admin.TabularInline):
    model = JobDescriptionSection
    extra = 1
    fields = ['section_type', 'title', 'content', 'order']
    ordering = ['order']


class JobDescriptionSkillInline(admin.TabularInline):
    model = JobDescriptionSkill
    extra = 1
    fields = ['skill', 'proficiency_level', 'is_mandatory']
    autocomplete_fields = ['skill']


class JobDescriptionBehavioralCompetencyInline(admin.TabularInline):
    model = JobDescriptionBehavioralCompetency
    extra = 1
    fields = ['competency', 'proficiency_level', 'is_mandatory']
    autocomplete_fields = ['competency']


class JobDescriptionBusinessResourceInline(admin.TabularInline):
    model = JobDescriptionBusinessResource
    extra = 1
    fields = ['resource']
    autocomplete_fields = ['resource']


class JobDescriptionAccessMatrixInline(admin.TabularInline):
    model = JobDescriptionAccessMatrix
    extra = 1
    fields = ['access_matrix']
    autocomplete_fields = ['access_matrix']


class JobDescriptionCompanyBenefitInline(admin.TabularInline):
    model = JobDescriptionCompanyBenefit
    extra = 1
    fields = ['benefit']
    autocomplete_fields = ['benefit']


@admin.register(JobDescription)
class JobDescriptionAdmin(admin.ModelAdmin):
    list_display = [
        'job_title', 'department', 'business_function', 'position_group',
        'status_badge', 'reports_to', 'version', 'is_active', 'created_at'
    ]
    list_filter = [
        'status', 'business_function', 'department', 'position_group',
        'is_active', 'created_at', 'line_manager_approved_at', 'employee_approved_at'
    ]
    search_fields = [
        'job_title', 'job_purpose', 'business_function__name',
        'department__name', 'reports_to__full_name'
    ]
    autocomplete_fields = [
        'business_function', 'department', 'unit', 'position_group',
        'reports_to', 'created_by', 'updated_by'
    ]
    readonly_fields = [
        'id', 'created_at', 'updated_at', 'line_manager_approved_at',
        'employee_approved_at', 'version', 'approval_workflow_display'
    ]
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'job_title', 'job_purpose', 'business_function', 'department',
                'unit', 'position_group', 'grading_level', 'reports_to'
            )
        }),
        ('Status & Approval', {
            'fields': (
                'status', 'approval_workflow_display', 'version', 'is_active'
            )
        }),
        ('Line Manager Approval', {
            'fields': (
                'line_manager_approved_by', 'line_manager_approved_at',
                'line_manager_comments', 'line_manager_signature'
            ),
            'classes': ['collapse']
        }),
        ('Employee Approval', {
            'fields': (
                'employee_approved_by', 'employee_approved_at',
                'employee_comments', 'employee_signature'
            ),
            'classes': ['collapse']
        }),
        ('Metadata', {
            'fields': (
                'id', 'created_by', 'created_at', 'updated_by', 'updated_at'
            ),
            'classes': ['collapse']
        })
    )
    
    inlines = [
        JobDescriptionSectionInline,
        JobDescriptionSkillInline,
        JobDescriptionBehavioralCompetencyInline,
        JobDescriptionBusinessResourceInline,
        JobDescriptionAccessMatrixInline,
        JobDescriptionCompanyBenefitInline
    ]
    
    actions = ['submit_for_approval', 'activate_job_descriptions', 'deactivate_job_descriptions']
    
    def status_badge(self, obj):
        status_colors = {
            'DRAFT': '#6B7280',
            'PENDING_LINE_MANAGER': '#F59E0B',
            'PENDING_EMPLOYEE': '#3B82F6',
            'APPROVED': '#10B981',
            'REJECTED': '#EF4444',
            'REVISION_REQUIRED': '#8B5CF6',
        }
        color = status_colors.get(obj.status, '#6B7280')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; border-radius: 4px; font-size: 12px;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def approval_workflow_display(self, obj):
        html = '<div style="line-height: 1.5;">'
        
        # Line Manager Approval
        if obj.line_manager_approved_at:
            html += f'<div>✅ <strong>Line Manager:</strong> {obj.line_manager_approved_by.get_full_name()} ({obj.line_manager_approved_at.strftime("%Y-%m-%d %H:%M")})</div>'
        else:
            html += '<div>⏳ <strong>Line Manager:</strong> Pending</div>'
        
        # Employee Approval
        if obj.employee_approved_at:
            html += f'<div>✅ <strong>Employee:</strong> {obj.employee_approved_by.get_full_name()} ({obj.employee_approved_at.strftime("%Y-%m-%d %H:%M")})</div>'
        else:
            html += '<div>⏳ <strong>Employee:</strong> Pending</div>'
        
        html += '</div>'
        return mark_safe(html)
    approval_workflow_display.short_description = 'Approval Workflow'
    
    def submit_for_approval(self, request, queryset):
        count = 0
        for obj in queryset:
            if obj.status == 'DRAFT':
                obj.status = 'PENDING_LINE_MANAGER'
                obj.save()
                count += 1
        
        self.message_user(
            request,
            f'{count} job description(s) submitted for approval.'
        )
    submit_for_approval.short_description = 'Submit selected job descriptions for approval'
    
    def activate_job_descriptions(self, request, queryset):
        count = queryset.update(is_active=True)
        self.message_user(
            request,
            f'{count} job description(s) activated.'
        )
    activate_job_descriptions.short_description = 'Activate selected job descriptions'
    
    def deactivate_job_descriptions(self, request, queryset):
        count = queryset.update(is_active=False)
        self.message_user(
            request,
            f'{count} job description(s) deactivated.'
        )
    deactivate_job_descriptions.short_description = 'Deactivate selected job descriptions'


@admin.register(JobDescriptionSection)
class JobDescriptionSectionAdmin(admin.ModelAdmin):
    list_display = ['job_description', 'section_type', 'title', 'order']
    list_filter = ['section_type', 'job_description__business_function']
    search_fields = ['title', 'content', 'job_description__job_title']
    autocomplete_fields = ['job_description']
    ordering = ['job_description', 'order']


@admin.register(JobDescriptionActivity)
class JobDescriptionActivityAdmin(admin.ModelAdmin):
    list_display = [
        'job_description', 'activity_type', 'performed_by',
        'performed_at', 'short_description'
    ]
    list_filter = [
        'activity_type', 'performed_at', 'job_description__business_function'
    ]
    search_fields = [
        'job_description__job_title', 'description', 'performed_by__username'
    ]
    autocomplete_fields = ['job_description', 'performed_by']
    readonly_fields = ['performed_at', 'metadata']
    date_hierarchy = 'performed_at'
    
    def short_description(self, obj):
        return obj.description[:100] + '...' if len(obj.description) > 100 else obj.description
    short_description.short_description = 'Description'


@admin.register(JobBusinessResource)
class JobBusinessResourceAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'is_active', 'created_at', 'created_by']
    list_filter = ['category', 'is_active', 'created_at']
    search_fields = ['name', 'description', 'category']
    autocomplete_fields = ['created_by']
    readonly_fields = ['created_at']
    
    fieldsets = (
        (None, {
            'fields': ('name', 'description', 'access_level', 'is_active')
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at'),
            'classes': ['collapse']
        })
    )


@admin.register(CompanyBenefit)
class CompanyBenefitAdmin(admin.ModelAdmin):
    list_display = ['name', 'benefit_type', 'is_active', 'created_at', 'created_by']
    list_filter = ['benefit_type', 'is_active', 'created_at']
    search_fields = ['name', 'description', 'benefit_type']
    autocomplete_fields = ['created_by']
    readonly_fields = ['created_at']
    
    fieldsets = (
        (None, {
            'fields': ('name', 'description', 'benefit_type', 'is_active')
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at'),
            'classes': ['collapse']
        })
    )


# Register junction table models for direct editing if needed
@admin.register(JobDescriptionSkill)
class JobDescriptionSkillAdmin(admin.ModelAdmin):
    list_display = ['job_description', 'skill', 'proficiency_level', 'is_mandatory']
    list_filter = ['proficiency_level', 'is_mandatory', 'skill__group']
    search_fields = ['job_description__job_title', 'skill__name']
    autocomplete_fields = ['job_description', 'skill']


@admin.register(JobDescriptionBehavioralCompetency)
class JobDescriptionBehavioralCompetencyAdmin(admin.ModelAdmin):
    list_display = ['job_description', 'competency', 'proficiency_level', 'is_mandatory']
    list_filter = ['proficiency_level', 'is_mandatory', 'competency__group']
    search_fields = ['job_description__job_title', 'competency__name']
    autocomplete_fields = ['job_description', 'competency']


# Custom admin site configuration
admin.site.site_header = "ALMET HRIS - Job Description Management"
admin.site.site_title = "Job Description Admin"
admin.site.index_title = "Job Description Administration", {
            'fields': ('name', 'description', 'category', 'is_active')
}


@admin.register(AccessMatrix)
class AccessMatrixAdmin(admin.ModelAdmin):
    list_display = ['name', 'access_level', 'is_active', 'created_at', 'created_by']
    list_filter = ['access_level', 'is_active', 'created_at']
    search_fields = ['name', 'description', 'access_level']
    autocomplete_fields = ['created_by']
    readonly_fields = ['created_at']
    
    fieldsets = (
        (None, {
            'fields': ('name', 'description', 'access_level', 'is_active')
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at'),
            'classes': ['collapse']
        }))