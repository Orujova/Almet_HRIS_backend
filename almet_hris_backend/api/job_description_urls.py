# job_description_urls.py - UPDATE

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .job_description_views import (
    JobDescriptionViewSet,
    JobBusinessResourceViewSet,
    AccessMatrixViewSet,
    CompanyBenefitViewSet,
    JobDescriptionStatsViewSet
)

router = DefaultRouter()

# Main job description management
router.register(r'job-descriptions', JobDescriptionViewSet, basename='jobdescription')

# Extra tables for job description components
router.register(r'business-resources', JobBusinessResourceViewSet, basename='jobbusinessresource')
router.register(r'access-matrix', AccessMatrixViewSet, basename='accessmatrix')
router.register(r'company-benefits', CompanyBenefitViewSet, basename='companybenefit')

# Statistics
router.register(r'job-description-stats', JobDescriptionStatsViewSet, basename='jobdescriptionstats')

urlpatterns = [
    path('', include(router.urls)),
    
    # PDF Download endpoints
    path('job-descriptions/<uuid:pk>/download-pdf/', 
         JobDescriptionViewSet.as_view({'get': 'download_pdf'}), 
         name='job-description-download-pdf'),
    
    path('job-descriptions/<uuid:pk>/download-signed/', 
         JobDescriptionViewSet.as_view({'get': 'download_signed'}), 
         name='job-description-download-signed'),
    
    
]