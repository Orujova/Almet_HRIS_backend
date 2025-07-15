# api/admin.py - ENHANCED: Complete Django Admin with Contract Status Management

from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from django.urls import reverse
from django.db.models import Count, Q
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from django.http import HttpResponse
from django.shortcuts import redirect
from django.contrib import messages
from datetime import date, timedelta
import csv

from .models import (
    MicrosoftUser, Employee, BusinessFunction, Department, Unit, 
    JobFunction, PositionGroup, EmployeeTag, EmployeeStatus, 
    EmployeeDocument, EmployeeActivity, VacantPosition,
    ContractTypeConfig, ContractStatusManager
)

class BaseModelAdmin(admin.ModelAdmin):
    """Base admin class with common styling"""
    from django.db import models
    from django.forms import TextInput, Textarea
    
    formfield_overrides = {
        models.CharField: {'widget': TextInput(attrs={'size': '40'})},
        models.TextField: {'widget': Textarea(attrs={'rows': 4, 'cols': 60})},
    }

class SoftDeleteAdminMixin:
    """Mixin to handle soft delete functionality in admin"""
    
    def get_queryset(self, request):
        # Show all objects including soft-deleted for admin
        if hasattr(self.model, 'all_objects'):
            return self.model.all_objects.get_queryset()
        return super().get_queryset(request)
    
    def delete_model(self, request, obj):
        """Override delete to use soft delete"""
        if hasattr(obj, 'soft_delete'):
            obj.soft_delete(user=request.user)
        else:
            super().delete_model(request, obj)
    
    def delete_queryset(self, request, queryset):
        """Override bulk delete to use soft delete"""
        for obj in queryset:
            if hasattr(obj, 'soft_delete'):
                obj.soft_delete(user=request.user)
            else:
                obj.delete()
    
    def get_actions(self, request):
        actions = super().get_actions(request)
        if hasattr(self.model, 'soft_delete'):
            actions['restore_selected'] = (self.restore_selected, 'restore_selected', 'Restore selected items')
        return actions
    
    def restore_selected(self, request, queryset):
        """Restore soft-deleted items"""
        count = 0
        for obj in queryset:
            if hasattr(obj, 'restore') and obj.is_deleted:
                obj.restore()
                count += 1
        
        self.message_user(request, f'Successfully restored {count} items.')
    restore_selected.short_description = "Restore selected soft-deleted items"

@admin.register(MicrosoftUser)
class MicrosoftUserAdmin(BaseModelAdmin):
    list_display = ('user', 'microsoft_id', 'user_email', 'token_status')
    search_fields = ('user__username', 'user__email', 'microsoft_id')
    readonly_fields = ('microsoft_id', 'token_expires')
    list_filter = ('token_expires',)
    
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'Email'
    
    def token_status(self, obj):
        if obj.token_expires:
            if obj.token_expires > timezone.now():
                return format_html('<span style="color: green;">✓ Valid</span>')
            else:
                return format_html('<span style="color: red;">✗ Expired</span>')
        return format_html('<span style="color: orange;">? Unknown</span>')
    token_status.short_description = 'Token Status'

admin.site.unregister(User)

@admin.register(User)
class EnhancedUserAdmin(UserAdmin):
    """Enhanced User admin with employee profile integration"""
    list_display = ('username', 'email', 'first_name', 'last_name', 'employee_profile_link', 'is_staff', 'date_joined')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'date_joined')
    search_fields = ('username', 'first_name', 'last_name', 'email')
    ordering = ('username',)
    
    def employee_profile_link(self, obj):
        """Link to employee profile if exists"""
        try:
            employee = obj.employee_profile
            url = reverse('admin:api_employee_change', args=[employee.id])
            return format_html(
                '<a href="{}" style="color: #417690;">View Profile</a>',
                url
            )
        except:
            return format_html('<span style="color: #999;">No Profile</span>')
    employee_profile_link.short_description = 'Employee Profile'

