# api/views.py

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
from datetime import datetime, timedelta
from django.utils.dateparse import parse_date

from .models import (
    Employee, BusinessFunction, Department, Unit, JobFunction, 
    PositionGroup, EmployeeTag, EmployeeDocument, EmployeeStatus,
    EmployeeActivity, MicrosoftUser
)
from .serializers import (
    EmployeeListSerializer, EmployeeDetailSerializer, EmployeeCreateUpdateSerializer,
    BusinessFunctionSerializer, DepartmentSerializer, UnitSerializer,
    JobFunctionSerializer, PositionGroupSerializer, EmployeeTagSerializer,
    EmployeeStatusSerializer, EmployeeDocumentSerializer, EmployeeActivitySerializer,
    UserSerializer, OrgChartNodeSerializer, EmployeeOrgChartVisibilitySerializer
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

# Custom Filter for Employee with advanced filtering
class EmployeeFilter(django_filters.FilterSet):
    # Basic search filters
    search = django_filters.CharFilter(method='filter_search', label='Global Search')
    employee_id = django_filters.CharFilter(lookup_expr='icontains')
    name = django_filters.CharFilter(method='filter_by_name')
    email = django_filters.CharFilter(field_name='user__email', lookup_expr='icontains')
    phone = django_filters.CharFilter(lookup_expr='icontains')
    
    # Organizational filters with multiple selection
    business_function = django_filters.ModelMultipleChoiceFilter(
        queryset=BusinessFunction.objects.filter(is_active=True),
        field_name='business_function'
    )
    department = django_filters.ModelMultipleChoiceFilter(
        queryset=Department.objects.filter(is_active=True),
        field_name='department'
    )
    unit = django_filters.ModelMultipleChoiceFilter(
        queryset=Unit.objects.filter(is_active=True),
        field_name='unit'
    )
    job_function = django_filters.ModelMultipleChoiceFilter(
        queryset=JobFunction.objects.filter(is_active=True),
        field_name='job_function'
    )
    position_group = django_filters.ModelMultipleChoiceFilter(
        queryset=PositionGroup.objects.filter(is_active=True),
        field_name='position_group'
    )
    
    # Status and tags
    status = django_filters.ModelMultipleChoiceFilter(
        queryset=EmployeeStatus.objects.filter(is_active=True),
        field_name='status'
    )
    tags = django_filters.ModelMultipleChoiceFilter(
        queryset=EmployeeTag.objects.filter(is_active=True),
        field_name='tags'
    )
    
    # Line manager filters
    line_manager = django_filters.ModelChoiceFilter(
        queryset=Employee.objects.all(),
        field_name='line_manager'
    )
    line_manager_name = django_filters.CharFilter(method='filter_by_line_manager_name')
    line_manager_hc = django_filters.CharFilter(field_name='line_manager__employee_id', lookup_expr='icontains')
    
    # Job details
    job_title = django_filters.CharFilter(lookup_expr='icontains')
    grade = django_filters.MultipleChoiceFilter(choices=[(i, i) for i in range(1, 9)])
    grade_min = django_filters.NumberFilter(field_name='grade', lookup_expr='gte')
    grade_max = django_filters.NumberFilter(field_name='grade', lookup_expr='lte')
    
    # Personal information
    gender = django_filters.MultipleChoiceFilter(choices=[('MALE', 'Male'), ('FEMALE', 'Female')])
    
    # Date filters
    start_date = django_filters.DateFilter()
    start_date_from = django_filters.DateFilter(field_name='start_date', lookup_expr='gte')
    start_date_to = django_filters.DateFilter(field_name='start_date', lookup_expr='lte')
    end_date = django_filters.DateFilter()
    end_date_from = django_filters.DateFilter(field_name='end_date', lookup_expr='gte')
    end_date_to = django_filters.DateFilter(field_name='end_date', lookup_expr='lte')
    
    # Date of birth filters
    birth_date_from = django_filters.DateFilter(field_name='date_of_birth', lookup_expr='gte')
    birth_date_to = django_filters.DateFilter(field_name='date_of_birth', lookup_expr='lte')
    
    # Employment duration
    years_of_service_min = django_filters.NumberFilter(method='filter_years_of_service_min')
    years_of_service_max = django_filters.NumberFilter(method='filter_years_of_service_max')
    
    # Visibility
    is_visible_in_org_chart = django_filters.BooleanFilter()
    
    class Meta:
        model = Employee
        fields = []

    def filter_search(self, queryset, name, value):
        """Global search across multiple fields"""
        if value:
            return queryset.filter(
                Q(employee_id__icontains=value) |
                Q(user__first_name__icontains=value) |
                Q(user__last_name__icontains=value) |
                Q(user__email__icontains=value) |
                Q(job_title__icontains=value) |
                Q(full_name__icontains=value) |
                Q(business_function__name__icontains=value) |
                Q(department__name__icontains=value) |
                Q(unit__name__icontains=value)
            )
        return queryset

    def filter_by_name(self, queryset, name, value):
        """Filter by full name or first/last name"""
        if value:
            return queryset.filter(
                Q(user__first_name__icontains=value) |
                Q(user__last_name__icontains=value) |
                Q(full_name__icontains=value)
            )
        return queryset

    def filter_by_line_manager_name(self, queryset, name, value):
        """Filter by line manager name"""
        if value:
            return queryset.filter(
                Q(line_manager__user__first_name__icontains=value) |
                Q(line_manager__user__last_name__icontains=value) |
                Q(line_manager__full_name__icontains=value)
            )
        return queryset

    def filter_years_of_service_min(self, queryset, name, value):
        """Filter by minimum years of service"""
        if value:
            cutoff_date = timezone.now().date() - timedelta(days=value * 365)
            return queryset.filter(start_date__lte=cutoff_date)
        return queryset

    def filter_years_of_service_max(self, queryset, name, value):
        """Filter by maximum years of service"""
        if value:
            cutoff_date = timezone.now().date() - timedelta(days=value * 365)
            return queryset.filter(start_date__gte=cutoff_date)
        return queryset

# Existing authentication views remain the same
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
    """
    Authenticate with Microsoft token from frontend
    """
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
    """
    Get current user info
    """
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

# Reference Data ViewSets with Full CRUD
class BusinessFunctionViewSet(viewsets.ModelViewSet):
    """
    API endpoint for business functions with full CRUD operations
    """
    queryset = BusinessFunction.objects.all()
    serializer_class = BusinessFunctionSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'code']
    filterset_fields = ['is_active']
    ordering_fields = ['name', 'code', 'created_at']
    ordering = ['name']

    @action(detail=False, methods=['get'])
    def dropdown_options(self, request):
        """Get simplified data for dropdown options"""
        queryset = self.queryset.filter(is_active=True)
        data = [{'id': obj.id, 'name': obj.name, 'code': obj.code} for obj in queryset]
        return Response(data)

