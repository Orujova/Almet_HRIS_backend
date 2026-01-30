# api/document_urls.py - All Under One Base URL

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .document_views import (
    DocumentCompanyViewSet,
    DocumentFolderViewSet,
    DocumentViewSet,
    DocumentStatisticsViewSet
)

# Create router
router = DefaultRouter()

# Register viewsets - all under 'documents/' base
router.register(r'companies', DocumentCompanyViewSet, basename='document-company')
router.register(r'folders', DocumentFolderViewSet, basename='document-folder')
router.register(r'files', DocumentViewSet, basename='document')
router.register(r'statistics', DocumentStatisticsViewSet, basename='document-statistics')

# URL patterns
urlpatterns = [
    path('', include(router.urls)),
]

"""
RESULTING URLS:

/api/documents/companies/
/api/documents/companies/{id}/
/api/documents/companies/{id}/folders/

/api/documents/folders/
/api/documents/folders/{id}/
/api/documents/folders/{id}/documents/
/api/documents/folders/by-company/{company_id}/

/api/documents/files/
/api/documents/files/{id}/
/api/documents/files/{id}/view/
/api/documents/files/{id}/download/
/api/documents/files/{id}/archive/
/api/documents/files/{id}/unarchive/
/api/documents/files/by-folder/{folder_id}/
/api/documents/files/by-type/{doc_type}/
/api/documents/files/recent/
/api/documents/files/popular/

/api/documents/statistics/overview/
"""