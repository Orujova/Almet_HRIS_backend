# api/views.py

from django.shortcuts import render
from django.utils import timezone
from rest_framework import status, viewsets
from django.db.models import Q, Count
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework import status, viewsets, filters
from rest_framework.pagination import PageNumberPagination
from django_filters.rest_framework import DjangoFilterBackend
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
import logging
import traceback

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

# Custom Pagination
class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

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
        serializer = UserSerializer(request.user)
        
        # Check if user has an employee profile
        try:
            employee = Employee.objects.get(user=request.user)
            employee_data = EmployeeDetailSerializer(employee).data
        except Employee.DoesNotExist:
            employee_data = None
        
        return Response({
            'success': True,
            'user': serializer.data,
            'employee': employee_data
        }, status=status.HTTP_200_OK)
    
    except Exception as e:
        logger.error(f'User info error: {str(e)}')
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
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'code']
    filterset_fields = ['is_active']
    ordering_fields = ['name', 'code', 'created_at']
    ordering = ['name']

class DepartmentViewSet(viewsets.ModelViewSet):
    """
    API endpoint for departments with full CRUD operations
    """
    queryset = Department.objects.select_related('business_function')
    serializer_class = DepartmentSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'business_function__name']
    filterset_fields = ['business_function', 'is_active']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']

class UnitViewSet(viewsets.ModelViewSet):
    """
    API endpoint for units with full CRUD operations
    """
    queryset = Unit.objects.select_related('department', 'department__business_function')
    serializer_class = UnitSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'department__name']
    filterset_fields = ['department', 'is_active']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']

class JobFunctionViewSet(viewsets.ModelViewSet):
    """
    API endpoint for job functions with full CRUD operations
    """
    queryset = JobFunction.objects.all()
    serializer_class = JobFunctionSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name']
    filterset_fields = ['is_active']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']

class PositionGroupViewSet(viewsets.ModelViewSet):
    """
    API endpoint for position groups with full CRUD operations
    """
    queryset = PositionGroup.objects.all()
    serializer_class = PositionGroupSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name']
    filterset_fields = ['is_active']
    ordering_fields = ['hierarchy_level', 'name', 'created_at']
    ordering = ['hierarchy_level']
    
    @swagger_auto_schema(
        method='get',
        operation_description="Get position groups ordered by hierarchy",
        responses={200: PositionGroupSerializer(many=True)}
    )
    @action(detail=False, methods=['get'])
    def by_hierarchy(self, request):
        """
        Get position groups ordered by hierarchy level
        """
        queryset = self.get_queryset().filter(is_active=True).order_by('hierarchy_level')
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

class EmployeeTagViewSet(viewsets.ModelViewSet):
    """
    API endpoint for employee tags with full CRUD operations
    """
    queryset = EmployeeTag.objects.all()
    serializer_class = EmployeeTagSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name']
    filterset_fields = ['tag_type', 'is_active']
    ordering_fields = ['name', 'tag_type', 'created_at']
    ordering = ['name']

class EmployeeStatusViewSet(viewsets.ModelViewSet):
    """
    API endpoint for employee statuses with full CRUD operations
    """
    queryset = EmployeeStatus.objects.all()
    serializer_class = EmployeeStatusSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name']
    filterset_fields = ['is_active']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']

