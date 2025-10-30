# api/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from . import views

# Competency Views Import
from .competency_views import (
    SkillGroupViewSet, SkillViewSet,
    BehavioralCompetencyGroupViewSet, BehavioralCompetencyViewSet,
    LeadershipCompetencyMainGroupViewSet, LeadershipCompetencyChildGroupViewSet, 
    LeadershipCompetencyItemViewSet,  # UPDATED: Added Leadership
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

# UPDATED: Competency Assessment Views Import with Leadership
from .competency_assessment_views import (
    CoreCompetencyScaleViewSet, BehavioralScaleViewSet, LetterGradeMappingViewSet,
    PositionCoreAssessmentViewSet, PositionBehavioralAssessmentViewSet,
    PositionLeadershipAssessmentViewSet,  # NEW: Leadership Position Assessment
    EmployeeCoreAssessmentViewSet, EmployeeBehavioralAssessmentViewSet,
    EmployeeLeadershipAssessmentViewSet,  # NEW: Leadership Employee Assessment
    AssessmentDashboardViewSet
)

from .role_views import RoleViewSet, PermissionViewSet, EmployeeRoleViewSet

router = DefaultRouter()


# ==================== ROLE & PERMISSION MANAGEMENT ====================
router.register(r'roles', RoleViewSet, basename='role')
router.register(r'permissions', PermissionViewSet, basename='permission')
router.register(r'employee-roles', EmployeeRoleViewSet, basename='employee-role')


# ==================== BUSINESS STRUCTURE ====================
router.register(r'business-functions', views.BusinessFunctionViewSet, basename='businessfunction')
router.register(r'departments', views.DepartmentViewSet, basename='department')
router.register(r'job-titles', views.JobTitleViewSet, basename='job-title')
router.register(r'units', views.UnitViewSet, basename='unit')
router.register(r'job-functions', views.JobFunctionViewSet, basename='jobfunction')
router.register(r'position-groups', views.PositionGroupViewSet, basename='positiongroup')


# ==================== EMPLOYEE MANAGEMENT ====================
router.register(r'employees', views.EmployeeViewSet, basename='employee')
router.register(r'employee-tags', views.EmployeeTagViewSet, basename='employeetag')
router.register(r'employee-statuses', views.EmployeeStatusViewSet, basename='employeestatus')
router.register(r'profile-images', views.ProfileImageViewSet, basename='profileimage')
router.register(r'contract-configs', views.ContractTypeConfigViewSet, basename='contractconfig')
router.register(r'vacant-positions', views.VacantPositionViewSet, basename='vacantposition')
router.register(r'org-chart', views.OrgChartViewSet, basename='orgchart')
router.register(r'employee-grading', views.EmployeeGradingViewSet, basename='employeegrading')
router.register(r'bulk-upload', views.BulkEmployeeUploadViewSet, basename='bulkupload')


# ==================== COMPETENCY MANAGEMENT ====================
# Skills
router.register(r'competency/skill-groups', SkillGroupViewSet, basename='competency-skillgroup')
router.register(r'competency/skills', SkillViewSet, basename='competency-skill')

# Behavioral Competencies
router.register(r'competency/behavioral-groups', BehavioralCompetencyGroupViewSet, basename='competency-behavioralgroup')
router.register(r'competency/behavioral-competencies', BehavioralCompetencyViewSet, basename='competency-behavioral')

# Leadership Competencies - NEW
router.register(r'competency/leadership-main-groups', LeadershipCompetencyMainGroupViewSet, basename='competency-leadership-main')
router.register(r'competency/leadership-child-groups', LeadershipCompetencyChildGroupViewSet, basename='competency-leadership-child')
router.register(r'competency/leadership-items', LeadershipCompetencyItemViewSet, basename='competency-leadership-items')


# ==================== JOB DESCRIPTIONS ====================
router.register(r'job-descriptions', JobDescriptionViewSet, basename='jobdescription')
router.register(r'job-description/business-resources', JobBusinessResourceViewSet, basename='jobbusinessresource')
router.register(r'job-description/access-matrix', AccessMatrixViewSet, basename='accessmatrix')
router.register(r'job-description/company-benefits', CompanyBenefitViewSet, basename='companybenefit')
router.register(r'job-description/stats', JobDescriptionStatsViewSet, basename='jobdescriptionstats')


# ==================== ASSET MANAGEMENT ====================
router.register(r'assets/categories', AssetCategoryViewSet, basename='assetcategory')
router.register(r'assets/assets', AssetViewSet, basename='asset')


# ==================== COMPETENCY ASSESSMENTS ====================
# Scale Management
router.register(r'assessments/core-scales', CoreCompetencyScaleViewSet, basename='assessment-core-scales')
router.register(r'assessments/behavioral-scales', BehavioralScaleViewSet, basename='assessment-behavioral-scales')
router.register(r'assessments/letter-grades', LetterGradeMappingViewSet, basename='assessment-letter-grades')

# Position Assessment Templates
router.register(r'assessments/position-core', PositionCoreAssessmentViewSet, basename='assessment-position-core')
router.register(r'assessments/position-behavioral', PositionBehavioralAssessmentViewSet, basename='assessment-position-behavioral')
router.register(r'assessments/position-leadership', PositionLeadershipAssessmentViewSet, basename='assessment-position-leadership')  # NEW

# Employee Assessments
router.register(r'assessments/employee-core', EmployeeCoreAssessmentViewSet, basename='assessment-employee-core')
router.register(r'assessments/employee-behavioral', EmployeeBehavioralAssessmentViewSet, basename='assessment-employee-behavioral')
router.register(r'assessments/employee-leadership', EmployeeLeadershipAssessmentViewSet, basename='assessment-employee-leadership')  # NEW

# Assessment Dashboard
router.register(r'assessments/dashboard', AssessmentDashboardViewSet, basename='assessment-dashboard')


# ==================== URL PATTERNS ====================
urlpatterns = [
    # Authentication
    path('auth/microsoft/', views.authenticate_microsoft, name='auth_microsoft'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('me/', views.user_info, name='user_info'),
    
    # Competency Stats
    path('competency/stats/', CompetencyStatsView.as_view(), name='competency-stats'),
    
    # Asset Activities & Export
    path('assets/assets/<uuid:pk>/activities/', 
         AssetViewSet.as_view({'get': 'activities'}), 
         name='asset-activities'),
    
    path('assets/assets/export/', 
         AssetViewSet.as_view({'post': 'export_assets'}), 
         name='asset-export'),
    
    # Org Chart Statistics
    path('org-chart/statistics/', 
         views.OrgChartViewSet.as_view({'get': 'get_statistics'}), 
         name='org_chart_statistics'),
    
    # Module URLs
    path('vacation/', include('api.vacation_urls')),
    path('business-trips/', include('api.business_trip_urls')),
    path('notifications/', include('api.notification_urls')),
    path('news/', include('api.news_urls')),
    path('performance/', include('api.performance_urls')),
    
    # Router URLs
    path('', include(router.urls)),
]