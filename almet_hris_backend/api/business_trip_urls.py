# api/business_trip_urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .business_trip_views import (
    TravelTypeViewSet,
    TransportTypeViewSet, 
    TripPurposeViewSet,
    ApprovalWorkflowViewSet,
    BusinessTripRequestViewSet,
    TripNotificationViewSet,
    TripSettingsViewSet
)

# Create router for business trip viewsets
business_trip_router = DefaultRouter()

# Configuration endpoints
business_trip_router.register(r'travel-types', TravelTypeViewSet, basename='travel-types')
business_trip_router.register(r'transport-types', TransportTypeViewSet, basename='transport-types')
business_trip_router.register(r'trip-purposes', TripPurposeViewSet, basename='trip-purposes')
business_trip_router.register(r'approval-workflows', ApprovalWorkflowViewSet, basename='approval-workflows')

# Main trip management endpoints
business_trip_router.register(r'requests', BusinessTripRequestViewSet, basename='trip-requests')

# Notification endpoints
business_trip_router.register(r'notifications', TripNotificationViewSet, basename='trip-notifications')

# Settings endpoints
business_trip_router.register(r'settings', TripSettingsViewSet, basename='trip-settings')

urlpatterns = [
    # Include all business trip routes
    path('', include(business_trip_router.urls)),
]