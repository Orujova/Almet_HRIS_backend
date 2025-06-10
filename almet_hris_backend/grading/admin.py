# grading/admin.py

from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from django.urls import reverse
from .models import (
    GradingSystem, SalaryGrade, GrowthRate, HorizontalRate, 
    SalaryScenario, ScenarioHistory
)

@admin.register(GradingSystem)
class GradingSystemAdmin(admin.ModelAdmin):
    list_display = ('name', 'base_currency', 'is_active', 'grades_count', 'scenarios_count', 'created_at')
    list_filter = ('is_active', 'base_currency', 'created_at')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at', 'updated_at')
    list_editable = ('is_active',)
    ordering = ('name',)
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'is_active')
        }),
        ('Configuration', {
            'fields': ('base_currency', 'created_by')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def grades_count(self, obj):
        count = obj.salary_grades.count()
        if count > 0:
            url = reverse('admin:grading_salarygrade_changelist') + f'?grading_system__id__exact={obj.id}'
            return format_html(
                '<a href="{}" style="color: #417690; text-decoration: none;">{} grades</a>',
                url, count
            )
        return '0 grades'
    grades_count.short_description = 'Salary Grades'
    
    def scenarios_count(self, obj):
        count = obj.scenarios.count()
        if count > 0:
            url = reverse('admin:grading_salaryscenario_changelist') + f'?grading_system__id__exact={obj.id}'
            return format_html(
                '<a href="{}" style="color: #417690; text-decoration: none;">{} scenarios</a>',
                url, count
            )
        return '0 scenarios'
    scenarios_count.short_description = 'Scenarios'

@admin.register(SalaryGrade)
class SalaryGradeAdmin(admin.ModelAdmin):
    list_display = (
        'position_group_display', 'hierarchy_level', 'grading_system', 
        'lower_decile', 'median', 'upper_decile', 'grade_range', 'updated_at'
    )
    list_filter = ('grading_system', 'position_group')
    readonly_fields = ('created_at', 'updated_at')
    ordering = ['grading_system', 'position_group__hierarchy_level']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('grading_system', 'position_group')
        }),
        ('Salary Grades', {
            'fields': ('lower_decile', 'lower_quartile', 'median', 'upper_quartile', 'upper_decile'),
            'description': 'All salary grade values in the base currency'
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def position_group_display(self, obj):
        return obj.position_group.get_name_display()
    position_group_display.short_description = 'Position'
    position_group_display.admin_order_field = 'position_group__name'
    
    def hierarchy_level(self, obj):
        level = obj.position_group.hierarchy_level
        colors = {1: '#8B0000', 2: '#DC143C', 3: '#FF6347', 4: '#FFA500', 
                 5: '#FFD700', 6: '#9ACD32', 7: '#32CD32', 8: '#808080'}
        color = colors.get(level, '#6c757d')
        return format_html(
            '<span style="background: {}; color: white; padding: 2px 6px; border-radius: 10px; font-size: 11px; font-weight: bold;">L{}</span>',
            color, level
        )
    hierarchy_level.short_description = 'Level'
    
    def grade_range(self, obj):
        return format_html(
            '<span style="font-family: monospace; color: #666; font-size: 12px;">{:,.0f} - {:,.0f}</span>',
            obj.lower_decile, obj.upper_decile
        )
    grade_range.short_description = 'Range'

@admin.register(GrowthRate)
class GrowthRateAdmin(admin.ModelAdmin):
    list_display = ('grading_system', 'transition_display', 'vertical_rate', 'rate_badge', 'created_at')
    list_filter = ('grading_system', 'vertical_rate')
    ordering = ['grading_system', 'from_position__hierarchy_level']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('grading_system', 'from_position', 'to_position', 'vertical_rate')
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        })
    )
    
    def transition_display(self, obj):
        return format_html(
            '{} <span style="color: #666;">→</span> {}',
            obj.from_position.get_name_display(), 
            obj.to_position.get_name_display()
        )
    transition_display.short_description = 'Transition'
    
    def rate_badge(self, obj):
        if obj.vertical_rate >= 50:
            color = '#28a745'
        elif obj.vertical_rate >= 30:
            color = '#ffc107'
        else:
            color = '#dc3545'
        
        return format_html(
            '<span style="background: {}; color: white; padding: 2px 8px; border-radius: 12px; font-weight: bold; font-size: 11px;">{}%</span>',
            color, obj.vertical_rate
        )
    rate_badge.short_description = 'Rate'

