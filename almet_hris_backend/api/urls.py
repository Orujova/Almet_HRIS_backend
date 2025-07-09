# api/urls.py - ENHANCED: Complete URL Configuration with Advanced Contract Status Management

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from . import views

# Create router for viewsets
router = DefaultRouter()

# Business Structure URLs
router.register(r'business-functions', views.BusinessFunctionViewSet, basename='businessfunction')
router.register(r'departments', views.DepartmentViewSet, basename='department')
router.register(r'units', views.UnitViewSet, basename='unit')
router.register(r'job-functions', views.JobFunctionViewSet, basename='jobfunction')
router.register(r'position-groups', views.PositionGroupViewSet, basename='positiongroup')

# Employee Management URLs (ENHANCED with Line Manager features)
router.register(r'employees', views.EmployeeViewSet, basename='employee')
router.register(r'employee-tags', views.EmployeeTagViewSet, basename='employeetag')
router.register(r'employee-statuses', views.EmployeeStatusViewSet, basename='employeestatus')

# NEW: Contract Type Configuration URLs
router.register(r'contract-configs', views.ContractTypeConfigViewSet, basename='contractconfig')

# Vacancy Management URLs
router.register(r'vacant-positions', views.VacantPositionViewSet, basename='vacantposition')

# Organizational Chart URLs (ENHANCED with department-specific charts)
router.register(r'org-chart', views.OrgChartViewSet, basename='orgchart')

# Headcount Analytics URLs
router.register(r'headcount-summaries', views.HeadcountSummaryViewSet, basename='headcountsummary')

# Employee Grading Integration URLs
router.register(r'employee-grading', views.EmployeeGradingViewSet, basename='employeegrading')

# NEW: Contract Status Management URLs
router.register(r'contract-status', views.ContractStatusManagementViewSet, basename='contractstatus')

# NEW: Line Manager Management URLs
router.register(r'line-manager-management', views.LineManagerManagementViewSet, basename='linemanagermanagement')

# NEW: Employee Analytics URLs
router.register(r'employee-analytics', views.EmployeeAnalyticsViewSet, basename='employeeanalytics')

urlpatterns = [
    # Authentication endpoints
    path('auth/microsoft/', views.authenticate_microsoft, name='auth_microsoft'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
   
    # User endpoints
    path('me/', views.user_info, name='user_info'),
    
    # Include all router URLs
    path('', include(router.urls)),
]