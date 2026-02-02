# api/document_views.py - FIXED with Manual Companies Support

from rest_framework import viewsets, status, filters, parsers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q, Count
from django_filters.rest_framework import DjangoFilterBackend
import logging

from .document_models import DocumentCompany, DocumentFolder, Document
from .document_serializers import (
    DocumentCompanySerializer, DocumentCompanyCreateSerializer,
    DocumentFolderSerializer, DocumentFolderCreateSerializer,
    DocumentListSerializer, DocumentDetailSerializer,
    DocumentCreateUpdateSerializer, DocumentStatisticsSerializer
)
from .models import BusinessFunction

logger = logging.getLogger(__name__)


# ==================== DOCUMENT COMPANY VIEWS ====================

class DocumentCompanyViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing document companies
    
    Two types:
    1. Auto-created from BusinessFunctions (read-only)
    2. Manual companies (can create/edit/delete)
    """
    
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'code']
    ordering_fields = ['code', 'name', 'created_at']
    ordering = ['code']
    
    def get_queryset(self):
        """
        Return ALL companies:
        - BusinessFunctions (auto-created)
        - Manual DocumentCompanies
        """
        queryset = DocumentCompany.objects.all()
        
        # Filter by active status
        is_active = self.request.query_params.get('is_active')
        if is_active == 'true':
            queryset = queryset.filter(is_active=True)
        
        return queryset.prefetch_related('folders').order_by('code')
    
    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return DocumentCompanyCreateSerializer
        return DocumentCompanySerializer
    
    def list(self, request, *args, **kwargs):
        """
        List all companies including auto-created from BusinessFunctions
        """
        # First, sync BusinessFunctions
        self._sync_business_functions()
        
        return super().list(request, *args, **kwargs)
    
    def _sync_business_functions(self):
        """
        Auto-create DocumentCompany for each BusinessFunction
        """
        business_functions = BusinessFunction.objects.filter(is_active=True)
        
        for bf in business_functions:
            # Check if DocumentCompany already exists
            company, created = DocumentCompany.objects.get_or_create(
                business_function=bf,
                defaults={
                    'name': bf.name,
                    'code': bf.code,
                 
                    'icon': '🏢',
                  
                    'is_active': bf.is_active
                }
            )
            
            if created:
                logger.info(f"Auto-created DocumentCompany for BusinessFunction: {bf.name}")
            else:
                # Update if BusinessFunction changed
                if company.name != bf.name or company.code != bf.code:
                    company.name = bf.name
                    company.code = bf.code
                    company.is_active = bf.is_active
                    company.save()
                    logger.info(f"Updated DocumentCompany for BusinessFunction: {bf.name}")
    
    def perform_create(self, serializer):
        """
        Create MANUAL company (without BusinessFunction)
        Anyone can create manual companies like 'General', 'Templates', etc.
        """
        serializer.save(created_by=self.request.user, business_function=None)
        logger.info(f"Manual document company created: {serializer.instance.name} by {self.request.user.username}")
    
    def perform_update(self, serializer):
        instance = serializer.instance
        
        # Don't allow editing auto-created companies
        if instance.business_function:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({
                "detail": "Cannot edit auto-created company. This is linked to BusinessFunction. Edit the BusinessFunction instead."
            })
        
        serializer.save()
        logger.info(f"Document company updated: {serializer.instance.name}")
    
    def perform_destroy(self, instance):
        # Don't allow deleting auto-created companies
        if instance.business_function:
            from rest_framework.exceptions import ValidationError
            raise ValidationError(
                "Cannot delete auto-created company. This is linked to BusinessFunction."
            )
        
        if instance.folders.exists():
            from rest_framework.exceptions import ValidationError
            raise ValidationError(
                f"Cannot delete '{instance.name}' - it has {instance.folders.count()} folders. "
                "Please delete all folders first."
            )
        
        instance.delete()
        logger.info(f"Document company deleted: {instance.name}")
    
    @action(detail=True, methods=['get'])
    def folders(self, request, pk=None):
        """Get all folders for this company"""
        company = self.get_object()
        folders = company.folders.filter(is_active=True).order_by('order', 'name')
        serializer = DocumentFolderSerializer(folders, many=True, context={'request': request})
        return Response(serializer.data)


# ==================== DOCUMENT FOLDER VIEWS ====================

class DocumentFolderViewSet(viewsets.ModelViewSet):
    """ViewSet for managing document folders"""
    
    queryset = DocumentFolder.objects.select_related('company', 'created_by').prefetch_related('documents')
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['company', 'is_active']
    search_fields = ['name', 'description']
    ordering_fields = ['order', 'name', 'created_at']
    ordering = ['company', 'order', 'name']
    
    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return DocumentFolderCreateSerializer
        return DocumentFolderSerializer
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
        logger.info(f"Document folder created: {serializer.instance.name} by {self.request.user.username}")
    
    def perform_update(self, serializer):
        serializer.save()
        logger.info(f"Document folder updated: {serializer.instance.name}")
    
    def perform_destroy(self, instance):
        if instance.documents.exists():
            from rest_framework.exceptions import ValidationError
            raise ValidationError(
                f"Cannot delete folder '{instance.name}' - it has {instance.documents.count()} documents. "
                "Please delete all documents first."
            )
        instance.delete()
        logger.info(f"Document folder deleted: {instance.name}")
    
    @action(detail=False, methods=['get'], url_path='by-company/(?P<company_id>[^/.]+)')
    def by_company(self, request, company_id=None):
        """Get all folders for a specific company"""
        folders = self.queryset.filter(company_id=company_id, is_active=True)
        serializer = self.get_serializer(folders, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def documents(self, request, pk=None):
        """Get all documents in this folder"""
        folder = self.get_object()
        documents = Document.objects.filter(
            folder=folder,
        
            is_archived=False
        ).select_related('folder', 'folder__company').order_by('-updated_at')
        
        serializer = DocumentListSerializer(documents, many=True, context={'request': request})
        
        # CRITICAL: Return array directly
        return Response(serializer.data)


# ==================== DOCUMENT VIEWS ====================

class DocumentViewSet(viewsets.ModelViewSet):
    """ViewSet for managing documents with FILE UPLOAD"""
    
    queryset = Document.objects.select_related(
        'folder', 'folder__company', 'created_by', 'updated_by'
    )
    
    permission_classes = [IsAuthenticated]
    
    parser_classes = [
        parsers.MultiPartParser,
        parsers.FormParser,
        parsers.JSONParser,
    ]
    
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['folder', 'document_type', 'is_active', 'is_archived']
    search_fields = ['title', 'description', 'tags']
    ordering_fields = ['title', 'updated_at', 'created_at', 'view_count', 'download_count']
    ordering = ['-updated_at']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return DocumentListSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return DocumentCreateUpdateSerializer
        return DocumentDetailSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by document type
        doc_type = self.request.query_params.get('type', None)
        if doc_type:
            queryset = queryset.filter(document_type=doc_type)
        
        # Filter by company
        company_id = self.request.query_params.get('company', None)
        if company_id:
            queryset = queryset.filter(folder__company_id=company_id)
        
        # Exclude archived by default
        if self.request.query_params.get('include_archived') != 'true':
            queryset = queryset.filter(is_archived=False)
        
        return queryset
    
    def create(self, request, *args, **kwargs):
        """Create new document with file upload"""
        logger.info(f"Document creation request from {request.user.username}")
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        
        logger.info(f"Document created: {serializer.instance.title}")
        
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
    
    def update(self, request, *args, **kwargs):
        """Update document with optional file replacement"""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        
        logger.info(f"Document update request for '{instance.title}'")
        
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        
        return Response(serializer.data)
    
    def partial_update(self, request, *args, **kwargs):
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)
    
    def perform_create(self, serializer):
        document = serializer.save(created_by=self.request.user)
        logger.info(f"Document created: {document.title}")
    
    def perform_update(self, serializer):
        document = serializer.save(updated_by=self.request.user)
        logger.info(f"Document updated: {document.title}")
    
    def perform_destroy(self, instance):
        document_title = instance.title
        instance.delete()
        logger.info(f"Document deleted: {document_title}")
    
    @action(detail=False, methods=['get'], url_path='by-folder/(?P<folder_id>[^/.]+)')
    def by_folder(self, request, folder_id=None):
        """Get all documents for a specific folder"""
        documents = self.queryset.filter(folder_id=folder_id, is_active=True)
        serializer = DocumentListSerializer(documents, many=True, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], url_path='by-type/(?P<doc_type>[^/.]+)')
    def by_type(self, request, doc_type=None):
        """Get all documents of a specific type"""
        documents = self.queryset.filter(document_type=doc_type, is_active=True)
        serializer = DocumentListSerializer(documents, many=True, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def view(self, request, pk=None):
        """Track document view"""
        document = self.get_object()
        document.increment_view_count()
        
        return Response({
            'message': 'Document view tracked',
            'view_count': document.view_count,
        })
    
    @action(detail=True, methods=['post'])
    def download(self, request, pk=None):
        """Track document download"""
        document = self.get_object()
        document.increment_download_count()
        
        return Response({
            'message': 'Document download tracked',
            'download_count': document.download_count,
            'file_url': request.build_absolute_uri(document.document_file.url) if document.document_file else None
        })
    
    @action(detail=True, methods=['post'])
    def archive(self, request, pk=None):
        """Archive a document"""
        document = self.get_object()
        document.is_archived = True
        document.save(update_fields=['is_archived'])
        
        return Response({'message': 'Document archived successfully'})
    
    @action(detail=True, methods=['post'])
    def unarchive(self, request, pk=None):
        """Unarchive a document"""
        document = self.get_object()
        document.is_archived = False
        document.save(update_fields=['is_archived'])
        
        return Response({'message': 'Document unarchived successfully'})
    
    @action(detail=False, methods=['get'])
    def recent(self, request):
        """Get recently updated documents"""
        limit = int(request.query_params.get('limit', 10))
        documents = self.queryset.filter(is_active=True, is_archived=False)[:limit]
        serializer = DocumentListSerializer(documents, many=True, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def popular(self, request):
        """Get most viewed/downloaded documents"""
        limit = int(request.query_params.get('limit', 10))
        documents = self.queryset.filter(
            is_active=True,
            is_archived=False
        ).order_by('-view_count', '-download_count')[:limit]
        
        serializer = DocumentListSerializer(documents, many=True, context={'request': request})
        return Response(serializer.data)


# ==================== STATISTICS VIEWS ====================

class DocumentStatisticsViewSet(viewsets.ViewSet):
    """ViewSet for document statistics"""
    
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def overview(self, request):
        """Get overall document statistics"""
        total_companies = DocumentCompany.objects.filter(is_active=True).count()
        total_folders = DocumentFolder.objects.filter(is_active=True).count()
        total_documents = Document.objects.filter(is_active=True, is_archived=False).count()
        
        # Documents by type
        documents_by_type = {}
        for doc_type, label in Document.DOCUMENT_TYPES:
            count = Document.objects.filter(
                document_type=doc_type,
                is_active=True,
                is_archived=False
            ).count()
            if count > 0:
                documents_by_type[label] = count
        
        # Total views and downloads
        documents = Document.objects.filter(is_active=True, is_archived=False)
        total_views = sum(d.view_count for d in documents)
        total_downloads = sum(d.download_count for d in documents)
        
        # Recent documents
        recent_docs = documents.order_by('-updated_at')[:5]
        
        return Response({
            'total_companies': total_companies,
            'total_folders': total_folders,
            'total_documents': total_documents,
            'documents_by_type': documents_by_type,
            'total_views': total_views,
            'total_downloads': total_downloads,
            'recent_documents': DocumentListSerializer(
                recent_docs,
                many=True,
                context={'request': request}
            ).data
        })