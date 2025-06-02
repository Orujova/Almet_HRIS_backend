# api/admin.py

from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from django.db import models
from django.forms import TextInput, Textarea
from .models import (
    MicrosoftUser, Employee, BusinessFunction, Department, Unit, 
    JobFunction, PositionGroup, EmployeeTag, EmployeeStatus, 
    EmployeeDocument, EmployeeActivity
)

# Custom admin styling
class BaseModelAdmin(admin.ModelAdmin):
    """Base admin class with common styling"""
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

@admin.register(BusinessFunction)
class BusinessFunctionAdmin(BaseModelAdmin):
    list_display = ('name', 'code', 'is_active', 'employee_count', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'code')
    readonly_fields = ('created_at', 'updated_at')
    list_editable = ('is_active',)
    ordering = ('name',)
    
    def employee_count(self, obj):
        count = obj.employees.count()
        if count > 0:
            return format_html(
                '<a href="/admin/api/employee/?business_function__id__exact={}" style="color: #417690; text-decoration: none;">{} employees</a>',
                obj.id, count
            )
        return '0 employees'
    employee_count.short_description = 'Employees'

@admin.register(Department)
class DepartmentAdmin(BaseModelAdmin):
    list_display = ('name', 'business_function', 'is_active', 'employee_count', 'created_at')
    list_filter = ('business_function', 'is_active', 'created_at')
    search_fields = ('name', 'business_function__name')
    readonly_fields = ('created_at', 'updated_at')
    list_editable = ('is_active',)
    ordering = ('business_function__name', 'name')
    autocomplete_fields = ['business_function']
    
    def employee_count(self, obj):
        count = obj.employees.count()
        if count > 0:
            return format_html(
                '<a href="/admin/api/employee/?department__id__exact={}" style="color: #417690; text-decoration: none;">{} employees</a>',
                obj.id, count
            )
        return '0 employees'
    employee_count.short_description = 'Employees'

@admin.register(Unit)
class UnitAdmin(BaseModelAdmin):
    list_display = ('name', 'department', 'business_function', 'is_active', 'employee_count')
    list_filter = ('department__business_function', 'department', 'is_active')
    search_fields = ('name', 'department__name', 'department__business_function__name')
    readonly_fields = ('created_at', 'updated_at')
    list_editable = ('is_active',)
    ordering = ('department__business_function__name', 'department__name', 'name')
    autocomplete_fields = ['department']
    
    def business_function(self, obj):
        return obj.department.business_function.name
    business_function.short_description = 'Business Function'
    business_function.admin_order_field = 'department__business_function__name'
    
    def employee_count(self, obj):
        count = obj.employees.count()
        if count > 0:
            return format_html(
                '<a href="/admin/api/employee/?unit__id__exact={}" style="color: #417690; text-decoration: none;">{} employees</a>',
                obj.id, count
            )
        return '0 employees'
    employee_count.short_description = 'Employees'