@admin.register(HorizontalRate)
class HorizontalRateAdmin(admin.ModelAdmin):
    list_display = ('grading_system', 'position_group_display', 'transition_type', 'horizontal_rate', 'rate_badge')
    list_filter = ('grading_system', 'transition_type', 'horizontal_rate')
    ordering = ['grading_system', 'position_group__hierarchy_level', 'transition_type']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('grading_system', 'position_group', 'transition_type', 'horizontal_rate')
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        })
    )
    
    def position_group_display(self, obj):
        return obj.position_group.get_name_display()
    position_group_display.short_description = 'Position'
    position_group_display.admin_order_field = 'position_group__name'
    
    def rate_badge(self, obj):
        if obj.horizontal_rate >= 10:
            color = '#17a2b8'
        elif obj.horizontal_rate >= 8:
            color = '#28a745'
        else:
            color = '#ffc107'
        
        return format_html(
            '<span style="background: {}; color: white; padding: 2px 8px; border-radius: 12px; font-weight: bold; font-size: 11px;">{}%</span>',
            color, obj.horizontal_rate
        )
    rate_badge.short_description = 'Rate'

@admin.register(SalaryScenario)
class SalaryScenarioAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'status_badge', 'grading_system', 'base_position_display', 
        'base_value', 'completion_status', 'calculation_status', 'created_by', 'created_at'
    )
    list_filter = ('status', 'grading_system', 'created_at', 'calculation_timestamp')
    search_fields = ('name', 'description')
    readonly_fields = ('id', 'calculated_grades', 'calculation_timestamp', 'created_at', 'updated_at', 'applied_at')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'name', 'description', 'status', 'grading_system')
        }),
        ('Configuration', {
            'fields': ('base_position', 'base_value', 'custom_vertical_rates', 'custom_horizontal_rates')
        }),
        ('Calculation Results', {
            'fields': ('calculated_grades', 'calculation_timestamp'),
            'classes': ('collapse',),
            'description': 'Calculated salary grades and metadata'
        }),
        ('Audit Information', {
            'fields': ('created_by', 'created_at', 'updated_at', 'applied_at'),
            'classes': ('collapse',)
        })
    )
    
    actions = ['calculate_scenarios', 'archive_scenarios', 'duplicate_scenarios']
    
    def status_badge(self, obj):
        colors = {'DRAFT': '#ffc107', 'CURRENT': '#28a745', 'ARCHIVED': '#6c757d'}
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 10px; border-radius: 15px; font-weight: bold; text-transform: uppercase; font-size: 11px;">{}</span>',
            color, obj.status
        )
    status_badge.short_description = 'Status'
    
    def base_position_display(self, obj):
        level = obj.base_position.hierarchy_level
        return format_html(
            '{} <span style="color: #666; font-size: 11px;">(L{})</span>',
            obj.base_position.get_name_display(), level
        )
    base_position_display.short_description = 'Base Position'
    
    def completion_status(self, obj):
        """Show completion percentage of rate configuration"""
        from api.models import PositionGroup
        
        positions = PositionGroup.objects.filter(is_active=True)
        total_positions = positions.count()
        total_vertical_needed = total_positions - 1
        total_horizontal_needed = total_positions * 4
        
        # Count completed rates
        completed_vertical = len([r for r in obj.custom_vertical_rates.values() if r is not None and r != ''])
        completed_horizontal = 0
        for rates in obj.custom_horizontal_rates.values():
            if isinstance(rates, dict):
                completed_horizontal += len([r for r in rates.values() if r is not None and r != ''])
        
        total_completed = completed_vertical + completed_horizontal
        total_needed = total_vertical_needed + total_horizontal_needed
        
        percentage = round((total_completed / total_needed) * 100, 1) if total_needed > 0 else 0
        
        if percentage == 100:
            color = '#28a745'
            icon = '✓'
        elif percentage >= 50:
            color = '#ffc107'
            icon = '◐'
        else:
            color = '#dc3545'
            icon = '○'
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{} {}%</span><br>'
            '<small style="color: #666;">V: {}/{} | H: {}/{}</small>',
            color, icon, percentage, completed_vertical, total_vertical_needed, 
            completed_horizontal, total_horizontal_needed
        )
    completion_status.short_description = 'Completion'
    
    def calculation_status(self, obj):
        if obj.calculated_grades and obj.calculation_timestamp:
            return format_html(
                '<span style="color: #28a745; font-weight: bold;">✓ Calculated</span><br>'
                '<small style="color: #666;">{}</small>',
                obj.calculation_timestamp.strftime('%Y-%m-%d %H:%M')
            )
        else:
            return format_html('<span style="color: #dc3545; font-weight: bold;">✗ Not calculated</span>')
    calculation_status.short_description = 'Calculation'
    
    def calculate_scenarios(self, request, queryset):
        """Admin action to calculate selected scenarios"""
        from .managers import SalaryCalculationManager
        
        calculated_count = 0
        error_count = 0
        
        for scenario in queryset:
            try:
                SalaryCalculationManager.calculate_scenario(scenario)
                calculated_count += 1
            except Exception as e:
                error_count += 1
                self.message_user(
                    request, 
                    f'Error calculating {scenario.name}: {str(e)}', 
                    level='ERROR'
                )
        
        if calculated_count > 0:
            self.message_user(
                request, 
                f'Successfully calculated {calculated_count} scenarios.'
            )
        
        if error_count > 0:
            self.message_user(
                request, 
                f'{error_count} scenarios failed to calculate.',
                level='WARNING'
            )
    
    calculate_scenarios.short_description = "Calculate selected scenarios"
    
    def archive_scenarios(self, request, queryset):
        """Admin action to archive selected draft scenarios"""
        archived_count = 0
        
        for scenario in queryset.filter(status='DRAFT'):
            scenario.status = 'ARCHIVED'
            scenario.save()
            
            # Create history record
            ScenarioHistory.objects.create(
                scenario=scenario,
                action='ARCHIVED',
                performed_by=request.user,
                changes_made={'archived_via': 'admin_bulk_action'}
            )
            archived_count += 1
        
        self.message_user(request, f'Successfully archived {archived_count} scenarios.')
    
    archive_scenarios.short_description = "Archive selected draft scenarios"
    
    def duplicate_scenarios(self, request, queryset):
        """Admin action to duplicate selected scenarios"""
        duplicated_count = 0
        
        for scenario in queryset:
            # Create new scenario name
            new_name = f"{scenario.name} (Admin Copy)"
            counter = 1
            while SalaryScenario.objects.filter(name=new_name).exists():
                counter += 1
                new_name = f"{scenario.name} (Admin Copy {counter})"
            
            # Create duplicate
            SalaryScenario.objects.create(
                grading_system=scenario.grading_system,
                name=new_name,
                description=f"Admin duplicate of: {scenario.description}",
                base_position=scenario.base_position,
                base_value=scenario.base_value,
                custom_vertical_rates=scenario.custom_vertical_rates,
                custom_horizontal_rates=scenario.custom_horizontal_rates,
                created_by=request.user
            )
            duplicated_count += 1
        
        self.message_user(request, f'Successfully duplicated {duplicated_count} scenarios.')
    
    duplicate_scenarios.short_description = "Duplicate selected scenarios"

