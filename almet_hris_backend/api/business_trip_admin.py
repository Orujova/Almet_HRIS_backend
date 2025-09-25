# api/business_trip_admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .business_trip_models import (
    TravelType, TransportType, TripPurpose, ApprovalWorkflow, ApprovalStep,
    BusinessTripRequest, TripSchedule, TripHotel, TripApproval, TripNotification
)

@admin.register(TravelType)
class TravelTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'description', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'code', 'description']
    ordering = ['name']
    
    fields = ['name', 'code', 'description', 'is_active']
    
    def get_queryset(self, request):
        return super().get_queryset(request).filter(is_deleted=False)

@admin.register(TransportType)
class TransportTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'description', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'code', 'description']
    ordering = ['name']
    
    fields = ['name', 'code', 'description', 'is_active']
    
    def get_queryset(self, request):
        return super().get_queryset(request).filter(is_deleted=False)

@admin.register(TripPurpose)
class TripPurposeAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'description', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'code', 'description']
    ordering = ['name']
    
    fields = ['name', 'code', 'description', 'is_active']
    
    def get_queryset(self, request):
        return super().get_queryset(request).filter(is_deleted=False)

class ApprovalStepInline(admin.TabularInline):
    model = ApprovalStep
    extra = 0
    fields = ['step_order', 'step_type', 'step_name', 'is_required', 
              'can_edit_amount', 'requires_amount_entry', 'specific_approver']
    ordering = ['step_order']

@admin.register(ApprovalWorkflow)
class ApprovalWorkflowAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active', 'is_default', 'applies_to_domestic', 
                    'applies_to_overseas', 'step_count', 'created_at']
    list_filter = ['is_active', 'is_default', 'applies_to_domestic', 'applies_to_overseas']
    search_fields = ['name', 'description']
    ordering = ['name']
    
    inlines = [ApprovalStepInline]
    
    fields = [
        'name', 'description', 'is_active', 'is_default',
        ('applies_to_domestic', 'applies_to_overseas'),
        ('min_amount', 'max_amount')
    ]
    
    def step_count(self, obj):
        return obj.steps.filter(is_deleted=False).count()
    step_count.short_description = 'Steps'
    
    def get_queryset(self, request):
        return super().get_queryset(request).filter(is_deleted=False)

class TripScheduleInline(admin.TabularInline):
    model = TripSchedule
    extra = 0
    fields = ['order', 'date', 'from_location', 'to_location', 'notes']
    ordering = ['order']

class TripHotelInline(admin.TabularInline):
    model = TripHotel
    extra = 0
    fields = ['hotel_name', 'check_in_date', 'check_out_date', 'location']
    ordering = ['check_in_date']

class TripApprovalInline(admin.TabularInline):
    model = TripApproval
    extra = 0
    fields = ['approval_step', 'approver', 'decision', 'amount', 'notes', 'created_at']
    readonly_fields = ['created_at']
    ordering = ['approval_step__step_order']
    
    def has_add_permission(self, request, obj):
        return False

