# api/handover_urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .handover_views import (
    HandoverTypeViewSet,
    HandoverRequestViewSet,
    HandoverTaskViewSet,
    HandoverAttachmentViewSet
)

router = DefaultRouter()

# Handover Types
router.register(r'types', HandoverTypeViewSet, basename='handover-type')

# Handover Requests
router.register(r'requests', HandoverRequestViewSet, basename='handover-request')

# Handover Tasks
router.register(r'tasks', HandoverTaskViewSet, basename='handover-task')

# Handover Attachments
router.register(r'attachments', HandoverAttachmentViewSet, basename='handover-attachment')

urlpatterns = [
    path('', include(router.urls)),
]
