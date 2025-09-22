# api/vacation_urls.py - Updated Vacation Management System URLs

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .vacation_views import (
    VacationSettingViewSet,
    VacationTypeViewSet,
    EmployeeVacationBalanceViewSet,
    VacationRequestViewSet,
    VacationScheduleViewSet,
    VacationStatisticsViewSet
)
from .additional_vacation_views import (
    vacation_dashboard_view,
    request_submission_view,
    approval_pending_view,
    approval_history_view,
    schedule_conflicts_view,
    my_schedules_lists_view,
    bulk_schedule_register,
    production_calendar_view
)

# Create router for vacation viewsets
vacation_router = DefaultRouter()

# Vacation system configuration
vacation_router.register(r'settings', VacationSettingViewSet, basename='vacation-settings')
vacation_router.register(r'types', VacationTypeViewSet, basename='vacation-types')

# Employee vacation management
vacation_router.register(r'balances', EmployeeVacationBalanceViewSet, basename='vacation-balances')
vacation_router.register(r'requests', VacationRequestViewSet, basename='vacation-requests')
vacation_router.register(r'schedules', VacationScheduleViewSet, basename='vacation-schedules')

# Statistics and analytics
vacation_router.register(r'statistics', VacationStatisticsViewSet, basename='vacation-statistics')

# Vacation URL patterns
vacation_urlpatterns = [
    # Include router URLs
    path('', include(vacation_router.urls)),
    
    # Dashboard endpoints - Main sections as per requirements
    path('dashboard/', vacation_dashboard_view, name='vacation-dashboard'),
    path('dashboard/stats/', VacationRequestViewSet.as_view({'get': 'dashboard_stats'}), name='vacation-dashboard-stats'),
    
    # Request Submission section endpoints
    path('submission/', request_submission_view, name='vacation-request-submission'),
    path('submission/immediate/', VacationRequestViewSet.as_view({'post': 'create'}), name='vacation-request-immediate'),
    path('submission/scheduled/', VacationScheduleViewSet.as_view({'post': 'create'}), name='vacation-schedule-create'),
    
    # Approval section endpoints
    path('approval/pending/', approval_pending_view, name='vacation-approval-pending'),
    path('approval/history/', approval_history_view, name='vacation-approval-history'),
    
    # Balance management endpoints
    path('balances/my-balance/', EmployeeVacationBalanceViewSet.as_view({'get': 'my_balance'}), name='my-vacation-balance'),
    path('balances/bulk-upload/', EmployeeVacationBalanceViewSet.as_view({'post': 'bulk_upload'}), name='vacation-balance-bulk-upload'),
    path('balances/export-template/', EmployeeVacationBalanceViewSet.as_view({'get': 'export_template'}), name='vacation-balance-template'),
    
    # Request management endpoints with specific views
    path('requests/my-requests/', VacationRequestViewSet.as_view({'get': 'list'}), name='my-vacation-requests'),
    path('requests/my-team/', VacationRequestViewSet.as_view({'get': 'list'}), name='team-vacation-requests'),
    path('requests/pending-approvals/', VacationRequestViewSet.as_view({'get': 'list'}), name='pending-vacation-approvals'),
    path('requests/hr-approval/', VacationRequestViewSet.as_view({'get': 'list'}), name='hr-vacation-approvals'),
    
    # Schedule management endpoints with specific views as per requirements
    path('schedules/my-schedules/', VacationScheduleViewSet.as_view({'get': 'list'}), name='my-vacation-schedules'),
    path('schedules/my-team/', VacationScheduleViewSet.as_view({'get': 'list'}), name='team-vacation-schedules'),
    path('schedules/my-peers/', VacationScheduleViewSet.as_view({'get': 'list'}), name='peers-vacation-schedules'),
    path('schedules/upcoming/', VacationScheduleViewSet.as_view({'get': 'list'}), name='upcoming-vacation-schedules'),
    path('schedules/lists/', my_schedules_lists_view, name='my-schedules-lists'),  # For the 3 tabs at bottom
    
    # Approval workflow endpoints
    path('requests/<int:pk>/submit/', VacationRequestViewSet.as_view({'post': 'submit'}), name='submit-vacation-request'),
    path('requests/<int:pk>/approve-reject/', VacationRequestViewSet.as_view({'post': 'approve_reject'}), name='approve-reject-vacation-request'),
    path('requests/<int:pk>/conflicts/', VacationRequestViewSet.as_view({'get': 'conflicts'}), name='vacation-request-conflicts'),
    
    # Schedule management endpoints
    path('schedules/<int:pk>/register/', VacationScheduleViewSet.as_view({'post': 'register_as_taken'}), name='register-vacation-schedule'),
    path('schedules/<int:pk>/conflicts/', schedule_conflicts_view, name='vacation-schedule-conflicts'),
    path('schedules/bulk-register/', bulk_schedule_register, name='bulk-schedule-register'),
    
    # Statistics and reporting endpoints
    path('statistics/overview/', VacationStatisticsViewSet.as_view({'get': 'overview'}), name='vacation-statistics-overview'),
    path('statistics/department-analysis/', VacationStatisticsViewSet.as_view({'get': 'department_analysis'}), name='vacation-department-analysis'),
    
    # Settings management endpoints
    path('settings/active/', VacationSettingViewSet.as_view({'get': 'active'}), name='active-vacation-settings'),
    path('settings/<int:pk>/activate/', VacationSettingViewSet.as_view({'post': 'activate'}), name='activate-vacation-settings'),
    path('settings/production-calendar/', production_calendar_view, name='production-calendar'),
]