@admin.register(ScenarioHistory)
class ScenarioHistoryAdmin(admin.ModelAdmin):
    list_display = ('scenario_name', 'action_badge', 'performed_by', 'timestamp', 'changes_summary')
    list_filter = ('action', 'timestamp', 'performed_by')
    readonly_fields = ('timestamp',)
    ordering = ['-timestamp']
    date_hierarchy = 'timestamp'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('scenario', 'action', 'performed_by', 'timestamp')
        }),
        ('Details', {
            'fields': ('previous_current_scenario', 'changes_made'),
            'classes': ('collapse',)
        })
    )
    
    def scenario_name(self, obj):
        url = reverse('admin:grading_salaryscenario_change', args=[obj.scenario.id])
        return format_html(
            '<a href="{}" style="color: #417690; text-decoration: none;">{}</a>',
            url, obj.scenario.name
        )
    scenario_name.short_description = 'Scenario'
    scenario_name.admin_order_field = 'scenario__name'
    
    def action_badge(self, obj):
        colors = {
            'CREATED': '#17a2b8', 
            'CALCULATED': '#ffc107', 
            'APPLIED': '#28a745', 
            'ARCHIVED': '#6c757d',
            'STATUS_CHANGED_TO_DRAFT': '#17a2b8',
            'STATUS_CHANGED_TO_CURRENT': '#28a745',
            'STATUS_CHANGED_TO_ARCHIVED': '#6c757d'
        }
        color = colors.get(obj.action, '#6c757d')
        display_action = obj.action.replace('_', ' ').replace('STATUS CHANGED TO ', '')
        
        return format_html(
            '<span style="background: {}; color: white; padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: bold;">{}</span>',
            color, display_action
        )
    action_badge.short_description = 'Action'
    
    def changes_summary(self, obj):
        if obj.changes_made:
            summary_items = []
            for key, value in obj.changes_made.items():
                if isinstance(value, dict) and 'old' in value and 'new' in value:
                    summary_items.append(f"{key}: {value['old']} → {value['new']}")
                else:
                    summary_items.append(f"{key}: {value}")
            
            summary = '; '.join(summary_items[:3])  # Show first 3 changes
            if len(summary_items) > 3:
                summary += f" (+{len(summary_items) - 3} more)"
            
            return format_html('<small style="color: #666;">{}</small>', summary)
        return '-'
    
    changes_summary.short_description = 'Changes'
    
    def has_add_permission(self, request):
        return False  # History entries are created automatically
    
    def has_change_permission(self, request, obj=None):
        return False  # History entries should not be editable
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser  # Only superusers can delete history

# Customize admin site headers for grading section
admin.site.site_header = "Almet HRIS - Employee & Grading Management"
admin.site.site_title = "Almet HRIS Admin"
admin.site.index_title = "Welcome to Almet HRIS Administration"