class DepartmentViewSet(viewsets.ModelViewSet):
    """
    API endpoint for departments with full CRUD operations
    """
    queryset = Department.objects.select_related('business_function')
    serializer_class = DepartmentSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'business_function__name']
    filterset_fields = ['business_function', 'is_active']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']

    @action(detail=False, methods=['get'])
    def dropdown_options(self, request):
        """Get simplified data for dropdown options with business function grouping"""
        business_function = request.query_params.get('business_function')
        queryset = self.queryset.filter(is_active=True)
        if business_function:
            queryset = queryset.filter(business_function_id=business_function)
        
        data = [{
            'id': obj.id, 
            'name': obj.name, 
            'business_function_id': obj.business_function.id,
            'business_function_name': obj.business_function.name
        } for obj in queryset]
        return Response(data)

class UnitViewSet(viewsets.ModelViewSet):
    """
    API endpoint for units with full CRUD operations
    """
    queryset = Unit.objects.select_related('department', 'department__business_function')
    serializer_class = UnitSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'department__name']
    filterset_fields = ['department', 'is_active']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']

    @action(detail=False, methods=['get'])
    def dropdown_options(self, request):
        """Get simplified data for dropdown options with department filtering"""
        department = request.query_params.get('department')
        queryset = self.queryset.filter(is_active=True)
        if department:
            queryset = queryset.filter(department_id=department)
        
        data = [{
            'id': obj.id, 
            'name': obj.name, 
            'department_id': obj.department.id,
            'department_name': obj.department.name,
            'business_function_name': obj.department.business_function.name
        } for obj in queryset]
        return Response(data)

class JobFunctionViewSet(viewsets.ModelViewSet):
    """
    API endpoint for job functions with full CRUD operations
    """
    queryset = JobFunction.objects.all()
    serializer_class = JobFunctionSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name']
    filterset_fields = ['is_active']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']

    @action(detail=False, methods=['get'])
    def dropdown_options(self, request):
        """Get simplified data for dropdown options"""
        queryset = self.queryset.filter(is_active=True)
        data = [{'id': obj.id, 'name': obj.name} for obj in queryset]
        return Response(data)

