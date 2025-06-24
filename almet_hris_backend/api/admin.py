# api/admin.py - ENHANCED: Complete Django Admin with Soft Delete Support

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
    EmployeeDocument, EmployeeActivity, VacantPosition, HeadcountSummary
)

# Custom admin styling
class BaseModelAdmin(admin.ModelAdmin):
    """Base admin class with common styling"""
    from django.db import models
    from django.forms import TextInput, Textarea
    
    formfield_overrides = {
        models.CharField: {'widget': TextInput(attrs={'size': '40'})},
        models.TextField: {'widget': Textarea(attrs={'rows': 4, 'cols': 60})},
    }

# Soft Delete Admin Mixin
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

# Unregister default User admin and create enhanced version
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

# Business Structure Admins
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
    list_display = ('name', 'status_type', 'color_display', 'affects_headcount', 'allows_org_chart', 'employee_count', 'is_active', 'is_deleted_display')
    list_filter = ('status_type', 'affects_headcount', 'allows_org_chart', 'is_active', 'is_deleted', 'created_at')
    search_fields = ('name',)
    ordering = ('name',)
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'status_type', 'color', 'is_active')
        }),
        ('Behavior Settings', {
            'fields': ('affects_headcount', 'allows_org_chart')
        }),
        ('Duration Settings', {
            'fields': (
                'onboarding_duration',
                ('probation_duration_3m', 'probation_duration_6m'),
                ('probation_duration_1y', 'probation_duration_2y', 'probation_duration_3y'),
                'probation_duration_permanent'
            ),
            'description': 'Configure automatic status transition durations'
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

# Employee Document Inline
class EmployeeDocumentInline(admin.TabularInline):
    model = EmployeeDocument
    extra = 0
    readonly_fields = ('uploaded_at', 'file_size', 'mime_type')
    fields = ('name', 'document_type', 'file_path', 'file_size', 'uploaded_at')

# Employee Activity Inline
class EmployeeActivityInline(admin.TabularInline):
    model = EmployeeActivity
    extra = 0
    readonly_fields = ('activity_type', 'description', 'performed_by', 'created_at')
    fields = ('activity_type', 'description', 'performed_by', 'created_at')
    can_delete = False
    
    def has_add_permission(self, request, obj=None):
        return False

# Main Employee Admin
@admin.register(Employee)
class EmployeeAdmin(SoftDeleteAdminMixin, admin.ModelAdmin):
    list_display = (
        'employee_id', 'full_name_display', 'email_display', 'position_display', 
        'business_function_display', 'status_display', 'grading_display', 
        'line_manager_display', 'start_date', 'contract_status_display', 
        'is_visible_in_org_chart', 'is_deleted_display'
    )
    list_filter = (
        'status', 'business_function', 'department', 'position_group', 
        'contract_duration', 'start_date', 'is_visible_in_org_chart', 
        'is_deleted', 'created_at'
    )
    search_fields = (
        'employee_id', 'full_name', 'user__email', 'user__first_name', 
        'user__last_name', 'job_title', 'phone'
    )
    ordering = ('employee_id',)
    autocomplete_fields = ['user', 'line_manager']
    filter_horizontal = ('tags',)
    readonly_fields = (
        'full_name', 'contract_end_date', 'years_of_service_display', 
        'direct_reports_count_display', 'created_at', 'updated_at'
    )
    inlines = [EmployeeDocumentInline, EmployeeActivityInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('user', 'employee_id', 'full_name')
        }),
        ('Personal Details', {
            'fields': (
                ('date_of_birth', 'gender'),
                'address',
                ('phone', 'emergency_contact'),
                'profile_image'
            ),
            'classes': ('collapse',)
        }),
        ('Job Information', {
            'fields': (
                ('business_function', 'department', 'unit'),
                ('job_function', 'job_title'),
                ('position_group', 'grading_level'),
                'line_manager'
            )
        }),
        ('Employment Dates & Contract', {
            'fields': (
                ('start_date', 'end_date'),
                ('contract_duration', 'contract_start_date', 'contract_end_date')
            )
        }),
        ('Status & Visibility', {
            'fields': (
                ('status', 'is_visible_in_org_chart'),
                'tags'
            )
        }),
        ('Additional Information', {
            'fields': ('notes', 'filled_vacancy'),
            'classes': ('collapse',)
        }),
        ('Calculated Fields', {
            'fields': ('years_of_service_display', 'direct_reports_count_display'),
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
    
    def years_of_service_display(self, obj):
        return f"{obj.years_of_service} years"
    years_of_service_display.short_description = 'Years of Service'
    
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
        'update_contract_status', 'auto_update_status'
    ]
    
    def export_employees_csv(self, request, queryset):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="employees_{date.today()}.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Employee ID', 'Name', 'Email', 'Job Title', 'Business Function',
            'Department', 'Unit', 'Position Group', 'Grade', 'Status',
            'Line Manager', 'Start Date', 'Contract Duration', 'Phone', 'Is Deleted'
        ])
        
        for employee in queryset:
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
                employee.phone or '',
                'Yes' if employee.is_deleted else 'No'
            ])
        
        return response
    export_employees_csv.short_description = 'Export selected to CSV'
    
    def mark_org_chart_visible(self, request, queryset):
        updated = queryset.update(is_visible_in_org_chart=True)
        self.message_user(request, f'Successfully made {updated} employees visible in org chart.')
    mark_org_chart_visible.short_description = 'Make visible in org chart'
    
    def mark_org_chart_hidden(self, request, queryset):
        updated = queryset.update(is_visible_in_org_chart=False)
        self.message_user(request, f'Successfully hid {updated} employees from org chart.')
    mark_org_chart_hidden.short_description = 'Hide from org chart'
    
    def update_contract_status(self, request, queryset):
        updated_count = 0
        for employee in queryset:
            employee.update_contract_status()
            updated_count += 1
        self.message_user(request, f'Successfully updated contract status for {updated_count} employees.')
    update_contract_status.short_description = 'Update contract status'
    
    def auto_update_status(self, request, queryset):
        updated_count = 0
        for employee in queryset:
            if employee.update_status_automatically():
                updated_count += 1
        self.message_user(request, f'Successfully auto-updated status for {updated_count} employees.')
    auto_update_status.short_description = 'Auto-update status based on contract'

