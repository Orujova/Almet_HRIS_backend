# api/policy_views.py - COMPLETE FILE

from rest_framework import viewsets, status, filters, parsers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db.models import Q, Count, Sum, Prefetch
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
import logging

from .policy_models import (
    PolicyFolder, CompanyPolicy, PolicyAcknowledgment,

)
from .policy_serializers import (
    PolicyFolderSerializer, PolicyFolderCreateUpdateSerializer,
    CompanyPolicyListSerializer, CompanyPolicyDetailSerializer,
    CompanyPolicyCreateUpdateSerializer, PolicyAcknowledgmentSerializer,

 BusinessFunctionWithFoldersSerializer,

)
from .models import BusinessFunction, Employee

logger = logging.getLogger(__name__)


# ==================== COMPANY POLICY VIEWS ====================

class CompanyPolicyViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing company policies with FILE UPLOAD support
    """
    
    queryset = CompanyPolicy.objects.select_related(
        'folder', 'folder__business_function',
        'created_by', 'updated_by', 
    ).prefetch_related('acknowledgments')
    
    permission_classes = [IsAuthenticated]
    
    # CRITICAL: Add MultiPartParser for file uploads
    parser_classes = [
        parsers.MultiPartParser,
        parsers.FormParser,
        parsers.JSONParser,
    ]
    
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = [
        'folder', 
        'requires_acknowledgment', 'is_active'
    ]
    search_fields = ['title', 'description']
    ordering_fields = [
        'title', 'updated_at', 'created_at', 
        'view_count', 'download_count'
    ]
    ordering = ['-updated_at']
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'list':
            return CompanyPolicyListSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return CompanyPolicyCreateUpdateSerializer
        return CompanyPolicyDetailSerializer
    
    def get_queryset(self):
        """Filter queryset based on query parameters"""
        queryset = super().get_queryset()
        
        # Filter by business function
        bf_id = self.request.query_params.get('business_function', None)
        if bf_id:
            queryset = queryset.filter(folder__business_function_id=bf_id)
        
        # Filter by active status
        is_active = self.request.query_params.get('is_active', None)
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        return queryset
    
    # NO @swagger_auto_schema on create/update/partial_update - let DRF handle it
    
    def create(self, request, *args, **kwargs):
        """Create new policy with file upload"""
        logger.info(f"Policy creation request from {request.user.username}")
        logger.debug(f"Request data: {request.data}")
        logger.debug(f"Request files: {request.FILES}")
        
        # Validate file presence
        if 'policy_file' not in request.FILES:
            return Response(
                {
                    'error': 'policy_file is required',
                    'detail': 'Please upload a PDF file'
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = self.get_serializer(data=request.data)
        
        try:
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
            
            logger.info(
                f"Policy created successfully: {serializer.instance.title} "
                f"(ID: {serializer.instance.id})"
            )
            
            headers = self.get_success_headers(serializer.data)
            return Response(
                serializer.data,
                status=status.HTTP_201_CREATED,
                headers=headers
            )
        except Exception as e:
            logger.error(f"Policy creation failed: {str(e)}")
            raise
    
    def update(self, request, *args, **kwargs):
        """Update policy with optional file replacement"""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        
        logger.info(
            f"Policy update request for '{instance.title}' by {request.user.username}"
        )
        
        serializer = self.get_serializer(
            instance,
            data=request.data,
            partial=partial
        )
        
        try:
            serializer.is_valid(raise_exception=True)
            self.perform_update(serializer)
            
            logger.info(f"Policy updated successfully: {serializer.instance.title}")
            
            return Response(serializer.data)
        except Exception as e:
            logger.error(f"Policy update failed: {str(e)}")
            raise
    
    def partial_update(self, request, *args, **kwargs):
        """Partial update of policy"""
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)
    
    def perform_create(self, serializer):
        """Set created_by user when creating policy"""
        policy = serializer.save(created_by=self.request.user)
        logger.info(f"Policy created: {policy.title} by {self.request.user.username}")
    
    def perform_update(self, serializer):
        """Set updated_by user and handle status changes"""
        policy = serializer.save(updated_by=self.request.user)
        logger.info(f"Policy updated: {policy.title} by {self.request.user.username}")
    
    def perform_destroy(self, instance):
        """Log policy deletion"""
        policy_title = instance.title
        instance.delete()
        logger.info(f"Policy deleted: {policy_title} by {self.request.user.username}")
    
    @swagger_auto_schema(
        operation_description="Get all policies for a specific folder",
        responses={
            200: CompanyPolicyListSerializer(many=True),
            404: 'Folder Not Found'
        }
    )
    @action(detail=False, methods=['get'], url_path='by-folder/(?P<folder_id>[^/.]+)')
    def by_folder(self, request, folder_id=None):
        """Get all policies for a specific folder"""
        try:
            folder = PolicyFolder.objects.get(id=folder_id)
        except PolicyFolder.DoesNotExist:
            return Response(
                {'error': 'Folder not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        policies = self.queryset.filter(
            folder=folder,
            is_active=True
        )
        
        serializer = CompanyPolicyListSerializer(
            policies,
            many=True,
            context={'request': request}
        )
        return Response(serializer.data)


 
    @swagger_auto_schema(
        operation_description="Track policy view and increment view counter",
        responses={
            200: openapi.Response(
                description="View tracked successfully",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'message': openapi.Schema(type=openapi.TYPE_STRING),
                        'view_count': openapi.Schema(type=openapi.TYPE_INTEGER),
                  
                    }
                )
            ),
            404: 'Policy Not Found'
        }
    )
    @action(detail=True, methods=['post'])
    def view(self, request, pk=None):
        """Track policy view"""
        policy = self.get_object()
        
        # Increment view count
        policy.increment_view_count()
        
     
        
        logger.info(f"Policy viewed: {policy.title} by {request.user.username}")
        
        return Response({
            'message': 'Policy view tracked successfully',
            'view_count': policy.view_count,
     
        })
    
    @swagger_auto_schema(
        operation_description="Track policy download and increment download counter",
        responses={
            200: openapi.Response(
                description="Download tracked successfully",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'message': openapi.Schema(type=openapi.TYPE_STRING),
                        'download_count': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'file_url': openapi.Schema(type=openapi.TYPE_STRING),
                    }
                )
            ),
            404: 'Policy Not Found'
        }
    )
    @action(detail=True, methods=['post'])
    def download(self, request, pk=None):
        """Track policy download"""
        policy = self.get_object()
        
        # Increment download count
        policy.increment_download_count()
        
   
        logger.info(f"Policy downloaded: {policy.title} by {request.user.username}")
        
        return Response({
            'message': 'Policy download tracked successfully',
            'download_count': policy.download_count,
            'file_url': request.build_absolute_uri(policy.policy_file.url) if policy.policy_file else None
        })
    

    
    @swagger_auto_schema(
        operation_description="Acknowledge policy reading by employee",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'notes': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description='Additional notes or comments'
                )
            }
        ),
        responses={
            201: PolicyAcknowledgmentSerializer,
            200: openapi.Response(
                description="Already acknowledged",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'message': openapi.Schema(type=openapi.TYPE_STRING),
                        'already_acknowledged': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                    }
                )
            ),
            400: 'Employee profile not found',
            404: 'Policy Not Found'
        }
    )
    @action(detail=True, methods=['post'])
    def acknowledge(self, request, pk=None):
        """Acknowledge policy reading"""
        policy = self.get_object()
        
        # Get employee from request user
        try:
            employee = Employee.objects.get(user=request.user)
        except Employee.DoesNotExist:
            return Response(
                {'error': 'Employee profile not found for this user'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if already acknowledged
        if PolicyAcknowledgment.objects.filter(
            policy=policy,
            employee=employee
        ).exists():
            return Response(
                {
                    'message': 'Policy already acknowledged',
                    'already_acknowledged': True
                },
                status=status.HTTP_200_OK
            )
        
        # Create acknowledgment
        acknowledgment = PolicyAcknowledgment.objects.create(
            policy=policy,
            employee=employee,
            ip_address=self._get_client_ip(request),
            notes=request.data.get('notes', '')
        )
        
        logger.info(f"Policy acknowledged: {policy.title} by {employee.full_name}")
        
        serializer = PolicyAcknowledgmentSerializer(acknowledgment)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @swagger_auto_schema(
        operation_description="Get all acknowledgments for this policy",
        responses={
            200: PolicyAcknowledgmentSerializer(many=True)
        }
    )
    @action(detail=True, methods=['get'])
    def acknowledgments(self, request, pk=None):
        """Get all acknowledgments for this policy"""
        policy = self.get_object()
        
        acknowledgments = PolicyAcknowledgment.objects.filter(
            policy=policy
        ).select_related('employee').order_by('-acknowledged_at')
        
        # Pagination
        page = self.paginate_queryset(acknowledgments)
        if page is not None:
            serializer = PolicyAcknowledgmentSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = PolicyAcknowledgmentSerializer(acknowledgments, many=True)
        return Response(serializer.data)
    
    



    
    def _get_client_ip(self, request):
        """Get client IP address from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