class PositionGroupViewSet(viewsets.ModelViewSet):
    """
    API endpoint for position groups with full CRUD operations
    """
    queryset = PositionGroup.objects.all()
    serializer_class = PositionGroupSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name']
    filterset_fields = ['is_active']
    ordering_fields = ['hierarchy_level', 'name', 'created_at']
    ordering = ['hierarchy_level']
    
    @action(detail=False, methods=['get'])
    def by_hierarchy(self, request):
        """Get position groups ordered by hierarchy level"""
        queryset = self.get_queryset().filter(is_active=True).order_by('hierarchy_level')
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def dropdown_options(self, request):
        """Get simplified data for dropdown options ordered by hierarchy"""
        queryset = self.queryset.filter(is_active=True).order_by('hierarchy_level')
        data = [{
            'id': obj.id, 
            'name': obj.get_name_display(), 
            'hierarchy_level': obj.hierarchy_level
        } for obj in queryset]
        return Response(data)

class EmployeeTagViewSet(viewsets.ModelViewSet):
    """
    API endpoint for employee tags with full CRUD operations
    """
    queryset = EmployeeTag.objects.all()
    serializer_class = EmployeeTagSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name']
    filterset_fields = ['tag_type', 'is_active']
    ordering_fields = ['name', 'tag_type', 'created_at']
    ordering = ['name']

    @action(detail=False, methods=['get'])
    def dropdown_options(self, request):
        """Get simplified data for dropdown options grouped by type"""
        tag_type = request.query_params.get('tag_type')
        queryset = self.queryset.filter(is_active=True)
        if tag_type:
            queryset = queryset.filter(tag_type=tag_type)
        
        data = [{
            'id': obj.id, 
            'name': obj.name, 
            'tag_type': obj.tag_type,
            'color': obj.color
        } for obj in queryset]
        return Response(data)

class EmployeeStatusViewSet(viewsets.ModelViewSet):
    """
    API endpoint for employee statuses with full CRUD operations
    """
    queryset = EmployeeStatus.objects.all()
    serializer_class = EmployeeStatusSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name']
    filterset_fields = ['is_active']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']

    @action(detail=False, methods=['get'])
    def dropdown_options(self, request):
        """Get simplified data for dropdown options"""
        queryset = self.queryset.filter(is_active=True)
        data = [{'id': obj.id, 'name': obj.name, 'color': obj.color} for obj in queryset]
        return Response(data)