# Employee Activity Admin
@admin.register(EmployeeActivity)
class EmployeeActivityAdmin(admin.ModelAdmin):
    list_display = ('employee_display', 'activity_type', 'description_short', 'performed_by_display', 'created_at')
    list_filter = ('activity_type', 'created_at', 'performed_by')
    search_fields = ('employee__full_name', 'employee__employee_id', 'description')
    ordering = ('-created_at',)
    readonly_fields = ('created_at',)
    
    def employee_display(self, obj):
        url = reverse('admin:api_employee_change', args=[obj.employee.id])
        style = 'color: #999; text-decoration: line-through;' if obj.employee.is_deleted else 'color: #417690;'
        deleted_indicator = ' (DELETED)' if obj.employee.is_deleted else ''
        return format_html(
            '<a href="{}" style="{}">{}</a><br><small style="color: #666;">{}{}</small>',
            url, style, obj.employee.full_name, obj.employee.employee_id, deleted_indicator
        )
    employee_display.short_description = 'Employee'
    
    def description_short(self, obj):
        if len(obj.description) > 60:
            return f"{obj.description[:60]}..."
        return obj.description
    description_short.short_description = 'Description'
    
    def performed_by_display(self, obj):
        if obj.performed_by:
            return obj.performed_by.username
        return format_html('<span style="color: #999;">System</span>')
    performed_by_display.short_description = 'Performed By'
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

# Employee Document Admin
@admin.register(EmployeeDocument)
class EmployeeDocumentAdmin(SoftDeleteAdminMixin, admin.ModelAdmin):
    list_display = ('name', 'employee_display', 'document_type', 'file_size_display', 'uploaded_by_display', 'uploaded_at', 'is_deleted_display')
    list_filter = ('document_type', 'uploaded_at', 'uploaded_by', 'is_deleted')
    search_fields = ('name', 'employee__full_name', 'employee__employee_id')
    ordering = ('-uploaded_at',)
    readonly_fields = ('uploaded_at', 'file_size', 'mime_type')
    autocomplete_fields = ['employee', 'uploaded_by']
    
    def is_deleted_display(self, obj):
        if obj.is_deleted:
            return format_html('<span style="color: red;">✗ Deleted</span>')
        return format_html('<span style="color: green;">✓ Active</span>')
    is_deleted_display.short_description = 'Status'
    
    def employee_display(self, obj):
        """Display employee with link to their profile"""
        url = reverse('admin:api_employee_change', args=[obj.employee.id])
        style = 'color: #999; text-decoration: line-through;' if obj.employee.is_deleted else 'color: #417690;'
        deleted_indicator = ' (DELETED)' if obj.employee.is_deleted else ''
        return format_html(
            '<a href="{}" style="{}">{}</a><br><small style="color: #666;">{}{}</small>',
            url, style, obj.employee.full_name, obj.employee.employee_id, deleted_indicator
        )
    employee_display.short_description = 'Employee'
    
    def file_size_display(self, obj):
        """Display file size in human readable format"""
        if obj.file_size:
            if obj.file_size < 1024:
                return f"{obj.file_size} B"
            elif obj.file_size < 1024 * 1024:
                return f"{obj.file_size / 1024:.1f} KB"
            else:
                return f"{obj.file_size / (1024 * 1024):.1f} MB"
        return "Unknown"
    file_size_display.short_description = 'File Size'
    
    def uploaded_by_display(self, obj):
        """Display who uploaded the document"""
        if obj.uploaded_by:
            return obj.uploaded_by.username
        return format_html('<span style="color: #999;">Unknown</span>')
    uploaded_by_display.short_description = 'Uploaded By'

