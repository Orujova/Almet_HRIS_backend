# api/urls.py

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

# Asset Management Views Import
from .asset_views import (
    AssetCategoryViewSet,
    AssetViewSet,
)

# UPDATED: Competency Assessment Views Import
from .competency_assessment_views import (
    CoreCompetencyScaleViewSet, BehavioralScaleViewSet, LetterGradeMappingViewSet,
    PositionCoreAssessmentViewSet, PositionBehavioralAssessmentViewSet,
    EmployeeCoreAssessmentViewSet, EmployeeBehavioralAssessmentViewSet,
    AssessmentDashboardViewSet
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

# Job Description Management URLs
router.register(r'job-descriptions', JobDescriptionViewSet, basename='jobdescription')
router.register(r'job-description/business-resources', JobBusinessResourceViewSet, basename='jobbusinessresource')
router.register(r'job-description/access-matrix', AccessMatrixViewSet, basename='accessmatrix')
router.register(r'job-description/company-benefits', CompanyBenefitViewSet, basename='companybenefit')
router.register(r'job-description/stats', JobDescriptionStatsViewSet, basename='jobdescriptionstats')

# Asset Management URLs
router.register(r'assets/categories', AssetCategoryViewSet, basename='assetcategory')
router.register(r'assets/assets', AssetViewSet, basename='asset')

# UPDATED: Competency Assessment URLs - simplified structure
router.register(r'assessments/core-scales', CoreCompetencyScaleViewSet, basename='assessment-core-scales')
router.register(r'assessments/behavioral-scales', BehavioralScaleViewSet, basename='assessment-behavioral-scales')
router.register(r'assessments/letter-grades', LetterGradeMappingViewSet, basename='assessment-letter-grades')
router.register(r'assessments/position-core', PositionCoreAssessmentViewSet, basename='assessment-position-core')
router.register(r'assessments/position-behavioral', PositionBehavioralAssessmentViewSet, basename='assessment-position-behavioral')
router.register(r'assessments/employee-core', EmployeeCoreAssessmentViewSet, basename='assessment-employee-core')
router.register(r'assessments/employee-behavioral', EmployeeBehavioralAssessmentViewSet, basename='assessment-employee-behavioral')
router.register(r'assessments/dashboard', AssessmentDashboardViewSet, basename='assessment-dashboard')

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
    
    # Asset management endpoints
    path('assets/assets/<uuid:pk>/activities/', 
         AssetViewSet.as_view({'get': 'activities'}), 
         name='asset-activities'),
    
    path('assets/assets/export/', 
         AssetViewSet.as_view({'post': 'export_assets'}), 
         name='asset-export'),
    
    # Statistics and filters
    path('org-chart/statistics/', 
         views.OrgChartViewSet.as_view({'get': 'get_statistics'}), 
         name='org_chart_statistics'),
    
    # Include router URLs
    path('', include(router.urls)),
]