@admin.register(JobFunction)
class JobFunctionAdmin(BaseModelAdmin):
    list_display = ('name', 'is_active', 'employee_count', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name',)
    readonly_fields = ('created_at', 'updated_at')
    list_editable = ('is_active',)
    ordering = ('name',)
    
    def employee_count(self, obj):
        count = obj.employees.count()
        if count > 0:
            return format_html(
                '<a href="/admin/api/employee/?job_function__id__exact={}" style="color: #417690; text-decoration: none;">{} employees</a>',
                obj.id, count
            )
        return '0 employees'
    employee_count.short_description = 'Employees'

@admin.register(PositionGroup)
class PositionGroupAdmin(BaseModelAdmin):
    list_display = ('get_name_display', 'hierarchy_level', 'is_active', 'employee_count', 'hierarchy_badge')
    list_filter = ('is_active', 'hierarchy_level')
    search_fields = ('name',)
    readonly_fields = ('created_at', 'updated_at')
    list_editable = ('is_active', 'hierarchy_level')
    ordering = ('hierarchy_level',)
    
    def hierarchy_badge(self, obj):
        colors = {
            1: '#8B0000',  # Dark red for VC
            2: '#DC143C',  # Crimson for Director
            3: '#FF6347',  # Tomato for Manager
            4: '#FFA500',  # Orange for HOD
            5: '#FFD700',  # Gold for Senior Specialist
            6: '#9ACD32',  # Yellow-green for Specialist
            7: '#32CD32',  # Lime green for Junior Specialist
            8: '#808080',  # Gray for Blue Collar
        }
        color = colors.get(obj.hierarchy_level, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: bold;">Level {}</span>',
            color, obj.hierarchy_level
        )
    hierarchy_badge.short_description = 'Level'
    
    def employee_count(self, obj):
        count = obj.employees.count()
        if count > 0:
            return format_html(
                '<a href="/admin/api/employee/?position_group__id__exact={}" style="color: #417690; text-decoration: none;">{} employees</a>',
                obj.id, count
            )
        return '0 employees'
    employee_count.short_description = 'Employees'

@admin.register(EmployeeTag)
class EmployeeTagAdmin(BaseModelAdmin):
    list_display = ('name', 'tag_type', 'color_preview', 'color', 'is_active', 'employee_count')
    list_filter = ('tag_type', 'is_active')
    search_fields = ('name',)
    readonly_fields = ('created_at', 'updated_at')
    list_editable = ('is_active', 'color')
    ordering = ('tag_type', 'name')
    
    def color_preview(self, obj):
        return format_html(
            '<div style="width: 20px; height: 20px; background-color: {}; border-radius: 50%; display: inline-block; border: 1px solid #ddd; margin-right: 5px;"></div>{}',
            obj.color, obj.color
        )
    color_preview.short_description = 'Color'
    
    def employee_count(self, obj):
        count = obj.employees.count()
        if count > 0:
            return format_html(
                '<a href="/admin/api/employee/?tags__id__exact={}" style="color: #417690; text-decoration: none;">{} employees</a>',
                obj.id, count
            )
        return '0 employees'
    employee_count.short_description = 'Employees'

@admin.register(EmployeeStatus)
class EmployeeStatusAdmin(BaseModelAdmin):
    list_display = ('name', 'color_preview', 'color', 'is_active', 'employee_count', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name',)
    readonly_fields = ('created_at', 'updated_at')
    list_editable = ('is_active', 'color')
    ordering = ('name',)
    
    def color_preview(self, obj):
        return format_html(
            '<span style="background-color: {}; color: white; padding: 4px 12px; border-radius: 15px; font-weight: bold; font-size: 12px;">{}</span>',
            obj.color, obj.name
        )
    color_preview.short_description = 'Status Preview'
    
    def employee_count(self, obj):
        count = obj.employees.count()
        if count > 0:
            return format_html(
                '<a href="/admin/api/employee/?status__id__exact={}" style="color: #417690; text-decoration: none;">{} employees</a>',
                obj.id, count
            )
        return '0 employees'
    employee_count.short_description = 'Employees'

class EmployeeDocumentInline(admin.TabularInline):
    model = EmployeeDocument
    extra = 0
    readonly_fields = ('uploaded_at', 'uploaded_by', 'file_size', 'mime_type')
    fields = ('name', 'document_type', 'file_path', 'file_size', 'mime_type', 'uploaded_at', 'uploaded_by')
    can_delete = True

class EmployeeActivityInline(admin.TabularInline):
    model = EmployeeActivity
    extra = 0
    readonly_fields = ('timestamp', 'performed_by', 'activity_type', 'description')
    fields = ('activity_type', 'description', 'timestamp', 'performed_by')
    ordering = ('-timestamp',)
    max_num = 10  # Show only last 10 activities
    
    def has_add_permission(self, request, obj=None):
        return False  # Activities are created automatically

@admin.register(Employee)
class EmployeeAdmin(BaseModelAdmin):
    list_display = (
        'employee_id', 'get_full_name', 'email', 'gender', 'department', 
        'position_group', 'status_badge', 'contract_info', 'start_date', 
        'years_of_service_display', 'is_visible_in_org_chart'
    )
    list_filter = (
        'status', 'gender', 'business_function', 'department', 'position_group', 
        'contract_duration', 'is_visible_in_org_chart', 'start_date', 'grade'
    )
    search_fields = (
        'employee_id', 'user__first_name', 'user__last_name', 
        'user__email', 'job_title', 'full_name', 'phone'
    )
    readonly_fields = (
        'full_name', 'status', 'current_status_display', 'years_of_service', 
        'direct_reports_count', 'created_at', 'updated_at', 'created_by', 'updated_by'
    )
    list_editable = ('is_visible_in_org_chart',)
    
    autocomplete_fields = [
        'user', 'business_function', 'department', 'unit', 
        'job_function', 'position_group', 'line_manager', 'status'
    ]
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'employee_id', 'user', 'full_name', 'date_of_birth', 
                'gender', 'phone', 'address', 'emergency_contact', 'profile_image'
            ),
            'classes': ('wide',)
        }),
        ('Organizational Structure', {
            'fields': (
                'business_function', 'department', 'unit', 'job_function', 
                'job_title', 'position_group', 'grade', 'line_manager'
            ),
            'classes': ('wide',)
        }),
        ('Employment & Contract', {
            'fields': (
                'start_date', 'end_date', 'contract_duration', 'contract_start_date'
            ),
            'classes': ('wide',)
        }),
        ('Status (Avtomatik)', {
            'fields': ('status', 'current_status_display'),
            'classes': ('wide',),
            'description': 'Status avtomatik olaraq contract və tarix əsasında təyin edilir'
        }),
        ('Settings & Tags', {
            'fields': ('is_visible_in_org_chart', 'tags', 'notes'),
            'classes': ('wide',)
        }),
        ('Statistics', {
            'fields': ('years_of_service', 'direct_reports_count'),
            'classes': ('collapse',)
        }),
        ('Audit Information', {
            'fields': ('created_at', 'updated_at', 'created_by', 'updated_by'),
            'classes': ('collapse',)
        }),
    )
    
    filter_horizontal = ('tags',)
    inlines = [EmployeeDocumentInline, EmployeeActivityInline]
    
    actions = ['update_statuses', 'make_visible_in_org_chart', 'hide_from_org_chart']
    
    def get_full_name(self, obj):
        return obj.full_name
    get_full_name.short_description = 'Full Name'
    get_full_name.admin_order_field = 'full_name'
    
    def email(self, obj):
        return obj.user.email if obj.user else '-'
    email.short_description = 'Email'
    email.admin_order_field = 'user__email'
    
    def status_badge(self, obj):
        if obj.status:
            return format_html(
                '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 10px; font-size: 11px; font-weight: bold;">{}</span>',
                obj.status.color, obj.status.name
            )
        return '-'
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status__name'
    
    def contract_info(self, obj):
        duration_display = obj.get_contract_duration_display()
        if obj.contract_duration == 'PERMANENT':
            color = '#28a745'
        elif obj.contract_duration == '1_YEAR':
            color = '#17a2b8'
        else:
            color = '#ffc107'
        
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 6px; border-radius: 8px; font-size: 10px;">{}</span>',
            color, duration_display
        )
    contract_info.short_description = 'Contract'
    contract_info.admin_order_field = 'contract_duration'
    
    def years_of_service_display(self, obj):
        years = obj.years_of_service
        if years >= 1:
            return f"{years:.1f} years"
        else:
            days = int(years * 365)
            return f"{days} days"
    years_of_service_display.short_description = 'Service'
    years_of_service_display.admin_order_field = 'start_date'
    
    def save_model(self, request, obj, form, change):
        if not change:  # Creating new employee
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)
        
        # Status avtomatik təyin ediləcək signal vasitəsilə
        # Əlavə activity log (signal-dan əlavə)
        activity_type = 'UPDATED' if change else 'CREATED'
        EmployeeActivity.objects.create(
            employee=obj,
            activity_type=activity_type,
            description=f"Employee {obj.full_name} was {activity_type.lower()} via admin panel",
            performed_by=request.user,
            metadata={
                'admin_action': True,
                'contract_duration': obj.contract_duration,
                'via_admin_panel': True
            }
        )
    
    def update_statuses(self, request, queryset):
        """Admin action to update employee statuses"""
        updated_count = 0
        for employee in queryset:
            old_status = employee.status.name if employee.status else None
            employee.update_automatic_status()
            employee.refresh_from_db()
            new_status = employee.status.name if employee.status else None
            
            if old_status != new_status:
                updated_count += 1
                EmployeeActivity.objects.create(
                    employee=employee,
                    activity_type='STATUS_CHANGED',
                    description=f"Status updated from {old_status} to {new_status} via admin bulk action",
                    performed_by=request.user,
                    metadata={'admin_bulk_action': True, 'old_status': old_status, 'new_status': new_status}
                )
        
        self.message_user(request, f'Successfully updated {updated_count} employee statuses.')
    update_statuses.short_description = "Update automatic statuses for selected employees"
    
    def make_visible_in_org_chart(self, request, queryset):
        """Admin action to make employees visible in org chart"""
        updated = queryset.update(is_visible_in_org_chart=True)
        for employee in queryset:
            EmployeeActivity.objects.create(
                employee=employee,
                activity_type='ORG_CHART_VISIBILITY_CHANGED',
                description=f"Made visible in org chart via admin bulk action",
                performed_by=request.user,
                metadata={'admin_bulk_action': True, 'new_visibility': True}
            )
        self.message_user(request, f'Successfully made {updated} employees visible in org chart.')
    make_visible_in_org_chart.short_description = "Make selected employees visible in org chart"
    
    def hide_from_org_chart(self, request, queryset):
        """Admin action to hide employees from org chart"""
        updated = queryset.update(is_visible_in_org_chart=False)
        for employee in queryset:
            EmployeeActivity.objects.create(
                employee=employee,
                activity_type='ORG_CHART_VISIBILITY_CHANGED',
                description=f"Hidden from org chart via admin bulk action",
                performed_by=request.user,
                metadata={'admin_bulk_action': True, 'new_visibility': False}
            )
        self.message_user(request, f'Successfully hid {updated} employees from org chart.')
    hide_from_org_chart.short_description = "Hide selected employees from org chart"