# Main Employee ViewSet
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
    
    # Search fields
    search_fields = [
        'employee_id', 'user__first_name', 'user__last_name', 
        'user__email', 'job_title', 'full_name'
    ]
    
    # Filter fields
    filterset_fields = {
        'business_function': ['exact'],
        'department': ['exact'],
        'unit': ['exact'],
        'job_function': ['exact'],
        'position_group': ['exact'],
        'status': ['exact'],
        'gender': ['exact'],
        'grade': ['exact', 'gte', 'lte'],
        'start_date': ['exact', 'gte', 'lte'],
    }
    
    # Ordering fields
    ordering_fields = [
        'employee_id', 'user__first_name', 'user__last_name', 
        'start_date', 'grade', 'created_at'
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
        
        # Advanced filtering
        request = self.request
        
        # Filter by line manager
        line_manager_id = request.query_params.get('line_manager')
        if line_manager_id:
            queryset = queryset.filter(line_manager_id=line_manager_id)
        
        # Filter by tags
        tags = request.query_params.getlist('tags')
        if tags:
            queryset = queryset.filter(tags__id__in=tags).distinct()
        
        # Filter by business function name
        business_function_name = request.query_params.get('business_function_name')
        if business_function_name:
            queryset = queryset.filter(business_function__name__icontains=business_function_name)
        
        # Filter by department name
        department_name = request.query_params.get('department_name')
        if department_name:
            queryset = queryset.filter(department__name__icontains=department_name)
        
        return queryset
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)
    
    @swagger_auto_schema(
        method='get',
        operation_description="Get organizational chart data",
        responses={200: OrgChartNodeSerializer(many=True)}
    )
    @action(detail=False, methods=['get'])
    def org_chart(self, request):
        """
        Get organizational chart data starting from top-level managers
        """
        # Get employees with no line manager (top level)
        top_level_employees = self.get_queryset().filter(
            line_manager__isnull=True,
            status__name='ACTIVE',
            is_visible_in_org_chart=True
        ).order_by('position_group__hierarchy_level', 'employee_id')
        
        serializer = OrgChartNodeSerializer(top_level_employees, many=True)
        return Response(serializer.data)
    
    @swagger_auto_schema(
        method='patch',
        operation_description="Update org chart visibility for multiple employees",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'employee_ids': openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(type=openapi.TYPE_INTEGER)
                ),
                'is_visible_in_org_chart': openapi.Schema(type=openapi.TYPE_BOOLEAN)
            }
        )
    )
    @action(detail=False, methods=['patch'])
    def update_org_chart_visibility(self, request):
        """
        Update org chart visibility for multiple employees
        """
        employee_ids = request.data.get('employee_ids', [])
        is_visible = request.data.get('is_visible_in_org_chart')
        
        if not employee_ids or is_visible is None:
            return Response(
                {'error': 'employee_ids and is_visible_in_org_chart are required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Update employees
        updated_employees = []
        for employee_id in employee_ids:
            try:
                employee = Employee.objects.get(id=employee_id)
                old_visibility = employee.is_visible_in_org_chart
                employee.is_visible_in_org_chart = is_visible
                employee.save()
                
                # Log activity if visibility changed
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
    
    @swagger_auto_schema(
        method='patch',
        operation_description="Update org chart visibility for a single employee",
        request_body=EmployeeOrgChartVisibilitySerializer
    )
    @action(detail=True, methods=['patch'])
    def org_chart_visibility(self, request, pk=None):
        """
        Update org chart visibility for a single employee
        """
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
    
    @swagger_auto_schema(
        method='get',
        operation_description="Get employee statistics",
        responses={200: openapi.Response(description="Employee statistics")}
    )
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """
        Get employee statistics for dashboard
        """
        queryset = self.get_queryset()
        
        stats = {
            'total_employees': queryset.count(),
            'active_employees': queryset.filter(status__name='ACTIVE').count(),
            'by_business_function': queryset.values('business_function__name').annotate(count=Count('id')),
            'by_department': queryset.values('department__name').annotate(count=Count('id')),
            'by_position_group': queryset.values('position_group__name').annotate(count=Count('id')),
            'by_status': queryset.values('status__name').annotate(count=Count('id')),
            'by_gender': queryset.values('gender').annotate(count=Count('id')),
            'by_grade': queryset.values('grade').annotate(count=Count('id')).order_by('grade'),
            'visible_in_org_chart': queryset.filter(is_visible_in_org_chart=True).count(),
            'hidden_from_org_chart': queryset.filter(is_visible_in_org_chart=False).count(),
        }
        
        return Response(stats)
    
    @swagger_auto_schema(
        method='post',
        operation_description="Bulk update employees",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'employee_ids': openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(type=openapi.TYPE_INTEGER)
                ),
                'updates': openapi.Schema(type=openapi.TYPE_OBJECT)
            }
        )
    )
    @action(detail=False, methods=['post'])
    def bulk_update(self, request):
        """
        Bulk update multiple employees
        """
        employee_ids = request.data.get('employee_ids', [])
        updates = request.data.get('updates', {})
        
        if not employee_ids or not updates:
            return Response(
                {'error': 'employee_ids and updates are required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate that only allowed fields are being updated
        allowed_fields = ['status', 'line_manager', 'is_visible_in_org_chart']
        invalid_fields = set(updates.keys()) - set(allowed_fields)
        if invalid_fields:
            return Response(
                {'error': f'Invalid fields for bulk update: {list(invalid_fields)}'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Perform bulk update
        updated_count = Employee.objects.filter(id__in=employee_ids).update(**updates)
        
        # Log activities for each updated employee
        for employee_id in employee_ids:
            try:
                employee = Employee.objects.get(id=employee_id)
                EmployeeActivity.objects.create(
                    employee=employee,
                    activity_type='UPDATED',
                    description=f"Bulk update performed on {employee.full_name}",
                    performed_by=request.user,
                    metadata={'updates': updates}
                )
            except Employee.DoesNotExist:
                continue
        
        return Response({
            'message': f'Successfully updated {updated_count} employees',
            'updated_count': updated_count
        })

class EmployeeDocumentViewSet(viewsets.ModelViewSet):
    """
    API endpoint for employee documents
    """
    serializer_class = EmployeeDocumentSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['employee', 'document_type']
    
    def get_queryset(self):
        return EmployeeDocument.objects.filter(employee__in=Employee.objects.all())
    
    def perform_create(self, serializer):
        serializer.save(uploaded_by=self.request.user)

class EmployeeActivityViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for employee activities (read-only)
    """
    serializer_class = EmployeeActivitySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['employee', 'activity_type']
    ordering = ['-timestamp']
    
    def get_queryset(self):
        return EmployeeActivity.objects.filter(employee__in=Employee.objects.all())