# Vacant Position Admin
@admin.register(VacantPosition)
class VacantPositionAdmin(SoftDeleteAdminMixin, admin.ModelAdmin):
    list_display = ('position_id', 'title', 'business_function', 'department', 'urgency_display', 'is_filled_display', 'created_at', 'is_deleted_display')
    list_filter = ('urgency', 'is_filled', 'business_function', 'department', 'is_deleted', 'created_at')
    search_fields = ('position_id', 'title', 'description')
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at')
    autocomplete_fields = ['business_function', 'department', 'unit', 'job_function', 'position_group', 'reporting_to', 'filled_by']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('position_id', 'title', 'description')
        }),
        ('Organizational Structure', {
            'fields': (
                ('business_function', 'department', 'unit'),
                ('job_function', 'position_group'),
                'reporting_to'
            )
        }),
        ('Vacancy Details', {
            'fields': (
                ('vacancy_type', 'urgency'),
                'expected_start_date',
                ('expected_salary_range_min', 'expected_salary_range_max')
            )
        }),
        ('Status Tracking', {
            'fields': (
                ('is_filled', 'filled_by', 'filled_date'),
                'created_by'
            )
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
    
    def is_filled_display(self, obj):
        if obj.is_filled:
            return format_html('<span style="color: green;">✓ Filled</span>')
        return format_html('<span style="color: orange;">○ Open</span>')
    is_filled_display.short_description = 'Status'
    is_filled_display.admin_order_field = 'is_filled'

# Headcount Summary Admin
@admin.register(HeadcountSummary)
class HeadcountSummaryAdmin(admin.ModelAdmin):
    list_display = ('summary_date', 'total_employees', 'active_employees', 'vacant_positions', 'created_at')
    list_filter = ('summary_date', 'created_at')
    ordering = ('-summary_date',)
    readonly_fields = (
        'created_at', 'headcount_by_function', 'headcount_by_department', 
        'headcount_by_position', 'headcount_by_status', 'contract_analysis'
    )
    
    fieldsets = (
        ('Summary Information', {
            'fields': (
                'summary_date',
                ('total_employees', 'active_employees', 'inactive_employees'),
                'vacant_positions'
            )
        }),
        ('Additional Metrics', {
            'fields': (
                ('avg_years_of_service', 'new_hires_month', 'departures_month'),
            )
        }),
        ('Detailed Breakdowns', {
            'fields': (
                'headcount_by_function',
                'headcount_by_department',
                'headcount_by_position',
                'headcount_by_status',
                'contract_analysis'
            ),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        })
    )
    
    actions = ['generate_current_summary']
    
    def generate_current_summary(self, request, queryset):
        """Generate a new headcount summary for today"""
        summary = HeadcountSummary.generate_summary()
        self.message_user(
            request, 
            f'Successfully generated headcount summary for {summary.summary_date}. '
            f'Total employees: {summary.total_employees}, Active: {summary.active_employees}'
        )
    generate_current_summary.short_description = 'Generate current headcount summary'

# Admin customizations
admin.site.site_header = "Almet HRIS Administration"
admin.site.site_title = "Almet HRIS Admin"
admin.site.index_title = "HR Management System"

# Custom admin CSS and JavaScript
class AdminStyleMixin:
    """Mixin to add custom styling to admin"""
    
    class Media:
        css = {
            'all': ('admin/css/custom_admin.css',)
        }
        js = ('admin/js/custom_admin.js',)

# Apply custom styling to all admin classes
for admin_class in [
    BusinessFunctionAdmin, DepartmentAdmin, UnitAdmin, JobFunctionAdmin,
    PositionGroupAdmin, EmployeeTagAdmin, EmployeeStatusAdmin, EmployeeAdmin,
    EmployeeActivityAdmin, EmployeeDocumentAdmin, VacantPositionAdmin,
    HeadcountSummaryAdmin
]:
    # Add custom styling mixin
    admin_class.__bases__ = admin_class.__bases__ + (AdminStyleMixin,)# api/admin.py - ENHANCED: Complete Django Admin with Soft Delete Support

from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from django.urls import reverse
from django.db.models import Count, Q
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from django.http import HttpResponse