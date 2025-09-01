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
router.register(r'core-scales', CoreCompetencyScaleViewSet, basename='core-scales')
router.register(r'behavioral-scales', BehavioralScaleViewSet, basename='behavioral-scales')
router.register(r'letter-grades', LetterGradeMappingViewSet, basename='letter-grades')

# Position Assessment Template URLs
router.register(r'position-core-assessments', PositionCoreAssessmentViewSet, basename='position-core-assessments')
router.register(r'position-behavioral-assessments', PositionBehavioralAssessmentViewSet, basename='position-behavioral-assessments')

# Employee Assessment URLs
router.register(r'employee-core-assessments', EmployeeCoreAssessmentViewSet, basename='employee-core-assessments')
router.register(r'employee-behavioral-assessments', EmployeeBehavioralAssessmentViewSet, basename='employee-behavioral-assessments')

# Dashboard and Reporting URLs
router.register(r'dashboard', AssessmentDashboardViewSet, basename='assessment-dashboard')

urlpatterns = [
    # Include router URLs
    path('', include(router.urls)),
]