# ==================== POLICY FOLDER VIEWS ====================

class PolicyFolderViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing policy folders
    """
    
    queryset = PolicyFolder.objects.select_related(
        'business_function', 'created_by'
    ).prefetch_related('policies')
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['business_function', 'is_active']
    search_fields = ['name', 'description']
    ordering_fields = ['name',  'created_at', 'updated_at']
    ordering = ['business_function',  'name']
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action in ['create', 'update', 'partial_update']:
            return PolicyFolderCreateUpdateSerializer
        return PolicyFolderSerializer
    
    def get_queryset(self):
        """Filter queryset based on query parameters"""
        queryset = super().get_queryset()
        
        # Filter by active status
        is_active = self.request.query_params.get('is_active', None)
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        return queryset
    
    def perform_create(self, serializer):
        """Set created_by user when creating folder"""
        serializer.save(created_by=self.request.user)
        logger.info(f"Policy folder created: {serializer.instance.name} by {self.request.user.username}")
    
    def perform_update(self, serializer):
        """Log folder updates"""
        serializer.save()
        logger.info(f"Policy folder updated: {serializer.instance.name} by {self.request.user.username}")
    
    def perform_destroy(self, instance):
        """Log folder deletion"""
        folder_name = instance.name
        instance.delete()
        logger.info(f"Policy folder deleted: {folder_name} by {self.request.user.username}")
    
    @swagger_auto_schema(
        operation_description="Get all folders for a specific business function",
        responses={
            200: PolicyFolderSerializer(many=True),
            404: 'Business Function Not Found'
        }
    )
    @action(detail=False, methods=['get'], url_path='by-business-function/(?P<bf_id>[^/.]+)')
    def by_business_function(self, request, bf_id=None):
        """Get all folders for a specific business function"""
        try:
            business_function = BusinessFunction.objects.get(id=bf_id)
        except BusinessFunction.DoesNotExist:
            return Response(
                {'error': 'Business function not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        folders = self.queryset.filter(
            business_function=business_function,
            is_active=True
        )
        
        serializer = self.get_serializer(folders, many=True)
        return Response(serializer.data)
    
    @swagger_auto_schema(
        operation_description="Get all policies in this folder",
        responses={
            200: CompanyPolicyListSerializer(many=True),
            404: 'Folder Not Found'
        }
    )
    @action(detail=True, methods=['get'])
    def policies(self, request, pk=None):
        """Get all policies in this folder"""
        folder = self.get_object()
        
        policies = CompanyPolicy.objects.filter(
            folder=folder,
            is_active=True
        ).select_related(
            'folder', 'folder__business_function',
            'created_by', 'updated_by'
        ).order_by('-updated_at')
        
        serializer = CompanyPolicyListSerializer(
            policies,
            many=True,
            context={'request': request}
        )
        return Response(serializer.data)
    
    @swagger_auto_schema(
        operation_description="Get folder statistics (policy counts, views, downloads)",
        responses={
            200: openapi.Response(
                description="Folder statistics",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'folder_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'folder_name': openapi.Schema(type=openapi.TYPE_STRING),
                        'business_function': openapi.Schema(type=openapi.TYPE_STRING),
                        'total_policies': openapi.Schema(type=openapi.TYPE_INTEGER),
                  
                        'policies_requiring_acknowledgment': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'total_views': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'total_downloads': openapi.Schema(type=openapi.TYPE_INTEGER),
                       
                    }
                )
            ),
            404: 'Folder Not Found'
        }
    )
    @action(detail=True, methods=['get'])
    def statistics(self, request, pk=None):
        """Get folder statistics"""
        folder = self.get_object()
        
        policies = folder.policies.filter(is_active=True)
        
        stats = {
            'folder_id': folder.id,
            'folder_name': folder.name,
            'business_function': folder.business_function.name,
            'total_policies': policies.count(),
     
            'policies_requiring_acknowledgment': policies.filter(requires_acknowledgment=True).count(),
            'total_views': sum(p.view_count for p in policies),
            'total_downloads': sum(p.download_count for p in policies),
           
        }
        
        return Response(stats)


# ==================== BUSINESS FUNCTION POLICY VIEWS ====================

class BusinessFunctionPolicyViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for getting business functions with their policy folders
    """
    
    queryset = BusinessFunction.objects.filter(
        is_active=True
    ).prefetch_related(
        Prefetch(
            'policy_folders',
            queryset=PolicyFolder.objects.filter(is_active=True).prefetch_related(
                Prefetch(
                    'policies',
                    queryset=CompanyPolicy.objects.filter(is_active=True)
                )
            )
        )
    ).order_by('code')
    serializer_class = BusinessFunctionWithFoldersSerializer
    permission_classes = [IsAuthenticated]
    
    @swagger_auto_schema(
        operation_description="Get business functions with comprehensive policy statistics",
        responses={
            200: openapi.Response(
                description="Business functions with statistics",
                schema=openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            'id': openapi.Schema(type=openapi.TYPE_INTEGER),
                            'name': openapi.Schema(type=openapi.TYPE_STRING),
                            'code': openapi.Schema(type=openapi.TYPE_STRING),
                            'folder_count': openapi.Schema(type=openapi.TYPE_INTEGER),
                            'total_policy_count': openapi.Schema(type=openapi.TYPE_INTEGER),
                        
                            'total_views': openapi.Schema(type=openapi.TYPE_INTEGER),
                            'total_downloads': openapi.Schema(type=openapi.TYPE_INTEGER),
                        }
                    )
                )
            )
        }
    )
    @action(detail=False, methods=['get'])
    def with_stats(self, request):
        """Get business functions with policy statistics"""
        business_functions = self.get_queryset()
        
        data = []
        for bf in business_functions:
            folders = bf.policy_folders.filter(is_active=True)
            
            # Calculate statistics
            total_policies = 0
   
            total_views = 0
            total_downloads = 0
            
            for folder in folders:
                policies = folder.policies.filter(is_active=True)
                total_policies += policies.count()
     
                total_views += sum(p.view_count for p in policies)
                total_downloads += sum(p.download_count for p in policies)
            
            data.append({
                'id': bf.id,
                'name': bf.name,
                'code': bf.code,
                'folder_count': folders.count(),
                'total_policy_count': total_policies,
       
                'total_views': total_views,
                'total_downloads': total_downloads
            })
        
        return Response(data)


