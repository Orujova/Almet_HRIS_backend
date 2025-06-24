# api/views.py - ENHANCED: Complete Employee Management with Soft Delete & Advanced Features

from django.shortcuts import render
from django.utils import timezone
from rest_framework import status, viewsets
from django.db.models import Q, Count, Case, When, Value
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework import status, viewsets, filters
from rest_framework.pagination import PageNumberPagination
from django_filters.rest_framework import DjangoFilterBackend
from django_filters import rest_framework as django_filters
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
import logging
import traceback
from datetime import datetime, timedelta, date
from django.utils.dateparse import parse_date
from django.db import transaction
from django.http import HttpResponse
import csv
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils.dataframe import dataframe_to_rows
import io

from .models import (
    Employee, BusinessFunction, Department, Unit, JobFunction, 
    PositionGroup, EmployeeTag, EmployeeDocument, EmployeeStatus,
    EmployeeActivity, VacantPosition, HeadcountSummary
)
from .serializers import (
    EmployeeListSerializer, EmployeeDetailSerializer, EmployeeCreateUpdateSerializer,
    BusinessFunctionSerializer, DepartmentSerializer, UnitSerializer,
    JobFunctionSerializer, PositionGroupSerializer, EmployeeTagSerializer,
    EmployeeStatusSerializer, EmployeeDocumentSerializer, EmployeeActivitySerializer,
    UserSerializer, OrgChartNodeSerializer, EmployeeOrgChartVisibilitySerializer,
    VacantPositionListSerializer, VacantPositionDetailSerializer, VacantPositionCreateSerializer,
    BulkEmployeeUpdateSerializer, BulkLineManagerUpdateSerializer, SingleLineManagerUpdateSerializer,
    EmployeeTagOperationSerializer, BulkEmployeeTagOperationSerializer,
    EmployeeGradingUpdateSerializer, EmployeeGradingListSerializer,
    HeadcountSummarySerializer, SoftDeleteSerializer, RestoreEmployeeSerializer,
    EmployeeExportSerializer, EmployeeStatusUpdateSerializer, AutoStatusUpdateSerializer
)
from .auth import MicrosoftTokenValidator

# Set up logger
logger = logging.getLogger(__name__)

# Enhanced Pagination with multiple page size options
class StandardResultsSetPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = 'page_size'
    max_page_size = 100
    page_query_param = 'page'
    
    def get_paginated_response(self, data):
        return Response({
            'count': self.page.paginator.count,
            'total_pages': self.page.paginator.num_pages,
            'current_page': self.page.number,
            'page_size': self.page_size,
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'results': data
        })

# Microsoft Authentication Views (unchanged)
@swagger_auto_schema(
    method='post',
    operation_description="Authenticate with Microsoft ID token and get JWT tokens",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=['id_token'],
        properties={
            'id_token': openapi.Schema(type=openapi.TYPE_STRING, description='Microsoft ID Token'),
        }
    ),
    responses={
        200: openapi.Response(
            description="Authentication successful",
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'success': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                    'access': openapi.Schema(type=openapi.TYPE_STRING, description='JWT Access Token'),
                    'refresh': openapi.Schema(type=openapi.TYPE_STRING, description='JWT Refresh Token'),
                    'user': openapi.Schema(type=openapi.TYPE_OBJECT),
                }
            )
        ),
        401: openapi.Response(description="Authentication failed")
    }
)
@api_view(['POST'])
@permission_classes([AllowAny])
def authenticate_microsoft(request):
    """Authenticate with Microsoft token from frontend"""
    try:
        logger.info('=== Microsoft authentication request received ===')
        logger.info(f'Request method: {request.method}')
        logger.info(f'Request headers: {dict(request.headers)}')
        logger.info(f'Request data keys: {list(request.data.keys()) if request.data else "No data"}')
        
        id_token = request.data.get('id_token')
        
        if not id_token:
            logger.warning('Microsoft authentication attempt without ID token')
            return Response({
                "error": "ID token is required",
                "success": False
            }, status=status.HTTP_400_BAD_REQUEST)
        
        logger.info('Microsoft authentication attempt - validating token')
        logger.info(f'Token length: {len(id_token)}')
        
        # Validate token and get/create user
        user = MicrosoftTokenValidator.validate_token(id_token)
        
        logger.info(f'Token validated successfully for user: {user.username}')
        
        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        refresh_token = str(refresh)
        
        logger.info(f'JWT tokens generated for user: {user.username}')
        
        response_data = {
            'success': True,
            'access': access_token,
            'refresh': refresh_token,
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'name': f"{user.first_name} {user.last_name}".strip(),
            }
        }
        
        logger.info(f'Returning successful response for user: {user.username}')
        return Response(response_data, status=status.HTTP_200_OK)
    
    except Exception as e:
        logger.error(f'Microsoft authentication error: {str(e)}')
        logger.error(f'Exception type: {type(e).__name__}')
        logger.error(f'Traceback: {traceback.format_exc()}')
        return Response({
            "error": f"Authentication failed: {str(e)}",
            "success": False,
            "details": str(e)
        }, status=status.HTTP_401_UNAUTHORIZED)

