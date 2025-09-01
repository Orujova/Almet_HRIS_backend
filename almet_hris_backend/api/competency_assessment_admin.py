# api/competency_assessment_admin.py

from django.contrib import admin
from .competency_assessment_models import (
    CoreCompetencyScale, BehavioralScale, LetterGradeMapping,
    PositionCoreAssessment, PositionCoreCompetencyRating,
    PositionBehavioralAssessment, PositionBehavioralCompetencyRating,
    EmployeeCoreAssessment, EmployeeCoreCompetencyRating,
    EmployeeBehavioralAssessment, EmployeeBehavioralCompetencyRating
)


# SCALE MANAGEMENT ADMIN

@admin.register(CoreCompetencyScale)
class CoreCompetencyScaleAdmin(admin.ModelAdmin):
    list_display = ['scale', 'description', 'is_active', 'created_at', 'created_by']
    list_filter = ['is_active', 'created_at']
    search_fields = ['scale', 'description']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['scale']
    
    fieldsets = (
        ('Scale Information', {
            'fields': ('scale', 'description', 'is_active')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at', 'created_by'),
            'classes': ('collapse',)
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('created_by')


@admin.register(BehavioralScale)
class BehavioralScaleAdmin(admin.ModelAdmin):
    list_display = ['scale', 'description', 'is_active', 'created_at', 'created_by']
    list_filter = ['is_active', 'created_at']
    search_fields = ['scale', 'description']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['scale']
    
    fieldsets = (
        ('Scale Information', {
            'fields': ('scale', 'description', 'is_active')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at', 'created_by'),
            'classes': ('collapse',)
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('created_by')


@admin.register(LetterGradeMapping)
class LetterGradeMappingAdmin(admin.ModelAdmin):
    list_display = ['letter_grade', 'min_percentage', 'max_percentage',  'description', 'is_active']
    list_filter = ['is_active', 'created_at']
    search_fields = ['letter_grade', 'description']
    ordering = ['-min_percentage']
    
    fieldsets = (
        ('Grade Information', {
            'fields': ('letter_grade', 'description')
        }),
        ('Percentage Range', {
            'fields': ('min_percentage', 'max_percentage')
        }),
        ('Display Settings', {
            'fields': ( 'is_active')
        }),
    )


# POSITION ASSESSMENT ADMIN

class PositionCoreCompetencyRatingInline(admin.TabularInline):
    model = PositionCoreCompetencyRating
    extra = 0
    fields = ['skill', 'required_level']
    autocomplete_fields = ['skill']


@admin.register(PositionCoreAssessment)
class PositionCoreAssessmentAdmin(admin.ModelAdmin):
    list_display = ['job_title', 'position_group', 'is_active', 'created_at']
    list_filter = ['position_group', 'is_active', 'created_at']
    search_fields = ['job_title', 'position_group__name']
    readonly_fields = ['id', 'created_at', 'updated_at']
    inlines = [PositionCoreCompetencyRatingInline]
    
    fieldsets = (
        ('Position Information', {
            'fields': ('position_group', 'job_title')
        }),
        ('Assessment Configuration', {
            'fields': ('is_active',)
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at', 'created_by'),
            'classes': ('collapse',)
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('position_group', 'created_by')


class PositionBehavioralCompetencyRatingInline(admin.TabularInline):
    model = PositionBehavioralCompetencyRating
    extra = 0
    fields = ['behavioral_competency', 'required_level']
    autocomplete_fields = ['behavioral_competency']


@admin.register(PositionBehavioralAssessment)
class PositionBehavioralAssessmentAdmin(admin.ModelAdmin):
    list_display = ['job_title', 'position_group', 'is_active', 'created_at']
    list_filter = ['position_group', 'is_active', 'created_at']
    search_fields = ['job_title', 'position_group__name']
    readonly_fields = ['id', 'created_at', 'updated_at']
    inlines = [PositionBehavioralCompetencyRatingInline]
    
    fieldsets = (
        ('Position Information', {
            'fields': ('position_group', 'job_title')
        }),
        ('Assessment Configuration', {
            'fields': ('is_active',)
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at', 'created_by'),
            'classes': ('collapse',)
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('position_group', 'created_by')


# EMPLOYEE ASSESSMENT ADMIN

class EmployeeCoreCompetencyRatingInline(admin.TabularInline):
    model = EmployeeCoreCompetencyRating
    extra = 0
    fields = ['skill', 'required_level', 'actual_level', 'gap', 'notes']
    readonly_fields = ['gap']
    autocomplete_fields = ['skill']


@admin.register(EmployeeCoreAssessment)
class EmployeeCoreAssessmentAdmin(admin.ModelAdmin):
    list_display = [
        'employee', 'position_assessment', 'assessment_date', 
        'status', 'completion_percentage', 'assessed_by'
    ]
    list_filter = ['status', 'assessment_date', 'position_assessment__position_group']
    search_fields = [
        'employee__full_name', 'employee__employee_id', 
        'position_assessment__job_title'
    ]
    readonly_fields = [
        'id', 'total_position_score', 'total_employee_score', 
        'gap_score', 'completion_percentage', 'created_at', 'updated_at'
    ]
    autocomplete_fields = ['employee', 'position_assessment', 'assessed_by']
    inlines = [EmployeeCoreCompetencyRatingInline]
    
    fieldsets = (
        ('Assessment Information', {
            'fields': ('employee', 'position_assessment', 'assessment_date', 'status')
        }),
        ('Assessment Details', {
            'fields': ('assessed_by', 'notes')
        }),
        ('Calculated Scores', {
            'fields': (
                'total_position_score', 'total_employee_score', 
                'gap_score', 'completion_percentage'
            ),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['recalculate_scores']
    
    def recalculate_scores(self, request, queryset):
        """Admin action to recalculate core assessment scores"""
        updated_count = 0
        for assessment in queryset:
            assessment.calculate_scores()
            updated_count += 1
        
        self.message_user(
            request, 
            f'Successfully recalculated scores for {updated_count} core assessments.'
        )
    
    recalculate_scores.short_description = "Recalculate core assessment scores"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'employee', 'position_assessment', 'assessed_by'
        )


class EmployeeBehavioralCompetencyRatingInline(admin.TabularInline):
    model = EmployeeBehavioralCompetencyRating
    extra = 0
    fields = ['behavioral_competency', 'required_level', 'actual_level', 'notes']
    autocomplete_fields = ['behavioral_competency']


@admin.register(EmployeeBehavioralAssessment)
class EmployeeBehavioralAssessmentAdmin(admin.ModelAdmin):
    list_display = [
        'employee', 'position_assessment', 'assessment_date', 
        'status', 'overall_percentage', 'overall_letter_grade', 'assessed_by'
    ]
    list_filter = ['status', 'assessment_date', 'position_assessment__position_group', 'overall_letter_grade']
    search_fields = [
        'employee__full_name', 'employee__employee_id', 
        'position_assessment__job_title'
    ]
    readonly_fields = [
        'id', 'group_scores', 'overall_percentage', 'overall_letter_grade',
        'created_at', 'updated_at'
    ]
    autocomplete_fields = ['employee', 'position_assessment', 'assessed_by']
    inlines = [EmployeeBehavioralCompetencyRatingInline]
    
    fieldsets = (
        ('Assessment Information', {
            'fields': ('employee', 'position_assessment', 'assessment_date', 'status')
        }),
        ('Assessment Details', {
            'fields': ('assessed_by', 'notes')
        }),
        ('Calculated Scores', {
            'fields': (
                'overall_percentage', 'overall_letter_grade', 'group_scores'
            ),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['recalculate_scores']
    
    def recalculate_scores(self, request, queryset):
        """Admin action to recalculate behavioral assessment scores"""
        updated_count = 0
        for assessment in queryset:
            assessment.calculate_scores()
            updated_count += 1
        
        self.message_user(
            request, 
            f'Successfully recalculated scores for {updated_count} behavioral assessments.'
        )
    
    recalculate_scores.short_description = "Recalculate behavioral assessment scores"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'employee', 'position_assessment', 'assessed_by'
        )


# INDIVIDUAL RATING ADMIN

@admin.register(PositionCoreCompetencyRating)
class PositionCoreCompetencyRatingAdmin(admin.ModelAdmin):
    list_display = [
        'position_assessment', 'skill', 'required_level', 'created_at'
    ]
    list_filter = [
        'required_level', 'skill__group', 
        'position_assessment__position_group', 'created_at'
    ]
    search_fields = [
        'position_assessment__job_title', 'skill__name', 'skill__group__name'
    ]
    autocomplete_fields = ['position_assessment', 'skill']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'position_assessment', 'skill__group'
        )


@admin.register(PositionBehavioralCompetencyRating)
class PositionBehavioralCompetencyRatingAdmin(admin.ModelAdmin):
    list_display = [
        'position_assessment', 'behavioral_competency', 'required_level', 'created_at'
    ]
    list_filter = [
        'required_level', 'behavioral_competency__group',
        'position_assessment__position_group', 'created_at'
    ]
    search_fields = [
        'position_assessment__job_title', 'behavioral_competency__name',
        'behavioral_competency__group__name'
    ]
    autocomplete_fields = ['position_assessment', 'behavioral_competency']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'position_assessment', 'behavioral_competency__group'
        )


@admin.register(EmployeeCoreCompetencyRating)
class EmployeeCoreCompetencyRatingAdmin(admin.ModelAdmin):
    list_display = [
        'assessment', 'skill', 'required_level', 'actual_level', 'gap', 'created_at'
    ]
    list_filter = [
        'required_level', 'actual_level', 'gap', 
        'skill__group', 'assessment__status', 'created_at'
    ]
    search_fields = [
        'assessment__employee__full_name', 'assessment__employee__employee_id',
        'skill__name', 'skill__group__name'
    ]
    readonly_fields = ['gap']
    autocomplete_fields = ['assessment', 'skill']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'assessment__employee', 'skill__group'
        )


@admin.register(EmployeeBehavioralCompetencyRating)
class EmployeeBehavioralCompetencyRatingAdmin(admin.ModelAdmin):
    list_display = [
        'assessment', 'behavioral_competency', 'required_level', 
        'actual_level', 'created_at'
    ]
    list_filter = [
        'required_level', 'actual_level', 'behavioral_competency__group',
        'assessment__status', 'created_at'
    ]
    search_fields = [
        'assessment__employee__full_name', 'assessment__employee__employee_id',
        'behavioral_competency__name', 'behavioral_competency__group__name'
    ]
    autocomplete_fields = ['assessment', 'behavioral_competency']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'assessment__employee', 'behavioral_competency__group'
        )