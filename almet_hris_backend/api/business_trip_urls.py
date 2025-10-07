# api/business_trip_urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import business_trip_views as views

router = DefaultRouter()

# Configuration viewsets - these will be accessible at /api/business-trips/travel-types/, etc.
router.register(r'travel-types', views.TravelTypeViewSet, basename='travel-type')
router.register(r'transport-types', views.TransportTypeViewSet, basename='transport-type')
router.register(r'purposes', views.TripPurposeViewSet, basename='trip-purpose')

urlpatterns = [
    # Dashboard
    path('dashboard/', views.trip_dashboard, name='trip-dashboard'),
    
    # Configuration options (all dropdowns in one call)
    path('options/', views.get_all_options, name='trip-options'),
    
    # Settings - HR Representative
    path('settings/hr-representative/', views.update_hr_representative, name='trip-update-hr'),
    path('settings/hr-representatives/', views.get_hr_representatives, name='trip-get-hrs'),
    
    # Settings - Finance Approver
    path('settings/finance-approver/', views.update_finance_approver, name='trip-update-finance'),
    path('settings/finance-approvers/', views.get_finance_approvers, name='trip-get-finances'),
    
    # Settings - General
    path('settings/general/', views.update_general_settings, name='trip-update-settings'),
    path('settings/general/get/', views.get_general_settings, name='trip-get-settings'),
    
    # Requests
    path('requests/create/', views.create_trip_request, name='trip-create'),
    path('requests/my/', views.my_trip_requests, name='trip-my-requests'),
    path('requests/all/', views.all_trip_requests, name='trip-all-requests'),
    path('requests/export/', views.export_my_trips, name='trip-export-my'),
    path('requests/export-all/', views.export_all_trips, name='trip-export-all'),
    
    # Approval
    path('approval/pending/', views.pending_approvals, name='trip-pending'),
    path('approval/history/', views.approval_history, name='trip-history'),
    path('approval/<int:pk>/action/', views.approve_reject_request, name='trip-approve'),
    
    # Include router URLs (this will add travel-types/, transport-types/, purposes/)
    path('', include(router.urls)),
]