# api/business_trip_urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .business_trip_views import (
    TravelTypeViewSet,
    TransportTypeViewSet, 
    TripPurposeViewSet,
    BusinessTripRequestViewSet,
    TripSettingsViewSet
)

# Create router for business trip viewsets
business_trip_router = DefaultRouter()

# Configuration endpoints
business_trip_router.register(r'travel-types', TravelTypeViewSet, basename='travel-types')
business_trip_router.register(r'transport-types', TransportTypeViewSet, basename='transport-types')
business_trip_router.register(r'trip-purposes', TripPurposeViewSet, basename='trip-purposes')


# Main trip management endpoints
business_trip_router.register(r'requests', BusinessTripRequestViewSet, basename='trip-requests')



# Settings endpoints
business_trip_router.register(r'settings', TripSettingsViewSet, basename='trip-settings')

urlpatterns = [
    # Include all business trip routes
    path('', include(business_trip_router.urls)),
]