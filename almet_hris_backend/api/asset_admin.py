# api/asset_admin.py

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.utils import timezone
from .asset_models import (
    AssetCategory, Asset, AssetAssignment,  AssetActivity
)


class AssetAssignmentInline(admin.TabularInline):
    model = AssetAssignment
    extra = 0
    fields = ['employee', 'check_out_date', 'check_in_date', 'condition_on_checkout', 'condition_on_checkin', 'check_out_notes']
    readonly_fields = ['created_at']
    ordering = ['-check_out_date']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('employee')

@admin.register(AssetCategory)
class AssetCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'description', 'is_active', 'asset_count', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'description']
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
    
    def asset_count(self, obj):
        count = obj.asset_set.count()
        if count > 0:
            url = reverse('admin:api_asset_changelist') + f'?category__id__exact={obj.id}'
            return format_html('<a href="{}">{} assets</a>', url, count)
        return count
    asset_count.short_description = 'Assets'
    
    def save_model(self, request, obj, form, change):
        if not change:  # Creating new object
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = [
        'asset_name', 'category', 'serial_number', 'status_badge', 
        'assigned_to', 'purchase_price', 'purchase_date',  'created_at'
    ]
    list_filter = [
        'status', 'category', 'purchase_date', 'created_at', 
        'assigned_to__department', 'brand'
    ]
    search_fields = [
        'asset_name', 'serial_number', 'brand', 'model',
        'assigned_to__full_name', 'assigned_to__employee_id'
    ]
    autocomplete_fields = ['category', 'assigned_to', 'created_by', 'updated_by', 'archived_by']
    readonly_fields = [
        'id', 'created_at', 'updated_at', 'depreciation_display', 
        'assignment_status_display', 'activity_summary'
    ]
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'asset_name', 'category', 'brand', 'model', 'serial_number'
            )
        }),
        ('Financial Information', {
            'fields': (
                'purchase_price', 'purchase_date', 'useful_life_years', 'depreciation_display'
            )
        }),
        ('Status & Assignment', {
            'fields': (
                'status', 'assigned_to', 'assignment_status_display'
            )
        }),
        ('Additional Information', {
            'fields': (
                'specifications', 'notes'
            ),
            'classes': ['collapse']
        }),
        ('Archive Information', {
            'fields': (
                'archived_at', 'archived_by', 'archive_reason'
            ),
            'classes': ['collapse']
        }),
        ('Metadata', {
            'fields': (
                'id', 'created_by', 'created_at', 'updated_by', 'updated_at', 'activity_summary'
            ),
            'classes': ['collapse']
        })
    )
    
    inlines = [AssetAssignmentInline]
    
    actions = [
        'mark_as_in_stock', 'mark_as_in_repair', 'mark_as_archived',
        'export_selected_assets'
    ]
    
    def status_badge(self, obj):
        status_colors = {
            'IN_STOCK': '#17a2b8',
            'IN_USE': '#28a745',
            'IN_REPAIR': '#ffc107',
            'ARCHIVED': '#6c757d',
        }
        color = status_colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 4px; font-size: 11px;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    
    def assignment_status_display(self, obj):
        current_assignment = obj.get_current_assignment()
        if current_assignment:
            assignment = current_assignment['assignment']
            employee = current_assignment['employee']
            html = f'<div><strong>Assigned to:</strong> {employee["name"]} ({employee["employee_id"]})</div>'
            if assignment:
                html += f'<div><strong>Check-out Date:</strong> {assignment.check_out_date}</div>'
                html += f'<div><strong>Days Assigned:</strong> {assignment.get_duration_days()}</div>'
            return mark_safe(html)
        return 'Not assigned'
    assignment_status_display.short_description = 'Assignment Details'
    
    def activity_summary(self, obj):
        recent_activities = obj.activities.order_by('-performed_at')[:5]
        if not recent_activities:
            return 'No activities'
        
        html = '<div style="max-width: 300px;">'
        for activity in recent_activities:
            html += f'<div style="margin-bottom: 5px; padding: 3px; border-left: 3px solid #007cba;">'
            html += f'<strong>{activity.get_activity_type_display()}</strong><br>'
            html += f'<small>{activity.performed_at.strftime("%Y-%m-%d %H:%M")} by {activity.performed_by.get_full_name() if activity.performed_by else "System"}</small>'
            html += '</div>'
        html += '</div>'
        return mark_safe(html)
    activity_summary.short_description = 'Recent Activities'
    
    def mark_as_in_stock(self, request, queryset):
        count = 0
        for asset in queryset:
            if asset.status != 'IN_STOCK':
                asset.status = 'IN_STOCK'
                asset.assigned_to = None
                asset.save()
                
                # Log activity
                AssetActivity.objects.create(
                    asset=asset,
                    activity_type='STATUS_CHANGED',
                    description=f'Status changed to In Stock by {request.user.get_full_name()}',
                    performed_by=request.user,
                    metadata={'old_status': asset.status, 'new_status': 'IN_STOCK'}
                )
                count += 1
        
        self.message_user(request, f'{count} asset(s) marked as In Stock.')
    mark_as_in_stock.short_description = 'Mark selected assets as In Stock'
    
    def mark_as_in_repair(self, request, queryset):
        count = 0
        for asset in queryset:
            if asset.status != 'IN_REPAIR':
                old_status = asset.status
                asset.status = 'IN_REPAIR'
                asset.save()
                
                # Log activity
                AssetActivity.objects.create(
                    asset=asset,
                    activity_type='STATUS_CHANGED',
                    description=f'Status changed to In Repair by {request.user.get_full_name()}',
                    performed_by=request.user,
                    metadata={'old_status': old_status, 'new_status': 'IN_REPAIR'}
                )
                count += 1
        
        self.message_user(request, f'{count} asset(s) marked as In Repair.')
    mark_as_in_repair.short_description = 'Mark selected assets as In Repair'
    
    def mark_as_archived(self, request, queryset):
        count = 0
        for asset in queryset:
            if asset.status != 'ARCHIVED':
                old_status = asset.status
                asset.status = 'ARCHIVED'
                asset.archived_at = timezone.now()
                asset.archived_by = request.user
                asset.assigned_to = None
                asset.save()
                
                # Log activity
                AssetActivity.objects.create(
                    asset=asset,
                    activity_type='ARCHIVED',
                    description=f'Asset archived by {request.user.get_full_name()}',
                    performed_by=request.user,
                    metadata={'old_status': old_status, 'archived_at': asset.archived_at.isoformat()}
                )
                count += 1
        
        self.message_user(request, f'{count} asset(s) archived.')
    mark_as_archived.short_description = 'Archive selected assets'
    
    def save_model(self, request, obj, form, change):
        if not change:  # Creating new object
            obj.created_by = request.user
        else:  # Updating existing object
            obj.updated_by = request.user
        
        super().save_model(request, obj, form, change)
        
        # Log activity
        activity_type = 'UPDATED' if change else 'CREATED'
        description = f'Asset {activity_type.lower()} by {request.user.get_full_name()}'
        
        AssetActivity.objects.create(
            asset=obj,
            activity_type=activity_type,
            description=description,
            performed_by=request.user,
            metadata={
                'asset_name': obj.asset_name,
                'serial_number': obj.serial_number,
                'status': obj.status
            }
        )


