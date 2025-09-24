# api/vacation_admin.py - Enhanced

from django.contrib import admin
from django.utils.html import format_html
from django.db import models
from django.forms import TextInput, Textarea
from django.urls import reverse
from django.utils.safestring import mark_safe
from .vacation_models import *

@admin.register(VacationSetting)
class VacationSettingAdmin(admin.ModelAdmin):
    list_display = [
        'id', 
        'is_active_display', 
        'default_hr_representative', 
        'allow_negative_balance', 
        'max_schedule_edits', 
        'notification_settings_display',
        'created_at'
    ]
    list_filter = ['is_active', 'allow_negative_balance']
    list_editable = ['allow_negative_balance', 'max_schedule_edits']
    
    fieldsets = (
        ('Production Calendar', {
            'fields': ('non_working_days',),
            'description': 'Qeyri-iş günləri JSON formatında: ["2025-01-01", "2025-03-08"]'
        }),
        ('Default Settings', {
            'fields': ('default_hr_representative', 'allow_negative_balance', 'max_schedule_edits'),
            'classes': ('wide',)
        }),
        ('Notification Settings', {
            'fields': ('notification_days_before', 'notification_frequency'),
            'classes': ('collapse',)
        }),
        ('System', {
            'fields': ('is_active', 'created_by'),
            'classes': ('collapse',)
        })
    )
    
    readonly_fields = ['created_by']
    
    formfield_overrides = {
        models.JSONField: {'widget': Textarea(attrs={'rows': 4, 'cols': 60})},
    }
    
    def is_active_display(self, obj):
        if obj.is_active:
            return format_html(
                '<span style="color: green; font-weight: bold;">✓ Active</span>'
            )
        return format_html(
            '<span style="color: red;">✗ Inactive</span>'
        )
    is_active_display.short_description = 'Status'
    
    def notification_settings_display(self, obj):
        return f"{obj.notification_days_before} days before, {obj.notification_frequency}x"
    notification_settings_display.short_description = 'Notifications'
    
    def save_model(self, request, obj, form, change):
        if not obj.created_by:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(VacationType)
class VacationTypeAdmin(admin.ModelAdmin):
    list_display = [
        'name', 
        'code', 
        'color_display', 
        'requires_approval', 
        'affects_balance',
        'max_consecutive_days',
        'is_active_display', 
        'created_at'
    ]
    list_filter = ['is_active', 'requires_approval', 'affects_balance']
    list_editable = ['requires_approval', 'affects_balance', 'max_consecutive_days']
    search_fields = ['name', 'code', 'description']
    ordering = ['name']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'code', 'description', 'color')
        }),
        ('Settings', {
            'fields': ('requires_approval', 'affects_balance', 'max_consecutive_days')
        }),
        ('Status', {
            'fields': ('is_active',)
        })
    )
    
    def color_display(self, obj):
        return format_html(
            '<span style="background-color: {}; padding: 5px 15px; color: white; border-radius: 3px; font-weight: bold;">{}</span>',
            obj.color, obj.color
        )
    color_display.short_description = 'Color'
    
    def is_active_display(self, obj):
        if obj.is_active:
            return format_html('<span style="color: green;">✓</span>')
        return format_html('<span style="color: red;">✗</span>')
    is_active_display.short_description = 'Active'


@admin.register(EmployeeVacationBalance)
class EmployeeVacationBalanceAdmin(admin.ModelAdmin):
    list_display = [
        'employee_link',
        'employee_department',
        'year', 
        'total_balance_display', 
        'used_days', 
        'scheduled_days', 
        'remaining_balance_display',
        'should_be_planned_display',
        'updated_at'
    ]
    list_filter = [
        'year', 
        'employee__department', 
        'employee__business_function'
    ]
    search_fields = [
        'employee__full_name', 
        'employee__employee_id',
        'employee__email'
    ]
    ordering = ['-year', 'employee__full_name']
    
    fieldsets = (
        ('Employee & Year', {
            'fields': ('employee', 'year')
        }),
        ('Balance Details', {
            'fields': (
                ('start_balance', 'yearly_balance'),
                ('used_days', 'scheduled_days')
            ),
            'description': 'Total Balance = Start Balance + Yearly Balance'
        }),
        ('Calculated Fields', {
            'fields': ('total_balance_display', 'remaining_balance_display', 'should_be_planned_display'),
            'classes': ('collapse',),
            'description': 'These are calculated automatically'
        }),
        ('System', {
            'fields': ('updated_by',),
            'classes': ('collapse',)
        })
    )
    
    readonly_fields = [
        'total_balance_display', 
        'remaining_balance_display', 
        'should_be_planned_display',
        'updated_by'
    ]
    
    def employee_link(self, obj):
        url = reverse('admin:api_employee_change', args=[obj.employee.pk])
        return format_html('<a href="{}">{}</a>', url, obj.employee.full_name)
    employee_link.short_description = 'Employee'
    
    def employee_department(self, obj):
        return obj.employee.department.name if obj.employee.department else '-'
    employee_department.short_description = 'Department'
    
    def total_balance_display(self, obj):
        return f"{obj.total_balance} days"
    total_balance_display.short_description = 'Total Balance'
    
    def remaining_balance_display(self, obj):
        remaining = obj.remaining_balance
        if remaining < 0:
            color = 'red'
            icon = '⚠️'
        elif remaining < 5:
            color = 'orange'
            icon = '⚡'
        else:
            color = 'green'
            icon = '✅'
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{} {} days</span>', 
            color, icon, remaining
        )
    remaining_balance_display.short_description = 'Remaining Balance'
    
    def should_be_planned_display(self, obj):
        should_plan = obj.should_be_planned
        if should_plan > 10:
            color = 'red'
            icon = '📅'
        elif should_plan > 5:
            color = 'orange'
            icon = '⏰'
        else:
            color = 'green'
            icon = '✓'
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{} {} days</span>', 
            color, icon, should_plan
        )
    should_be_planned_display.short_description = 'Should Plan'
    
    def save_model(self, request, obj, form, change):
        if not obj.updated_by:
            obj.updated_by = request.user
        super().save_model(request, obj, form, change)
    
    # Bulk actions
    actions = ['bulk_set_yearly_balance']
    
    def bulk_set_yearly_balance(self, request, queryset):
        """Bulk action to set yearly balance"""
        # This would need a custom form, simplified for now
        count = queryset.update(yearly_balance=28, updated_by=request.user)
        self.message_user(request, f"{count} balances updated to 28 days.")
    bulk_set_yearly_balance.short_description = "Set yearly balance to 28 days"