@admin.register(ContractTypeConfig)
class ContractTypeConfigAdmin(SoftDeleteAdminMixin, admin.ModelAdmin):
    list_display = (
        'contract_type', 'display_name', 'onboarding_days', 'probation_days', 
        'total_days_display', 'auto_transitions_display', 'notify_days_display', 
        'is_active', 'is_deleted_display'
    )
    list_filter = ('enable_auto_transitions', 'transition_to_inactive_on_end', 'is_active', 'is_deleted')
    search_fields = ('contract_type', 'display_name')
    ordering = ('contract_type',)
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('contract_type', 'display_name', 'is_active')
        }),
        ('Status Duration Configuration', {
            'fields': (
                ('onboarding_days', 'probation_days'),
            ),
            'description': 'Configure how long each status lasts for this contract type'
        }),
        ('Auto-Transition Settings', {
            'fields': (
                'enable_auto_transitions',
                'transition_to_inactive_on_end',
            )
        }),
        ('Notification Settings', {
            'fields': ('notify_days_before_end',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def is_deleted_display(self, obj):
        if obj.is_deleted:
            return format_html('<span style="color: red;">✗ Deleted</span>')
        return format_html('<span style="color: green;">✓ Active</span>')
    is_deleted_display.short_description = 'Status'
    
    def total_days_display(self, obj):
        total = obj.get_total_days_until_active()
        return format_html(
            '<span style="background: #e3f2fd; color: #1976d2; padding: 2px 6px; border-radius: 4px; font-size: 11px;">{} days</span>',
            total
        )
    total_days_display.short_description = 'Total Until Active'
    
    def auto_transitions_display(self, obj):
        if obj.enable_auto_transitions:
            return format_html('<span style="color: green;">✓ Enabled</span>')
        return format_html('<span style="color: red;">✗ Disabled</span>')
    auto_transitions_display.short_description = 'Auto Transitions'
    
    def notify_days_display(self, obj):
        if obj.notify_days_before_end > 0:
            return format_html(
                '<span style="color: #f57c00;">{} days before</span>',
                obj.notify_days_before_end
            )
        return format_html('<span style="color: #999;">No notifications</span>')
    notify_days_display.short_description = 'Notifications'
    
    actions = ['create_default_configs', 'test_status_calculations']
    
    def create_default_configs(self, request, queryset):
        """Create default contract configurations"""
        configs = ContractTypeConfig.get_or_create_defaults()
        created_count = len([c for c in configs.values() if c])
        self.message_user(
            request, 
            f'Successfully created/updated {created_count} default contract configurations.'
        )
    create_default_configs.short_description = 'Create default contract configurations'
    
    def test_status_calculations(self, request, queryset):
        """Test status calculations for selected contract types"""
        for config in queryset:
            # Get employees with this contract type
            employees = Employee.objects.filter(contract_duration=config.contract_type)[:5]
            results = []
            
            for employee in employees:
                preview = employee.get_status_preview()
                results.append(f"{employee.employee_id}: {preview['current_status']} → {preview['required_status']} ({preview['reason']})")
            
            if results:
                messages.info(request, f"Contract {config.contract_type} sample results: " + "; ".join(results[:3]))
    test_status_calculations.short_description = 'Test status calculations for selected contract types'

@admin.register(BusinessFunction)
class BusinessFunctionAdmin(SoftDeleteAdminMixin, admin.ModelAdmin):
    list_display = ('code', 'name', 'employee_count', 'department_count', 'is_active', 'is_deleted_display', 'created_at')
    list_filter = ('is_active', 'is_deleted', 'created_at')
    search_fields = ('name', 'code', 'description')
    ordering = ('code', 'name')
    readonly_fields = ('created_at', 'updated_at')
    
    def is_deleted_display(self, obj):
        if obj.is_deleted:
            return format_html('<span style="color: red;">✗ Deleted</span>')
        return format_html('<span style="color: green;">✓ Active</span>')
    is_deleted_display.short_description = 'Status'
    
    def employee_count(self, obj):
        count = obj.employees.filter(status__affects_headcount=True, is_deleted=False).count()
        if count > 0:
            url = reverse('admin:api_employee_changelist') + f'?business_function__id__exact={obj.id}'
            return format_html(
                '<a href="{}" style="color: #417690;">{} employees</a>',
                url, count
            )
        return '0 employees'
    employee_count.short_description = 'Active Employees'
    
    def department_count(self, obj):
        count = obj.departments.filter(is_active=True, is_deleted=False).count()
        if count > 0:
            url = reverse('admin:api_department_changelist') + f'?business_function__id__exact={obj.id}'
            return format_html(
                '<a href="{}" style="color: #417690;">{} departments</a>',
                url, count
            )
        return '0 departments'
    department_count.short_description = 'Departments'

@admin.register(Department)
class DepartmentAdmin(SoftDeleteAdminMixin, admin.ModelAdmin):
    list_display = ('name', 'business_function', 'head_display', 'employee_count', 'unit_count', 'is_active', 'is_deleted_display')
    list_filter = ('business_function', 'is_active', 'is_deleted', 'created_at')
    search_fields = ('name', 'business_function__name', 'business_function__code')
    autocomplete_fields = ['head_of_department']
    readonly_fields = ('created_at', 'updated_at')
    
    def is_deleted_display(self, obj):
        if obj.is_deleted:
            return format_html('<span style="color: red;">✗ Deleted</span>')
        return format_html('<span style="color: green;">✓ Active</span>')
    is_deleted_display.short_description = 'Status'
    
    def head_display(self, obj):
        if obj.head_of_department and not obj.head_of_department.is_deleted:
            url = reverse('admin:api_employee_change', args=[obj.head_of_department.id])
            return format_html(
                '<a href="{}" style="color: #417690;">{}</a>',
                url, obj.head_of_department.full_name
            )
        return format_html('<span style="color: #999;">No Head</span>')
    head_display.short_description = 'Department Head'
    
    def employee_count(self, obj):
        count = obj.employees.filter(status__affects_headcount=True, is_deleted=False).count()
        if count > 0:
            url = reverse('admin:api_employee_changelist') + f'?department__id__exact={obj.id}'
            return format_html(
                '<a href="{}" style="color: #417690;">{} employees</a>',
                url, count
            )
        return '0 employees'
    employee_count.short_description = 'Active Employees'
    
    def unit_count(self, obj):
        count = obj.units.filter(is_active=True, is_deleted=False).count()
        if count > 0:
            url = reverse('admin:api_unit_changelist') + f'?department__id__exact={obj.id}'
            return format_html(
                '<a href="{}" style="color: #417690;">{} units</a>',
                url, count
            )
        return '0 units'
    unit_count.short_description = 'Units'

@admin.register(Unit)
class UnitAdmin(SoftDeleteAdminMixin, admin.ModelAdmin):
    list_display = ('name', 'department', 'business_function_name', 'unit_head_display', 'employee_count', 'is_active', 'is_deleted_display')
    list_filter = ('department__business_function', 'department', 'is_active', 'is_deleted', 'created_at')
    search_fields = ('name', 'department__name', 'department__business_function__name')
    ordering = ('department__business_function__code', 'department__name', 'name')
    autocomplete_fields = ['unit_head']
    readonly_fields = ('created_at', 'updated_at')
    
    def is_deleted_display(self, obj):
        if obj.is_deleted:
            return format_html('<span style="color: red;">✗ Deleted</span>')
        return format_html('<span style="color: green;">✓ Active</span>')
    is_deleted_display.short_description = 'Status'
    
    def business_function_name(self, obj):
        return obj.department.business_function.name
    business_function_name.short_description = 'Business Function'
    
    def unit_head_display(self, obj):
        if obj.unit_head and not obj.unit_head.is_deleted:
            url = reverse('admin:api_employee_change', args=[obj.unit_head.id])
            return format_html(
                '<a href="{}" style="color: #417690;">{}</a>',
                url, obj.unit_head.full_name
            )
        return format_html('<span style="color: #999;">No Head</span>')
    unit_head_display.short_description = 'Unit Head'
    
    def employee_count(self, obj):
        count = obj.employees.filter(status__affects_headcount=True, is_deleted=False).count()
        if count > 0:
            url = reverse('admin:api_employee_changelist') + f'?unit__id__exact={obj.id}'
            return format_html(
                '<a href="{}" style="color: #417690;">{} employees</a>',
                url, count
            )
        return '0 employees'
    employee_count.short_description = 'Active Employees'

@admin.register(JobFunction)
class JobFunctionAdmin(SoftDeleteAdminMixin, admin.ModelAdmin):
    list_display = ('name', 'employee_count', 'is_active', 'is_deleted_display', 'created_at')
    list_filter = ('is_active', 'is_deleted', 'created_at')
    search_fields = ('name', 'description')
    ordering = ('name',)
    readonly_fields = ('created_at', 'updated_at')
    
    def is_deleted_display(self, obj):
        if obj.is_deleted:
            return format_html('<span style="color: red;">✗ Deleted</span>')
        return format_html('<span style="color: green;">✓ Active</span>')
    is_deleted_display.short_description = 'Status'
    
    def employee_count(self, obj):
        count = obj.employees.filter(status__affects_headcount=True, is_deleted=False).count()
        if count > 0:
            url = reverse('admin:api_employee_changelist') + f'?job_function__id__exact={obj.id}'
            return format_html(
                '<a href="{}" style="color: #417690;">{} employees</a>',
                url, count
            )
        return '0 employees'
    employee_count.short_description = 'Active Employees'

@admin.register(PositionGroup)
class PositionGroupAdmin(SoftDeleteAdminMixin, admin.ModelAdmin):
    list_display = ('hierarchy_display', 'name_display', 'grading_shorthand', 'employee_count', 'grading_levels_display', 'is_active', 'is_deleted_display')
    list_filter = ('is_active', 'is_deleted', 'created_at')
    search_fields = ('name',)
    ordering = ('hierarchy_level',)
    readonly_fields = ('grading_shorthand', 'created_at', 'updated_at')
    
    def is_deleted_display(self, obj):
        if obj.is_deleted:
            return format_html('<span style="color: red;">✗ Deleted</span>')
        return format_html('<span style="color: green;">✓ Active</span>')
    is_deleted_display.short_description = 'Status'
    
    def hierarchy_display(self, obj):
        colors = {1: '#8B0000', 2: '#DC143C', 3: '#FF6347', 4: '#FFA500', 
                 5: '#FFD700', 6: '#9ACD32', 7: '#32CD32', 8: '#808080'}
        color = colors.get(obj.hierarchy_level, '#6c757d')
        return format_html(
            '<span style="background: {}; color: white; padding: 4px 8px; border-radius: 12px; font-size: 12px; font-weight: bold;">Level {}</span>',
            color, obj.hierarchy_level
        )
    hierarchy_display.short_description = 'Hierarchy Level'
    hierarchy_display.admin_order_field = 'hierarchy_level'
    
    def name_display(self, obj):
        return obj.get_name_display()
    name_display.short_description = 'Position Name'
    name_display.admin_order_field = 'name'
    
    def grading_levels_display(self, obj):
        levels = obj.get_grading_levels()
        level_badges = []
        for level in levels:
            level_badges.append(
                f'<span style="background: #e3f2fd; color: #1976d2; padding: 2px 6px; border-radius: 4px; font-size: 10px; margin-right: 2px;">{level["code"]}</span>'
            )
        return format_html(''.join(level_badges))
    grading_levels_display.short_description = 'Grading Levels'
    
    def employee_count(self, obj):
        count = obj.employees.filter(status__affects_headcount=True, is_deleted=False).count()
        if count > 0:
            url = reverse('admin:api_employee_changelist') + f'?position_group__id__exact={obj.id}'
            return format_html(
                '<a href="{}" style="color: #417690;">{} employees</a>',
                url, count
            )
        return '0 employees'
    employee_count.short_description = 'Active Employees'

@admin.register(EmployeeTag)
class EmployeeTagAdmin(SoftDeleteAdminMixin, admin.ModelAdmin):
    list_display = ('name', 'tag_type', 'color_display', 'employee_count', 'is_active', 'is_deleted_display', 'created_at')
    list_filter = ('tag_type', 'is_active', 'is_deleted', 'created_at')
    search_fields = ('name',)
    ordering = ('tag_type', 'name')
    
    def is_deleted_display(self, obj):
        if obj.is_deleted:
            return format_html('<span style="color: red;">✗ Deleted</span>')
        return format_html('<span style="color: green;">✓ Active</span>')
    is_deleted_display.short_description = 'Status'
    
    def color_display(self, obj):
        return format_html(
            '<div style="width: 20px; height: 20px; background-color: {}; border-radius: 3px; display: inline-block;"></div> {}',
            obj.color, obj.color
        )
    color_display.short_description = 'Color'
    
    def employee_count(self, obj):
        count = obj.employees.filter(status__affects_headcount=True, is_deleted=False).count()
        if count > 0:
            url = reverse('admin:api_employee_changelist') + f'?tags__id__exact={obj.id}'
            return format_html(
                '<a href="{}" style="color: #417690;">{} employees</a>',
                url, count
            )
        return '0 employees'
    employee_count.short_description = 'Tagged Employees'

@admin.register(EmployeeStatus)
class EmployeeStatusAdmin(SoftDeleteAdminMixin, admin.ModelAdmin):
    list_display = (
        'name', 'status_type', 'color_display', 'affects_headcount', 'allows_org_chart', 
        'auto_transition_display', 'employee_count', 'is_default_display', 'is_active', 'is_deleted_display'
    )
    list_filter = (
        'status_type', 'affects_headcount', 'allows_org_chart', 'auto_transition_enabled', 
        'is_transitional', 'is_default_for_new_employees', 'is_active', 'is_deleted'
    )
    search_fields = ('name', 'description')
    ordering = ('order', 'name')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'status_type', 'color', 'description', 'order', 'is_active')
        }),
        ('Behavior Settings', {
            'fields': (
                'affects_headcount', 'allows_org_chart', 
                'is_transitional', 'is_default_for_new_employees'
            )
        }),
        ('Auto-Transition Settings', {
            'fields': (
                'auto_transition_enabled', 'auto_transition_days', 
                'auto_transition_to', 'transition_priority'
            ),
            'description': 'Configure automatic status transitions'
        }),
        ('Notification Settings', {
            'fields': ('send_notifications', 'notification_template'),
            'classes': ('collapse',)
        }),
        ('System Settings', {
            'fields': ('is_system_status',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def is_deleted_display(self, obj):
        if obj.is_deleted:
            return format_html('<span style="color: red;">✗ Deleted</span>')
        return format_html('<span style="color: green;">✓ Active</span>')
    is_deleted_display.short_description = 'Status'
    
    def color_display(self, obj):
        return format_html(
            '<div style="width: 20px; height: 20px; background-color: {}; border-radius: 3px; display: inline-block; margin-right: 8px;"></div><span style="font-family: monospace;">{}</span>',
            obj.color, obj.color
        )
    color_display.short_description = 'Color'
    
    def auto_transition_display(self, obj):
        if obj.auto_transition_enabled and obj.auto_transition_to:
            return format_html(
                '<span style="color: green;">✓ {} days → {}</span>',
                obj.auto_transition_days or '?', obj.auto_transition_to.name
            )
        elif obj.auto_transition_enabled:
            return format_html('<span style="color: orange;">⚠ Enabled (no target)</span>')
        return format_html('<span style="color: #999;">✗ Disabled</span>')
    auto_transition_display.short_description = 'Auto Transition'
    
    def is_default_display(self, obj):
        if obj.is_default_for_new_employees:
            return format_html('<span style="color: green;">✓ Default</span>')
        return format_html('<span style="color: #999;">-</span>')
    is_default_display.short_description = 'Default for New'
    
    def employee_count(self, obj):
        count = obj.employees.filter(is_deleted=False).count()
        if count > 0:
            url = reverse('admin:api_employee_changelist') + f'?status__id__exact={obj.id}'
            return format_html(
                '<a href="{}" style="color: #417690;">{} employees</a>',
                url, count
            )
        return '0 employees'
    employee_count.short_description = 'Employees'
    
    actions = ['create_default_statuses']
    
    def create_default_statuses(self, request, queryset):
        """Create default employee statuses"""
        statuses = EmployeeStatus.get_or_create_default_statuses()
        created_count = len([s for s in statuses.values() if s])
        self.message_user(
            request, 
            f'Successfully created/updated {created_count} default statuses.'
        )
    create_default_statuses.short_description = 'Create default statuses'

class EmployeeDocumentInline(admin.TabularInline):
    model = EmployeeDocument
    extra = 0
    readonly_fields = ('uploaded_at', 'file_size', 'mime_type')
    fields = ('name', 'document_type', 'file_path', 'file_size', 'uploaded_at')

class EmployeeActivityInline(admin.TabularInline):
    model = EmployeeActivity
    extra = 0
    readonly_fields = ('activity_type', 'description', 'performed_by', 'created_at')
    fields = ('activity_type', 'description', 'performed_by', 'created_at')
    can_delete = False
    
    def has_add_permission(self, request, obj=None):
        return False

@admin.register(Employee)
class EmployeeAdmin(SoftDeleteAdminMixin, admin.ModelAdmin):
    list_display = (
        'employee_id', 'profile_image_display', 'full_name_display', 'email_display', 
        'position_display', 'business_function_display', 'status_display', 
        'grading_display', 'line_manager_display', 'start_date', 
        'contract_status_display', 'status_needs_update_display', 
        'is_visible_in_org_chart', 'is_deleted_display'
    )
    list_filter = (
        'status', 'business_function', 'department', 'position_group', 
        'contract_duration', 'start_date', 'is_visible_in_org_chart', 
        'is_deleted', 'created_at', 'gender'
    )
    search_fields = (
        'employee_id', 'full_name', 'user__email', 'user__first_name', 
        'user__last_name', 'job_title', 'phone', 'father_name'  # ENHANCED: Added father_name
    )
    ordering = ('employee_id',)
    autocomplete_fields = ['user', 'line_manager']  # ENHANCED: Added line_manager autocomplete
    filter_horizontal = ('tags',)
    readonly_fields = (
        'full_name', 'contract_end_date', 'years_of_service_display', 
        'direct_reports_count_display', 'status_preview_display', 'created_at', 'updated_at'
    )
    inlines = [EmployeeDocumentInline, EmployeeActivityInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('user', 'employee_id', 'full_name')
        }),
        ('Personal Details', {
   'fields': (
        ('date_of_birth', 'gender'),
        ('father_name',),
         'address',
         ('phone', 'emergency_contact'),
        ('profile_image', 'profile_image_preview')
     ),
     'classes': ('collapse',)
 }),
        ('Job Information', {
            'fields': (
                ('business_function', 'department', 'unit'),
                ('job_function', 'job_title'),
                ('position_group', 'grading_level'),
                'line_manager'  # ENHANCED: Line manager field
            )
        }),
        ('Employment Dates & Contract', {
            'fields': (
                ('start_date', 'end_date'),
                ('contract_duration', 'contract_start_date', 'contract_end_date'),
                ('contract_extensions', 'last_extension_date', 'renewal_status')
            )
        }),
        ('Status & Visibility', {
            'fields': (
                ('status', 'is_visible_in_org_chart'),
                'tags'
            )
        }),
        ('Line Management', {  # NEW SECTION
            'fields': ('direct_reports_count_display',),
            'description': 'Information about direct reports and management hierarchy'
        }),
        ('Status Management', {
            'fields': ('status_preview_display',),
            'description': 'Current status analysis based on contract configuration'
        }),
        ('Additional Information', {
            'fields': ('notes', 'filled_vacancy'),
            'classes': ('collapse',)
        }),
        ('Calculated Fields', {
            'fields': ('years_of_service_display',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def profile_image_display(self, obj):
        """Display profile image in admin"""
        if obj.profile_image:
            return format_html(
                '<img src="{}" style="width: 60px; height: 60px; object-fit: cover; border-radius: 50%;" />',
                obj.profile_image.url
            )
        return format_html('<div style="width: 60px; height: 60px; background: #f0f0f0; border-radius: 50%; display: flex; align-items: center; justify-content: center; color: #999;">No Image</div>')
    profile_image_display.short_description = 'Profile Image'
    
    def profile_image_preview(self, obj):
        """Large profile image preview for detail view"""
        if obj.profile_image:
            return format_html(
                '<div style="margin: 10px 0;">'
                '<img src="{}" style="max-width: 200px; max-height: 200px; border: 1px solid #ddd; border-radius: 8px;" />'
                '<br><small><a href="{}" target="_blank">View full size</a></small>'
                '</div>',
                obj.profile_image.url, obj.profile_image.url
            )
        return 'No profile image uploaded'
    profile_image_preview.short_description = 'Profile Image Preview'
    
    def is_deleted_display(self, obj):
        if obj.is_deleted:
            return format_html('<span style="color: red;">✗ Deleted</span>')
        return format_html('<span style="color: green;">✓ Active</span>')
    is_deleted_display.short_description = 'Status'
    
    def full_name_display(self, obj):
        url = reverse('admin:api_employee_change', args=[obj.id])
        deleted_indicator = ' (DELETED)' if obj.is_deleted else ''
        style = 'color: #999; text-decoration: line-through;' if obj.is_deleted else 'color: #417690; font-weight: bold;'
        return format_html(
            '<a href="{}" style="{}">{}{}</a>',
            url, style, obj.full_name, deleted_indicator
        )
    full_name_display.short_description = 'Name'
    full_name_display.admin_order_field = 'full_name'
    
    def email_display(self, obj):
        if obj.user and obj.user.email:
            style = 'color: #999;' if obj.is_deleted else 'color: #417690;'
            return format_html(
                '<a href="mailto:{}" style="{}">{}</a>',
                obj.user.email, style, obj.user.email
            )
        return '-'
    email_display.short_description = 'Email'
    
    def position_display(self, obj):
        style = 'color: #999;' if obj.is_deleted else ''
        return format_html(
            '<div style="{}"><strong>{}</strong><br><small style="color: #666;">{}</small></div>',
            style, obj.job_title, obj.position_group.get_name_display()
        )
    position_display.short_description = 'Position'
    
    def business_function_display(self, obj):
        style = 'color: #999;' if obj.is_deleted else ''
        return format_html(
            '<div style="{}"><strong>{}</strong><br><small style="color: #666;">{}</small></div>',
            style, obj.business_function.code, obj.department.name
        )
    business_function_display.short_description = 'Function/Department'
    
    def status_display(self, obj):
        style = 'opacity: 0.5;' if obj.is_deleted else ''
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 8px; border-radius: 10px; font-size: 11px; font-weight: bold; {}">{}{};</span>',
            obj.status.color, style, obj.status.name, ' (DEL)' if obj.is_deleted else ''
        )
    status_display.short_description = 'Status'
    status_display.admin_order_field = 'status__name'
    
    def grading_display(self, obj):
        if obj.grading_level:
            style = 'color: #999;' if obj.is_deleted else 'color: #1976d2;'
            return format_html(
                '<div><strong style="{}">{}</strong></div>',
                style, obj.get_grading_display()
            )
        return format_html('<span style="color: #999;">No Grading</span>')
    grading_display.short_description = 'Grading'
    
    # ENHANCED: Line Manager Display
    def line_manager_display(self, obj):
        if obj.line_manager and not obj.line_manager.is_deleted:
            url = reverse('admin:api_employee_change', args=[obj.line_manager.id])
            style = 'color: #999;' if obj.is_deleted else 'color: #417690;'
            return format_html(
                '<a href="{}" style="{}">{}</a><br><small style="color: #666;">{}</small>',
                url, style, obj.line_manager.full_name, obj.line_manager.employee_id
            )
        return format_html('<span style="color: #999;">No Manager</span>')
    line_manager_display.short_description = 'Line Manager'
    
    def contract_status_display(self, obj):
        duration_display = obj.get_contract_duration_display()
        style = 'color: #999;' if obj.is_deleted else ''
        
        if obj.contract_end_date:
            days_left = (obj.contract_end_date - date.today()).days
            if days_left <= 30:
                color = '#dc3545'  # Red
            elif days_left <= 90:
                color = '#ffc107'  # Yellow
            else:
                color = '#28a745'  # Green
            
            return format_html(
                '<div style="{}; color: {};">{}<br><small>Ends: {}</small></div>',
                style, color, duration_display, obj.contract_end_date.strftime('%d/%m/%Y')
            )
        return format_html('<div style="{}">{}</div>', style, duration_display)
    contract_status_display.short_description = 'Contract'
    
    def status_needs_update_display(self, obj):
        """Show if employee status needs updating based on contract"""
        try:
            preview = obj.get_status_preview()
            if preview['needs_update']:
                return format_html(
                    '<span style="background: #ff9800; color: white; padding: 2px 6px; border-radius: 4px; font-size: 10px;">⚠ Update Needed</span><br><small style="color: #666;">{} → {}</small>',
                    preview['current_status'], preview['required_status']
                )
            else:
                return format_html('<span style="color: green;">✓ Current</span>')
        except:
            return format_html('<span style="color: #999;">-</span>')
    status_needs_update_display.short_description = 'Status Check'
    
    def status_preview_display(self, obj):
        """Detailed status preview for admin form"""
        try:
            preview = obj.get_status_preview()
            if preview['needs_update']:
                return format_html(
                    '<div style="background: #fff3cd; padding: 10px; border-radius: 4px; border-left: 4px solid #ffc107;">'
                    '<strong>Status Update Needed</strong><br>'
                    'Current: <strong>{}</strong><br>'
                    'Required: <strong>{}</strong><br>'
                    'Reason: {}<br>'
                    'Contract: {} ({} days since start)<br>'
                    'Contract End: {}'
                    '</div>',
                    preview['current_status'], 
                    preview['required_status'],
                    preview['reason'],
                    preview['contract_type'],
                    preview['days_since_start'],
                    preview.get('contract_end_date', 'N/A')
                )
            else:
                return format_html(
                    '<div style="background: #d4edda; padding: 10px; border-radius: 4px; border-left: 4px solid #28a745;">'
                    '<strong>Status is Current</strong><br>'
                    'Current Status: <strong>{}</strong><br>'
                    'Reason: {}<br>'
                    'Contract: {} ({} days since start)'
                    '</div>',
                    preview['current_status'],
                    preview['reason'],
                    preview['contract_type'],
                    preview['days_since_start']
                )
        except Exception as e:
            return format_html(
                '<div style="background: #f8d7da; padding: 10px; border-radius: 4px; border-left: 4px solid #dc3545;">'
                '<strong>Error calculating status</strong><br>{}'
                '</div>',
                str(e)
            )
    status_preview_display.short_description = 'Status Preview'
    
    def years_of_service_display(self, obj):
        return f"{obj.years_of_service} years"
    years_of_service_display.short_description = 'Years of Service'
    
    # ENHANCED: Direct Reports Count Display
    def direct_reports_count_display(self, obj):
        count = obj.get_direct_reports_count()
        if count > 0:
            url = reverse('admin:api_employee_changelist') + f'?line_manager__id__exact={obj.id}'
            style = 'color: #999;' if obj.is_deleted else 'color: #417690;'
            return format_html(
                '<a href="{}" style="{}">{} reports</a>',
                url, style, count
            )
        return '0 reports'
    direct_reports_count_display.short_description = 'Direct Reports'
    
    actions = [
        'export_employees_csv', 'mark_org_chart_visible', 'mark_org_chart_hidden', 
        'update_contract_status', 'auto_update_status', 'bulk_assign_line_manager',
        'extend_contracts', 'preview_status_updates', 'clear_line_managers'  # NEW ACTION
    ]
    
    # Complete the admin.py file - this continues from where it was cut off

    def export_employees_csv(self, request, queryset):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="employees_{date.today()}.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Employee ID', 'Name', 'Email', 'Job Title', 'Business Function',
            'Department', 'Unit', 'Position Group', 'Grade', 'Status',
            'Line Manager', 'Start Date', 'Contract Duration', 'Contract End Date',
            'Status Needs Update', 'Phone', 'Father Name', 'Is Deleted'
        ])
        
        for employee in queryset:
            preview = employee.get_status_preview()
            writer.writerow([
                employee.employee_id,
                employee.full_name,
                employee.user.email if employee.user else '',
                employee.job_title,
                employee.business_function.name,
                employee.department.name,
                employee.unit.name if employee.unit else '',
                employee.position_group.get_name_display(),
                employee.get_grading_display(),
                employee.status.name,
                employee.line_manager.full_name if employee.line_manager else '',
                employee.start_date,
                employee.get_contract_duration_display(),
                employee.contract_end_date or '',
                'Yes' if preview['needs_update'] else 'No',
                employee.phone or '',
                employee.father_name or '',
                'Yes' if employee.is_deleted else 'No'
            ])
        
        self.message_user(request, f'Exported {queryset.count()} employees to CSV.')
        return response
    export_employees_csv.short_description = 'Export selected employees to CSV'
    
    def mark_org_chart_visible(self, request, queryset):
        count = queryset.update(is_visible_in_org_chart=True)
        self.message_user(request, f'{count} employees marked as visible in org chart.')
    mark_org_chart_visible.short_description = 'Mark as visible in org chart'
    
    def mark_org_chart_hidden(self, request, queryset):
        count = queryset.update(is_visible_in_org_chart=False)
        self.message_user(request, f'{count} employees hidden from org chart.')
    mark_org_chart_hidden.short_description = 'Hide from org chart'
    

    
    
    def bulk_assign_line_manager(self, request, queryset):
        """Bulk assign line manager - will redirect to change page"""
        selected = request.POST.getlist(admin.ACTION_CHECKBOX_NAME)
        return redirect(f'/admin/api/employee/?id__in={",".join(selected)}')
    bulk_assign_line_manager.short_description = 'Bulk assign line manager'
    
    def extend_contracts(self, request, queryset):
        """Extend contracts for selected employees"""
        extendable = queryset.exclude(contract_duration='PERMANENT').filter(contract_end_date__isnull=False)
        extended_count = 0
        
        for employee in extendable:
            success, message = employee.extend_contract(3, request.user)  # 3 months extension
            if success:
                extended_count += 1
        
        self.message_user(
            request, 
            f'Extended contracts for {extended_count} employees by 3 months.'
        )
    extend_contracts.short_description = 'Extend contracts by 3 months'
    
    def preview_status_updates(self, request, queryset):
        """Preview what status updates would happen"""
        updates_needed = 0
        for employee in queryset:
            preview = employee.get_status_preview()
            if preview['needs_update']:
                updates_needed += 1
        
        self.message_user(
            request, 
            f'{updates_needed} out of {queryset.count()} selected employees need status updates.'
        )
    preview_status_updates.short_description = 'Preview status updates needed'
    
    def clear_line_managers(self, request, queryset):
        """Clear line managers for selected employees"""
        count = queryset.update(line_manager=None)
        self.message_user(request, f'Cleared line managers for {count} employees.')
    clear_line_managers.short_description = 'Clear line managers'
    
    # Enhanced get_queryset to show soft-deleted employees in admin
    def get_queryset(self, request):
        if request.GET.get('show_deleted'):
            return Employee.all_objects.get_queryset()
        return super().get_queryset(request)

@admin.register(VacantPosition)
class VacantPositionAdmin(SoftDeleteAdminMixin, admin.ModelAdmin):
    list_display = (
        'position_id', 'title', 'business_function_display', 'department_display',
        'vacancy_type', 'urgency_display', 'expected_start_date', 
        'reporting_to_display', 'filled_status_display', 'days_open_display'
    )
    list_filter = (
        'business_function', 'department', 'vacancy_type', 'urgency', 
        'is_filled', 'expected_start_date', 'created_at'
    )
    search_fields = ('position_id', 'title', 'description')
    autocomplete_fields = ['reporting_to', 'filled_by', 'created_by']
    readonly_fields = ('filled_date', 'created_at', 'updated_at')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('position_id', 'title', 'description')
        }),
        ('Organizational Structure', {
            'fields': (
                ('business_function', 'department', 'unit'),
                ('job_function', 'position_group')
            )
        }),
        ('Vacancy Details', {
            'fields': (
                ('vacancy_type', 'urgency'),
                'expected_start_date',
                ('expected_salary_range_min', 'expected_salary_range_max')
            )
        }),
        ('Management', {
            'fields': ('reporting_to', 'created_by')
        }),
        ('Status', {
            'fields': (
                ('is_filled', 'filled_by', 'filled_date')
            )
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def business_function_display(self, obj):
        return f"{obj.business_function.code} - {obj.business_function.name}"
    business_function_display.short_description = 'Business Function'
    
    def department_display(self, obj):
        return obj.department.name
    department_display.short_description = 'Department'
    
    def urgency_display(self, obj):
        colors = {
            'LOW': '#28a745',
            'MEDIUM': '#ffc107', 
            'HIGH': '#fd7e14',
            'CRITICAL': '#dc3545'
        }
        color = colors.get(obj.urgency, '#6c757d')
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 8px; border-radius: 10px; font-size: 11px; font-weight: bold;">{}</span>',
            color, obj.get_urgency_display()
        )
    urgency_display.short_description = 'Urgency'
    urgency_display.admin_order_field = 'urgency'
    
    def reporting_to_display(self, obj):
        if obj.reporting_to:
            url = reverse('admin:api_employee_change', args=[obj.reporting_to.id])
            return format_html(
                '<a href="{}" style="color: #417690;">{}</a>',
                url, obj.reporting_to.full_name
            )
        return format_html('<span style="color: #999;">Not specified</span>')
    reporting_to_display.short_description = 'Reports To'
    
    def filled_status_display(self, obj):
        if obj.is_filled:
            return format_html(
                '<span style="color: green;">✓ Filled by {}</span>',
                obj.filled_by.full_name if obj.filled_by else 'Unknown'
            )
        return format_html('<span style="color: orange;">◯ Open</span>')
    filled_status_display.short_description = 'Status'
    
    def days_open_display(self, obj):
        if obj.is_filled and obj.filled_date:
            days = (obj.filled_date - obj.created_at.date()).days
            return format_html(
                '<span style="color: green;">{} days (filled)</span>',
                days
            )
        else:
            days = (date.today() - obj.created_at.date()).days
            color = '#dc3545' if days > 60 else '#ffc107' if days > 30 else '#28a745'
            return format_html(
                '<span style="color: {};">{} days (open)</span>',
                color, days
            )
    days_open_display.short_description = 'Days Open'
    
    actions = ['mark_as_filled', 'generate_vacancy_report']
    
    def mark_as_filled(self, request, queryset):
        """Mark selected vacancies as filled (without specifying employee)"""
        count = queryset.filter(is_filled=False).update(
            is_filled=True,
            filled_date=date.today()
        )
        self.message_user(request, f'Marked {count} vacancies as filled.')
    mark_as_filled.short_description = 'Mark as filled'
    
    def generate_vacancy_report(self, request, queryset):
        """Generate CSV report for selected vacancies"""
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="vacancies_{date.today()}.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Position ID', 'Title', 'Business Function', 'Department', 
            'Vacancy Type', 'Urgency', 'Expected Start Date', 'Reports To',
            'Status', 'Days Open', 'Created Date'
        ])
        
        for vacancy in queryset:
            days_open = (date.today() - vacancy.created_at.date()).days
            writer.writerow([
                vacancy.position_id,
                vacancy.title,
                vacancy.business_function.name,
                vacancy.department.name,
                vacancy.get_vacancy_type_display(),
                vacancy.get_urgency_display(),
                vacancy.expected_start_date,
                vacancy.reporting_to.full_name if vacancy.reporting_to else '',
                'Filled' if vacancy.is_filled else 'Open',
                days_open,
                vacancy.created_at.date()
            ])
        
        return response
    generate_vacancy_report.short_description = 'Export vacancy report'