@swagger_auto_schema(
    method='get',
    operation_description="Get current user information",
    responses={
        200: openapi.Response(
            description="User information retrieved successfully",
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'success': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                    'user': openapi.Schema(type=openapi.TYPE_OBJECT),
                    'employee': openapi.Schema(type=openapi.TYPE_OBJECT),
                }
            )
        ),
        401: openapi.Response(description="Unauthorized - Invalid or missing token")
    },
    security=[{'Bearer': []}]
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_info(request):
    """Get current user info"""
    try:
        logger.info(f'User info request for user: {request.user.username}')
        serializer = UserSerializer(request.user)
        
        # Check if user has an employee profile with proper select_related
        try:
            employee = Employee.objects.select_related(
                'user', 'business_function', 'department', 'unit', 
                'job_function', 'position_group', 'status', 'line_manager'
            ).prefetch_related('tags').get(user=request.user)
            
            employee_data = EmployeeDetailSerializer(employee).data
            logger.info(f'[{request.user.username}] Employee profile found: {employee.employee_id}')
            
        except Employee.DoesNotExist:
            logger.info(f'[{request.user.username}] No employee profile found')
            employee_data = None
        except Exception as e:
            logger.error(f'[{request.user.username}] Error during employee profile processing for user ID {request.user.id}: {str(e)}')
            logger.error(f'[{request.user.username}] Employee processing traceback: {traceback.format_exc()}')
            employee_data = None
        
        response_data = {
            'success': True,
            'user': serializer.data,
            'employee': employee_data
        }
        
        logger.info(f'[{request.user.username}] User info response prepared successfully')
        return Response(response_data, status=status.HTTP_200_OK)
    
    except Exception as e:
        logger.error(f'[{request.user.username}] Unhandled error in user_info: {str(e)}')
        logger.error(f'[{request.user.username}] Full traceback: {traceback.format_exc()}')
        return Response({
            "error": f"Failed to get user info: {str(e)}",
            "success": False
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# Enhanced Employee Filter Class for Advanced Filtering
class EmployeeFilter:
    def __init__(self, queryset, params):
        self.queryset = queryset
        self.params = params
    
    def filter(self):
        queryset = self.queryset
        
        # Text search across multiple fields
        search = self.params.get('search')
        if search:
            queryset = queryset.filter(
                Q(full_name__icontains=search) |
                Q(employee_id__icontains=search) |
                Q(user__email__icontains=search) |
                Q(job_title__icontains=search) |
                Q(business_function__name__icontains=search) |
                Q(department__name__icontains=search)
            )
        
        # Multiple status filtering
        status_names = self.params.getlist('status')
        if status_names:
            queryset = queryset.filter(status__name__in=status_names)
        
        # Multiple business function filtering
        business_functions = self.params.getlist('business_function')
        if business_functions:
            queryset = queryset.filter(business_function__id__in=business_functions)
        
        # Multiple department filtering
        departments = self.params.getlist('department')
        if departments:
            queryset = queryset.filter(department__id__in=departments)
        
        # Multiple position group filtering
        position_groups = self.params.getlist('position_group')
        if position_groups:
            queryset = queryset.filter(position_group__id__in=position_groups)
        
        # Multiple line manager filtering
        line_managers = self.params.getlist('line_manager')
        if line_managers:
            queryset = queryset.filter(line_manager__id__in=line_managers)
        
        # Multiple tag filtering
        tags = self.params.getlist('tags')
        if tags:
            queryset = queryset.filter(tags__id__in=tags)
        
        # Multiple contract duration filtering
        contract_durations = self.params.getlist('contract_duration')
        if contract_durations:
            queryset = queryset.filter(contract_duration__in=contract_durations)
        
        # Date range filtering
        start_date_from = self.params.get('start_date_from')
        start_date_to = self.params.get('start_date_to')
        if start_date_from:
            queryset = queryset.filter(start_date__gte=start_date_from)
        if start_date_to:
            queryset = queryset.filter(start_date__lte=start_date_to)
        
        # Active headcount only
        active_only = self.params.get('active_only')
        if active_only and active_only.lower() == 'true':
            queryset = queryset.filter(status__affects_headcount=True)
        
        # Org chart visibility
        org_chart_visible = self.params.get('org_chart_visible')
        if org_chart_visible and org_chart_visible.lower() == 'true':
            queryset = queryset.filter(is_visible_in_org_chart=True)
        
        # Include deleted filter
        include_deleted = self.params.get('include_deleted')
        if include_deleted and include_deleted.lower() == 'true':
            # Use all_objects manager to include soft-deleted employees
            queryset = Employee.all_objects.filter(
                pk__in=queryset.values_list('pk', flat=True)
            )
        
        return queryset

# Multi-field Sorting Class with Excel-like functionality
class EmployeeSorter:
    SORTABLE_FIELDS = {
        'employee_id': 'employee_id',
        'name': 'full_name',
        'email': 'user__email',
        'start_date': 'start_date',
        'end_date': 'end_date',
        'business_function': 'business_function__name',
        'department': 'department__name',
        'unit': 'unit__name',
        'job_title': 'job_title',
        'position_group': 'position_group__hierarchy_level',
        'grading_level': 'grading_level',
        'status': 'status__name',
        'line_manager': 'line_manager__full_name',
        'contract_duration': 'contract_duration',
        'contract_end_date': 'contract_end_date',
        'created_at': 'created_at',
        'updated_at': 'updated_at',
        'years_of_service': 'start_date',  # Will be calculated
    }
    
    def __init__(self, queryset, sort_params):
        self.queryset = queryset
        self.sort_params = sort_params or []
    
    def sort(self):
        if not self.sort_params:
            return self.queryset.order_by('employee_id')
        
        order_fields = []
        for sort_param in self.sort_params:
            if sort_param.startswith('-'):
                field_name = sort_param[1:]
                descending = True
            else:
                field_name = sort_param
                descending = False
            
            if field_name in self.SORTABLE_FIELDS:
                db_field = self.SORTABLE_FIELDS[field_name]
                if descending:
                    db_field = f'-{db_field}'
                order_fields.append(db_field)
        
        if order_fields:
            return self.queryset.order_by(*order_fields)
        return self.queryset.order_by('employee_id')

# Business Structure ViewSets (unchanged)
class BusinessFunctionViewSet(viewsets.ModelViewSet):
    queryset = BusinessFunction.objects.all()
    serializer_class = BusinessFunctionSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['is_active']
    search_fields = ['name', 'code']
    ordering = ['code']

class DepartmentViewSet(viewsets.ModelViewSet):
    queryset = Department.objects.select_related('business_function', 'head_of_department').all()
    serializer_class = DepartmentSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['business_function', 'is_active']
    search_fields = ['name']
    ordering = ['business_function__code']

class UnitViewSet(viewsets.ModelViewSet):
    queryset = Unit.objects.select_related('department__business_function', 'unit_head').all()
    serializer_class = UnitSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['department', 'is_active']
    search_fields = ['name']
    ordering = ['department__business_function__code']

class JobFunctionViewSet(viewsets.ModelViewSet):
    queryset = JobFunction.objects.all()
    serializer_class = JobFunctionSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['is_active']
    search_fields = ['name']
    ordering = ['name']

class PositionGroupViewSet(viewsets.ModelViewSet):
    queryset = PositionGroup.objects.all()
    serializer_class = PositionGroupSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['is_active']
    search_fields = ['name']
    ordering = ['hierarchy_level']
    
    @action(detail=True, methods=['get'])
    def grading_levels(self, request, pk=None):
        """Get available grading levels for this position group"""
        position_group = self.get_object()
        levels = position_group.get_grading_levels()
        return Response({
            'position_group': position_group.get_name_display(),
            'shorthand': position_group.grading_shorthand,
            'levels': levels
        })

class EmployeeTagViewSet(viewsets.ModelViewSet):
    queryset = EmployeeTag.objects.all()
    serializer_class = EmployeeTagSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['tag_type', 'is_active']
    search_fields = ['name']
    ordering = ['tag_type', 'name']

class EmployeeStatusViewSet(viewsets.ModelViewSet):
    queryset = EmployeeStatus.objects.all()
    serializer_class = EmployeeStatusSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['status_type', 'affects_headcount', 'allows_org_chart', 'is_active']
    search_fields = ['name']
    ordering = ['name']

# Vacant Position ViewSet
class VacantPositionViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = [
        'business_function', 'department', 'position_group', 'vacancy_type', 
        'urgency', 'is_filled'
    ]
    search_fields = ['title', 'position_id', 'description']
    ordering_fields = ['created_at', 'expected_start_date', 'urgency']
    ordering = ['-created_at']
    
    def get_queryset(self):
        return VacantPosition.objects.select_related(
            'business_function', 'department', 'unit', 'job_function',
            'position_group', 'reporting_to', 'filled_by', 'created_by'
        ).all()
    
    def get_serializer_class(self):
        if self.action == 'list':
            return VacantPositionListSerializer
        elif self.action == 'create':
            return VacantPositionCreateSerializer
        else:
            return VacantPositionDetailSerializer
    
    @action(detail=True, methods=['post'])
    def mark_filled(self, request, pk=None):
        """Mark a vacant position as filled"""
        vacancy = self.get_object()
        employee_id = request.data.get('employee_id')
        
        if not employee_id:
            return Response(
                {'error': 'employee_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            employee = Employee.objects.get(id=employee_id)
            vacancy.mark_as_filled(employee)
            
            # Log activity
            EmployeeActivity.objects.create(
                employee=employee,
                activity_type='POSITION_CHANGED',
                description=f"Employee assigned to fill vacant position {vacancy.position_id}",
                performed_by=request.user,
                metadata={'vacancy_id': str(vacancy.id), 'position_id': vacancy.position_id}
            )
            
            return Response({'message': 'Position marked as filled successfully'})
        except Employee.DoesNotExist:
            return Response(
                {'error': 'Employee not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get vacancy statistics"""
        total_vacancies = self.get_queryset().count()
        open_vacancies = self.get_queryset().filter(is_filled=False).count()
        filled_vacancies = total_vacancies - open_vacancies
        
        # By urgency
        urgency_stats = {}
        for urgency_choice in VacantPosition.URGENCY_LEVELS:
            urgency_code = urgency_choice[0]
            count = self.get_queryset().filter(urgency=urgency_code, is_filled=False).count()
            urgency_stats[urgency_choice[1]] = count
        
        # By business function
        function_stats = {}
        for func in BusinessFunction.objects.filter(is_active=True):
            count = self.get_queryset().filter(business_function=func, is_filled=False).count()
            if count > 0:
                function_stats[func.name] = count
        
        return Response({
            'total_vacancies': total_vacancies,
            'open_vacancies': open_vacancies,
            'filled_vacancies': filled_vacancies,
            'by_urgency': urgency_stats,
            'by_business_function': function_stats
        })

# Main Employee ViewSet with Enhanced Features
class EmployeeViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    
    def get_queryset(self):
        return Employee.objects.select_related(
            'user', 'business_function', 'department', 'unit', 'job_function',
            'position_group', 'status', 'line_manager'
        ).prefetch_related(
            'tags', 'documents', 'activities'
        ).all()
    
    def get_serializer_class(self):
        if self.action == 'list':
            return EmployeeListSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return EmployeeCreateUpdateSerializer
        else:
            return EmployeeDetailSerializer
    
    def list(self, request, *args, **kwargs):
        """Enhanced list with filtering and sorting"""
        queryset = self.get_queryset()
        
        # Apply custom filtering
        employee_filter = EmployeeFilter(queryset, request.query_params)
        queryset = employee_filter.filter()
        
        # Apply sorting
        sort_params = request.query_params.get('ordering', '').split(',')
        sort_params = [param.strip() for param in sort_params if param.strip()]
        employee_sorter = EmployeeSorter(queryset, sort_params)
        queryset = employee_sorter.sort()
        
        # Paginate
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    def destroy(self, request, *args, **kwargs):
        """Override destroy to use soft delete"""
        instance = self.get_object()
        instance.soft_delete(user=request.user)
        
        # Log activity
        EmployeeActivity.objects.create(
            employee=instance,
            activity_type='SOFT_DELETED',
            description=f"Employee {instance.full_name} was soft deleted",
            performed_by=request.user
        )
        
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    # Line Manager Management Actions
    @action(detail=False, methods=['post'])
    def bulk_update_line_manager(self, request):
        """Bulk update line manager for multiple employees"""
        serializer = BulkLineManagerUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        employee_ids = serializer.validated_data['employee_ids']
        line_manager_id = serializer.validated_data['line_manager_id']
        
        try:
            line_manager = Employee.objects.get(id=line_manager_id) if line_manager_id else None
            
            with transaction.atomic():
                employees = Employee.objects.filter(id__in=employee_ids)
                updated_count = 0
                
                for employee in employees:
                    employee.change_line_manager(line_manager, request.user)
                    updated_count += 1
                
                return Response({
                    'message': f'Successfully updated line manager for {updated_count} employees',
                    'updated_count': updated_count,
                    'new_line_manager': line_manager.full_name if line_manager else 'None'
                })
        except Employee.DoesNotExist:
            return Response(
                {'error': 'Line manager not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Bulk line manager update failed: {str(e)}")
            return Response(
                {'error': 'Bulk line manager update failed', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def update_single_line_manager(self, request):
        """Update line manager for a single employee"""
        serializer = SingleLineManagerUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        employee_id = serializer.validated_data['employee_id']
        line_manager_id = serializer.validated_data['line_manager_id']
        
        try:
            employee = Employee.objects.get(id=employee_id)
            line_manager = Employee.objects.get(id=line_manager_id) if line_manager_id else None
            
            employee.change_line_manager(line_manager, request.user)
            
            return Response({
                'message': 'Line manager updated successfully',
                'employee': employee.full_name,
                'new_line_manager': line_manager.full_name if line_manager else 'None'
            })
        except Employee.DoesNotExist:
            return Response(
                {'error': 'Employee or line manager not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    # Tag Management Actions
    @action(detail=False, methods=['post'])
    def add_tag(self, request):
        """Add tag to employee"""
        serializer = EmployeeTagOperationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        employee_id = serializer.validated_data['employee_id']
        tag_id = serializer.validated_data['tag_id']
        
        try:
            employee = Employee.objects.get(id=employee_id)
            tag = EmployeeTag.objects.get(id=tag_id)
            
            if employee.add_tag(tag, request.user):
                return Response({
                    'message': f'Tag "{tag.name}" added to {employee.full_name}',
                    'employee': employee.full_name,
                    'tag': tag.name
                })
            else:
                return Response({
                    'message': f'Tag "{tag.name}" already exists on {employee.full_name}',
                    'employee': employee.full_name,
                    'tag': tag.name
                })
        except Employee.DoesNotExist:
            return Response({'error': 'Employee not found'}, status=status.HTTP_404_NOT_FOUND)
        except EmployeeTag.DoesNotExist:
            return Response({'error': 'Tag not found'}, status=status.HTTP_404_NOT_FOUND)
    
    @action(detail=False, methods=['post'])
    def remove_tag(self, request):
        """Remove tag from employee"""
        serializer = EmployeeTagOperationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        employee_id = serializer.validated_data['employee_id']
        tag_id = serializer.validated_data['tag_id']
        
        try:
            employee = Employee.objects.get(id=employee_id)
            tag = EmployeeTag.objects.get(id=tag_id)
            
            if employee.remove_tag(tag, request.user):
                return Response({
                    'message': f'Tag "{tag.name}" removed from {employee.full_name}',
                    'employee': employee.full_name,
                    'tag': tag.name
                })
            else:
                return Response({
                    'message': f'Tag "{tag.name}" was not found on {employee.full_name}',
                    'employee': employee.full_name,
                    'tag': tag.name
                })
        except Employee.DoesNotExist:
            return Response({'error': 'Employee not found'}, status=status.HTTP_404_NOT_FOUND)
        except EmployeeTag.DoesNotExist:
            return Response({'error': 'Tag not found'}, status=status.HTTP_404_NOT_FOUND)
    
    @action(detail=False, methods=['post'])
    def bulk_add_tag(self, request):
        """Add tag to multiple employees"""
        serializer = BulkEmployeeTagOperationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        employee_ids = serializer.validated_data['employee_ids']
        tag_id = serializer.validated_data['tag_id']
        
        try:
            tag = EmployeeTag.objects.get(id=tag_id)
            employees = Employee.objects.filter(id__in=employee_ids)
            
            added_count = 0
            for employee in employees:
                if employee.add_tag(tag, request.user):
                    added_count += 1
            
            return Response({
                'message': f'Tag "{tag.name}" added to {added_count} employees',
                'added_count': added_count,
                'total_employees': len(employee_ids),
                'tag': tag.name
            })
        except EmployeeTag.DoesNotExist:
            return Response({'error': 'Tag not found'}, status=status.HTTP_404_NOT_FOUND)
    
    @action(detail=False, methods=['post'])
    def bulk_remove_tag(self, request):
        """Remove tag from multiple employees"""
        serializer = BulkEmployeeTagOperationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        employee_ids = serializer.validated_data['employee_ids']
        tag_id = serializer.validated_data['tag_id']
        
        try:
            tag = EmployeeTag.objects.get(id=tag_id)
            employees = Employee.objects.filter(id__in=employee_ids)
            
            removed_count = 0
            for employee in employees:
                if employee.remove_tag(tag, request.user):
                    removed_count += 1
            
            return Response({
                'message': f'Tag "{tag.name}" removed from {removed_count} employees',
                'removed_count': removed_count,
                'total_employees': len(employee_ids),
                'tag': tag.name
            })
        except EmployeeTag.DoesNotExist:
            return Response({'error': 'Tag not found'}, status=status.HTTP_404_NOT_FOUND)
    
    # Soft Delete Management
    @action(detail=False, methods=['post'])
    def soft_delete(self, request):
        """Soft delete multiple employees"""
        serializer = SoftDeleteSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        employee_ids = serializer.validated_data['employee_ids']
        
        try:
            with transaction.atomic():
                employees = Employee.objects.filter(id__in=employee_ids)
                deleted_count = 0
                
                for employee in employees:
                    employee.soft_delete(user=request.user)
                    deleted_count += 1
                    
                    # Log activity
                    EmployeeActivity.objects.create(
                        employee=employee,
                        activity_type='SOFT_DELETED',
                        description=f"Employee {employee.full_name} was soft deleted",
                        performed_by=request.user,
                        metadata={'bulk_delete': True}
                    )
                
                return Response({
                    'message': f'Successfully soft deleted {deleted_count} employees',
                    'deleted_count': deleted_count
                })
        except Exception as e:
            logger.error(f"Soft delete failed: {str(e)}")
            return Response(
                {'error': 'Soft delete failed', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def restore(self, request):
        """Restore soft-deleted employees"""
        serializer = RestoreEmployeeSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        employee_ids = serializer.validated_data['employee_ids']
        
        try:
            with transaction.atomic():
                employees = Employee.all_objects.filter(id__in=employee_ids, is_deleted=True)
                restored_count = 0
                
                for employee in employees:
                    employee.restore()
                    restored_count += 1
                    
                    # Log activity
                    EmployeeActivity.objects.create(
                        employee=employee,
                        activity_type='RESTORED',
                        description=f"Employee {employee.full_name} was restored",
                        performed_by=request.user,
                        metadata={'bulk_restore': True}
                    )
                
                return Response({
                    'message': f'Successfully restored {restored_count} employees',
                    'restored_count': restored_count
                })
        except Exception as e:
            logger.error(f"Restore failed: {str(e)}")
            return Response(
                {'error': 'Restore failed', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    # Enhanced Export Functionality
    @action(detail=False, methods=['post'])
    def export_selected(self, request):
        """Export selected employees to Excel or CSV"""
        serializer = EmployeeExportSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        employee_ids = serializer.validated_data.get('employee_ids', [])
        export_format = serializer.validated_data.get('export_format', 'excel')
        include_fields = serializer.validated_data.get('include_fields', None)
        
        # Get queryset
        if employee_ids:
            queryset = Employee.objects.filter(id__in=employee_ids)
        else:
            # If no specific IDs, use filtered results
            queryset = self.get_queryset()
            employee_filter = EmployeeFilter(queryset, request.query_params)
            queryset = employee_filter.filter()
        
        # Apply sorting
        sort_params = request.query_params.get('ordering', '').split(',')
        sort_params = [param.strip() for param in sort_params if param.strip()]
        employee_sorter = EmployeeSorter(queryset, sort_params)
        queryset = employee_sorter.sort()
        
        # Define default fields for export
        default_fields = [
            'employee_id', 'name', 'email', 'job_title', 'business_function_name',
            'department_name', 'unit_name', 'position_group_name', 'grading_display',
            'status_name', 'line_manager_name', 'start_date', 'contract_duration_display',
            'phone', 'years_of_service'
        ]
        
        # Use custom fields if provided
        fields_to_include = include_fields if include_fields else default_fields
        
        if export_format == 'excel':
            return self._export_to_excel(queryset, fields_to_include)
        else:
            return self._export_to_csv(queryset, fields_to_include)
    
    def _export_to_excel(self, queryset, fields):
        """Export employees to Excel format with styling"""
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        
        wb = Workbook()
        ws = wb.active
        ws.title = "Employees Export"
        
        # Field mappings for headers
        field_headers = {
            'employee_id': 'Employee ID',
            'name': 'Full Name',
            'email': 'Email',
            'job_title': 'Job Title',
            'business_function_name': 'Business Function',
            'department_name': 'Department',
            'unit_name': 'Unit',
            'position_group_name': 'Position Group',
            'grading_display': 'Grade',
            'status_name': 'Status',
            'line_manager_name': 'Line Manager',
            'start_date': 'Start Date',
            'contract_duration_display': 'Contract Duration',
            'phone': 'Phone',
            'years_of_service': 'Years of Service'
        }
        
        # Write headers
        headers = [field_headers.get(field, field.replace('_', ' ').title()) for field in fields]
        ws.append(headers)
        
        # Style headers
        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
        header_alignment = Alignment(horizontal="center", vertical="center")
        
        for cell in ws[1]:
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_alignment
        
        # Write data
        serializer = EmployeeListSerializer(queryset, many=True)
        for employee_data in serializer.data:
            row_data = []
            for field in fields:
                value = employee_data.get(field, '')
                if value is None:
                    value = ''
                row_data.append(str(value))
            ws.append(row_data)
        
        # Auto-adjust column widths
        for column in ws.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 50)
            ws.column_dimensions[column_letter].width = adjusted_width
        
        # Save to BytesIO
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        
        response = HttpResponse(
            output.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="employees_export_{date.today()}.xlsx"'
        
        return response
    
    def _export_to_csv(self, queryset, fields):
        """Export employees to CSV format"""
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="employees_export_{date.today()}.csv"'
        
        writer = csv.writer(response)
        
        # Field mappings for headers
        field_headers = {
            'employee_id': 'Employee ID',
            'name': 'Full Name',
            'email': 'Email',
            'job_title': 'Job Title',
            'business_function_name': 'Business Function',
            'department_name': 'Department',
            'unit_name': 'Unit',
            'position_group_name': 'Position Group',
            'grading_display': 'Grade',
            'status_name': 'Status',
            'line_manager_name': 'Line Manager',
            'start_date': 'Start Date',
            'contract_duration_display': 'Contract Duration',
            'phone': 'Phone',
            'years_of_service': 'Years of Service'
        }
        
        # Write headers
        headers = [field_headers.get(field, field.replace('_', ' ').title()) for field in fields]
        writer.writerow(headers)
        
        # Write data
        serializer = EmployeeListSerializer(queryset, many=True)
        for employee_data in serializer.data:
            row_data = []
            for field in fields:
                value = employee_data.get(field, '')
                if value is None:
                    value = ''
                row_data.append(str(value))
            writer.writerow(row_data)
        
        return response
    
    # Status Management
    @action(detail=False, methods=['post'])
    def update_status(self, request):
        """Update status for multiple employees"""
        serializer = EmployeeStatusUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        employee_ids = serializer.validated_data['employee_ids']
        status_id = serializer.validated_data['status_id']
        
        try:
            new_status = EmployeeStatus.objects.get(id=status_id)
            employees = Employee.objects.filter(id__in=employee_ids)
            
            updated_count = 0
            for employee in employees:
                old_status = employee.status
                employee.status = new_status
                employee.save()
                updated_count += 1
                
                # Log activity
                EmployeeActivity.objects.create(
                    employee=employee,
                    activity_type='STATUS_CHANGED',
                    description=f"Status manually changed from {old_status.name} to {new_status.name}",
                    performed_by=request.user,
                    metadata={
                        'old_status': old_status.name,
                        'new_status': new_status.name,
                        'manual_update': True
                    }
                )
            
            return Response({
                'message': f'Successfully updated status for {updated_count} employees',
                'updated_count': updated_count,
                'new_status': new_status.name
            })
        except EmployeeStatus.DoesNotExist:
            return Response({'error': 'Status not found'}, status=status.HTTP_404_NOT_FOUND)
    
    @action(detail=False, methods=['post'])
    def auto_update_status(self, request):
        """Automatically update employee statuses based on contract and dates"""
        serializer = AutoStatusUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        employee_ids = serializer.validated_data.get('employee_ids', [])
        force_update = serializer.validated_data.get('force_update', False)
        
        try:
            if employee_ids:
                employees = Employee.objects.filter(id__in=employee_ids)
            else:
                employees = Employee.objects.all()
            
            updated_count = 0
            for employee in employees:
                if employee.update_status_automatically() or force_update:
                    updated_count += 1
            
            return Response({
                'message': f'Successfully auto-updated status for {updated_count} employees',
                'updated_count': updated_count,
                'total_processed': employees.count()
            })
        except Exception as e:
            logger.error(f"Auto status update failed: {str(e)}")
            return Response(
                {'error': 'Auto status update failed', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    # Other existing actions...
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get comprehensive employee statistics"""
        queryset = self.get_queryset()
        
        # Apply filtering
        employee_filter = EmployeeFilter(queryset, request.query_params)
        queryset = employee_filter.filter()
        
        total_employees = queryset.count()
        active_employees = queryset.filter(status__affects_headcount=True).count()
        
        # By status
        status_stats = {}
        for emp_status in EmployeeStatus.objects.filter(is_active=True):
            count = queryset.filter(status=emp_status).count()
            if count > 0:
                status_stats[emp_status.name] = {
                    'count': count,
                    'color': emp_status.color,
                    'affects_headcount': emp_status.affects_headcount
                }
        
        # By business function
        function_stats = {}
        for func in BusinessFunction.objects.filter(is_active=True):
            count = queryset.filter(business_function=func).count()
            if count > 0:
                function_stats[func.name] = count
        
        # By position group
        position_stats = {}
        for pos in PositionGroup.objects.filter(is_active=True):
            count = queryset.filter(position_group=pos).count()
            if count > 0:
                position_stats[pos.get_name_display()] = count
        
        # Contract analysis
        contract_stats = {}
        for duration in Employee.CONTRACT_DURATION_CHOICES:
            count = queryset.filter(contract_duration=duration[0]).count()
            if count > 0:
                contract_stats[duration[1]] = count
        
        # Recent activity
        recent_hires = queryset.filter(
            start_date__gte=date.today() - timedelta(days=30)
        ).count()
        
        upcoming_contract_endings = queryset.filter(
            contract_end_date__lte=date.today() + timedelta(days=30),
            contract_end_date__gte=date.today()
        ).count()
        
        return Response({
            'total_employees': total_employees,
            'active_employees': active_employees,
            'inactive_employees': total_employees - active_employees,
            'by_status': status_stats,
            'by_business_function': function_stats,
            'by_position_group': position_stats,
            'by_contract_duration': contract_stats,
            'recent_hires_30_days': recent_hires,
            'upcoming_contract_endings_30_days': upcoming_contract_endings
        })
    
    @action(detail=False, methods=['get'])
    def line_managers(self, request):
        """Get list of potential line managers"""
        managers = Employee.objects.filter(
            status__affects_headcount=True,
            position_group__hierarchy_level__lte=4  # Manager level and above
        ).select_related('position_group').order_by('full_name')
        
        manager_data = [
            {
                'id': emp.id,
                'employee_id': emp.employee_id,
                'name': emp.full_name,
                'job_title': emp.job_title,
                'position_group': emp.position_group.get_name_display(),
                'department': emp.department.name,
                'direct_reports_count': emp.get_direct_reports_count()
            }
            for emp in managers
        ]
        
        return Response(manager_data)
    
    @action(detail=True, methods=['get'])
    def activities(self, request, pk=None):
        """Get employee activity history"""
        employee = self.get_object()
        activities = employee.activities.all()[:50]  # Last 50 activities
        serializer = EmployeeActivitySerializer(activities, many=True)
        return Response(serializer.data)

# Employee Grading Integration ViewSet
class EmployeeGradingViewSet(viewsets.ViewSet):
    """ViewSet for employee grading integration"""
    permission_classes = [IsAuthenticated]
    
    def list(self, request):
        """Get employees with grading information"""
        employees = Employee.objects.select_related(
            'position_group'
        ).filter(status__affects_headcount=True)
        
        serializer = EmployeeGradingListSerializer(employees, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def bulk_update_grades(self, request):
        """Bulk update employee grades"""
        updates = request.data.get('updates', [])
        
        if not updates:
            return Response(
                {'error': 'updates list is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            with transaction.atomic():
                updated_count = 0
                
                for update in updates:
                    serializer = EmployeeGradingUpdateSerializer(data=update)
                    if serializer.is_valid():
                        employee_id = serializer.validated_data['employee_id']
                        grading_level = serializer.validated_data['grading_level']
                        
                        try:
                            employee = Employee.objects.get(id=employee_id)
                            
                            if employee.grading_level != grading_level:
                                old_grading = employee.grading_level
                                employee.grading_level = grading_level
                                employee.save()
                                updated_count += 1
                                
                                # Log activity
                                EmployeeActivity.objects.create(
                                    employee=employee,
                                    activity_type='GRADE_CHANGED',
                                    description=f"Grading level updated from {old_grading} to {grading_level}",
                                    performed_by=request.user,
                                    metadata={
                                        'old_grading_level': old_grading,
                                        'new_grading_level': grading_level
                                    }
                                )
                                
                        except Employee.DoesNotExist:
                            continue
                
                return Response({
                    'message': f'Successfully updated grades for {updated_count} employees',
                    'updated_count': updated_count
                })
        except Exception as e:
            logger.error(f"Bulk grade update failed: {str(e)}")
            return Response(
                {'error': 'Bulk grade update failed', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

# Organizational Chart ViewSet
class OrgChartViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for organizational chart data"""
    permission_classes = [IsAuthenticated]
    serializer_class = OrgChartNodeSerializer
    
    def get_queryset(self):
        return Employee.objects.filter(
            line_manager__isnull=True,  # Top-level employees
            status__allows_org_chart=True,
            is_visible_in_org_chart=True,
            is_deleted=False
        ).select_related(
            'business_function', 'department', 'position_group', 'status'
        ).order_by('position_group__hierarchy_level', 'employee_id')
    
    @action(detail=False, methods=['get'])
    def full_tree(self, request):
        """Get complete organizational chart tree"""
        top_level = self.get_queryset()
        serializer = self.get_serializer(top_level, many=True)
        return Response({
            'org_chart': serializer.data,
            'total_employees': Employee.objects.filter(
                status__allows_org_chart=True,
                is_visible_in_org_chart=True,
                is_deleted=False
            ).count()
        })

# Headcount Summary ViewSet
class HeadcountSummaryViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for headcount summaries and analytics"""
    queryset = HeadcountSummary.objects.all()
    serializer_class = HeadcountSummarySerializer
    permission_classes = [IsAuthenticated]
    ordering = ['-summary_date']
    
    @action(detail=False, methods=['post'])
    def generate_current(self, request):
        """Generate headcount summary for today"""
        summary = HeadcountSummary.generate_summary()
        serializer = self.get_serializer(summary)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def latest(self, request):
        """Get latest headcount summary"""
        try:
            latest = HeadcountSummary.objects.latest('summary_date')
            serializer = self.get_serializer(latest)
            return Response(serializer.data)
        except HeadcountSummary.DoesNotExist:
            # Generate if none exists
            summary = HeadcountSummary.generate_summary()
            serializer = self.get_serializer(summary)
            return Response(serializer.data)