@admin.register(EmployeeDocument)
class EmployeeDocumentAdmin(BaseModelAdmin):
    list_display = ('name', 'employee_info', 'document_type', 'file_size_display', 'uploaded_at', 'uploaded_by')
    list_filter = ('document_type', 'uploaded_at', 'mime_type')
    search_fields = ('name', 'employee__employee_id', 'employee__user__first_name', 'employee__user__last_name')
    readonly_fields = ('uploaded_at', 'uploaded_by', 'file_size', 'mime_type')
    autocomplete_fields = ['employee']
    ordering = ('-uploaded_at',)
    
    def employee_info(self, obj):
        return format_html(
            '<a href="/admin/api/employee/{}/change/" style="color: #417690; text-decoration: none;">{} - {}</a>',
            obj.employee.id, obj.employee.employee_id, obj.employee.full_name
        )
    employee_info.short_description = 'Employee'
    employee_info.admin_order_field = 'employee__employee_id'
    
    def file_size_display(self, obj):
        if obj.file_size:
            if obj.file_size < 1024:
                return f"{obj.file_size} B"
            elif obj.file_size < 1024 * 1024:
                return f"{obj.file_size / 1024:.1f} KB"
            else:
                return f"{obj.file_size / (1024 * 1024):.1f} MB"
        return '-'
    file_size_display.short_description = 'File Size'
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.uploaded_by = request.user
        super().save_model(request, obj, form, change)

