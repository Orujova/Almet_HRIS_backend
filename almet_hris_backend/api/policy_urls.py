from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .policy_views import (
    PolicyCategoryViewSet,
    CompanyPolicyViewSet,
    PolicyAcknowledgmentViewSet
)

router = DefaultRouter()
router.register('categories', PolicyCategoryViewSet, basename='policy-category')
router.register('policies', CompanyPolicyViewSet, basename='company-policy')
router.register('acknowledgments', PolicyAcknowledgmentViewSet, basename='policy-acknowledgment')

urlpatterns = [
    path('', include(router.urls)),
]