@admin.register(VacationRequest)
class VacationRequestAdmin(admin.ModelAdmin):
    list_display = [
        'request_id',
        'employee_link',
        'employee_department',
        'vacation_type',
        'dates_display',
        'number_of_days',
        'status_display',
        'approval_status_display',
        'created_at'
    ]
    list_filter = [
        'status', 
        'vacation_type', 
        'request_type',
        'created_at',
        'employee__department'
    ]
    search_fields = [
        'request_id', 
        'employee__full_name',
        'employee__employee_id'
    ]
    ordering = ['-created_at']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Request Information', {
            'fields': ('request_id', 'employee', 'requester', 'request_type')
        }),
        ('Vacation Details', {
            'fields': (
                'vacation_type',
                ('start_date', 'end_date', 'return_date'),
                'number_of_days',
                'comment'
            )
        }),
        ('Approval Chain', {
            'fields': (
                'line_manager',
                'hr_representative',
                'status'
            )
        }),
        ('Line Manager Approval', {
            'fields': (
                'line_manager_approved_by',
                'line_manager_approved_at',
                'line_manager_comment'
            ),
            'classes': ('collapse',)
        }),
        ('HR Approval', {
            'fields': (
                'hr_approved_by',
                'hr_approved_at',
                'hr_comment'
            ),
            'classes': ('collapse',)
        }),
        ('Rejection', {
            'fields': (
                'rejected_by',
                'rejected_at',
                'rejection_reason'
            ),
            'classes': ('collapse',)
        })
    )
    
    readonly_fields = [
        'request_id', 
        'return_date', 
        'number_of_days',
        'line_manager_approved_by',
        'line_manager_approved_at',
        'hr_approved_by',
        'hr_approved_at',
        'rejected_by',
        'rejected_at'
    ]
    
    def employee_link(self, obj):
        url = reverse('admin:api_employee_change', args=[obj.employee.pk])
        return format_html('<a href="{}">{}</a>', url, obj.employee.full_name)
    employee_link.short_description = 'Employee'
    
    def employee_department(self, obj):
        return obj.employee.department.name if obj.employee.department else '-'
    employee_department.short_description = 'Department'
    
    def dates_display(self, obj):
        return f"{obj.start_date} to {obj.end_date}"
    dates_display.short_description = 'Dates'
    
    def status_display(self, obj):
        status_colors = {
            'DRAFT': ('gray', '📝'),
            'PENDING_LINE_MANAGER': ('orange', '👤'),
            'PENDING_HR': ('purple', '🏢'),
            'APPROVED': ('green', '✅'),
            'REJECTED_LINE_MANAGER': ('red', '❌'),
            'REJECTED_HR': ('red', '❌'),
        }
        color, icon = status_colors.get(obj.status, ('black', '❓'))
        return format_html(
            '<span style="color: {}; font-weight: bold;">{} {}</span>',
            color, icon, obj.get_status_display()
        )
    status_display.short_description = 'Status'
    
    def approval_status_display(self, obj):
        approvals = []
        
        if obj.line_manager_approved_at:
            approvals.append('<span style="color: green;">LM ✅</span>')
        elif obj.status == 'PENDING_LINE_MANAGER':
            approvals.append('<span style="color: orange;">LM ⏳</span>')
        elif obj.status == 'REJECTED_LINE_MANAGER':
            approvals.append('<span style="color: red;">LM ❌</span>')
        
        if obj.hr_approved_at:
            approvals.append('<span style="color: green;">HR ✅</span>')
        elif obj.status == 'PENDING_HR':
            approvals.append('<span style="color: orange;">HR ⏳</span>')
        elif obj.status == 'REJECTED_HR':
            approvals.append('<span style="color: red;">HR ❌</span>')
        
        return format_html(' '.join(approvals)) if approvals else '-'
    approval_status_display.short_description = 'Approvals'
    
    # Custom actions
    actions = ['approve_selected', 'reject_selected']
    
    def approve_selected(self, request, queryset):
        """Bulk approve requests (admin override)"""
        count = 0
        for obj in queryset:
            if obj.status in ['PENDING_LINE_MANAGER', 'PENDING_HR']:
                obj.status = 'APPROVED'
                obj.save()
                count += 1
        
        self.message_user(request, f"{count} requests approved.")
    approve_selected.short_description = "Approve selected requests (Admin override)"