@admin.register(BusinessTripRequest)
class BusinessTripRequestAdmin(admin.ModelAdmin):
    list_display = [
        'request_id', 'employee_link', 'travel_type', 'status_badge', 
        'start_date', 'end_date', 'duration_days', 'approved_amount', 
        'current_step_display', 'submitted_at'
    ]
    list_filter = [
        'status', 'travel_type', 'transport_type', 'purpose', 
        'requester_type', 'submitted_at', 'created_at'
    ]
    search_fields = [
        'request_id', 'employee__full_name', 'employee__employee_id',
        'requested_by__full_name', 'notes'
    ]
    ordering = ['-created_at']
    
    inlines = [TripScheduleInline, TripHotelInline, TripApprovalInline]
    
    fieldsets = (
        ('Request Information', {
            'fields': ('request_id', 'requester_type', 'requested_by', 'employee')
        }),
        ('Travel Details', {
            'fields': ('travel_type', 'transport_type', 'purpose', 'start_date', 'end_date')
        }),
        ('Financial Information', {
            'fields': ('estimated_amount', 'approved_amount')
        }),
        ('Approval Information', {
            'fields': ('status', 'workflow', 'current_step')
        }),
        ('Approvers', {
            'fields': ('line_manager', 'finance_approver', 'hr_approver')
        }),
        ('Additional Information', {
            'fields': ('phone_number', 'send_sms_reminders', 'notes', 'rejection_reason'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('submitted_at', 'completed_at', 'created_at', 'updated_at'),
            'classes': ('collapse',),
            'description': 'System timestamps (read-only)'
        })
    )
    
    readonly_fields = ['request_id', 'duration_days', 'submitted_at', 'completed_at', 'created_at', 'updated_at']
    
    def employee_link(self, obj):
        url = reverse('admin:api_employee_change', args=[obj.employee.pk])
        return format_html('<a href="{}">{} ({})</a>', 
                         url, obj.employee.full_name, obj.employee.employee_id)
    employee_link.short_description = 'Employee'
    employee_link.admin_order_field = 'employee__full_name'
    
    def status_badge(self, obj):
        colors = {
            'DRAFT': '#6c757d',
            'SUBMITTED': '#007bff',
            'IN_PROGRESS': '#ffc107',
            'PENDING_LINE_MANAGER': '#fd7e14',
            'PENDING_FINANCE': '#6f42c1',
            'PENDING_HR': '#e83e8c',
            'APPROVED': '#28a745',
            'REJECTED': '#dc3545',
            'CANCELLED': '#6c757d',
            'COMPLETED': '#20c997'
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; border-radius: 3px; font-size: 11px;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status'
    
    def current_step_display(self, obj):
        if obj.current_step:
            return f"{obj.current_step.step_name} (Step {obj.current_step.step_order})"
        return '-'
    current_step_display.short_description = 'Current Step'
    
    def duration_days(self, obj):
        return obj.duration_days
    duration_days.short_description = 'Duration (Days)'
    
    def get_queryset(self, request):
        return super().get_queryset(request).filter(is_deleted=False).select_related(
            'employee', 'requested_by', 'travel_type', 'transport_type', 
            'purpose', 'workflow', 'current_step'
        )

@admin.register(TripApproval)
class TripApprovalAdmin(admin.ModelAdmin):
    list_display = [
        'trip_request_link', 'step_info', 'approver_link', 'decision_badge',
        'amount', 'created_at'
    ]
    list_filter = ['decision', 'approval_step__step_type', 'created_at']
    search_fields = [
        'trip_request__request_id', 'trip_request__employee__full_name',
        'approver__full_name', 'notes'
    ]
    ordering = ['-created_at']
    
    fields = [
        'trip_request', 'approval_step', 'approver', 'decision',
        'amount', 'notes', 'created_at', 'updated_at'
    ]
    readonly_fields = ['created_at', 'updated_at']
    
    def trip_request_link(self, obj):
        url = reverse('admin:api_businesstriprequest_change', args=[obj.trip_request.pk])
        return format_html('<a href="{}">{}</a>', url, obj.trip_request.request_id)
    trip_request_link.short_description = 'Trip Request'
    trip_request_link.admin_order_field = 'trip_request__request_id'
    
    def approver_link(self, obj):
        url = reverse('admin:api_employee_change', args=[obj.approver.pk])
        return format_html('<a href="{}">{}</a>', url, obj.approver.full_name)
    approver_link.short_description = 'Approver'
    approver_link.admin_order_field = 'approver__full_name'
    
    def step_info(self, obj):
        return f"{obj.approval_step.step_name} (Step {obj.approval_step.step_order})"
    step_info.short_description = 'Step'
    step_info.admin_order_field = 'approval_step__step_order'
    
    def decision_badge(self, obj):
        colors = {
            'APPROVED': '#28a745',
            'REJECTED': '#dc3545',
            'PENDING': '#ffc107'
        }
        color = colors.get(obj.decision, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; border-radius: 3px; font-size: 11px;">{}</span>',
            color, obj.get_decision_display()
        )
    decision_badge.short_description = 'Decision'
    decision_badge.admin_order_field = 'decision'
    
    def get_queryset(self, request):
        return super().get_queryset(request).filter(is_deleted=False).select_related(
            'trip_request', 'approval_step', 'approver'
        )

@admin.register(TripNotification)
class TripNotificationAdmin(admin.ModelAdmin):
    list_display = [
        'trip_request_link', 'recipient_link', 'notification_type',
        'template', 'sent_status', 'created_at'
    ]
    list_filter = [
        'notification_type', 'template', 'is_sent', 'created_at'
    ]
    search_fields = [
        'trip_request__request_id', 'recipient__full_name', 
        'subject', 'message'
    ]
    ordering = ['-created_at']
    
    fields = [
        'trip_request', 'recipient', 'notification_type', 'template',
        'subject', 'message', 'is_sent', 'sent_at', 'error_message',
        'metadata', 'created_at'
    ]
    readonly_fields = ['created_at', 'updated_at']
    
    def trip_request_link(self, obj):
        url = reverse('admin:api_businesstriprequest_change', args=[obj.trip_request.pk])
        return format_html('<a href="{}">{}</a>', url, obj.trip_request.request_id)
    trip_request_link.short_description = 'Trip Request'
    
    def recipient_link(self, obj):
        url = reverse('admin:api_employee_change', args=[obj.recipient.pk])
        return format_html('<a href="{}">{}</a>', url, obj.recipient.full_name)
    recipient_link.short_description = 'Recipient'
    
    def sent_status(self, obj):
        if obj.is_sent:
            return format_html(
                '<span style="color: green;">✓ Sent</span>'
            )
        elif obj.error_message:
            return format_html(
                '<span style="color: red;">✗ Failed</span>'
            )
        else:
            return format_html(
                '<span style="color: orange;">⏳ Pending</span>'
            )
    sent_status.short_description = 'Status'
    
    def get_queryset(self, request):
        return super().get_queryset(request).filter(is_deleted=False).select_related(
            'trip_request', 'recipient'
        )