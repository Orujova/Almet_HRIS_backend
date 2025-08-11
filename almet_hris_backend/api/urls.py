# api/urls.py - Updated to include Job Description URLs

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from . import views

# Competency Views Import
from .competency_views import (
    SkillGroupViewSet, SkillViewSet,
    BehavioralCompetencyGroupViewSet, BehavioralCompetencyViewSet,
    CompetencyStatsView
)

# Job Description Views Import
from .job_description_views import (
    JobDescriptionViewSet,
    JobBusinessResourceViewSet,
    AccessMatrixViewSet,
    CompanyBenefitViewSet,
    JobDescriptionStatsViewSet
)

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

# Organizational Chart URLs
router.register(r'org-chart', views.OrgChartViewSet, basename='orgchart')

# Employee Grading Integration URLs
router.register(r'employee-grading', views.EmployeeGradingViewSet, basename='employeegrading')

# Bulk Upload URLs
router.register(r'bulk-upload', views.BulkEmployeeUploadViewSet, basename='bulkupload')

# Competency Management URLs
router.register(r'competency/skill-groups', SkillGroupViewSet, basename='competency-skillgroup')
router.register(r'competency/skills', SkillViewSet, basename='competency-skill')
router.register(r'competency/behavioral-groups', BehavioralCompetencyGroupViewSet, basename='competency-behavioralgroup')
router.register(r'competency/behavioral-competencies', BehavioralCompetencyViewSet, basename='competency-behavioral')

# Job Description Management URLs - NEW
router.register(r'job-descriptions', JobDescriptionViewSet, basename='jobdescription')
router.register(r'job-description/business-resources', JobBusinessResourceViewSet, basename='jobbusinessresource')
router.register(r'job-description/access-matrix', AccessMatrixViewSet, basename='accessmatrix')
router.register(r'job-description/company-benefits', CompanyBenefitViewSet, basename='companybenefit')
router.register(r'job-description/stats', JobDescriptionStatsViewSet, basename='jobdescriptionstats')


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
    
    # Competency Stats endpoint
    path('competency/stats/', CompetencyStatsView.as_view(), name='competency-stats'),
    
    # Job Description specific endpoints - NEW
    path('job-descriptions/<uuid:pk>/submit-for-approval/', 
         JobDescriptionViewSet.as_view({'post': 'submit_for_approval'}), 
         name='job-description-submit'),
    
    path('job-descriptions/<uuid:pk>/approve-as-line-manager/', 
         JobDescriptionViewSet.as_view({'post': 'approve_as_line_manager'}), 
         name='job-description-approve-manager'),
    
    path('job-descriptions/<uuid:pk>/approve-as-employee/', 
         JobDescriptionViewSet.as_view({'post': 'approve_as_employee'}), 
         name='job-description-approve-employee'),
    
    path('job-descriptions/<uuid:pk>/reject/', 
         JobDescriptionViewSet.as_view({'post': 'reject'}), 
         name='job-description-reject'),
    
    path('job-descriptions/<uuid:pk>/request-revision/', 
         JobDescriptionViewSet.as_view({'post': 'request_revision'}), 
         name='job-description-revision'),
    
    path('job-descriptions/<uuid:pk>/activities/', 
         JobDescriptionViewSet.as_view({'get': 'activities'}), 
         name='job-description-activities'),
    
    path('job-descriptions/pending-approvals/', 
         JobDescriptionViewSet.as_view({'get': 'pending_approvals'}), 
         name='job-description-pending'),
    
    path('job-descriptions/statistics/', 
         JobDescriptionViewSet.as_view({'get': 'statistics'}), 
         name='job-description-statistics'),
    
    path('job-descriptions/export/', 
         JobDescriptionViewSet.as_view({'post': 'export'}), 
         name='job-description-export'),
    
    # Statistics and filters
    path('org-chart/statistics/', 
         views.OrgChartViewSet.as_view({'get': 'get_statistics'}), 
         name='org_chart_statistics'),
    
    # Include all router URLs
    path('', include(router.urls)),
]