@admin.register(EmployeeDocument)
class EmployeeDocumentAdmin(SoftDeleteAdminMixin, admin.ModelAdmin):
    list_display = (
        'name', 'employee_display', 'document_type', 'file_preview', 
        'file_size_display', 'expiry_status', 'confidential_status',
        'download_count', 'uploaded_at', 'uploaded_by', 'is_deleted_display'
    )
    list_filter = (
        'document_type', 'is_confidential', 'uploaded_at', 
        'expiry_date', 'mime_type', 'is_deleted'
    )
    search_fields = ('name', 'employee__employee_id', 'employee__full_name', 'description', 'original_filename')
    autocomplete_fields = ['employee', 'uploaded_by']
    readonly_fields = (
        'id', 'file_size', 'mime_type', 'original_filename', 'uploaded_at',
        'file_preview_large', 'download_count', 'last_accessed'
    )
    date_hierarchy = 'uploaded_at'
    
    fieldsets = (
        ('Document Information', {
            'fields': ('employee', 'name', 'document_type', 'description')
        }),
        ('File Details', {
            'fields': ('document_file', 'file_preview_large')
        }),
        ('Security & Expiry', {
            'fields': ('is_confidential', 'expiry_date')
        }),
        ('File Metadata', {
            'fields': ('file_size', 'mime_type', 'original_filename'),
            'classes': ('collapse',)
        }),
        ('Upload Information', {
            'fields': ('uploaded_at', 'uploaded_by', 'download_count', 'last_accessed'),
            'classes': ('collapse',)
        })
    )
    
    def employee_display(self, obj):
        url = reverse('admin:api_employee_change', args=[obj.employee.id])
        return format_html(
            '<a href="{}" style="color: #417690;">{} ({})</a>',
            url, obj.employee.full_name, obj.employee.employee_id
        )
    employee_display.short_description = 'Employee'
    
    def file_preview(self, obj):
        """Small file preview for list view"""
        if obj.document_file:
            if obj.is_image():
                return format_html(
                    '<img src="{}" style="width: 50px; height: 50px; object-fit: cover; border-radius: 4px;" />',
                    obj.document_file.url
                )
            elif obj.is_pdf():
                return format_html('<span style="color: #dc3545;">📄 PDF</span>')
            else:
                return format_html('<span style="color: #6c757d;">📎 File</span>')
        return '-'
    file_preview.short_description = 'Preview'
    
    def file_preview_large(self, obj):
        """Large file preview for detail view"""
        if obj.document_file:
            if obj.is_image():
                return format_html(
                    '<div style="margin: 10px 0;">'
                    '<img src="{}" style="max-width: 300px; max-height: 300px; border: 1px solid #ddd; border-radius: 4px;" />'
                    '<br><small><a href="{}" target="_blank">View full size</a></small>'
                    '</div>',
                    obj.document_file.url, obj.document_file.url
                )
            else:
                return format_html(
                    '<div style="margin: 10px 0;">'
                    '<a href="{}" target="_blank" style="color: #417690;">📎 Download File</a>'
                    '<br><small>File: {} ({})</small>'
                    '</div>',
                    obj.document_file.url, obj.original_filename or obj.name, obj.get_file_size_display()
                )
        return 'No file uploaded'
    file_preview_large.short_description = 'File Preview'
    
    def file_size_display(self, obj):
        return obj.get_file_size_display()
    file_size_display.short_description = 'File Size'
    file_size_display.admin_order_field = 'file_size'
    
    def expiry_status(self, obj):
        if obj.expiry_date:
            days_until_expiry = (obj.expiry_date - date.today()).days
            if days_until_expiry < 0:
                return format_html(
                    '<span style="color: red; font-weight: bold;">⚠ Expired</span>'
                )
            elif days_until_expiry <= 30:
                return format_html(
                    '<span style="color: orange; font-weight: bold;">⚡ Expires in {} days</span>',
                    days_until_expiry
                )
            else:
                return format_html(
                    '<span style="color: green;">✓ Valid until {}</span>',
                    obj.expiry_date.strftime('%d/%m/%Y')
                )
        return '-'
    expiry_status.short_description = 'Expiry Status'
    
    def confidential_status(self, obj):
        if obj.is_confidential:
            return format_html('<span style="color: red;">🔒 Confidential</span>')
        return format_html('<span style="color: green;">🔓 Public</span>')
    confidential_status.short_description = 'Security'
    confidential_status.admin_order_field = 'is_confidential'
    
    def is_deleted_display(self, obj):
        if obj.is_deleted:
            return format_html('<span style="color: red;">✗ Deleted</span>')
        return format_html('<span style="color: green;">✓ Active</span>')
    is_deleted_display.short_description = 'Status'
    
    actions = ['mark_as_confidential', 'mark_as_public', 'export_documents', 'check_expiry']
    
    def mark_as_confidential(self, request, queryset):
        """Mark selected documents as confidential"""
        count = queryset.update(is_confidential=True)
        self.message_user(request, f'Marked {count} documents as confidential.')
    mark_as_confidential.short_description = 'Mark as confidential'
    
    def mark_as_public(self, request, queryset):
        """Mark selected documents as public"""
        count = queryset.update(is_confidential=False)
        self.message_user(request, f'Marked {count} documents as public.')
    mark_as_public.short_description = 'Mark as public'
    
    def export_documents(self, request, queryset):
        """Export document metadata to CSV"""
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="documents_export_{date.today()}.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Document ID', 'Employee ID', 'Employee Name', 'Document Name',
            'Document Type', 'File Size', 'Is Confidential', 'Expiry Date',
            'Upload Date', 'Download Count', 'Uploaded By'
        ])
        
        for doc in queryset:
            writer.writerow([
                str(doc.id), doc.employee.employee_id, doc.employee.full_name,
                doc.name, doc.get_document_type_display(), doc.get_file_size_display(),
                'Yes' if doc.is_confidential else 'No', doc.expiry_date or '',
                doc.uploaded_at.strftime('%Y-%m-%d'), doc.download_count,
                doc.uploaded_by.username if doc.uploaded_by else ''
            ])
        
        self.message_user(request, f'Exported {queryset.count()} documents to CSV.')
        return response
    export_documents.short_description = 'Export document metadata to CSV'
    
    def check_expiry(self, request, queryset):
        """Check document expiry status"""
        expiring_soon = 0
        expired = 0
        
        for doc in queryset:
            if doc.expiry_date:
                days_until_expiry = (doc.expiry_date - date.today()).days
                if days_until_expiry < 0:
                    expired += 1
                elif days_until_expiry <= 30:
                    expiring_soon += 1
        
        message = f'Expiry check complete: {expired} expired, {expiring_soon} expiring within 30 days'
        self.message_user(request, message)
    check_expiry.short_description = 'Check document expiry status'

