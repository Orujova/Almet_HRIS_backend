# api/company_policies_urls.py - FULL URL Configuration

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .policy_views import (
    PolicyFolderViewSet,
    CompanyPolicyViewSet,
    BusinessFunctionPolicyViewSet,
    PolicyStatisticsViewSet
)

# Create router
router = DefaultRouter()

# Register viewsets with router
router.register(r'policy-folders', PolicyFolderViewSet, basename='policy-folder')
router.register(r'policies', CompanyPolicyViewSet, basename='policy')
router.register(r'business-functions-policies', BusinessFunctionPolicyViewSet, basename='business-function-policy')
router.register(r'policy-statistics', PolicyStatisticsViewSet, basename='policy-statistics')

# URL patterns
urlpatterns = [
    # Include all router URLs
    path('', include(router.urls)),
]