# ==================== STATISTICS VIEWS ====================

class PolicyStatisticsViewSet(viewsets.ViewSet):
    """
    ViewSet for policy statistics and analytics
    """
    
    permission_classes = [IsAuthenticated]
    
    @swagger_auto_schema(
        operation_description="Get overall policy statistics across the system",
        responses={
            200: openapi.Response(
                description="Overall statistics",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'total_policies': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'total_folders': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'total_business_functions': openapi.Schema(type=openapi.TYPE_INTEGER),
                    
                        'policies_requiring_acknowledgment': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'total_views': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'total_downloads': openapi.Schema(type=openapi.TYPE_INTEGER),
                        
                    }
                )
            )
        }
    )
    @action(detail=False, methods=['get'])
    def overview(self, request):
        """Get overall policy statistics"""
        # Basic counts
        total_policies = CompanyPolicy.objects.filter(is_active=True).count()
        total_folders = PolicyFolder.objects.filter(is_active=True).count()
        total_business_functions = BusinessFunction.objects.filter(
            is_active=True,
            policy_folders__isnull=False
        ).distinct().count()
        
        # Policy statistics
        policies = CompanyPolicy.objects.filter(is_active=True)

        policies_requiring_ack = policies.filter(requires_acknowledgment=True).count()
        
        # Aggregated statistics
        total_views = sum(p.view_count for p in policies)
        total_downloads = sum(p.download_count for p in policies)
        
      
        
        return Response({
            'total_policies': total_policies,
            'total_folders': total_folders,
            'total_business_functions': total_business_functions,
       
            'policies_requiring_acknowledgment': policies_requiring_ack,
            'total_views': total_views,
            'total_downloads': total_downloads,
          
        })
    
    @swagger_auto_schema(
        operation_description="Get statistics grouped by business function",
        responses={
            200: openapi.Response(
                description="Statistics by business function",
                schema=openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            'business_function_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                            'business_function_name': openapi.Schema(type=openapi.TYPE_STRING),
                            'business_function_code': openapi.Schema(type=openapi.TYPE_STRING),
                            'folder_count': openapi.Schema(type=openapi.TYPE_INTEGER),
                            'policy_count': openapi.Schema(type=openapi.TYPE_INTEGER),
                         
                            'total_views': openapi.Schema(type=openapi.TYPE_INTEGER),
                            'total_downloads': openapi.Schema(type=openapi.TYPE_INTEGER),
                        }
                    )
                )
            )
        }
    )
    @action(detail=False, methods=['get'])
    def by_business_function(self, request):
        """Get statistics by business function"""
        business_functions = BusinessFunction.objects.filter(
            is_active=True
        ).prefetch_related('policy_folders__policies')
        
        data = []
        for bf in business_functions:
            folders = bf.policy_folders.filter(is_active=True)
            policies = CompanyPolicy.objects.filter(
                folder__in=folders,
                is_active=True
            )
            
            data.append({
                'business_function_id': bf.id,
                'business_function_name': bf.name,
                'business_function_code': bf.code,
                'folder_count': folders.count(),
                'policy_count': policies.count(),
     
                'total_views': sum(p.view_count for p in policies),
                'total_downloads': sum(p.download_count for p in policies)
            })
        
        return Response(data)
    
    @swagger_auto_schema(
        operation_description="Get most viewed policies",
        manual_parameters=[
            openapi.Parameter(
                'limit',
                openapi.IN_QUERY,
                description="Number of policies to return (default: 10)",
                type=openapi.TYPE_INTEGER,
                required=False
            )
        ],
        responses={
            200: CompanyPolicyListSerializer(many=True)
        }
    )
    @action(detail=False, methods=['get'])
    def most_viewed(self, request):
        """Get most viewed policies"""
        limit = int(request.query_params.get('limit', 10))
        
        policies = CompanyPolicy.objects.filter(
            is_active=True
        ).select_related(
            'folder', 'folder__business_function'
        ).order_by('-view_count')[:limit]
        
        serializer = CompanyPolicyListSerializer(
            policies,
            many=True,
            context={'request': request}
        )
        return Response(serializer.data)
    
    @swagger_auto_schema(
        operation_description="Get most downloaded policies",
        manual_parameters=[
            openapi.Parameter(
                'limit',
                openapi.IN_QUERY,
                description="Number of policies to return (default: 10)",
                type=openapi.TYPE_INTEGER,
                required=False
            )
        ],
        responses={
            200: CompanyPolicyListSerializer(many=True)
        }
    )
    @action(detail=False, methods=['get'])
    def most_downloaded(self, request):
        """Get most downloaded policies"""
        limit = int(request.query_params.get('limit', 10))
        
        policies = CompanyPolicy.objects.filter(
            is_active=True
        ).select_related(
            'folder', 'folder__business_function'
        ).order_by('-download_count')[:limit]
        
        serializer = CompanyPolicyListSerializer(
            policies,
            many=True,
            context={'request': request}
        )
        return Response(serializer.data)
    
    @swagger_auto_schema(
        operation_description="Get acknowledgment statistics for policies requiring acknowledgment",
        responses={
            200: openapi.Response(
                description="Acknowledgment statistics",
                schema=openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            'policy_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                            'policy_title': openapi.Schema(type=openapi.TYPE_STRING),
                            'business_function': openapi.Schema(type=openapi.TYPE_STRING),
                            'total_employees': openapi.Schema(type=openapi.TYPE_INTEGER),
                            'acknowledged_count': openapi.Schema(type=openapi.TYPE_INTEGER),
                            'acknowledgment_percentage': openapi.Schema(type=openapi.TYPE_NUMBER),
                        }
                    )
                )
            )
        }
    )
    @action(detail=False, methods=['get'])
    def acknowledgment_status(self, request):
        """Get acknowledgment statistics"""
        policies_requiring_ack = CompanyPolicy.objects.filter(
            is_active=True,
            requires_acknowledgment=True
        )
        
        total_employees = Employee.objects.filter(is_deleted=False).count()
        
        data = []
        for policy in policies_requiring_ack:
            ack_count = policy.get_acknowledgment_count()
            percentage = policy.get_acknowledgment_percentage()
            
            data.append({
                'policy_id': policy.id,
                'policy_title': policy.title,
                'business_function': policy.folder.business_function.code,
                'total_employees': total_employees,
                'acknowledged_count': ack_count,
                'acknowledgment_percentage': percentage
            })
        
        return Response(data)