@admin.register(EmployeeActivity)
class EmployeeActivityAdmin(admin.ModelAdmin):
    list_display = ('employee_display', 'activity_type', 'short_description', 'performed_by', 'created_at')
    list_filter = ('activity_type', 'created_at', 'performed_by')
    search_fields = ('employee__employee_id', 'employee__full_name', 'description')
    readonly_fields = ('id', 'created_at', 'metadata')
    date_hierarchy = 'created_at'
    
    def employee_display(self, obj):
        url = reverse('admin:api_employee_change', args=[obj.employee.id])
        return format_html(
            '<a href="{}" style="color: #417690;">{} ({})</a>',
            url, obj.employee.full_name, obj.employee.employee_id
        )
    employee_display.short_description = 'Employee'
    
    def short_description(self, obj):
        if len(obj.description) > 100:
            return obj.description[:100] + '...'
        return obj.description
    short_description.short_description = 'Description'
    def get_list_filter(self):
        """Enhanced list filter with file activity types"""
        return (
            'activity_type', 'created_at', 'performed_by',
            ('activity_type', admin.ChoicesFieldListFilter),
        )
    
    def get_activity_icon(self, obj):
        """Get icon for activity type"""
        icons = {
            'CREATED': '➕',
            'UPDATED': '✏️',
            'STATUS_CHANGED': '🔄',
            'MANAGER_CHANGED': '👤',
            'POSITION_CHANGED': '📊',
            'CONTRACT_UPDATED': '📋',
            'DOCUMENT_UPLOADED': '📎',
            'PROFILE_UPDATED': '🖼️',
            'GRADE_CHANGED': '⭐',
            'TAG_ADDED': '🏷️',
            'TAG_REMOVED': '🗑️',
            'SOFT_DELETED': '❌',
            'RESTORED': '♻️',
            'BULK_CREATED': '📦',
            'STATUS_AUTO_UPDATED': '🤖',
        }
        return icons.get(obj.activity_type, '📝')
    
    def activity_display(self, obj):
        """Enhanced activity display with icons"""
        icon = self.get_activity_icon(obj)
        return format_html(
            '<span style="margin-right: 8px;">{}</span>{}',
            icon, obj.get_activity_type_display()
        )
    activity_display.short_description = 'Activity Type'
    activity_display.admin_order_field = 'activity_type'
    def has_add_permission(self, request):
        return False  # Activities are auto-generated
    
    def has_change_permission(self, request, obj=None):
        return False  # Activities are read-only

