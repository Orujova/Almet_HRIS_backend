# api/admin.py - FIXED: Complete version with all missing methods

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
class BusinessFunctionAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'employee_count', 'department_count', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'code', 'description')
    ordering = ('code', 'name')
    readonly_fields = ('created_at', 'updated_at')
    
    def employee_count(self, obj):
        count = obj.employees.filter(status__affects_headcount=True).count()
        if count > 0:
            url = reverse('admin:api_employee_changelist') + f'?business_function__id__exact={obj.id}'
            return format_html(
                '<a href="{}" style="color: #417690;">{} employees</a>',
                url, count
            )
        return '0 employees'
    employee_count.short_description = 'Active Employees'
    
    def department_count(self, obj):
        count = obj.departments.filter(is_active=True).count()
        if count > 0:
            url = reverse('admin:api_department_changelist') + f'?business_function__id__exact={obj.id}'
            return format_html(
                '<a href="{}" style="color: #417690;">{} departments</a>',
                url, count
            )
        return '0 departments'
    department_count.short_description = 'Departments'

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'business_function', 'head_display', 'employee_count', 'unit_count', 'is_active')
    list_filter = ('business_function', 'is_active', 'created_at')
    search_fields = ('name', 'business_function__name', 'business_function__code')
    autocomplete_fields = ['head_of_department']
    readonly_fields = ('created_at', 'updated_at')
    
    
    
    def head_display(self, obj):
        if obj.head_of_department:
            url = reverse('admin:api_employee_change', args=[obj.head_of_department.id])
            return format_html(
                '<a href="{}" style="color: #417690;">{}</a>',
                url, obj.head_of_department.full_name
            )
        return format_html('<span style="color: #999;">No Head</span>')
    head_display.short_description = 'Department Head'
    
    def employee_count(self, obj):
        count = obj.employees.filter(status__affects_headcount=True).count()
        if count > 0:
            url = reverse('admin:api_employee_changelist') + f'?department__id__exact={obj.id}'
            return format_html(
                '<a href="{}" style="color: #417690;">{} employees</a>',
                url, count
            )
        return '0 employees'
    employee_count.short_description = 'Active Employees'
    
    def unit_count(self, obj):
        count = obj.units.filter(is_active=True).count()
        if count > 0:
            url = reverse('admin:api_unit_changelist') + f'?department__id__exact={obj.id}'
            return format_html(
                '<a href="{}" style="color: #417690;">{} units</a>',
                url, count
            )
        return '0 units'
    unit_count.short_description = 'Units'

@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = ( 'name', 'department', 'business_function_name', 'unit_head_display', 'employee_count', 'is_active')
    list_filter = ('department__business_function', 'department', 'is_active', 'created_at')
    search_fields = ('name',  'department__name', 'department__business_function__name')
    ordering = ('department__business_function__code', 'department__name', 'name')
    autocomplete_fields = ['unit_head']
    readonly_fields = ('created_at', 'updated_at')
    
   
    
    def business_function_name(self, obj):
        return obj.department.business_function.name
    business_function_name.short_description = 'Business Function'
    
    def unit_head_display(self, obj):
        if obj.unit_head:
            url = reverse('admin:api_employee_change', args=[obj.unit_head.id])
            return format_html(
                '<a href="{}" style="color: #417690;">{}</a>',
                url, obj.unit_head.full_name
            )
        return format_html('<span style="color: #999;">No Head</span>')
    unit_head_display.short_description = 'Unit Head'
    
    def employee_count(self, obj):
        count = obj.employees.filter(status__affects_headcount=True).count()
        if count > 0:
            url = reverse('admin:api_employee_changelist') + f'?unit__id__exact={obj.id}'
            return format_html(
                '<a href="{}" style="color: #417690;">{} employees</a>',
                url, count
            )
        return '0 employees'
    employee_count.short_description = 'Active Employees'

@admin.register(JobFunction)
class JobFunctionAdmin(admin.ModelAdmin):
    list_display = ('name', 'employee_count', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'description')
    ordering = ('name',)
    readonly_fields = ('created_at', 'updated_at')
    
    def employee_count(self, obj):
        count = obj.employees.filter(status__affects_headcount=True).count()
        if count > 0:
            url = reverse('admin:api_employee_changelist') + f'?job_function__id__exact={obj.id}'
            return format_html(
                '<a href="{}" style="color: #417690;">{} employees</a>',
                url, count
            )
        return '0 employees'
    employee_count.short_description = 'Active Employees'