@admin.register(VacationSchedule)
class VacationScheduleAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'employee_link',
        'employee_department',
        'vacation_type',
        'dates_display',
        'number_of_days',
        'status_display',
        'edit_info_display',
        'created_at'
    ]
    list_filter = [
        'status', 
        'vacation_type',
        'employee__department',
        'created_at'
    ]
    search_fields = [
        'employee__full_name',
        'employee__employee_id'
    ]
    ordering = ['-start_date']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Schedule Information', {
            'fields': ('employee', 'vacation_type', 'status')
        }),
        ('Dates', {
            'fields': (
                ('start_date', 'end_date', 'return_date'),
                'number_of_days'
            )
        }),
        ('Edit Tracking', {
            'fields': (
                'edit_count',
                'last_edited_by',
                'last_edited_at'
            ),
            'classes': ('collapse',)
        }),
        ('Additional Info', {
            'fields': ('comment', 'created_by')
        })
    )
    
    readonly_fields = [
        'return_date', 
        'number_of_days',
        'edit_count',
        'last_edited_by',
        'last_edited_at'
    ]
    
    def employee_link(self, obj):
        url = reverse('admin:api_employee_change', args=[obj.employee.pk])
        return format_html('<a href="{}">{}</a>', url, obj.employee.full_name)
    employee_link.short_description = 'Employee'
    
    def employee_department(self, obj):
        return obj.employee.department.name if obj.employee.department else '-'
    employee_department.short_description = 'Department'
    
    def dates_display(self, obj):
        return f"{obj.start_date} to {obj.end_date}"
    dates_display.short_description = 'Dates'
    
    def status_display(self, obj):
        if obj.status == 'SCHEDULED':
            return format_html('<span style="color: blue; font-weight: bold;">📅 Scheduled</span>')
        elif obj.status == 'REGISTERED':
            return format_html('<span style="color: green; font-weight: bold;">✅ Registered</span>')
        return obj.status
    status_display.short_description = 'Status'
    
    def edit_info_display(self, obj):
        can_edit = obj.can_edit()
        edit_text = f"Edits: {obj.edit_count}"
        
        if can_edit:
            return format_html(
                '<span style="color: green;">{} (Can edit)</span>',
                edit_text
            )
        else:
            return format_html(
                '<span style="color: red;">{} (Cannot edit)</span>',
                edit_text
            )
    edit_info_display.short_description = 'Edit Status'
    
    # Actions
    actions = ['register_schedules']
    
    def register_schedules(self, request, queryset):
        """Bulk register schedules"""
        count = 0
        for schedule in queryset.filter(status='SCHEDULED'):
            schedule.register_as_taken(request.user)
            count += 1
        
        self.message_user(request, f"{count} schedules registered.")
    register_schedules.short_description = "Register selected schedules as taken"


@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(admin.ModelAdmin):
    list_display = [
        'request_type',
        'stage',
        'subject_preview',
        'is_active_display',
        'updated_at'
    ]
    list_filter = ['request_type', 'stage', 'is_active']
    search_fields = ['subject', 'body']
    ordering = ['request_type', 'stage']
    
    fieldsets = (
        ('Template Information', {
            'fields': ('request_type', 'stage', 'is_active')
        }),
        ('Email Content', {
            'fields': ('subject', 'body'),
            'description': 'Use variables like {employee_name}, {start_date}, {end_date}, {approver_name}, etc.'
        })
    )
    
    formfield_overrides = {
        models.TextField: {'widget': Textarea(attrs={'rows': 10, 'cols': 80})},
        models.CharField: {'widget': TextInput(attrs={'size': 80})},
    }
    
    def subject_preview(self, obj):
        if len(obj.subject) > 50:
            return f"{obj.subject[:50]}..."
        return obj.subject
    subject_preview.short_description = 'Subject'
    
    def is_active_display(self, obj):
        if obj.is_active:
            return format_html('<span style="color: green;">✅ Active</span>')
        return format_html('<span style="color: red;">❌ Inactive</span>')
    is_active_display.short_description = 'Status'


# Custom admin site configuration
admin.site.site_header = "Vacation Management System"
admin.site.site_title = "Vacation Admin"
admin.site.index_title = "Welcome to Vacation Management"