admin.site.site_header = 'ALMET HRIS Administration'
admin.site.site_title = 'ALMET HRIS Admin'
admin.site.index_title = 'Employee Management System'

class AlmetHRISAdminSite(admin.AdminSite):
    site_header = 'ALMET HRIS Administration'
    site_title = 'ALMET HRIS Admin'
    index_title = 'Employee Management System Dashboard'
    
    def index(self, request, extra_context=None):
        """Custom admin dashboard with key metrics"""
        extra_context = extra_context or {}
        
        # Get key metrics
        total_employees = Employee.objects.count()
        active_employees = Employee.objects.filter(status__affects_headcount=True).count()
        vacant_positions = VacantPosition.objects.filter(is_filled=False).count()
        
        # Contract expiry alerts
        expiring_soon = Employee.objects.filter(
            contract_end_date__lte=date.today() + timedelta(days=30),
            contract_end_date__gte=date.today(),
            contract_duration__in=['3_MONTHS', '6_MONTHS', '1_YEAR', '2_YEARS', '3_YEARS']
        ).count()
        
        # Status updates needed
        from .status_management import EmployeeStatusManager
        needing_updates = len(EmployeeStatusManager.get_employees_needing_update())
        
        extra_context.update({
            'total_employees': total_employees,
            'active_employees': active_employees,
            'vacant_positions': vacant_positions,
            'expiring_contracts': expiring_soon,
            'status_updates_needed': needing_updates,
        })
        
        return super().index(request, extra_context)