@admin.register(PositionGroup)
class PositionGroupAdmin(admin.ModelAdmin):
    list_display = ('hierarchy_display', 'name_display', 'grading_shorthand', 'employee_count', 'grading_levels_display', 'is_active')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name',)
    ordering = ('hierarchy_level',)
    readonly_fields = ('grading_shorthand', 'created_at', 'updated_at')
    
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
        levels = ['LD', 'LQ', 'M', 'UQ', 'UD']
        level_badges = []
        for level in levels:
            level_badges.append(f'<span style="background: #e3f2fd; color: #1976d2; padding: 2px 6px; border-radius: 4px; font-size: 10px; margin-right: 2px;">{obj.grading_shorthand}_{level}</span>')
        return format_html(''.join(level_badges))
    grading_levels_display.short_description = 'Grading Levels'
    
    def employee_count(self, obj):
        count = obj.employees.filter(status__affects_headcount=True).count()
        if count > 0:
            url = reverse('admin:api_employee_changelist') + f'?position_group__id__exact={obj.id}'
            return format_html(
                '<a href="{}" style="color: #417690;">{} employees</a>',
                url, count
            )
        return '0 employees'
    employee_count.short_description = 'Active Employees'

@admin.register(EmployeeTag)
class EmployeeTagAdmin(admin.ModelAdmin):
    list_display = ('name', 'tag_type', 'color_display', 'employee_count', 'is_active', 'created_at')
    list_filter = ('tag_type', 'is_active', 'created_at')
    search_fields = ('name',)
    ordering = ('tag_type', 'name')
    
    def color_display(self, obj):
        return format_html(
            '<div style="width: 20px; height: 20px; background-color: {}; border-radius: 3px; display: inline-block;"></div> {}',
            obj.color, obj.color
        )
    color_display.short_description = 'Color'
    
    def employee_count(self, obj):
        count = obj.employees.filter(status__affects_headcount=True).count()
        if count > 0:
            url = reverse('admin:api_employee_changelist') + f'?tags__id__exact={obj.id}'
            return format_html(
                '<a href="{}" style="color: #417690;">{} employees</a>',
                url, count
            )
        return '0 employees'
    employee_count.short_description = 'Tagged Employees'