# Export for main urls.py
urlpatterns = vacation_urlpatterns# api/vacation_urls.py - Updated Vacation Management System URLs

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .vacation_views import (
    VacationSettingViewSet,
    VacationTypeViewSet,
    EmployeeVacationBalanceViewSet,
    VacationRequestViewSet,
    VacationScheduleViewSet,
    VacationStatisticsViewSet
)

# Create router for vacation viewsets
vacation_router = DefaultRouter()

# Vacation system configuration
vacation_router.register(r'settings', VacationSettingViewSet, basename='vacation-settings')
vacation_router.register(r'types', VacationTypeViewSet, basename='vacation-types')

# Employee vacation management
vacation_router.register(r'balances', EmployeeVacationBalanceViewSet, basename='vacation-balances')
vacation_router.register(r'requests', VacationRequestViewSet, basename='vacation-requests')
vacation_router.register(r'schedules', VacationScheduleViewSet, basename='vacation-schedules')

# Statistics and analytics
vacation_router.register(r'statistics', VacationStatisticsViewSet, basename='vacation-statistics')

# Vacation URL patterns
vacation_urlpatterns = [
    # Include router URLs
    path('', include(vacation_router.urls)),
    
    # Additional custom endpoints for specific functionality
    # These endpoints provide specialized views not covered by the standard viewsets
    
    # Dashboard endpoints
    path('dashboard/stats/', VacationRequestViewSet.as_view({'get': 'dashboard_stats'}), name='vacation-dashboard-stats'),
    
    # Balance management endpoints
   
    path('balances/export-template/', EmployeeVacationBalanceViewSet.as_view({'get': 'export_template'}), name='vacation-balance-template'),
    
    # Request management endpoints with specific views
    # These provide filtered views of requests based on user roles
    path('requests/my-requests/', VacationRequestViewSet.as_view({'get': 'list'}), name='my-vacation-requests'),
    path('requests/my-team/', VacationRequestViewSet.as_view({'get': 'list'}), name='team-vacation-requests'),
    path('requests/pending-approvals/', VacationRequestViewSet.as_view({'get': 'list'}), name='pending-vacation-approvals'),
    path('requests/hr-approval/', VacationRequestViewSet.as_view({'get': 'list'}), name='hr-vacation-approvals'),
    
    # Schedule management endpoints with specific views
    path('schedules/my-schedules/', VacationScheduleViewSet.as_view({'get': 'list'}), name='my-vacation-schedules'),
    path('schedules/my-team/', VacationScheduleViewSet.as_view({'get': 'list'}), name='team-vacation-schedules'),
    path('schedules/my-peers/', VacationScheduleViewSet.as_view({'get': 'list'}), name='peers-vacation-schedules'),
    path('schedules/upcoming/', VacationScheduleViewSet.as_view({'get': 'list'}), name='upcoming-vacation-schedules'),
    
    # Approval workflow endpoints
    path('requests/<int:pk>/submit/', VacationRequestViewSet.as_view({'post': 'submit'}), name='submit-vacation-request'),
    path('requests/<int:pk>/approve-reject/', VacationRequestViewSet.as_view({'post': 'approve_reject'}), name='approve-reject-vacation-request'),
    path('requests/<int:pk>/conflicts/', VacationRequestViewSet.as_view({'get': 'conflicts'}), name='vacation-request-conflicts'),
    
    # Schedule registration endpoint
    path('schedules/<int:pk>/register/', VacationScheduleViewSet.as_view({'post': 'register_as_taken'}), name='register-vacation-schedule'),
    path('schedules/<int:pk>/conflicts/', VacationScheduleViewSet.as_view({'get': 'conflicts'}), name='vacation-schedule-conflicts'),
    
    # Statistics and reporting endpoints
    path('statistics/overview/', VacationStatisticsViewSet.as_view({'get': 'overview'}), name='vacation-statistics-overview'),
    path('statistics/department-analysis/', VacationStatisticsViewSet.as_view({'get': 'department_analysis'}), name='vacation-department-analysis'),
    
    # Settings management endpoints
    path('settings/active/', VacationSettingViewSet.as_view({'get': 'active'}), name='active-vacation-settings'),
    path('settings/<int:pk>/activate/', VacationSettingViewSet.as_view({'post': 'activate'}), name='activate-vacation-settings'),
]

# Export for main urls.py
urlpatterns = vacation_urlpatterns