class QuickActionsAdmin(admin.ModelAdmin):
    """Mixin for quick actions in admin"""
    
    def get_actions(self, request):
        actions = super().get_actions(request)
        actions['quick_export'] = (self.quick_export, 'quick_export', 'Quick export to CSV')
        return actions
    
    def quick_export(self, request, queryset):
        """Quick export action for any model"""
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{self.model._meta.model_name}_{date.today()}.csv"'
        
        writer = csv.writer(response)
        
        # Get all field names
        field_names = [field.name for field in self.model._meta.fields if not field.name.startswith('_')]
        writer.writerow(field_names)
        
        # Write data
        for obj in queryset:
            row = []
            for field_name in field_names:
                value = getattr(obj, field_name, '')
                if value is None:
                    value = ''
                row.append(str(value))
            writer.writerow(row)
        
        self.message_user(request, f'Exported {queryset.count()} records.')
        return response
    quick_export.short_description = 'Quick export selected items to CSV'

class AlmetAdminMixin:
    """Mixin to add custom styling and JavaScript to admin"""
    
    class Media:
        css = {
            'all': ('admin/css/almet_admin.css',)
        }
        js = ('admin/js/almet_admin.js',)

for admin_class in [EmployeeAdmin, BusinessFunctionAdmin, DepartmentAdmin]:
    if hasattr(admin_class, '__bases__'):
        admin_class.__bases__ = admin_class.__bases__ + (AlmetAdminMixin,)
        class FileManagementAdminMixin:
         """Mixin for file management actions"""
    
    def cleanup_orphaned_files(self, request, queryset):
        """Clean up orphaned files that have no database records"""
        import os
        from django.conf import settings
        
        cleaned_count = 0
        
        # Check employee documents
        documents_path = os.path.join(settings.MEDIA_ROOT, 'employee_documents')
        if os.path.exists(documents_path):
            for root, dirs, files in os.walk(documents_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    relative_path = os.path.relpath(file_path, settings.MEDIA_ROOT)
                    
                    # Check if file exists in database
                    if not EmployeeDocument.objects.filter(document_file=relative_path).exists():
                        try:
                            os.remove(file_path)
                            cleaned_count += 1
                        except:
                            pass
        
        # Check profile images
        profiles_path = os.path.join(settings.MEDIA_ROOT, 'employee_profiles')
        if os.path.exists(profiles_path):
            for root, dirs, files in os.walk(profiles_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    relative_path = os.path.relpath(file_path, settings.MEDIA_ROOT)
                    
                    # Check if file exists in database
                    if not Employee.objects.filter(profile_image=relative_path).exists():
                        try:
                            os.remove(file_path)
                            cleaned_count += 1
                        except:
                            pass
        
        self.message_user(request, f'Cleaned up {cleaned_count} orphaned files.')
    cleanup_orphaned_files.short_description = 'Clean up orphaned files'
    
    def generate_file_report(self, request, queryset):
        """Generate file usage report"""
        from django.db.models import Sum, Count
        
        # Document statistics
        doc_stats = EmployeeDocument.objects.aggregate(
            total_documents=Count('id'),
            total_size=Sum('file_size'),
            confidential_docs=Count('id', filter=Q(is_confidential=True))
        )
        
        # Profile image statistics
        profile_stats = Employee.objects.aggregate(
            employees_with_images=Count('id', filter=Q(profile_image__isnull=False))
        )
        
        total_employees = Employee.objects.count()
        
        message = (
            f"File Usage Report: "
            f"{doc_stats['total_documents']} documents, "
            f"{doc_stats['total_size'] // (1024*1024) if doc_stats['total_size'] else 0} MB total, "
            f"{doc_stats['confidential_docs']} confidential, "
            f"{profile_stats['employees_with_images']}/{total_employees} employees have profile images"
        )
        
        self.message_user(request, message)
    generate_file_report.short_description = 'Generate file usage report'


EmployeeDocumentAdmin.__bases__ = EmployeeDocumentAdmin.__bases__ + (FileManagementAdminMixin,)


EmployeeDocumentAdmin.actions.extend(['cleanup_orphaned_files', 'generate_file_report'])


admin.site.site_header = 'ALMET HRIS Administration - Enhanced File Management'
admin.site.site_title = 'ALMET HRIS Admin'
admin.site.index_title = 'Employee Management System with Document Control'


class AlmetAdminWithFilesMixin:
    """Enhanced admin mixin with file management styling"""
    
    class Media:
        css = {
            'all': (
                'admin/css/almet_admin.css',
                'admin/css/file_management.css',
            )
        }
        js = (
            'admin/js/almet_admin.js',
            'admin/js/file_management.js',
        )


for admin_class in [EmployeeAdmin, EmployeeDocumentAdmin]:
    if hasattr(admin_class, '__bases__'):
        admin_class.__bases__ = admin_class.__bases__ + (AlmetAdminWithFilesMixin,)
        