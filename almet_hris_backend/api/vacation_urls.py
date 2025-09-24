# api/vacation_urls.py - Enhanced URLs

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import vacation_views as views

# Router for ViewSets
router = DefaultRouter()
router.register(r'types', views.VacationTypeViewSet, basename='vacation-types')
router.register(r'notification-templates', views.NotificationTemplateViewSet, basename='notification-templates')

urlpatterns = [
    # Router URLs (Vacation Types & Notification Templates)
    path('', include(router.urls)),
    
    # ============= DASHBOARD =============
    path('dashboard/', views.vacation_dashboard, name='vacation-dashboard'),
    
    # ============= SEPARATED SETTINGS ENDPOINTS =============
    
    # Production Calendar Settings
    path('production-calendar/', views.get_production_calendar, name='vacation-get-production-calendar'),
    path('production-calendar/set/', views.set_production_calendar, name='vacation-set-production-calendar'),
    
    # General Vacation Settings (allow_negative_balance, max_schedule_edits, notifications)
    path('settings/', views.get_general_vacation_settings, name='vacation-get-general-settings'),
    path('settings/set/', views.set_general_vacation_settings, name='vacation-set-general-settings'),
    
    # HR Representative Settings
    path('hr-representatives/', views.get_hr_representatives, name='vacation-get-hr-representatives'),
    path('hr-representatives/set-default/', views.set_default_hr_representative, name='vacation-set-default-hr'),
    
    # ============= REQUEST SUBMISSION =============
    path('form-data/', views.get_form_data, name='vacation-form-data'),
    path('employees/search/', views.search_employees, name='vacation-search-employees'),
    
    # Request Immediately
    path('requests/immediate/', views.create_immediate_request, name='vacation-create-immediate-request'),
    
    # Scheduling
    path('schedules/create/', views.create_schedule, name='vacation-create-schedule'),
    path('schedules/tabs/', views.my_schedule_tabs, name='vacation-my-schedule-tabs'),
    path('schedules/<int:pk>/register/', views.register_schedule, name='vacation-register-schedule'),
    path('schedules/<int:pk>/edit/', views.edit_schedule, name='vacation-edit-schedule'),
    path('schedules/<int:pk>/delete/', views.delete_schedule, name='vacation-delete-schedule'),
    
    # ============= APPROVAL =============
    path('approval/pending/', views.approval_pending_requests, name='vacation-approval-pending'),
    path('approval/history/', views.approval_history, name='vacation-approval-history'),
    path('requests/<int:pk>/approve-reject/', views.approve_reject_request, name='vacation-approve-reject-request'),
    
    # ============= MY ALL REQUESTS & SCHEDULES =============
    path('my-all/', views.my_all_requests_schedules, name='vacation-my-all-requests-schedules'),
    path('my-all/export/', views.export_my_vacations, name='vacation-export-my-vacations'),
    
    # ============= BALANCE MANAGEMENT =============
    path('balances/bulk-upload/', views.bulk_upload_balances, name='vacation-bulk-upload-balances'),
    path('balances/template/', views.download_balance_template, name='vacation-download-balance-template'),
    path('balances/export/', views.export_balances, name='vacation-export-balances'),
    
    # ============= UTILITIES =============
    path('calculate-working-days/', views.calculate_working_days, name='vacation-calculate-working-days'),
]