@admin.register(EmployeeStatus)
class EmployeeStatusAdmin(admin.ModelAdmin):
    list_display = ('name', 'status_type', 'color_display', 'affects_headcount', 'allows_org_chart', 'employee_count', 'is_active')
    list_filter = ('status_type', 'affects_headcount', 'allows_org_chart', 'is_active', 'created_at')
    search_fields = ('name',)
    ordering = ('name',)
    readonly_fields = ('created_at', 'updated_at')
    
    def color_display(self, obj):
        return format_html(
            '<div style="width: 20px; height: 20px; background-color: {}; border-radius: 3px; display: inline-block; margin-right: 8px;"></div><span style="font-family: monospace;">{}</span>',
            obj.color, obj.color
        )
    color_display.short_description = 'Color'
    
    def employee_count(self, obj):
        count = obj.employees.count()
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
class EmployeeAdmin(admin.ModelAdmin):
    list_display = (
        'employee_id', 'full_name_display', 'email_display', 'position_display', 
        'business_function_display', 'status_display', 'grading_display', 
        'line_manager_display', 'start_date', 'contract_status_display', 'is_visible_in_org_chart'
    )
    list_filter = (
        'status', 'business_function', 'department', 'position_group', 
        'contract_duration', 'start_date', 'is_visible_in_org_chart', 'created_at'
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
    
    def full_name_display(self, obj):
        url = reverse('admin:api_employee_change', args=[obj.id])
        return format_html(
            '<a href="{}" style="color: #417690; font-weight: bold;">{}</a>',
            url, obj.full_name
        )
    full_name_display.short_description = 'Name'
    full_name_display.admin_order_field = 'full_name'
    
    def email_display(self, obj):
        if obj.user and obj.user.email:
            return format_html(
                '<a href="mailto:{}" style="color: #417690;">{}</a>',
                obj.user.email, obj.user.email
            )
        return '-'
    email_display.short_description = 'Email'
    
    def position_display(self, obj):
        return format_html(
            '<div><strong>{}</strong><br><small style="color: #666;">{}</small></div>',
            obj.job_title,
            obj.position_group.get_name_display()
        )
    position_display.short_description = 'Position'
    
    def business_function_display(self, obj):
        return format_html(
            '<div><strong>{}</strong><br><small style="color: #666;">{}</small></div>',
            obj.business_function.code,
            obj.department.name
        )
    business_function_display.short_description = 'Function/Department'
    
    def status_display(self, obj):
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 8px; border-radius: 10px; font-size: 11px; font-weight: bold;">{}</span>',
            obj.status.color, obj.status.name
        )
    status_display.short_description = 'Status'
    status_display.admin_order_field = 'status__name'
    
    def grading_display(self, obj):
        if obj.grading_level:
            return format_html(
                '<div><strong style="color: #1976d2;">{}</strong><br><small style="color: #666;">{}</small></div>',
                obj.get_grading_display(),
                obj.grade or 'No Grade'
            )
        return format_html('<span style="color: #999;">No Grading</span>')
    grading_display.short_description = 'Grading'
    
    def line_manager_display(self, obj):
        if obj.line_manager:
            url = reverse('admin:api_employee_change', args=[obj.line_manager.id])
            return format_html(
                '<a href="{}" style="color: #417690;">{}</a><br><small style="color: #666;">{}</small>',
                url, obj.line_manager.full_name, obj.line_manager.employee_id
            )
        return format_html('<span style="color: #999;">No Manager</span>')
    line_manager_display.short_description = 'Line Manager'
    
    def contract_status_display(self, obj):
        duration_display = obj.get_contract_duration_display()
        if obj.contract_end_date:
            days_left = (obj.contract_end_date - date.today()).days
            if days_left <= 30:
                color = '#dc3545'  # Red
            elif days_left <= 90:
                color = '#ffc107'  # Yellow
            else:
                color = '#28a745'  # Green
            
            return format_html(
                '<div style="color: {};">{}<br><small>Ends: {}</small></div>',
                color, duration_display, obj.contract_end_date.strftime('%d/%m/%Y')
            )
        return duration_display
    contract_status_display.short_description = 'Contract'
    
    def years_of_service_display(self, obj):
        return f"{obj.years_of_service} years"
    years_of_service_display.short_description = 'Years of Service'
    
    def direct_reports_count_display(self, obj):
        count = obj.get_direct_reports_count()
        if count > 0:
            url = reverse('admin:api_employee_changelist') + f'?line_manager__id__exact={obj.id}'
            return format_html(
                '<a href="{}" style="color: #417690;">{} reports</a>',
                url, count
            )
        return '0 reports'
    direct_reports_count_display.short_description = 'Direct Reports'
    
    actions = ['export_employees_csv', 'mark_org_chart_visible', 'mark_org_chart_hidden', 'update_contract_status']
    
    def export_employees_csv(self, request, queryset):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="employees_{date.today()}.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Employee ID', 'Name', 'Email', 'Job Title', 'Business Function',
            'Department', 'Unit', 'Position Group', 'Grade', 'Status',
            'Line Manager', 'Start Date', 'Contract Duration', 'Phone'
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
                employee.phone or ''
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
        return format_html(
            '<a href="{}" style="color: #417690;">{}</a><br><small style="color: #666;">{}</small>',
            url, obj.employee.full_name, obj.employee.employee_id
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

# Employee Document Admin - FIXED: All missing methods added
@admin.register(EmployeeDocument)
class EmployeeDocumentAdmin(admin.ModelAdmin):
    list_display = ('name', 'employee_display', 'document_type', 'file_size_display', 'uploaded_by_display', 'uploaded_at')
    list_filter = ('document_type', 'uploaded_at', 'uploaded_by')
    search_fields = ('name', 'employee__full_name', 'employee__employee_id')
    ordering = ('-uploaded_at',)
    readonly_fields = ('uploaded_at', 'file_size', 'mime_type')
    autocomplete_fields = ['employee', 'uploaded_by']
    
    def employee_display(self, obj):
        """Display employee with link to their profile"""
        url = reverse('admin:api_employee_change', args=[obj.employee.id])
        return format_html(
            '<a href="{}" style="color: #417690;">{}</a><br><small style="color: #666;">{}</small>',
            url, obj.employee.full_name, obj.employee.employee_id
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

# If VacantPosition and HeadcountSummary models exist, add their admins
try:
    from .models import VacantPosition
    
    @admin.register(VacantPosition)
    class VacantPositionAdmin(admin.ModelAdmin):
        list_display = ('position_id', 'title', 'business_function', 'department', 'urgency', 'is_filled', 'created_at')
        list_filter = ('urgency', 'is_filled', 'business_function', 'department', 'created_at')
        search_fields = ('position_id', 'title', 'description')
        ordering = ('-created_at',)
        readonly_fields = ('created_at', 'updated_at')
        
except ImportError:
    pass

try:
    from .models import HeadcountSummary
    
    @admin.register(HeadcountSummary)
    class HeadcountSummaryAdmin(admin.ModelAdmin):
        list_display = ('summary_date', 'total_employees', 'active_employees', 'vacant_positions', 'created_at')
        list_filter = ('summary_date', 'created_at')
        ordering = ('-summary_date',)
        readonly_fields = ('created_at',)
        
except ImportError:
    pass

# Admin customizations
admin.site.site_header = "Almet HRIS Administration"
admin.site.site_title = "Almet HRIS Admin"
admin.site.index_title = "HR Management System"