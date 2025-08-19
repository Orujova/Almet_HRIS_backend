# api/asset_urls.py - CLEAN FINAL VERSION

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .asset_views import (
    AssetCategoryViewSet,
    AssetViewSet,
    AssetAssignmentViewSet,

    AssetStatsViewSet
)



router = DefaultRouter()

# Asset management endpoints
router.register(r'categories', AssetCategoryViewSet, basename='assetcategory')
router.register(r'assets', AssetViewSet, basename='asset')
router.register(r'assignments', AssetAssignmentViewSet, basename='assetassignment')

router.register(r'stats', AssetStatsViewSet, basename='assetstats')

urlpatterns = [
    path('', include(router.urls)),
]