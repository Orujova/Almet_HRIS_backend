# api/admin.py

from django.contrib import admin
from django.utils.html import format_html
from .models import (
    MicrosoftUser, Employee, BusinessFunction, Department, Unit, 
    JobFunction, PositionGroup, Office, EmployeeTag, EmployeeDocument, 
    EmployeeActivity
)

@admin.register(MicrosoftUser)
class MicrosoftUserAdmin(admin.ModelAdmin):
    list_display = ('user', 'microsoft_id', 'user_email')
    search_fields = ('user__username', 'user__email', 'microsoft_id')
    readonly_fields = ('microsoft_id',)
    
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'Email'

@admin.register(BusinessFunction)
class BusinessFunctionAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'code')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'business_function', 'is_active', 'employee_count')
    list_filter = ('business_function', 'is_active', 'created_at')
    search_fields = ('name', 'business_function__name')
    readonly_fields = ('created_at', 'updated_at')
    
    def employee_count(self, obj):
        return obj.employees.count()
    employee_count.short_description = 'Employees'

@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = ('name', 'department', 'business_function', 'is_active')
    list_filter = ('department__business_function', 'department', 'is_active')
    search_fields = ('name', 'department__name')
    readonly_fields = ('created_at', 'updated_at')
    
    def business_function(self, obj):
        return obj.department.business_function.name
    business_function.short_description = 'Business Function'

@admin.register(JobFunction)
class JobFunctionAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active', 'employee_count', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name',)
    readonly_fields = ('created_at', 'updated_at')
    
    def employee_count(self, obj):
        return obj.employees.count()
    employee_count.short_description = 'Employees'

@admin.register(PositionGroup)
class PositionGroupAdmin(admin.ModelAdmin):
    list_display = ('get_name_display', 'hierarchy_level', 'is_active', 'employee_count')
    list_filter = ('is_active', 'hierarchy_level')
    search_fields = ('name',)
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('hierarchy_level',)
    
    def employee_count(self, obj):
        return obj.employees.count()
    employee_count.short_description = 'Employees'

@admin.register(Office)
class OfficeAdmin(admin.ModelAdmin):
    list_display = ('name', 'business_function', 'is_active', 'employee_count')
    list_filter = ('business_function', 'is_active')
    search_fields = ('name', 'business_function__name')
    readonly_fields = ('created_at', 'updated_at')
    
    def employee_count(self, obj):
        return obj.employees.count()
    employee_count.short_description = 'Employees'

@admin.register(EmployeeTag)
class EmployeeTagAdmin(admin.ModelAdmin):
    list_display = ('name', 'tag_type', 'color_preview', 'is_active', 'employee_count')
    list_filter = ('tag_type', 'is_active')
    search_fields = ('name',)
    readonly_fields = ('created_at', 'updated_at')
    
    def color_preview(self, obj):
        return format_html(
            '<span style="background-color: {}; padding: 2px 6px; border-radius: 3px; color: white;">{}</span>',
            obj.color,
            obj.color
        )
    color_preview.short_description = 'Color'
    
    def employee_count(self, obj):
        return obj.employees.count()
    employee_count.short_description = 'Employees'

class EmployeeDocumentInline(admin.TabularInline):
    model = EmployeeDocument
    extra = 0
    readonly_fields = ('uploaded_at', 'uploaded_by')
    fields = ('name', 'document_type', 'file_path', 'uploaded_at', 'uploaded_by')

class EmployeeActivityInline(admin.TabularInline):
    model = EmployeeActivity
    extra = 0
    readonly_fields = ('timestamp', 'performed_by')
    fields = ('activity_type', 'description', 'timestamp', 'performed_by')
    ordering = ('-timestamp',)
    
    def has_add_permission(self, request, obj=None):
        return False  # Activities are created automatically

@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = (
        'employee_id', 'get_full_name', 'department', 'position_group', 
        'status', 'start_date', 'is_visible_in_org_chart'
    )
    list_filter = (
        'status', 'business_function', 'department', 'position_group', 
        'office', 'is_visible_in_org_chart', 'start_date'
    )
    search_fields = (
        'employee_id', 'user__first_name', 'user__last_name', 
        'user__email', 'job_title'
    )
    readonly_fields = ('created_at', 'updated_at', 'created_by', 'updated_by')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('employee_id', 'user', 'date_of_birth', 'phone', 'address', 'emergency_contact')
        }),
        ('Job Information', {
            'fields': (
                'business_function', 'department', 'unit', 'job_function', 
                'job_title', 'position_group', 'grade', 'office'
            )
        }),
        ('Employment', {
            'fields': ('start_date', 'end_date', 'line_manager', 'status')
        }),
        ('Settings', {
            'fields': ('is_visible_in_org_chart', 'tags', 'notes')
        }),
        ('Audit Information', {
            'fields': ('created_at', 'updated_at', 'created_by', 'updated_by'),
            'classes': ('collapse',)
        }),
    )
    
    filter_horizontal = ('tags',)
    inlines = [EmployeeDocumentInline, EmployeeActivityInline]
    
    def get_full_name(self, obj):
        return obj.full_name
    get_full_name.short_description = 'Name'
    get_full_name.admin_order_field = 'user__first_name'
    
    def save_model(self, request, obj, form, change):
        if not change:  # Creating new employee
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)
        
        # Create activity log
        activity_type = 'UPDATED' if change else 'CREATED'
        EmployeeActivity.objects.create(
            employee=obj,
            activity_type=activity_type,
            description=f"Employee {obj.full_name} was {activity_type.lower()} via admin panel",
            performed_by=request.user
        )

@admin.register(EmployeeDocument)
class EmployeeDocumentAdmin(admin.ModelAdmin):
    list_display = ('name', 'employee', 'document_type', 'uploaded_at', 'uploaded_by')
    list_filter = ('document_type', 'uploaded_at')
    search_fields = ('name', 'employee__employee_id', 'employee__user__first_name', 'employee__user__last_name')
    readonly_fields = ('uploaded_at', 'uploaded_by')
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.uploaded_by = request.user
        super().save_model(request, obj, form, change)

@admin.register(EmployeeActivity)
class EmployeeActivityAdmin(admin.ModelAdmin):
    list_display = ('employee', 'activity_type', 'timestamp', 'performed_by')
    list_filter = ('activity_type', 'timestamp')
    search_fields = ('employee__employee_id', 'employee__user__first_name', 'employee__user__last_name', 'description')
    readonly_fields = ('timestamp',)
    ordering = ('-timestamp',)
    
    def has_add_permission(self, request):
        return False  # Activities should be created automatically
    
    def has_change_permission(self, request, obj=None):
        return False  # Activities should not be editable
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser  # Only superusers can delete activities