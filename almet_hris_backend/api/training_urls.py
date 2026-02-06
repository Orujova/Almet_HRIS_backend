# api/training_urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .training_views import (
TrainingRequestViewSet,
    TrainingViewSet,
    TrainingAssignmentViewSet,
    TrainingMaterialViewSet
)

router = DefaultRouter()

router.register(r'trainings', TrainingViewSet, basename='training')
router.register(r'assignments', TrainingAssignmentViewSet, basename='training-assignment')
router.register(r'materials', TrainingMaterialViewSet, basename='training-material')
router.register(r'requests', TrainingRequestViewSet, basename='training-request')

urlpatterns = [
    path('', include(router.urls)),
]