@admin.register(AssetAssignment)
class AssetAssignmentAdmin(admin.ModelAdmin):
    list_display = [
        'asset', 'employee', 'check_out_date', 'check_in_date', 
        'duration_display', 'condition_on_checkout', 'condition_on_checkin', 'is_active'
    ]
    list_filter = [
        'check_out_date', 'check_in_date', 'condition_on_checkout', 
        'condition_on_checkin', 'asset__category', 'employee__department'
    ]
    search_fields = [
        'asset__asset_name', 'asset__serial_number', 
        'employee__full_name', 'employee__employee_id'
    ]
    autocomplete_fields = ['asset', 'employee', 'assigned_by', 'checked_in_by']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'check_out_date'
    
    fieldsets = (
        ('Assignment Information', {
            'fields': (
                'asset', 'employee', 'check_out_date', 'check_in_date'
            )
        }),
        ('Condition', {
            'fields': (
                'condition_on_checkout', 'condition_on_checkin'
            )
        }),
        ('Notes', {
            'fields': (
                'check_out_notes', 'check_in_notes'
            )
        }),
        ('Metadata', {
            'fields': (
                'assigned_by', 'checked_in_by', 'created_at', 'updated_at'
            ),
            'classes': ['collapse']
        })
    )
    
    def duration_display(self, obj):
        days = obj.get_duration_days()
        if obj.is_active():
            return format_html('<strong>{} days (Active)</strong>', days)
        return f'{days} days'
    duration_display.short_description = 'Duration'
    
    def is_active(self, obj):
        return obj.is_active()
    is_active.boolean = True
    is_active.short_description = 'Active'




@admin.register(AssetActivity)
class AssetActivityAdmin(admin.ModelAdmin):
    list_display = [
        'asset', 'activity_type', 'performed_by', 'performed_at', 'short_description'
    ]
    list_filter = [
        'activity_type', 'performed_at', 'asset__category'
    ]
    search_fields = [
        'asset__asset_name', 'asset__serial_number', 'description', 'performed_by__username'
    ]
    autocomplete_fields = ['asset', 'performed_by']
    readonly_fields = ['performed_at', 'metadata']
    date_hierarchy = 'performed_at'
    
    def short_description(self, obj):
        return obj.description[:100] + '...' if len(obj.description) > 100 else obj.description
    short_description.short_description = 'Description'


# Custom admin site configuration
admin.site.site_header = "ALMET HRIS - Asset Management"
admin.site.site_title = "Asset Admin"
admin.site.index_title = "Asset Management Administration"