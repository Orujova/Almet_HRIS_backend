# api/competency_assessment_urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .competency_assessment_views import (
    CoreCompetencyScaleViewSet, BehavioralScaleViewSet, LetterGradeMappingViewSet,
    PositionCoreAssessmentViewSet, PositionBehavioralAssessmentViewSet,
    EmployeeCoreAssessmentViewSet, EmployeeBehavioralAssessmentViewSet,
    AssessmentDashboardViewSet
)

# Create router for assessment viewsets
router = DefaultRouter()

# Scale Management URLs
router.register(r'core-scales', CoreCompetencyScaleViewSet, basename='assessment-core-scales')
router.register(r'behavioral-scales', BehavioralScaleViewSet, basename='assessment-behavioral-scales')
router.register(r'letter-grades', LetterGradeMappingViewSet, basename='assessment-letter-grades')

# Position Assessment Template URLs
router.register(r'position-core', PositionCoreAssessmentViewSet, basename='assessment-position-core')
router.register(r'position-behavioral', PositionBehavioralAssessmentViewSet, basename='assessment-position-behavioral')

# Employee Assessment URLs
router.register(r'employee-core', EmployeeCoreAssessmentViewSet, basename='assessment-employee-core')
router.register(r'employee-behavioral', EmployeeBehavioralAssessmentViewSet, basename='assessment-employee-behavioral')

# Dashboard and Reporting URLs
router.register(r'dashboard', AssessmentDashboardViewSet, basename='assessment-dashboard')

urlpatterns = [
    # Include router URLs
    path('', include(router.urls)),
    
    # Custom endpoints with proper parameter handling
    path('dashboard/employee_overview/', 
         AssessmentDashboardViewSet.as_view({'get': 'employee_overview'}), 
         name='assessment-dashboard-employee-overview'),
    
    path('letter-grades/get_grade_for_percentage/', 
         LetterGradeMappingViewSet.as_view({'get': 'get_grade_for_percentage'}), 
         name='assessment-letter-grades-get-grade'),
    
    path('position-core/get_for_employee/', 
         PositionCoreAssessmentViewSet.as_view({'get': 'get_for_employee'}), 
         name='assessment-position-core-for-employee'),
    
    path('position-behavioral/get_for_employee/', 
         PositionBehavioralAssessmentViewSet.as_view({'get': 'get_for_employee'}), 
         name='assessment-position-behavioral-for-employee'),
    
    # Assessment status management endpoints
    path('employee-core/<uuid:pk>/save_draft/', 
         EmployeeCoreAssessmentViewSet.as_view({'post': 'save_draft'}), 
         name='assessment-employee-core-save-draft'),
    
    path('employee-core/<uuid:pk>/submit_assessment/', 
         EmployeeCoreAssessmentViewSet.as_view({'post': 'submit_assessment'}), 
         name='assessment-employee-core-submit'),
    
    path('employee-core/<uuid:pk>/reopen_assessment/', 
         EmployeeCoreAssessmentViewSet.as_view({'post': 'reopen_assessment'}), 
         name='assessment-employee-core-reopen'),
    
    path('employee-behavioral/<uuid:pk>/save_draft/', 
         EmployeeBehavioralAssessmentViewSet.as_view({'post': 'save_draft'}), 
         name='assessment-employee-behavioral-save-draft'),
    
    path('employee-behavioral/<uuid:pk>/submit_assessment/', 
         EmployeeBehavioralAssessmentViewSet.as_view({'post': 'submit_assessment'}), 
         name='assessment-employee-behavioral-submit'),
    
    path('employee-behavioral/<uuid:pk>/reopen_assessment/', 
         EmployeeBehavioralAssessmentViewSet.as_view({'post': 'reopen_assessment'}), 
         name='assessment-employee-behavioral-reopen'),
]