# Enhanced Employee ViewSet with Advanced Filtering
class EmployeeViewSet(viewsets.ModelViewSet):
    """
    API endpoint for employees with advanced filtering and search
    """
    queryset = Employee.objects.select_related(
        'user', 'business_function', 'department', 'unit', 
        'job_function', 'position_group', 'status', 'line_manager'
    ).prefetch_related('tags')
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = EmployeeFilter
    
    # Advanced search fields
    search_fields = [
        'employee_id', 'user__first_name', 'user__last_name', 
        'user__email', 'job_title', 'full_name', 'phone'
    ]
    
    # Comprehensive ordering fields
    ordering_fields = [
        'employee_id', 'user__first_name', 'user__last_name', 'full_name',
        'start_date', 'end_date', 'date_of_birth', 'grade', 'created_at',
        'business_function__name', 'department__name', 'unit__name',
        'job_function__name', 'position_group__hierarchy_level', 
        'status__name', 'job_title'
    ]
    ordering = ['employee_id']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return EmployeeListSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return EmployeeCreateUpdateSerializer
        else:
            return EmployeeDetailSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Multi-level sorting
        ordering = self.request.query_params.get('ordering', '').split(',')
        if ordering and ordering[0]:
            # Remove empty strings and apply ordering
            valid_ordering = [o.strip() for o in ordering if o.strip()]
            if valid_ordering:
                queryset = queryset.order_by(*valid_ordering)
        
        return queryset
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)
    
    @action(detail=False, methods=['get'])
    def filter_options(self, request):
        """Get all available filter options for frontend dropdowns"""
        options = {
            'business_functions': BusinessFunction.objects.filter(is_active=True).values('id', 'name', 'code'),
            'departments': Department.objects.filter(is_active=True).select_related('business_function').values(
                'id', 'name', 'business_function__id', 'business_function__name'
            ),
            'units': Unit.objects.filter(is_active=True).select_related('department', 'department__business_function').values(
                'id', 'name', 'department__id', 'department__name', 'department__business_function__name'
            ),
            'job_functions': JobFunction.objects.filter(is_active=True).values('id', 'name'),
            'position_groups': PositionGroup.objects.filter(is_active=True).values('id', 'name', 'hierarchy_level').order_by('hierarchy_level'),
            'statuses': EmployeeStatus.objects.filter(is_active=True).values('id', 'name', 'color'),
            'tags': EmployeeTag.objects.filter(is_active=True).values('id', 'name', 'tag_type', 'color'),
            'grades': [{'value': i, 'label': f'Grade {i}'} for i in range(1, 9)],
            'genders': [{'value': 'MALE', 'label': 'Male'}, {'value': 'FEMALE', 'label': 'Female'}],
            'line_managers': Employee.objects.filter(
                direct_reports__isnull=False
            ).distinct().values('id', 'employee_id', 'full_name', 'job_title'),
        }
        return Response(options)
    
    @action(detail=False, methods=['get'])
    def dropdown_search(self, request):
        """Advanced dropdown search for various fields"""
        field = request.query_params.get('field')
        search = request.query_params.get('search', '')
        limit = int(request.query_params.get('limit', 50))
        
        if field == 'line_managers':
            queryset = Employee.objects.filter(
                Q(employee_id__icontains=search) |
                Q(full_name__icontains=search) |
                Q(job_title__icontains=search)
            )[:limit]
            data = [{
                'id': emp.id,
                'employee_id': emp.employee_id,
                'name': emp.full_name,
                'job_title': emp.job_title,
                'label': f"{emp.employee_id} - {emp.full_name} ({emp.job_title})"
            } for emp in queryset]
            
        elif field == 'job_titles':
            queryset = Employee.objects.filter(
                job_title__icontains=search
            ).values('job_title').distinct()[:limit]
            data = [{'value': item['job_title'], 'label': item['job_title']} for item in queryset]
            
        else:
            data = []
        
        return Response(data)
    
    @action(detail=False, methods=['get'])
    def org_chart(self, request):
        """Get organizational chart data starting from top-level managers"""
        top_level_employees = self.get_queryset().filter(
            line_manager__isnull=True,
            status__name='ACTIVE',
            is_visible_in_org_chart=True
        ).order_by('position_group__hierarchy_level', 'employee_id')
        
        serializer = OrgChartNodeSerializer(top_level_employees, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['patch'])
    def update_org_chart_visibility(self, request):
        """Update org chart visibility for multiple employees"""
        employee_ids = request.data.get('employee_ids', [])
        is_visible = request.data.get('is_visible_in_org_chart')
        
        if not employee_ids or is_visible is None:
            return Response(
                {'error': 'employee_ids and is_visible_in_org_chart are required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        updated_employees = []
        for employee_id in employee_ids:
            try:
                employee = Employee.objects.get(id=employee_id)
                old_visibility = employee.is_visible_in_org_chart
                employee.is_visible_in_org_chart = is_visible
                employee.save()
                
                if old_visibility != is_visible:
                    EmployeeActivity.objects.create(
                        employee=employee,
                        activity_type='ORG_CHART_VISIBILITY_CHANGED',
                        description=f"Org chart visibility changed from {old_visibility} to {is_visible} for {employee.full_name}",
                        performed_by=request.user,
                        metadata={'old_visibility': old_visibility, 'new_visibility': is_visible}
                    )
                
                updated_employees.append({
                    'id': employee.id,
                    'employee_id': employee.employee_id,
                    'name': employee.full_name,
                    'is_visible_in_org_chart': employee.is_visible_in_org_chart
                })
                
            except Employee.DoesNotExist:
                continue
        
        return Response({
            'message': f'Successfully updated {len(updated_employees)} employees',
            'updated_employees': updated_employees
        })
    
    @action(detail=True, methods=['patch'])
    def org_chart_visibility(self, request, pk=None):
        """Update org chart visibility for a single employee"""
        employee = self.get_object()
        serializer = EmployeeOrgChartVisibilitySerializer(
            employee, 
            data=request.data, 
            partial=True, 
            context={'request': request}
        )
        
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get employee statistics for dashboard"""
        queryset = self.get_queryset()
        
        stats = {
            'total_employees': queryset.count(),
            'active_employees': queryset.filter(status__name='ACTIVE').count(),
            'by_business_function': list(queryset.values('business_function__name').annotate(count=Count('id')).order_by('-count')),
            'by_department': list(queryset.values('department__name').annotate(count=Count('id')).order_by('-count')),
            'by_position_group': list(queryset.values('position_group__name').annotate(count=Count('id')).order_by('position_group__hierarchy_level')),
            'by_status': list(queryset.values('status__name', 'status__color').annotate(count=Count('id')).order_by('-count')),
            'by_gender': list(queryset.values('gender').annotate(count=Count('id'))),
            'by_grade': list(queryset.values('grade').annotate(count=Count('id')).order_by('grade')),
            'visible_in_org_chart': queryset.filter(is_visible_in_org_chart=True).count(),
            'hidden_from_org_chart': queryset.filter(is_visible_in_org_chart=False).count(),
            'new_hires_last_30_days': queryset.filter(
                start_date__gte=timezone.now().date() - timedelta(days=30)
            ).count(),
            'employees_on_leave': queryset.filter(status__name='ON LEAVE').count(),
            'probation_employees': queryset.filter(status__name='PROBATION').count(),
        }
        
        return Response(stats)
    
    @action(detail=False, methods=['post'])
    def bulk_update(self, request):
        """Bulk update multiple employees"""
        employee_ids = request.data.get('employee_ids', [])
        updates = request.data.get('updates', {})
        
        if not employee_ids or not updates:
            return Response(
                {'error': 'employee_ids and updates are required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate that only allowed fields are being updated
        allowed_fields = ['status', 'line_manager', 'is_visible_in_org_chart', 'tags']
        invalid_fields = set(updates.keys()) - set(allowed_fields)
        if invalid_fields:
            return Response(
                {'error': f'Invalid fields for bulk update: {list(invalid_fields)}'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Handle tags separately as it's a many-to-many field
        tag_ids = updates.pop('tags', None)
        
        # Perform bulk update for regular fields
        updated_count = 0
        if updates:
            updated_count = Employee.objects.filter(id__in=employee_ids).update(**updates)
        
        # Handle tags update
        if tag_ids is not None:
            for employee_id in employee_ids:
                try:
                    employee = Employee.objects.get(id=employee_id)
                    employee.tags.set(tag_ids)
                    updated_count += 1
                except Employee.DoesNotExist:
                    continue
        
        # Log activities for each updated employee
        for employee_id in employee_ids:
            try:
                employee = Employee.objects.get(id=employee_id)
                update_description = []
                if 'status' in updates:
                    update_description.append(f"status changed")
                if 'line_manager' in updates:
                    update_description.append(f"line manager changed")
                if 'is_visible_in_org_chart' in updates:
                    update_description.append(f"org chart visibility changed")
                if tag_ids is not None:
                    update_description.append(f"tags updated")
                
                EmployeeActivity.objects.create(
                    employee=employee,
                    activity_type='UPDATED',
                    description=f"Bulk update performed on {employee.full_name}: {', '.join(update_description)}",
                    performed_by=request.user,
                    metadata={'updates': updates, 'tag_ids': tag_ids}
                )
            except Employee.DoesNotExist:
                continue
        
        return Response({
            'message': f'Successfully updated {updated_count} employees',
            'updated_count': updated_count
        })

    @action(detail=False, methods=['get'])
    def export_data(self, request):
        """Export employee data with current filters applied"""
        # Apply the same filters as the list view
        queryset = self.filter_queryset(self.get_queryset())
        
        # Get export format (csv, excel)
        export_format = request.query_params.get('format', 'csv')
        
        # Serialize the data
        serializer = EmployeeListSerializer(queryset, many=True)
        
        if export_format == 'csv':
            # Return CSV data structure for frontend processing
            data = {
                'format': 'csv',
                'filename': f'employees_export_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv',
                'data': serializer.data,
                'count': queryset.count()
            }
        else:
            # Return Excel data structure for frontend processing
            data = {
                'format': 'excel',
                'filename': f'employees_export_{timezone.now().strftime("%Y%m%d_%H%M%S")}.xlsx',
                'data': serializer.data,
                'count': queryset.count()
            }
        
        return Response(data)

class EmployeeDocumentViewSet(viewsets.ModelViewSet):
    """
    API endpoint for employee documents
    """
    serializer_class = EmployeeDocumentSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['employee', 'document_type']
    search_fields = ['name', 'employee__employee_id', 'employee__full_name']
    ordering_fields = ['name', 'document_type', 'uploaded_at']
    ordering = ['-uploaded_at']
    
    def get_queryset(self):
        return EmployeeDocument.objects.select_related('employee', 'uploaded_by').all()
    
    def perform_create(self, serializer):
        serializer.save(uploaded_by=self.request.user)
        
        # Log document upload activity
        document = serializer.instance
        EmployeeActivity.objects.create(
            employee=document.employee,
            activity_type='DOCUMENT_UPLOADED',
            description=f"Document '{document.name}' uploaded for {document.employee.full_name}",
            performed_by=self.request.user,
            metadata={
                'document_id': str(document.id),
                'document_name': document.name,
                'document_type': document.document_type
            }
        )

class EmployeeActivityViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for employee activities (read-only)
    """
    serializer_class = EmployeeActivitySerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['employee', 'activity_type', 'performed_by']
    search_fields = ['employee__employee_id', 'employee__full_name', 'description']
    ordering_fields = ['timestamp', 'activity_type']
    ordering = ['-timestamp']
    
    def get_queryset(self):
        return EmployeeActivity.objects.select_related('employee', 'performed_by').all()
    
    @action(detail=False, methods=['get'])
    def recent_activities(self, request):
        """Get recent activities across all employees"""
        limit = int(request.query_params.get('limit', 50))
        queryset = self.get_queryset()[:limit]
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def activity_summary(self, request):
        """Get activity summary statistics"""
        from django.utils import timezone
        from datetime import timedelta
        
        # Get activities from last 30 days
        thirty_days_ago = timezone.now() - timedelta(days=30)
        recent_activities = self.get_queryset().filter(timestamp__gte=thirty_days_ago)
        
        summary = {
            'total_activities_last_30_days': recent_activities.count(),
            'by_activity_type': list(
                recent_activities.values('activity_type')
                .annotate(count=Count('id'))
                .order_by('-count')
            ),
            'most_active_employees': list(
                recent_activities.values('employee__employee_id', 'employee__full_name')
                .annotate(activity_count=Count('id'))
                .order_by('-activity_count')[:10]
            ),
            'most_active_users': list(
                recent_activities.filter(performed_by__isnull=False)
                .values('performed_by__username', 'performed_by__first_name', 'performed_by__last_name')
                .annotate(activity_count=Count('id'))
                .order_by('-activity_count')[:10]
            )
        }
        
        return Response(summary)
    
    # Yeni ViewSet status management üçün
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def status_dashboard(request):
    """
    Status dashboard məlumatları
    """
    from .status_management import EmployeeStatusManager
    
    # Bütün employee-lər üçün status analizi
    employees = Employee.objects.select_related('status').all()
    
    dashboard_data = {
        'total_employees': employees.count(),
        'status_breakdown': {},
        'needs_update': [],
        'contract_analysis': {},
        'recent_status_changes': []
    }
    
    # Status breakdown
    status_counts = employees.values('status__name').annotate(count=Count('id'))
    for item in status_counts:
        status_name = item['status__name'] or 'NO_STATUS'
        dashboard_data['status_breakdown'][status_name] = item['count']
    
    # Employee-lər ki status yeniləməyə ehtiyacı var
    needs_update = []
    for employee in employees[:50]:  # İlk 50-ni yoxla
        preview = EmployeeStatusManager.get_status_preview(employee)
        if preview['needs_update']:
            needs_update.append({
                'employee_id': employee.employee_id,
                'name': employee.full_name,
                'current_status': preview['current_status'],
                'required_status': preview['required_status'],
                'reason': preview['reason']
            })
    
    dashboard_data['needs_update'] = needs_update[:10]  # İlk 10-u göstər
    dashboard_data['total_needs_update'] = len(needs_update)
    
    # Contract analysis
    contract_counts = employees.values('contract_duration').annotate(count=Count('id'))
    for item in contract_counts:
        contract_type = item['contract_duration']
        dashboard_data['contract_analysis'][contract_type] = {
            'count': item['count'],
            'probation_days': EmployeeStatusManager.get_probation_days(contract_type)
        }
    
    # Son 10 status dəyişikliyi
    recent_activities = EmployeeActivity.objects.filter(
        activity_type='STATUS_CHANGED'
    ).select_related('employee', 'performed_by').order_by('-timestamp')[:10]
    
    dashboard_data['recent_status_changes'] = [
        {
            'employee_id': activity.employee.employee_id,
            'employee_name': activity.employee.full_name,
            'description': activity.description,
            'timestamp': activity.timestamp,
            'performed_by': activity.performed_by.get_full_name() if activity.performed_by else 'System',
            'metadata': activity.metadata
        }
        for activity in recent_activities
    ]
    
    return Response(dashboard_data)