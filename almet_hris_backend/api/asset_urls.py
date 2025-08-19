# api/asset_urls.py - CLEAN FINAL VERSION

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .asset_views import (
    AssetCategoryViewSet,
    AssetViewSet,


  
)



router = DefaultRouter()

# Asset management endpoints
router.register(r'categories', AssetCategoryViewSet, basename='assetcategory')
router.register(r'assets', AssetViewSet, basename='asset')




urlpatterns = [
    path('', include(router.urls)),
]