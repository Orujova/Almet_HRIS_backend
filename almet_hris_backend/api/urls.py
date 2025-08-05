# urls.py - FIXED: URL Configuration

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

# Employee Management URLs
router.register(r'employees', views.EmployeeViewSet, basename='employee')
router.register(r'employee-tags', views.EmployeeTagViewSet, basename='employeetag')
router.register(r'employee-statuses', views.EmployeeStatusViewSet, basename='employeestatus')

# Profile Image Management
router.register(r'profile-images', views.ProfileImageViewSet, basename='profileimage')

# Contract Type Configuration URLs
router.register(r'contract-configs', views.ContractTypeConfigViewSet, basename='contractconfig')

# Vacancy Management URLs
router.register(r'vacant-positions', views.VacantPositionViewSet, basename='vacantposition')

# FIXED: Organizational Chart URLs
router.register(r'org-chart', views.OrgChartViewSet, basename='orgchart')

# Employee Grading Integration URLs
router.register(r'employee-grading', views.EmployeeGradingViewSet, basename='employeegrading')

# Bulk Upload URLs
router.register(r'bulk-upload', views.BulkEmployeeUploadViewSet, basename='bulkupload')

urlpatterns = [
    # Authentication endpoints
    path('auth/microsoft/', views.authenticate_microsoft, name='auth_microsoft'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
   
    # User endpoints
    path('me/', views.user_info, name='user_info'),
    
    # Vacancy-specific endpoints
    path('vacancies/convert-to-employee/<int:vacancy_id>/', 
         views.VacantPositionViewSet.as_view({'post': 'convert_to_employee'}), 
         name='convert_vacancy_to_employee'),
    
    path('vacancies/<int:pk>/mark-filled/', 
         views.VacantPositionViewSet.as_view({'post': 'mark_filled'}), 
         name='mark_vacancy_filled'),
    
    path('vacancies/<int:pk>/reopen/', 
         views.VacantPositionViewSet.as_view({'post': 'reopen_vacancy'}), 
         name='reopen_vacancy'),
    
    # Headcount endpoints with vacancy integration
    path('employees/headcount-with-vacancies/', 
         views.EmployeeViewSet.as_view({'get': 'headcount_with_vacancies'}), 
         name='headcount_with_vacancies'),
    
   
    
    # Statistics and filters
    path('org-chart/statistics/', 
         views.OrgChartViewSet.as_view({'get': 'get_statistics'}), 
         name='org_chart_statistics'),
         
    
    
    # Include all router URLs
    path('', include(router.urls)),
]