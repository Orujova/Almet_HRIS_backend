# api/job_description_admin.py - UPDATED: Smart employee selection based on organizational hierarchy

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db import models
from django.forms import ModelChoiceField
from .job_description_models import (
    JobDescription, JobDescriptionSection, JobDescriptionSkill,
    JobDescriptionBehavioralCompetency, JobBusinessResource, AccessMatrix,
    CompanyBenefit, JobDescriptionBusinessResource, JobDescriptionAccessMatrix,
    JobDescriptionCompanyBenefit, JobDescriptionActivity
)
from .models import Employee


class SmartEmployeeChoiceField(ModelChoiceField):
    """Custom field that filters employees based on organizational criteria"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Start with all active employees
        self.queryset = Employee.objects.filter(is_deleted=False).select_related(  # CHANGE: is_active=True -> is_deleted=False
            'business_function', 'department', 'unit', 'job_function', 
            'position_group', 'line_manager'
        )
    
    def label_from_instance(self, obj):
        """Enhanced label showing organizational info"""
        parts = [f"{obj.full_name} ({obj.employee_id})"]
        
        if obj.business_function:
            parts.append(obj.business_function.name)
        if obj.department:
            parts.append(obj.department.name)
        if obj.job_function:
            parts.append(obj.job_function.name)
        if obj.position_group:
            parts.append(f"Grade: {obj.grading_level}")
        
        return f"{parts[0]} - {' | '.join(parts[1:])}"


class JobDescriptionAdminForm(models.forms.ModelForm):
    """Custom form with smart employee selection"""
    
    assigned_employee = SmartEmployeeChoiceField(
        queryset=Employee.objects.none(),  # Will be populated dynamically
        required=True,
        help_text="Select employee based on organizational criteria. Manager will be auto-assigned."
    )
    
    class Meta:
        model = JobDescription
        fields = '__all__'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Get initial organizational criteria
        business_function = self.data.get('business_function') or (
            self.instance.business_function.id if self.instance.pk and self.instance.business_function else None
        )
        department = self.data.get('department') or (
            self.instance.department.id if self.instance.pk and self.instance.department else None
        )
        unit = self.data.get('unit') or (
            self.instance.unit.id if self.instance.pk and self.instance.unit else None
        )
        job_function = self.data.get('job_function') or (
            self.instance.job_function.id if self.instance.pk and self.instance.job_function else None
        )
        position_group = self.data.get('position_group') or (
            self.instance.position_group.id if self.instance.pk and self.instance.position_group else None
        )
        grading_level = self.data.get('grading_level') or (
            self.instance.grading_level if self.instance.pk else None
        )
        
        # Filter employees based on criteria
        eligible_employees = JobDescription.get_eligible_employees(
            business_function_id=business_function,
            department_id=department,
            unit_id=unit,
            job_function_id=job_function,
            position_group_id=position_group,
            grading_level=grading_level
        )
        
        if eligible_employees.exists():
            self.fields['assigned_employee'].queryset = eligible_employees
            self.fields['assigned_employee'].help_text = f"Showing {eligible_employees.count()} eligible employees based on organizational criteria"
        else:
            # If no eligible employees found, show all active employees
            self.fields['assigned_employee'].queryset = Employee.objects.filter(is_deleted=False).select_related(
                'business_function', 'department', 'unit', 'job_function', 'position_group'
            )
            self.fields['assigned_employee'].help_text = "No employees match exact criteria. Showing all active employees."
        
        # Make reports_to read-only since it's auto-assigned
        self.fields['reports_to'].widget.attrs['readonly'] = True
        self.fields['reports_to'].help_text = "This field is automatically populated based on the selected employee's line manager"
    
    def clean_assigned_employee(self):
        """Validate employee selection"""
        employee = self.cleaned_data.get('assigned_employee')
        if not employee:
            raise models.forms.ValidationError("Employee selection is required")
        
        if employee.is_deleted:  # CHANGE: not employee.is_active -> employee.is_deleted
            raise models.forms.ValidationError("Selected employee is deleted/inactive")
        
        return employee
    
    class Media:
        js = ('admin/js/job_description_smart_employee.js',)  # Add custom JS for dynamic filtering


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
    form = JobDescriptionAdminForm
    
    list_display = [
        'job_title', 'assigned_employee_info', 'department', 'business_function', 'position_group',
        'status_badge', 'reports_to_info', 'version',  'created_at'
    ]
    list_filter = [
        'status', 'business_function', 'department', 'position_group',
       'created_at', 'line_manager_approved_at', 'employee_approved_at'
    ]
    search_fields = [
        'job_title', 'job_purpose', 'business_function__name',
        'department__name', 'assigned_employee__full_name', 
        'assigned_employee__employee_id', 'reports_to__full_name'
    ]
    autocomplete_fields = [
        'business_function', 'department', 'unit', 'position_group',
        'job_function', 'created_by', 'updated_by'
    ]
    readonly_fields = [
        'id', 'created_at', 'updated_at', 'line_manager_approved_at',
        'employee_approved_at', 'version', 'approval_workflow_display',
        'reports_to'  # Auto-assigned field
    ]
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'job_title', 'job_purpose', 'business_function', 'department',
                'unit', 'job_function', 'position_group', 'grading_level'
            )
        }),
        ('Employee Assignment', {
            'fields': (
                'assigned_employee', 'reports_to'
            ),
            'description': 'Select employee based on organizational criteria. Manager is auto-assigned.'
        }),
        ('Status & Approval', {
            'fields': (
                'status', 'approval_workflow_display', 'version', 
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
    
    def assigned_employee_info(self, obj):
        """Display employee info with organizational details"""
        if obj.assigned_employee:
            employee = obj.assigned_employee
            info_parts = [f"<strong>{employee.full_name}</strong> ({employee.employee_id})"]
            
            if employee.job_function:
                info_parts.append(f"Function: {employee.job_function.name}")
            if employee.grading_level:
                info_parts.append(f"Grade: {employee.grading_level}")
            
            return format_html('<br>'.join(info_parts))
        return "No Employee Assigned"
    assigned_employee_info.short_description = 'Assigned Employee'
    
    def reports_to_info(self, obj):
        """Display manager info"""
        if obj.reports_to:
            manager = obj.reports_to
            return format_html(
                '<strong>{}</strong><br>{}',
                manager.full_name,
                manager.job_title or 'No Title'
            )
        return "No Manager"
    reports_to_info.short_description = 'Reports To'
    
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
        errors = []
        
        for obj in queryset:
            try:
                if obj.status == 'DRAFT':
                    if not obj.assigned_employee:
                        errors.append(f"{obj.job_title}: No employee assigned")
                        continue
                    if not obj.reports_to:
                        errors.append(f"{obj.job_title}: No manager assigned (check employee's line manager)")
                        continue
                    
                    obj.status = 'PENDING_LINE_MANAGER'
                    obj.save()
                    count += 1
            except Exception as e:
                errors.append(f"{obj.job_title}: {str(e)}")
        
        if count > 0:
            self.message_user(
                request,
                f'{count} job description(s) submitted for approval.'
            )
        
        if errors:
            self.message_user(
                request,
                f'Errors: {"; ".join(errors)}',
                level='ERROR'
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
    
    def save_model(self, request, obj, form, change):
        """Override save to handle creation/update metadata"""
        if not change:  # Creating
            obj.created_by = request.user
        else:  # Updating
            obj.updated_by = request.user
        
        super().save_model(request, obj, form, change)


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
    list_display = ['name', 'is_active', 'created_at', 'created_by']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'description']
    autocomplete_fields = ['created_by']
    readonly_fields = ['created_at']
    
    fieldsets = (
        (None, {
            'fields': ('name', 'description', 'is_active')
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at'),
            'classes': ['collapse']
        })
    )


@admin.register(CompanyBenefit)
class CompanyBenefitAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active', 'created_at', 'created_by']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'description']
    autocomplete_fields = ['created_by']
    readonly_fields = ['created_at']
    
    fieldsets = (
        (None, {
            'fields': ('name', 'description', 'is_active')
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at'),
            'classes': ['collapse']
        })
    )


@admin.register(AccessMatrix)
class AccessMatrixAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active', 'created_at', 'created_by']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'description']
    autocomplete_fields = ['created_by']
    readonly_fields = ['created_at']
    
    fieldsets = (
        (None, {
            'fields': ('name', 'description', 'is_active')
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at'),
            'classes': ['collapse']
        })
    )


# Register junction table models for direct editing if needed
@admin.register(JobDescriptionSkill)
class JobDescriptionSkillAdmin(admin.ModelAdmin):
    list_display = ['job_description', 'skill']
    list_filter = [ 'skill__group']
    search_fields = ['job_description__job_title', 'skill__name']
    autocomplete_fields = ['job_description', 'skill']


@admin.register(JobDescriptionBehavioralCompetency)
class JobDescriptionBehavioralCompetencyAdmin(admin.ModelAdmin):
    list_display = ['job_description', 'competency']
    list_filter = [ 'competency__group']
    search_fields = ['job_description__job_title', 'competency__name']
    autocomplete_fields = ['job_description', 'competency']


# Custom admin site configuration
admin.site.site_header = "ALMET HRIS - Job Description Management"
admin.site.site_title = "Job Description Admin"
admin.site.index_title = "Job Description Administration"