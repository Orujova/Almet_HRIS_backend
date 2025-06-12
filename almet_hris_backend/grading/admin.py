# grading/admin.py - FIXED: Removed competitiveness/riskLevel references

from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from django.urls import reverse
from .models import GradingSystem, SalaryGrade, SalaryScenario, ScenarioHistory
from .managers import SalaryCalculationManager

@admin.register(GradingSystem)
class GradingSystemAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active', 'grades_count', 'scenarios_count', 'current_scenario_name', 'created_at')
    list_filter = ('is_active', 'base_currency', 'created_at')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at', 'updated_at')
    list_editable = ('is_active',)
    ordering = ('name',)
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'is_active', 'base_currency')
        }),
        ('Configuration', {
            'fields': ('initial_data', 'created_by')
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
    
    def current_scenario_name(self, obj):
        try:
            current = obj.scenarios.get(status='CURRENT')
            return format_html(
                '<span style="color: #28a745; font-weight: bold;">{}</span>',
                current.name
            )
        except SalaryScenario.DoesNotExist:
            return format_html('<span style="color: #dc3545;">No current scenario</span>')
    current_scenario_name.short_description = 'Current Scenario'

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

@admin.register(SalaryScenario)
class SalaryScenarioAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'status_badge', 'grading_system', 'base_value', 'averages_display',
        'completion_status', 'balance_score_display', 'created_by', 'created_at'
    )
    list_filter = ('status', 'grading_system', 'created_at', 'calculation_timestamp')
    search_fields = ('name', 'description')
    readonly_fields = (
        'id', 'calculated_grades', 'calculation_timestamp', 'metrics',
        'created_at', 'updated_at', 'applied_at'
    )
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'name', 'description', 'status', 'grading_system')
        }),
        ('Configuration', {
            'fields': ('base_value', 'grade_order', 'input_rates')
        }),
        ('Calculation Results', {
            'fields': ('calculated_grades', 'calculation_timestamp', 'vertical_avg', 'horizontal_avg', 'metrics'),
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
    
    def averages_display(self, obj):
        return format_html(
            'V: <strong>{:.1f}%</strong> | H: <strong>{:.1f}%</strong>',
            float(obj.vertical_avg) * 100,
            float(obj.horizontal_avg) * 100
        )
    averages_display.short_description = 'Averages'
    
    def completion_status(self, obj):
        """Show completion percentage of rate configuration"""
        if not obj.input_rates or not obj.grade_order:
            return format_html('<span style="color: #dc3545; font-weight: bold;">✗ Not configured</span>')
        
        total_grades = len(obj.grade_order)
        configured_grades = 0
        
        for grade_name in obj.grade_order:
            grade_data = obj.input_rates.get(grade_name, {})
            if (grade_data.get('vertical') is not None and 
                grade_data.get('horizontal_intervals') is not None):
                configured_grades += 1
        
        percentage = round((configured_grades / total_grades) * 100, 1) if total_grades > 0 else 0
        
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
            '<small style="color: #666;">{}/{} grades</small>',
            color, icon, percentage, configured_grades, total_grades
        )
    completion_status.short_description = 'Completion'
    
    def balance_score_display(self, obj):
        """Display balance score"""
        if obj.vertical_avg is not None and obj.horizontal_avg is not None:
            data = {
                'verticalAvg': float(obj.vertical_avg),
                'horizontalAvg': float(obj.horizontal_avg)
            }
            score = SalaryCalculationManager.get_balance_score(data)
            
            if score >= 0.8:
                color = '#28a745'
            elif score >= 0.6:
                color = '#ffc107'
            else:
                color = '#dc3545'
            
            return format_html(
                '<span style="color: {}; font-weight: bold;">{:.2f}</span>',
                color, score
            )
        return '-'
    balance_score_display.short_description = 'Balance Score'
    
    def calculate_scenarios(self, request, queryset):
        """Admin action to calculate selected scenarios"""
        calculated_count = 0
        error_count = 0
        
        for scenario in queryset:
            try:
                if scenario.input_rates and scenario.base_value:
                    # Calculate grades
                    calculated_grades = SalaryCalculationManager.calculate_scenario_grades(
                        scenario.base_value,
                        scenario.input_rates,
                        scenario.grade_order or SalaryCalculationManager.get_position_groups_from_db()
                    )
                    
                    # Update scenario
                    scenario.calculated_grades = calculated_grades
                    scenario.calculation_timestamp = timezone.now()
                    scenario.calculate_averages()
                    scenario.save()
                    
                    calculated_count += 1
                else:
                    error_count += 1
                    self.message_user(
                        request,
                        f'Scenario {scenario.name} missing required data',
                        level='ERROR'
                    )
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
                base_value=scenario.base_value,
                grade_order=scenario.grade_order,
                input_rates=scenario.input_rates,
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
            'ARCHIVED': '#6c757d'
        }
        color = colors.get(obj.action, '#6c757d')
        
        return format_html(
            '<span style="background: {}; color: white; padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: bold;">{}</span>',
            color, obj.action
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

# Customize admin site headers
admin.site.site_header = "Almet HRIS - Employee & Grading Management"
admin.site.site_title = "Almet HRIS Admin"
admin.site.index_title = "Welcome to Almet HRIS Administration"