@admin.register(EmployeeActivity)
class EmployeeActivityAdmin(admin.ModelAdmin):
    list_display = ('employee_info', 'activity_type', 'timestamp', 'performed_by', 'description_short')
    list_filter = ('activity_type', 'timestamp', 'performed_by')
    search_fields = ('employee__employee_id', 'employee__user__first_name', 'employee__user__last_name', 'description')
    readonly_fields = ('timestamp', 'metadata')
    ordering = ('-timestamp',)
    date_hierarchy = 'timestamp'
    
    def employee_info(self, obj):
        return format_html(
            '<a href="/admin/api/employee/{}/change/" style="color: #417690; text-decoration: none;">{} - {}</a>',
            obj.employee.id, obj.employee.employee_id, obj.employee.full_name
        )
    employee_info.short_description = 'Employee'
    employee_info.admin_order_field = 'employee__employee_id'
    
    def description_short(self, obj):
        if len(obj.description) > 100:
            return f"{obj.description[:100]}..."
        return obj.description
    description_short.short_description = 'Description'
    
    def has_add_permission(self, request):
        return False  # Activities should be created automatically
    
    def has_change_permission(self, request, obj=None):
        return False  # Activities should not be editable
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser  # Only superusers can delete activities

# Customize admin site headers
admin.site.site_header = "Employee Management System"
admin.site.site_title = "EMS Admin"
admin.site.index_title = "Welcome to Employee Management System Administration"

# Add custom CSS for better styling
class Media:
    css = {
        'all': ('admin/css/custom_admin.css',)
    }

# Custom admin actions for bulk operations
def export_employees_csv(modeladmin, request, queryset):
    """Export selected employees to CSV"""
    import csv
    from django.http import HttpResponse
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="employees.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Employee ID', 'Full Name', 'Email', 'Department', 'Position', 
        'Start Date', 'Contract Duration', 'Status', 'Line Manager'
    ])
    
    for employee in queryset:
        writer.writerow([
            employee.employee_id,
            employee.full_name,
            employee.user.email if employee.user else '',
            employee.department.name,
            employee.position_group.get_name_display(),
            employee.start_date,
            employee.get_contract_duration_display(),
            employee.status.name if employee.status else '',
            employee.line_manager.full_name if employee.line_manager else ''
        ])
    
    return response

export_employees_csv.short_description = "Export selected employees to CSV"

# Add the action to EmployeeAdmin
EmployeeAdmin.actions.append(export_employees_csv)