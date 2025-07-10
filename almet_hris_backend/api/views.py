# api/views.py - ENHANCED: Complete Employee Management with Advanced Contract Status Management

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
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser
from rest_framework.parsers import MultiPartParser, FormParser
from datetime import datetime, timedelta, date
from django.utils.dateparse import parse_date
from django.db import transaction
from django.http import HttpResponse
import csv
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils.dataframe import dataframe_to_rows
import io
import pandas as pd
from django.contrib.auth.models import User
from .status_management import EmployeeStatusManager, LineManagerStatusIntegration, StatusAutomationRules
from .models import (
    Employee, BusinessFunction, Department, Unit, JobFunction, 
    PositionGroup, EmployeeTag, EmployeeDocument, EmployeeStatus,
    EmployeeActivity, VacantPosition, ContractTypeConfig,
    ContractStatusManager
)
from .serializers import (
    EmployeeListSerializer, EmployeeDetailSerializer, EmployeeCreateUpdateSerializer,
    BusinessFunctionSerializer, DepartmentSerializer, UnitSerializer,
    JobFunctionSerializer, PositionGroupSerializer, EmployeeTagSerializer,
    EmployeeStatusSerializer, EmployeeDocumentSerializer, EmployeeActivitySerializer,
    UserSerializer, OrgChartNodeSerializer, EmployeeOrgChartVisibilitySerializer,
    VacantPositionListSerializer, VacantPositionDetailSerializer, VacantPositionCreateSerializer,
    
    
    EmployeeGradingUpdateSerializer, EmployeeGradingListSerializer,
   BulkEmployeeGradingUpdateSerializer,
    EmployeeExportSerializer,
    ContractTypeConfigSerializer, BulkContractExtensionSerializer,ContractExtensionSerializer,SingleEmployeeTagUpdateSerializer,SingleLineManagerAssignmentSerializer,BulkEmployeeTagUpdateSerializer,BulkSoftDeleteSerializer,StatusPreviewRequestSerializer,BulkRestoreSerializer,BulkLineManagerAssignmentSerializer
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

# Microsoft Authentication Views
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
                Q(department__name__icontains=search) |
                Q(father_name__icontains=search)  # NEW: Include father_name in search
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
        
        # Multiple line manager filtering (ENHANCED)
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
        
        # Status needs update filter (NEW)
        status_needs_update = self.params.get('status_needs_update')
        if status_needs_update and status_needs_update.lower() == 'true':
            # This requires special handling - we'll filter this in the view
            pass
        
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
        'father_name': 'father_name',  # NEW FIELD
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

# Business Structure ViewSets
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
    ordering = ['order', 'name']

# NEW: Contract Type Configuration ViewSet
class ContractTypeConfigViewSet(viewsets.ModelViewSet):
    queryset = ContractTypeConfig.objects.all()
    serializer_class = ContractTypeConfigSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['contract_type', 'enable_auto_transitions', 'is_active']
    search_fields = ['contract_type', 'display_name']
    ordering = ['contract_type']
    
   
    
    @action(detail=True, methods=['get'])
    def test_calculations(self, request, pk=None):
        """Test status calculations for this contract type"""
        config = self.get_object()
        
        # Get sample employees with this contract type
        employees = Employee.objects.filter(contract_duration=config.contract_type)[:10]
        
        results = []
        for employee in employees:
            preview = employee.get_status_preview()
            results.append({
                'employee_id': employee.employee_id,
                'name': employee.full_name,
                'current_status': preview['current_status'],
                'required_status': preview['required_status'],
                'needs_update': preview['needs_update'],
                'reason': preview['reason'],
                'days_since_start': preview['days_since_start']
            })
        
        return Response({
            'contract_type': config.contract_type,
            'configuration': {
                'onboarding_days': config.onboarding_days,
                'probation_days': config.probation_days,
                'total_days_until_active': config.get_total_days_until_active()
            },
            'sample_employees': results
        })

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
    parser_classes = [JSONParser, MultiPartParser, FormParser]
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
        
        # Filter employees whose status needs update (if requested)
        status_needs_update = request.query_params.get('status_needs_update')
        if status_needs_update and status_needs_update.lower() == 'true':
            employees_needing_update = []
            for employee in queryset:
                try:
                    preview = employee.get_status_preview()
                    if preview['needs_update']:
                        employees_needing_update.append(employee.id)
                except:
                    pass
            queryset = queryset.filter(id__in=employees_needing_update)
        
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
    
  
  
    def _generate_bulk_template(self):
        """Generate Excel template with dropdowns and validation"""
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment
        from openpyxl.worksheet.datavalidation import DataValidation
        
        wb = Workbook()
        ws = wb.active
        ws.title = "Employee Template"
        
        # Define headers with validation requirements (ENHANCED with father_name)
        headers = [
            'Employee ID*', 'First Name*', 'Last Name*', 'Email*',
            'Date of Birth', 'Gender', 'Father Name', 'Address', 'Phone', 'Emergency Contact',
            'Business Function*', 'Department*', 'Unit', 'Job Function*',
            'Job Title*', 'Position Group*', 'Grading Level',
            'Start Date*', 'Contract Duration*', 'Contract Start Date',
            'Line Manager Employee ID', 'Is Visible in Org Chart',
            'Tag Names (comma separated)', 'Notes'
        ]
        
        # Write headers
        ws.append(headers)
        
        # Style headers
        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
        header_alignment = Alignment(horizontal="center", vertical="center")
        
        for cell in ws[1]:
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_alignment
        
        # Add sample data row (ENHANCED with father_name)
        sample_data = [
            'HC001', 'John', 'Doe', 'john.doe@company.com',
            '1990-01-15', 'MALE', 'Robert Doe', '123 Main St, City', '+994501234567', 'Jane Doe +994501234568',
            'IT', 'Software Development', 'Backend Team', 'Software Engineer',
            'Senior Software Engineer', 'SENIOR SPECIALIST', 'SS_M',
            '2024-01-15', 'PERMANENT', '2024-01-15',
            'HC002', 'TRUE', 'SKILL:Python,STATUS:New Hire', 'New team member'
        ]
        ws.append(sample_data)
        
        # Create reference sheets for dropdowns
        self._create_reference_sheets(wb)
        
        # Add data validations
        self._add_data_validations(ws)
        
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
        
        # Add instructions sheet
        self._add_instructions_sheet(wb)
        
        # Save to BytesIO
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        
        response = HttpResponse(
            output.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="employee_bulk_template_{date.today()}.xlsx"'
        
        return response
    
    def _create_reference_sheets(self, workbook):
        """Create reference sheets with lookup data"""
        
        # Business Functions sheet
        bf_sheet = workbook.create_sheet(title="Business Functions")
        bf_sheet.append(['Business Function'])
        for bf in BusinessFunction.objects.filter(is_active=True).order_by('name'):
            bf_sheet.append([bf.name])
        
        # Departments sheet
        dept_sheet = workbook.create_sheet(title="Departments")
        dept_sheet.append(['Business Function', 'Department'])
        for dept in Department.objects.select_related('business_function').filter(is_active=True).order_by('business_function__name', 'name'):
            dept_sheet.append([dept.business_function.name, dept.name])
        
        # Units sheet
        unit_sheet = workbook.create_sheet(title="Units")
        unit_sheet.append(['Department', 'Unit'])
        for unit in Unit.objects.select_related('department').filter(is_active=True).order_by('department__name', 'name'):
            unit_sheet.append([unit.department.name, unit.name])
        
        # Job Functions sheet
        jf_sheet = workbook.create_sheet(title="Job Functions")
        jf_sheet.append(['Job Function'])
        for jf in JobFunction.objects.filter(is_active=True).order_by('name'):
            jf_sheet.append([jf.name])
        
        # Position Groups sheet
        pg_sheet = workbook.create_sheet(title="Position Groups")
        pg_sheet.append(['Position Group', 'Available Grading Levels'])
        for pg in PositionGroup.objects.filter(is_active=True).order_by('hierarchy_level'):
            levels = ', '.join([level['code'] for level in pg.get_grading_levels()])
            pg_sheet.append([pg.get_name_display(), levels])
        
        # Line Managers sheet (NEW)
        lm_sheet = workbook.create_sheet(title="Line Managers")
        lm_sheet.append(['Employee ID', 'Name', 'Position'])
        for manager in Employee.objects.filter(
            status__affects_headcount=True,
            position_group__hierarchy_level__lte=4,
            is_deleted=False
        ).order_by('employee_id'):
            lm_sheet.append([manager.employee_id, manager.full_name, manager.job_title])
        
        # Other options sheet
        options_sheet = workbook.create_sheet(title="Options")
        options_sheet.append(['Gender Options'])
        options_sheet.append(['MALE'])
        options_sheet.append(['FEMALE'])
        options_sheet.append([''])
        options_sheet.append(['Contract Duration Options'])
        for duration in Employee.contract_duration:
            options_sheet.append([duration[0]])
        options_sheet.append([''])
        options_sheet.append(['Boolean Options'])
        options_sheet.append(['TRUE'])
        options_sheet.append(['FALSE'])
    
    def _add_data_validations(self, worksheet):
        """Add data validation to template"""
        from openpyxl.worksheet.datavalidation import DataValidation
        
        # Gender validation (column F)
        gender_validation = DataValidation(
            type="list",
            formula1='"MALE,FEMALE"',
            showDropDown=True
        )
        gender_validation.add("F3:F1000")
        worksheet.add_data_validation(gender_validation)
        
        # Business Function validation (column K)
        bf_validation = DataValidation(
            type="list",
            formula1="'Business Functions'!A2:A100",
            showDropDown=True
        )
        bf_validation.add("K3:K1000")
        worksheet.add_data_validation(bf_validation)
        
        # Job Function validation (column N)
        jf_validation = DataValidation(
            type="list",
            formula1="'Job Functions'!A2:A100",
            showDropDown=True
        )
        jf_validation.add("N3:N1000")
        worksheet.add_data_validation(jf_validation)
        
        # Position Group validation (column P)
        pg_validation = DataValidation(
            type="list",
            formula1="'Position Groups'!A2:A100",
            showDropDown=True
        )
        pg_validation.add("P3:P1000")
        worksheet.add_data_validation(pg_validation)
        
        # Contract Duration validation (column S)
        contract_validation = DataValidation(
            type="list",
            formula1='"3_MONTHS,6_MONTHS,1_YEAR,2_YEARS,3_YEARS,PERMANENT"',
            showDropDown=True
        )
        contract_validation.add("S3:S1000")
        worksheet.add_data_validation(contract_validation)
        
        # Boolean validation for Org Chart visibility (column V)
        bool_validation = DataValidation(
            type="list",
            formula1='"TRUE,FALSE"',
            showDropDown=True
        )
        bool_validation.add("V3:V1000")
        worksheet.add_data_validation(bool_validation)
    
    def _add_instructions_sheet(self, workbook):
        """Add instructions sheet to the workbook"""
        instructions_sheet = workbook.create_sheet(title="Instructions")
        
        instructions = [
            ["BULK EMPLOYEE CREATION TEMPLATE INSTRUCTIONS"],
            [""],
            ["REQUIRED FIELDS (marked with *)"],
            ["• Employee ID: Unique identifier (e.g., HC001)"],
            ["• First Name: Employee's first name"],
            ["• Last Name: Employee's last name"],
            ["• Email: Unique email address"],
            ["• Business Function: Must match exactly from dropdown"],
            ["• Department: Must exist under selected Business Function"],
            ["• Job Function: Must match exactly from dropdown"],
            ["• Job Title: Position title"],
            ["• Position Group: Must match exactly from dropdown"],
            ["• Start Date: Format YYYY-MM-DD (e.g., 2024-01-15)"],
            ["• Contract Duration: Select from dropdown"],
            [""],
            ["OPTIONAL FIELDS"],
            ["• Date of Birth: Format YYYY-MM-DD"],
            ["• Gender: MALE or FEMALE"],
            ["• Father Name: Father's name (optional)"],
            ["• Unit: Must exist under selected Department"],
            ["• Grading Level: Must be valid for Position Group (see Position Groups sheet)"],
            ["• Contract Start Date: If different from Start Date"],
            ["• Line Manager Employee ID: Must be existing employee ID (see Line Managers sheet)"],
            ["• Is Visible in Org Chart: TRUE or FALSE (default: TRUE)"],
            ["• Tag Names: Comma separated, format TYPE:Name (e.g., SKILL:Python,STATUS:New)"],
            [""],
            ["VALIDATION RULES"],
            ["• Employee IDs must be unique"],
            ["• Email addresses must be unique"],
            ["• Departments must belong to selected Business Function"],
            ["• Units must belong to selected Department"],
            ["• Grading Levels must be valid for Position Group"],
            ["• Line Manager must be existing employee"],
            ["• Dates must be in YYYY-MM-DD format"],
            [""],
            ["NOTES"],
            ["• Remove the sample data row before uploading"],
            ["• Check the reference sheets for valid values"],
            ["• Ensure all required fields are filled"],
            ["• Date format must be YYYY-MM-DD"],
            ["• Maximum 1000 employees per upload"],
            ["• Father Name is optional but can be useful for identification"]
        ]
        
        for row in instructions:
            instructions_sheet.append(row)
        
        # Style the title
        title_font = Font(bold=True, size=14, color="FFFFFF")
        title_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
        instructions_sheet['A1'].font = title_font
        instructions_sheet['A1'].fill = title_fill
        
        # Auto-adjust column width
        instructions_sheet.column_dimensions['A'].width = 80
    

    def _validate_and_prepare_employee_data(self, row, business_functions, departments, 
                                          units, job_functions, position_groups, 
                                          employee_lookup, tags_lookup, default_status, row_num):
        """Validate and prepare employee data from Excel row"""
        data = {}
        errors = []
        
        # Required fields validation
        required_fields = {
            'Employee ID*': 'employee_id',
            'First Name*': 'first_name',
            'Last Name*': 'last_name',
            'Email*': 'email',
            'Business Function*': 'business_function_name',
            'Department*': 'department_name',
            'Job Function*': 'job_function_name',
            'Job Title*': 'job_title',
            'Position Group*': 'position_group_name',
            'Start Date*': 'start_date',
            'Contract Duration*': 'contract_duration'
        }
        
        for excel_field, data_field in required_fields.items():
            value = row.get(excel_field)
            if pd.isna(value) or not str(value).strip():
                errors.append(f"Missing required field: {excel_field}")
            else:
                data[data_field] = str(value).strip()
        
        if errors:
            return {'error': f"Row {row_num}: {'; '.join(errors)}"}
        
        # Validate unique fields
        if Employee.objects.filter(employee_id=data['employee_id']).exists():
            errors.append(f"Employee ID {data['employee_id']} already exists")
        
        if User.objects.filter(email=data['email']).exists():
            errors.append(f"Email {data['email']} already exists")
        
        # Validate business structure
        business_function = business_functions.get(data['business_function_name'])
        if not business_function:
            errors.append(f"Invalid Business Function: {data['business_function_name']}")
        else:
            data['business_function'] = business_function
            
            # Validate department
            dept_key = f"{data['business_function_name']}|{data['department_name']}"
            department = departments.get(dept_key)
            if not department:
                errors.append(f"Invalid Department: {data['department_name']} for Business Function: {data['business_function_name']}")
            else:
                data['department'] = department
                
                # Validate unit (optional)
                unit_name = row.get('Unit')
                if not pd.isna(unit_name) and str(unit_name).strip():
                    unit_key = f"{data['department_name']}|{str(unit_name).strip()}"
                    unit = units.get(unit_key)
                    if not unit:
                        errors.append(f"Invalid Unit: {unit_name} for Department: {data['department_name']}")
                    else:
                        data['unit'] = unit
        
        # Validate job function
        job_function = job_functions.get(data['job_function_name'])
        if not job_function:
            errors.append(f"Invalid Job Function: {data['job_function_name']}")
        else:
            data['job_function'] = job_function
        
        # Validate position group
        position_group = position_groups.get(data['position_group_name'])
        if not position_group:
            errors.append(f"Invalid Position Group: {data['position_group_name']}")
        else:
            data['position_group'] = position_group
            
            # Validate grading level
            grading_level = row.get('Grading Level')
            if not pd.isna(grading_level) and str(grading_level).strip():
                grading_level = str(grading_level).strip()
                valid_levels = [level['code'] for level in position_group.get_grading_levels()]
                if grading_level not in valid_levels:
                    errors.append(f"Invalid Grading Level: {grading_level} for Position Group: {data['position_group_name']}")
                else:
                    data['grading_level'] = grading_level
            else:
                # Default to median
                data['grading_level'] = f"{position_group.grading_shorthand}_M"
        
        # Validate dates
        try:
            start_date = pd.to_datetime(data['start_date']).date()
            data['start_date'] = start_date
        except:
            errors.append(f"Invalid Start Date format: {data['start_date']} (use YYYY-MM-DD)")
        
        contract_start_date = row.get('Contract Start Date')
        if not pd.isna(contract_start_date):
            try:
                data['contract_start_date'] = pd.to_datetime(contract_start_date).date()
            except:
                errors.append(f"Invalid Contract Start Date format: {contract_start_date} (use YYYY-MM-DD)")
        else:
            data['contract_start_date'] = data.get('start_date')
        
        # Validate contract duration
        valid_durations = [choice[0] for choice in Employee.contract_duration]
        if data['contract_duration'] not in valid_durations:
            errors.append(f"Invalid Contract Duration: {data['contract_duration']}")
        
        # Validate line manager (optional) - ENHANCED
        line_manager_id = row.get('Line Manager Employee ID')
        if not pd.isna(line_manager_id) and str(line_manager_id).strip():
            line_manager = employee_lookup.get(str(line_manager_id).strip())
            if not line_manager:
                errors.append(f"Line Manager not found: {line_manager_id}")
            else:
                data['line_manager'] = line_manager
        
        # Process optional fields
        optional_fields = {
            'Date of Birth': 'date_of_birth',
            'Gender': 'gender',
            'Father Name': 'father_name',  # NEW FIELD
            'Address': 'address',
            'Phone': 'phone',
            'Emergency Contact': 'emergency_contact',
            'Notes': 'notes'
        }
        
        for excel_field, data_field in optional_fields.items():
            value = row.get(excel_field)
            if not pd.isna(value) and str(value).strip():
                if data_field == 'date_of_birth':
                    try:
                        data[data_field] = pd.to_datetime(value).date()
                    except:
                        errors.append(f"Invalid Date of Birth format: {value} (use YYYY-MM-DD)")
                elif data_field == 'gender':
                    gender_value = str(value).strip().upper()
                    if gender_value in ['MALE', 'FEMALE']:
                        data[data_field] = gender_value
                    else:
                        errors.append(f"Invalid Gender: {value} (use MALE or FEMALE)")
                else:
                    data[data_field] = str(value).strip()
        
        # Process org chart visibility
        org_chart_visible = row.get('Is Visible in Org Chart')
        if not pd.isna(org_chart_visible):
            org_chart_str = str(org_chart_visible).strip().upper()
            data['is_visible_in_org_chart'] = org_chart_str == 'TRUE'
        else:
            data['is_visible_in_org_chart'] = True
        
        # Process tags
        tag_names = row.get('Tag Names (comma separated)')
        if not pd.isna(tag_names) and str(tag_names).strip():
            tags = []
            for tag_spec in str(tag_names).split(','):
                tag_spec = tag_spec.strip()
                if ':' in tag_spec:
                    tag_type, tag_name = tag_spec.split(':', 1)
                    tag_type = tag_type.strip().upper()
                    tag_name = tag_name.strip()
                    
                    # Get or create tag
                    tag, created = EmployeeTag.objects.get_or_create(
                        name=tag_name,
                        defaults={
                            'tag_type': tag_type if tag_type in ['LEAVE', 'STATUS', 'SKILL', 'PROJECT', 'PERFORMANCE'] else 'OTHER',
                            'is_active': True
                        }
                    )
                    tags.append(tag)
                else:
                    # Simple tag name without type
                    tag, created = EmployeeTag.objects.get_or_create(
                        name=tag_spec,
                        defaults={'tag_type': 'OTHER', 'is_active': True}
                    )
                    tags.append(tag)
            data['tags'] = tags
        
        # Set default status
        data['status'] = default_status
        
        if errors:
            return {'error': f"Row {row_num}: {'; '.join(errors)}"}
        
        return data
    
   

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
        
        # Define default fields for export (ENHANCED with father_name)
        default_fields = [
            'employee_id', 'name', 'email', 'job_title', 'business_function_name',
            'department_name', 'unit_name', 'position_group_name', 'grading_display',
            'status_name', 'line_manager_name', 'start_date', 'contract_duration_display',
            'phone', 'father_name', 'years_of_service'
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
        
        # Field mappings for headers (ENHANCED with father_name)
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
            'father_name': 'Father Name',
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
        
        # Field mappings for headers (ENHANCED with father_name)
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
            'father_name': 'Father Name',
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
    
    # views.py - EmployeeViewSet class-ına bu method-u əlavə edin

    def _process_bulk_employee_data_from_excel(self, df, user):
        """Excel data-sını process et və employee-lar yarat"""
        results = {
            'total_rows': len(df),
            'successful': 0,
            'failed': 0,
            'errors': [],
            'created_employees': []
        }
        
        try:
            # Log the actual columns for debugging
            logger.info(f"Excel columns found: {list(df.columns)}")
            logger.info(f"Excel shape: {df.shape}")
            
            # Convert all columns to string to avoid Series object issues
            df_str = df.astype(str)
            
            # Enhanced column mappings - more flexible matching
            column_mappings = {
                'employee_id': ['Employee ID*', 'Employee ID', 'employee_id'],
                'first_name': ['First Name*', 'First Name', 'first_name'],
                'last_name': ['Last Name*', 'Last Name', 'last_name'],
                'email': ['Email*', 'Email', 'email'],
                'date_of_birth': ['Date of Birth', 'date_of_birth'],
                'gender': ['Gender', 'gender'],
                'father_name': ['Father Name', 'father_name'],
                'phone': ['Phone', 'phone'],
                'address': ['Address', 'address'],
                'emergency_contact': ['Emergency Contact', 'emergency_contact'],
                'business_function': ['Business Function*', 'Business Function', 'business_function'],
                'department': ['Department*', 'Department', 'department'],
                'unit': ['Unit', 'unit'],
                'job_function': ['Job Function*', 'Job Function', 'job_function'],
                'job_title': ['Job Title*', 'Job Title', 'job_title'],
                'position_group': ['Position Group*', 'Position Group', 'position_group'],
                'grading_level': ['Grading Level', 'grading_level'],
                'start_date': ['Start Date*', 'Start Date', 'start_date'],
                'contract_duration': ['Contract Duration*', 'Contract Duration', 'contract_duration'],
                'contract_start_date': ['Contract Start Date', 'contract_start_date'],
                'line_manager_id': ['Line Manager Employee ID', 'Line Manager ID', 'line_manager_id'],
                'is_visible_in_org_chart': ['Is Visible in Org Chart', 'Org Chart Visible'],
                'tags': ['Tag Names (comma separated)', 'Tags', 'tags'],
                'notes': ['Notes', 'notes']
            }
            
            # Find actual column names - exact matching first
            actual_columns = {}
            df_columns = [str(col).strip() for col in df_str.columns]
            
            logger.info(f"Available columns: {df_columns}")
            
            # Map columns with exact matching
            for field, possible_names in column_mappings.items():
                found_column = None
                for possible_name in possible_names:
                    for df_col in df_columns:
                        if df_col.strip() == possible_name.strip():
                            found_column = df_col
                            break
                    if found_column:
                        break
                
                if found_column:
                    actual_columns[field] = found_column
                    logger.info(f"Mapped {field} -> {found_column}")
            
            logger.info(f"Final column mapping: {actual_columns}")
            
            # Check required fields
            required_fields = ['employee_id', 'first_name', 'last_name', 'email', 
                              'business_function', 'department', 'job_function', 
                              'job_title', 'position_group', 'start_date', 'contract_duration']
            
            missing_required = []
            for req_field in required_fields:
                if req_field not in actual_columns:
                    missing_required.append(req_field)
            
            if missing_required:
                error_msg = f"Missing required columns: {', '.join(missing_required)}"
                logger.error(error_msg)
                results['errors'].append(error_msg)
                results['failed'] = len(df_str)
                return results
            
            # Remove sample data row (row with HC001, John, Doe, etc.)
            df_clean = df_str.copy()
            
            # Remove rows where Employee ID is sample data
            employee_id_col = actual_columns['employee_id']
            sample_ids = ['HC001', 'HC002', 'EMP001', 'TEST001']  # Common sample IDs
            
            for sample_id in sample_ids:
                df_clean = df_clean[df_clean[employee_id_col].str.strip() != sample_id]
            
            # Remove rows with sample names
            first_name_col = actual_columns['first_name']
            sample_names = ['John', 'Jane', 'Test', 'Sample']
            for sample_name in sample_names:
                df_clean = df_clean[df_clean[first_name_col].str.strip() != sample_name]
            
            # Remove completely empty rows
            df_clean = df_clean.dropna(how='all')
            
            # Remove rows where employee_id is empty or nan
            df_clean = df_clean[df_clean[employee_id_col].notna()]
            df_clean = df_clean[df_clean[employee_id_col].str.strip() != '']
            df_clean = df_clean[df_clean[employee_id_col].str.strip() != 'nan']
            
            logger.info(f"After cleaning: {len(df_clean)} rows to process")
            
            if df_clean.empty:
                results['errors'].append("No valid data rows found. Please add employee data after removing sample rows.")
                results['failed'] = len(df_str)
                return results
            
            # Update total_rows
            results['total_rows'] = len(df_clean)
            
            # Prepare lookup dictionaries
            business_functions = {}
            for bf in BusinessFunction.objects.filter(is_active=True):
                business_functions[bf.name.lower()] = bf
            
            departments = {}
            for dept in Department.objects.select_related('business_function').filter(is_active=True):
                departments[dept.name.lower()] = dept
            
            job_functions = {}
            for jf in JobFunction.objects.filter(is_active=True):
                job_functions[jf.name.lower()] = jf
            
            position_groups = {}
            for pg in PositionGroup.objects.filter(is_active=True):
                position_groups[pg.get_name_display().lower()] = pg
            
            employee_lookup = {}
            for emp in Employee.objects.all():
                employee_lookup[emp.employee_id] = emp
            
            # Get default status
            default_status = EmployeeStatus.objects.filter(is_default_for_new_employees=True).first()
            if not default_status:
                default_status = EmployeeStatus.objects.filter(name='ONBOARDING').first()
            if not default_status:
                default_status = EmployeeStatus.objects.filter(is_active=True).first()
            
            if not default_status:
                results['errors'].append("No employee status found. Please create default status first.")
                results['failed'] = len(df_clean)
                return results
            
            # Process each row
            with transaction.atomic():
                for index, row in df_clean.iterrows():
                    try:
                        # Extract required fields with safe string conversion
                        def safe_get(col_name, default=''):
                            if col_name in actual_columns:
                                value = row.get(actual_columns[col_name], default)
                                return str(value).strip() if value and str(value).strip().lower() != 'nan' else default
                            return default
                        
                        employee_id = safe_get('employee_id')
                        first_name = safe_get('first_name')
                        last_name = safe_get('last_name')
                        email = safe_get('email')
                        business_function_name = safe_get('business_function')
                        department_name = safe_get('department')
                        job_function_name = safe_get('job_function')
                        job_title = safe_get('job_title')
                        position_group_name = safe_get('position_group')
                        start_date_str = safe_get('start_date')
                        contract_duration = safe_get('contract_duration', 'PERMANENT')
                        
                        logger.info(f"Processing row {index}: {employee_id}, {first_name}, {last_name}")
                        
                        # Validate required fields
                        if not all([employee_id, first_name, last_name, email, business_function_name, 
                                   department_name, job_function_name, job_title, position_group_name, start_date_str]):
                            results['errors'].append(f"Row {index + 2}: Missing required data")
                            results['failed'] += 1
                            continue
                        
                        # Check duplicates
                        if Employee.objects.filter(employee_id=employee_id).exists():
                            results['errors'].append(f"Row {index + 2}: Employee ID {employee_id} already exists")
                            results['failed'] += 1
                            continue
                        
                        if User.objects.filter(email=email).exists():
                            results['errors'].append(f"Row {index + 2}: Email {email} already exists")
                            results['failed'] += 1
                            continue
                        
                        # Validate business function
                        business_function = business_functions.get(business_function_name.lower())
                        if not business_function:
                            results['errors'].append(f"Row {index + 2}: Business Function '{business_function_name}' not found")
                            results['failed'] += 1
                            continue
                        
                        # Validate department
                        department = departments.get(department_name.lower())
                        if not department:
                            results['errors'].append(f"Row {index + 2}: Department '{department_name}' not found")
                            results['failed'] += 1
                            continue
                        
                        # Validate job function
                        job_function = job_functions.get(job_function_name.lower())
                        if not job_function:
                            results['errors'].append(f"Row {index + 2}: Job Function '{job_function_name}' not found")
                            results['failed'] += 1
                            continue
                        
                        # Validate position group
                        position_group = position_groups.get(position_group_name.lower())
                        if not position_group:
                            results['errors'].append(f"Row {index + 2}: Position Group '{position_group_name}' not found")
                            results['failed'] += 1
                            continue
                        
                        # Parse start date
                        try:
                            start_date = pd.to_datetime(start_date_str).date()
                        except:
                            results['errors'].append(f"Row {index + 2}: Invalid start date '{start_date_str}'")
                            results['failed'] += 1
                            continue
                        
                        # Validate contract duration
                        valid_durations = [choice[0] for choice in Employee.contract_duration]
                        if contract_duration not in valid_durations:
                            contract_duration = 'PERMANENT'
                        
                        # Optional fields
                        date_of_birth = None
                        dob_str = safe_get('date_of_birth')
                        if dob_str:
                            try:
                                date_of_birth = pd.to_datetime(dob_str).date()
                            except:
                                pass
                        
                        gender = safe_get('gender').upper()
                        if gender not in ['MALE', 'FEMALE']:
                            gender = None
                        
                        father_name = safe_get('father_name')
                        phone = safe_get('phone')
                        address = safe_get('address')
                        emergency_contact = safe_get('emergency_contact')
                        
                        # Unit (optional)
                        unit = None
                        unit_name = safe_get('unit')
                        if unit_name:
                            unit = Unit.objects.filter(name__iexact=unit_name, department=department).first()
                        
                        # Grading level
                        grading_level = safe_get('grading_level')
                        if not grading_level:
                            grading_level = f"{position_group.grading_shorthand}_M"
                        
                        # Contract start date
                        contract_start_date = start_date
                        csd_str = safe_get('contract_start_date')
                        if csd_str:
                            try:
                                contract_start_date = pd.to_datetime(csd_str).date()
                            except:
                                pass
                        
                        # Line manager
                        line_manager = None
                        line_manager_id = safe_get('line_manager_id')
                        if line_manager_id:
                            line_manager = employee_lookup.get(line_manager_id)
                        
                        # Org chart visibility
                        is_visible_str = safe_get('is_visible_in_org_chart', 'TRUE').upper()
                        is_visible_in_org_chart = is_visible_str in ['TRUE', '1', 'YES']
                        
                        notes = safe_get('notes')
                        
                        # Create user
                        user_obj = User.objects.create_user(
                            username=email,
                            email=email,
                            first_name=first_name,
                            last_name=last_name
                        )
                        
                        # Create employee
                        employee = Employee.objects.create(
                            user=user_obj,
                            employee_id=employee_id,
                            date_of_birth=date_of_birth,
                            gender=gender,
                            father_name=father_name,
                            address=address,
                            phone=phone,
                            emergency_contact=emergency_contact,
                            business_function=business_function,
                            department=department,
                            unit=unit,
                            job_function=job_function,
                            job_title=job_title,
                            position_group=position_group,
                            grading_level=grading_level,
                            start_date=start_date,
                            contract_duration=contract_duration,
                            contract_start_date=contract_start_date,
                            line_manager=line_manager,
                            status=default_status,
                            is_visible_in_org_chart=is_visible_in_org_chart,
                            notes=notes,
                            created_by=user
                        )
                        
                        # Process tags
                        tags_str = safe_get('tags')
                        if tags_str:
                            tags = []
                            for tag_spec in tags_str.split(','):
                                tag_spec = tag_spec.strip()
                                if ':' in tag_spec:
                                    tag_type, tag_name = tag_spec.split(':', 1)
                                    tag_type = tag_type.strip().upper()
                                    tag_name = tag_name.strip()
                                    
                                    tag, created = EmployeeTag.objects.get_or_create(
                                        name=tag_name,
                                        defaults={
                                            'tag_type': tag_type if tag_type in ['LEAVE', 'STATUS', 'SKILL', 'PROJECT', 'PERFORMANCE'] else 'OTHER',
                                            'is_active': True
                                        }
                                    )
                                    tags.append(tag)
                                else:
                                    tag, created = EmployeeTag.objects.get_or_create(
                                        name=tag_spec,
                                        defaults={'tag_type': 'OTHER', 'is_active': True}
                                    )
                                    tags.append(tag)
                            
                            if tags:
                                employee.tags.set(tags)
                        
                        # Log activity
                        EmployeeActivity.objects.create(
                            employee=employee,
                            activity_type='BULK_CREATED',
                            description=f"Employee {employee.full_name} created via bulk upload",
                            performed_by=user,
                            metadata={'bulk_creation': True, 'row_number': index + 2}
                        )
                        
                        results['successful'] += 1
                        results['created_employees'].append({
                            'employee_id': employee.employee_id,
                            'name': employee.full_name,
                            'email': employee.user.email
                        })
                        
                        logger.info(f"Created employee: {employee.employee_id} - {employee.full_name}")
                        
                    except Exception as e:
                        error_msg = f"Row {index + 2}: {str(e)}"
                        results['errors'].append(error_msg)
                        results['failed'] += 1
                        logger.error(f"Error creating employee from row {index + 2}: {e}")
                        logger.error(f"Traceback: {traceback.format_exc()}")
                        continue
            
            logger.info(f"Bulk creation completed: {results['successful']} successful, {results['failed']} failed")
            return results
            
        except Exception as e:
            logger.error(f"Bulk processing failed: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            results['errors'].append(f"Processing failed: {str(e)}")
            results['failed'] = results['total_rows']
            return results
        
    @swagger_auto_schema(
        method='post',
        operation_description="Add tag to single employee",
        request_body=SingleEmployeeTagUpdateSerializer,
        responses={200: "Tag added successfully", 400: "Bad request"}
    )
    @action(detail=False, methods=['post'], url_path='add-tag')
    def add_tag_to_employee(self, request):
        """Add tag to single employee using employee ID"""
        serializer = SingleEmployeeTagUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        employee_id = serializer.validated_data['employee_id']
        tag_id = serializer.validated_data['tag_id']
        
        try:
            employee = Employee.objects.get(id=employee_id)
            tag = EmployeeTag.objects.get(id=tag_id)
            
            if employee.add_tag(tag, request.user):
                return Response({
                    'success': True,
                    'message': f'Tag "{tag.name}" added to {employee.full_name}',
                    'employee_id': employee.id,
                    'employee_name': employee.full_name,
                    'tag_name': tag.name
                })
            else:
                return Response({
                    'success': False,
                    'message': f'Tag "{tag.name}" already exists on {employee.full_name}',
                    'employee_id': employee.id,
                    'employee_name': employee.full_name,
                    'tag_name': tag.name
                })
        except (Employee.DoesNotExist, EmployeeTag.DoesNotExist) as e:
            return Response({'error': str(e)}, status=status.HTTP_404_NOT_FOUND)
    
    @swagger_auto_schema(
        method='post',
        operation_description="Remove tag from single employee",
        request_body=SingleEmployeeTagUpdateSerializer,
        responses={200: "Tag removed successfully", 400: "Bad request"}
    )
    @action(detail=False, methods=['post'], url_path='remove-tag')
    def remove_tag_from_employee(self, request):
        """Remove tag from single employee using employee ID"""
        serializer = SingleEmployeeTagUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        employee_id = serializer.validated_data['employee_id']
        tag_id = serializer.validated_data['tag_id']
        
        try:
            employee = Employee.objects.get(id=employee_id)
            tag = EmployeeTag.objects.get(id=tag_id)
            
            if employee.remove_tag(tag, request.user):
                return Response({
                    'success': True,
                    'message': f'Tag "{tag.name}" removed from {employee.full_name}',
                    'employee_id': employee.id,
                    'employee_name': employee.full_name,
                    'tag_name': tag.name
                })
            else:
                return Response({
                    'success': False,
                    'message': f'Tag "{tag.name}" was not found on {employee.full_name}',
                    'employee_id': employee.id,
                    'employee_name': employee.full_name,
                    'tag_name': tag.name
                })
        except (Employee.DoesNotExist, EmployeeTag.DoesNotExist) as e:
            return Response({'error': str(e)}, status=status.HTTP_404_NOT_FOUND)
    
    @swagger_auto_schema(
        method='post',
        operation_description="Add tag to multiple employees",
        request_body=BulkEmployeeTagUpdateSerializer,
        responses={200: "Tags added successfully", 400: "Bad request"}
    )
    @action(detail=False, methods=['post'], url_path='bulk-add-tag')
    def bulk_add_tag(self, request):
        """Add tag to multiple employees using employee IDs"""
        serializer = BulkEmployeeTagUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        employee_ids = serializer.validated_data['employee_ids']
        tag_id = serializer.validated_data['tag_id']
        
        try:
            tag = EmployeeTag.objects.get(id=tag_id)
            employees = Employee.objects.filter(id__in=employee_ids)
            
            added_count = 0
            already_had_count = 0
            results = []
            
            with transaction.atomic():
                for employee in employees:
                    if employee.add_tag(tag, request.user):
                        added_count += 1
                        results.append({
                            'employee_id': employee.id,
                            'employee_name': employee.full_name,
                            'status': 'added'
                        })
                    else:
                        already_had_count += 1
                        results.append({
                            'employee_id': employee.id,
                            'employee_name': employee.full_name,
                            'status': 'already_had'
                        })
            
            return Response({
                'success': True,
                'message': f'Tag "{tag.name}" processed for {len(employee_ids)} employees',
                'tag_name': tag.name,
                'total_employees': len(employee_ids),
                'added_count': added_count,
                'already_had_count': already_had_count,
                'results': results
            })
        except EmployeeTag.DoesNotExist:
            return Response({'error': 'Tag not found'}, status=status.HTTP_404_NOT_FOUND)
    
    @swagger_auto_schema(
        method='post',
        operation_description="Remove tag from multiple employees",
        request_body=BulkEmployeeTagUpdateSerializer,
        responses={200: "Tags removed successfully", 400: "Bad request"}
    )
    @action(detail=False, methods=['post'], url_path='bulk-remove-tag')
    def bulk_remove_tag(self, request):
        """Remove tag from multiple employees using employee IDs"""
        serializer = BulkEmployeeTagUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        employee_ids = serializer.validated_data['employee_ids']
        tag_id = serializer.validated_data['tag_id']
        
        try:
            tag = EmployeeTag.objects.get(id=tag_id)
            employees = Employee.objects.filter(id__in=employee_ids)
            
            removed_count = 0
            didnt_have_count = 0
            results = []
            
            with transaction.atomic():
                for employee in employees:
                    if employee.remove_tag(tag, request.user):
                        removed_count += 1
                        results.append({
                            'employee_id': employee.id,
                            'employee_name': employee.full_name,
                            'status': 'removed'
                        })
                    else:
                        didnt_have_count += 1
                        results.append({
                            'employee_id': employee.id,
                            'employee_name': employee.full_name,
                            'status': 'didnt_have'
                        })
            
            return Response({
                'success': True,
                'message': f'Tag "{tag.name}" removal processed for {len(employee_ids)} employees',
                'tag_name': tag.name,
                'total_employees': len(employee_ids),
                'removed_count': removed_count,
                'didnt_have_count': didnt_have_count,
                'results': results
            })
        except EmployeeTag.DoesNotExist:
            return Response({'error': 'Tag not found'}, status=status.HTTP_404_NOT_FOUND)
    
    # ENHANCED LINE MANAGER MANAGEMENT
    @swagger_auto_schema(
        method='post',
        operation_description="Assign line manager to single employee",
        request_body=SingleLineManagerAssignmentSerializer,
        responses={200: "Line manager assigned successfully", 400: "Bad request"}
    )
    @action(detail=False, methods=['post'], url_path='assign-line-manager')
    def assign_line_manager(self, request):
        """Assign line manager to single employee"""
        serializer = SingleLineManagerAssignmentSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        employee_id = serializer.validated_data['employee_id']
        line_manager_id = serializer.validated_data['line_manager_id']
        
        try:
            employee = Employee.objects.get(id=employee_id)
            line_manager = Employee.objects.get(id=line_manager_id) if line_manager_id else None
            
            old_manager_name = employee.line_manager.full_name if employee.line_manager else 'None'
            new_manager_name = line_manager.full_name if line_manager else 'None'
            
            employee.change_line_manager(line_manager, request.user)
            
            return Response({
                'success': True,
                'message': f'Line manager updated for {employee.full_name}',
                'employee_id': employee.id,
                'employee_name': employee.full_name,
                'old_line_manager': old_manager_name,
                'new_line_manager': new_manager_name
            })
        except Employee.DoesNotExist:
            return Response({'error': 'Employee or line manager not found'}, status=status.HTTP_404_NOT_FOUND)
    
    @swagger_auto_schema(
        method='post',
        operation_description="Assign line manager to multiple employees",
        request_body=BulkLineManagerAssignmentSerializer,
        responses={200: "Line managers assigned successfully", 400: "Bad request"}
    )
    @action(detail=False, methods=['post'], url_path='bulk-assign-line-manager')
    def bulk_assign_line_manager(self, request):
        """Assign line manager to multiple employees"""
        serializer = BulkLineManagerAssignmentSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        employee_ids = serializer.validated_data['employee_ids']
        line_manager_id = serializer.validated_data['line_manager_id']
        
        try:
            line_manager = Employee.objects.get(id=line_manager_id) if line_manager_id else None
            employees = Employee.objects.filter(id__in=employee_ids)
            
            updated_count = 0
            results = []
            
            with transaction.atomic():
                for employee in employees:
                    old_manager_name = employee.line_manager.full_name if employee.line_manager else 'None'
                    employee.change_line_manager(line_manager, request.user)
                    updated_count += 1
                    
                    results.append({
                        'employee_id': employee.id,
                        'employee_name': employee.full_name,
                        'old_line_manager': old_manager_name,
                        'new_line_manager': line_manager.full_name if line_manager else 'None'
                    })
            
            return Response({
                'success': True,
                'message': f'Line manager updated for {updated_count} employees',
                'new_line_manager': line_manager.full_name if line_manager else 'None',
                'total_employees': len(employee_ids),
                'updated_count': updated_count,
                'results': results
            })
        except Employee.DoesNotExist:
            return Response({'error': 'Line manager not found'}, status=status.HTTP_404_NOT_FOUND)
    
    @swagger_auto_schema(
        method='post',
        operation_description="Update contract for single employee",
        request_body=ContractExtensionSerializer,
        responses={200: "Contract updated successfully", 400: "Bad request"}
    )
    @action(detail=False, methods=['post'], url_path='extend-contract')
    def extend_employee_contract(self, request):
        """Update contract for single employee with new type and start date"""
        serializer = ContractExtensionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        employee_id = serializer.validated_data['employee_id']
        new_contract_type = serializer.validated_data['new_contract_type']
        new_start_date = serializer.validated_data['new_start_date']
        reason = serializer.validated_data.get('reason', '')
        
        try:
            employee = Employee.objects.get(id=employee_id)
            
            # Store old values
            old_contract_type = employee.contract_duration
            old_start_date = employee.contract_start_date
            old_end_date = employee.contract_end_date
            
            # Update contract
            employee.contract_duration = new_contract_type
            employee.contract_start_date = new_start_date
            employee.contract_extensions += 1
            employee.last_extension_date = timezone.now().date()
            employee.renewal_status = 'APPROVED'
            
            if request.user:
                employee.updated_by = request.user
            
            # Save will auto-calculate new end date
            employee.save()
            
            # Log detailed activity
            EmployeeActivity.objects.create(
                employee=employee,
                activity_type='CONTRACT_UPDATED',
                description=f"Contract updated: {old_contract_type} → {new_contract_type}. New start: {new_start_date}. Reason: {reason}",
                performed_by=request.user,
                metadata={
                    'old_contract_type': old_contract_type,
                    'new_contract_type': new_contract_type,
                    'old_start_date': str(old_start_date) if old_start_date else None,
                    'new_start_date': str(new_start_date),
                    'old_end_date': str(old_end_date) if old_end_date else None,
                    'new_end_date': str(employee.contract_end_date) if employee.contract_end_date else None,
                    'reason': reason,
                    'extension_count': employee.contract_extensions
                }
            )
            
            return Response({
                'success': True,
                'message': f'Contract updated successfully for {employee.full_name}',
                'employee_id': employee.id,
                'employee_name': employee.full_name,
                'old_contract_type': old_contract_type,
                'new_contract_type': new_contract_type,
                'old_start_date': old_start_date,
                'new_start_date': new_start_date,
                'old_end_date': old_end_date,
                'new_end_date': employee.contract_end_date,
                'extensions_count': employee.contract_extensions
            })
                
        except Employee.DoesNotExist:
            return Response({'error': 'Employee not found'}, status=status.HTTP_404_NOT_FOUND)
    
    @swagger_auto_schema(
        method='post',
        operation_description="Update contracts for multiple employees",
        request_body=BulkContractExtensionSerializer,
        responses={200: "Contracts updated successfully", 400: "Bad request"}
    )
    @action(detail=False, methods=['post'], url_path='bulk-extend-contracts')
    def bulk_extend_contracts(self, request):
        """Update contracts for multiple employees"""
        serializer = BulkContractExtensionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        employee_ids = serializer.validated_data['employee_ids']
        new_contract_type = serializer.validated_data['new_contract_type']
        new_start_date = serializer.validated_data['new_start_date']
        reason = serializer.validated_data.get('reason', '')
        
        try:
            employees = Employee.objects.filter(id__in=employee_ids)
            
            updated_count = 0
            failed_count = 0
            results = []
            
            with transaction.atomic():
                for employee in employees:
                    try:
                        old_contract_type = employee.contract_duration
                        old_start_date = employee.contract_start_date
                        old_end_date = employee.contract_end_date
                        
                        # Update contract
                        employee.contract_duration = new_contract_type
                        employee.contract_start_date = new_start_date
                        employee.contract_extensions += 1
                        employee.last_extension_date = timezone.now().date()
                        employee.renewal_status = 'APPROVED'
                        
                        if request.user:
                            employee.updated_by = request.user
                        
                        # Save will auto-calculate new end date
                        employee.save()
                        
                        # Log detailed activity
                        EmployeeActivity.objects.create(
                            employee=employee,
                            activity_type='CONTRACT_UPDATED',
                            description=f"Bulk contract update: {old_contract_type} → {new_contract_type}. New start: {new_start_date}. Reason: {reason}",
                            performed_by=request.user,
                            metadata={
                                'bulk_update': True,
                                'old_contract_type': old_contract_type,
                                'new_contract_type': new_contract_type,
                                'old_start_date': str(old_start_date) if old_start_date else None,
                                'new_start_date': str(new_start_date),
                                'old_end_date': str(old_end_date) if old_end_date else None,
                                'new_end_date': str(employee.contract_end_date) if employee.contract_end_date else None,
                                'reason': reason,
                                'extension_count': employee.contract_extensions
                            }
                        )
                        
                        updated_count += 1
                        results.append({
                            'employee_id': employee.id,
                            'employee_name': employee.full_name,
                            'status': 'success',
                            'old_contract_type': old_contract_type,
                            'new_contract_type': new_contract_type,
                            'old_end_date': old_end_date,
                            'new_end_date': employee.contract_end_date,
                            'extensions_count': employee.contract_extensions
                        })
                    except Exception as e:
                        failed_count += 1
                        results.append({
                            'employee_id': employee.id,
                            'employee_name': employee.full_name,
                            'status': 'failed',
                            'error': str(e)
                        })
            
            return Response({
                'success': True,
                'message': f'Contract update completed: {updated_count} updated, {failed_count} failed',
                'total_employees': len(employee_ids),
                'updated_count': updated_count,
                'failed_count': failed_count,
                'new_contract_type': new_contract_type,
                'new_start_date': new_start_date,
                'reason': reason,
                'results': results
            })
            
        except Exception as e:
            return Response({'error': f'Bulk contract update failed: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    # ENHANCED SOFT DELETE/RESTORE (Simplified as requested)
    @swagger_auto_schema(
        method='post',
        operation_description="Soft delete multiple employees",
        request_body=BulkSoftDeleteSerializer,
        responses={200: "Employees soft deleted successfully", 400: "Bad request"}
    )
    @action(detail=False, methods=['post'], url_path='soft-delete')
    def bulk_soft_delete(self, request):
        """Soft delete multiple employees using employee IDs"""
        serializer = BulkSoftDeleteSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        employee_ids = serializer.validated_data['employee_ids']
        
        try:
            with transaction.atomic():
                employees = Employee.objects.filter(id__in=employee_ids, is_deleted=False)
                deleted_count = 0
                results = []
                
                for employee in employees:
                    employee.soft_delete(user=request.user)
                    deleted_count += 1
                    
                    # Log activity
                    EmployeeActivity.objects.create(
                        employee=employee,
                        activity_type='SOFT_DELETED',
                        description=f"Employee {employee.full_name} was soft deleted (bulk operation)",
                        performed_by=request.user,
                        metadata={'bulk_delete': True}
                    )
                    
                    results.append({
                        'employee_id': employee.id,
                        'employee_name': employee.full_name,
                        'status': 'deleted'
                    })
                
                return Response({
                    'success': True,
                    'message': f'Successfully soft deleted {deleted_count} employees',
                    'total_requested': len(employee_ids),
                    'deleted_count': deleted_count,
                    'results': results
                })
        except Exception as e:
            return Response({'error': f'Soft delete failed: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @swagger_auto_schema(
        method='post',
        operation_description="Restore multiple soft-deleted employees",
        request_body=BulkRestoreSerializer,
        responses={200: "Employees restored successfully", 400: "Bad request"}
    )
    @action(detail=False, methods=['post'], url_path='restore')
    def bulk_restore(self, request):
        """Restore multiple soft-deleted employees using employee IDs"""
        serializer = BulkRestoreSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        employee_ids = serializer.validated_data['employee_ids']
        
        try:
            with transaction.atomic():
                employees = Employee.all_objects.filter(id__in=employee_ids, is_deleted=True)
                restored_count = 0
                results = []
                
                for employee in employees:
                    employee.restore()
                    restored_count += 1
                    
                    # Log activity
                    EmployeeActivity.objects.create(
                        employee=employee,
                        activity_type='RESTORED',
                        description=f"Employee {employee.full_name} was restored (bulk operation)",
                        performed_by=request.user,
                        metadata={'bulk_restore': True}
                    )
                    
                    results.append({
                        'employee_id': employee.id,
                        'employee_name': employee.full_name,
                        'status': 'restored'
                    })
                
                return Response({
                    'success': True,
                    'message': f'Successfully restored {restored_count} employees',
                    'total_requested': len(employee_ids),
                    'restored_count': restored_count,
                    'results': results
                })
        except Exception as e:
            return Response({'error': f'Restore failed: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    # STATUS PREVIEW EXPLANATION
    @swagger_auto_schema(
        method='post',
        operation_description="Preview status updates for employees (shows what status changes would happen)",
        request_body=StatusPreviewRequestSerializer,
        responses={200: "Status preview generated successfully", 400: "Bad request"}
    )
    @action(detail=False, methods=['post'], url_path='preview-status-updates')
    def preview_status_updates(self, request):
        """
        Preview what status updates would happen for selected employees.
        
        This endpoint shows you what automatic status changes would occur
        based on each employee's contract configuration and how long they've been working.
        
        For example:
        - An employee who started 10 days ago with 7-day onboarding should move from ONBOARDING to PROBATION
        - An employee who completed probation should move to ACTIVE
        - An employee whose contract expired should move to INACTIVE
        
        This is useful to see what changes would happen before actually applying them.
        """
        serializer = StatusPreviewRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        employee_ids = serializer.validated_data.get('employee_ids', [])
        
        # Get employees to check
        if employee_ids:
            employees = Employee.objects.filter(id__in=employee_ids, is_deleted=False)
        else:
            employees = Employee.objects.filter(is_deleted=False)[:100]  # Limit to prevent timeout
        
        updates_needed = []
        current_status = []
        contract_expired = []
        errors = []
        
        for employee in employees:
            try:
                preview = employee.get_status_preview()
                
                employee_info = {
                    'employee_id': employee.id,
                    'employee_hc_number': employee.employee_id,
                    'employee_name': employee.full_name,
                    'current_status': preview['current_status'],
                    'required_status': preview['required_status'],
                    'needs_update': preview['needs_update'],
                    'reason': preview['reason'],
                    'contract_type': preview['contract_type'],
                    'days_since_start': preview['days_since_start'],
                    'contract_end_date': preview.get('contract_end_date'),
                    'department': employee.department.name,
                    'line_manager': employee.line_manager.full_name if employee.line_manager else None
                }
                
                if preview['needs_update']:
                    if 'contract ended' in preview['reason'].lower():
                        contract_expired.append(employee_info)
                    else:
                        updates_needed.append(employee_info)
                else:
                    current_status.append(employee_info)
                    
            except Exception as e:
                errors.append({
                    'employee_id': employee.id,
                    'employee_hc_number': employee.employee_id,
                    'employee_name': employee.full_name,
                    'error': str(e)
                })
        
        # Group by transition type for easier understanding
        transition_summary = {}
        for emp in updates_needed + contract_expired:
            transition = f"{emp['current_status']} → {emp['required_status']}"
            if transition not in transition_summary:
                transition_summary[transition] = []
            transition_summary[transition].append(emp)
        
        return Response({
            'success': True,
            'message': f'Status preview completed for {len(employees)} employees',
            'summary': {
                'total_checked': len(employees),
                'updates_needed': len(updates_needed),
                'current_status': len(current_status),
                'contract_expired': len(contract_expired),
                'errors': len(errors)
            },
            'transition_summary': {
                transition: len(employees) 
                for transition, employees in transition_summary.items()
            },
            'details': {
                'updates_needed': updates_needed,
                'contract_expired': contract_expired,
                'current_status': current_status[:10],  # Limit to first 10
                'errors': errors
            },
            'explanation': {
                'updates_needed': 'Employees whose status should change based on contract rules',
                'contract_expired': 'Employees whose contracts have ended and should be inactive',
                'current_status': 'Employees whose status is already correct',
                'transition_types': {
                    'ONBOARDING → PROBATION': 'Employees who completed onboarding period',
                    'PROBATION → ACTIVE': 'Employees who completed probation period',
                    'ACTIVE → INACTIVE': 'Employees whose contracts have expired'
                }
            }
        })
    
    # CONTRACT EXPIRY NOTIFICATIONS
    @action(detail=False, methods=['get'], url_path='contract-expiry-alerts')
    def get_contract_expiry_alerts(self, request):
        """Get employees whose contracts are expiring soon with notification capabilities"""
        days = int(request.query_params.get('days', 30))
        
        from .status_management import EmployeeStatusManager
        expiry_analysis = EmployeeStatusManager.get_contract_expiry_analysis(days)
        
        # Group employees by urgency
        urgent_employees = [emp for emp in expiry_analysis['employees'] if emp['urgency'] in ['critical', 'high']]
        
        return Response({
            'success': True,
            'days_ahead': days,
            'total_expiring': expiry_analysis['total_expiring'],
            'urgency_breakdown': expiry_analysis['by_urgency'],
            'department_breakdown': expiry_analysis['by_department'],
            'line_manager_breakdown': expiry_analysis['by_line_manager'],
            'urgent_employees': urgent_employees,
            'all_employees': expiry_analysis['employees'],
            'notification_recommendations': {
                'critical_contracts': [emp for emp in expiry_analysis['employees'] if emp['urgency'] == 'critical'],
                'renewal_decisions_needed': [emp for emp in expiry_analysis['employees'] if emp['renewal_status'] == 'PENDING'],
                'manager_notifications': list(set([emp['line_manager'] for emp in expiry_analysis['employees'] if emp['line_manager']]))
            }
        })
    
   
  

    @action(detail=False, methods=['get'])
    def contracts_expiring_soon(self, request):
        """Get employees whose contracts are expiring soon"""
        days = int(request.query_params.get('days', 30))
        
        expiring_employees = ContractStatusManager.get_contract_expiring_soon(days)
        
        serializer = EmployeeListSerializer(expiring_employees, many=True)
        
        return Response({
            'days': days,
            'count': expiring_employees.count(),
            'employees': serializer.data
        })
    
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
        
        # Contract analysis - FIXED
        contract_stats = {}
        # Get all unique contract types from employees
        contract_types = queryset.values_list('contract_duration', flat=True).distinct()
        for contract_type in contract_types:
            if contract_type:
                count = queryset.filter(contract_duration=contract_type).count()
                if count > 0:
                    try:
                        config = ContractTypeConfig.objects.get(contract_type=contract_type, is_active=True)
                        display_name = config.display_name
                    except ContractTypeConfig.DoesNotExist:
                        display_name = contract_type.replace('_', ' ').title()
                    contract_stats[display_name] = count
        
        # Recent activity
        recent_hires = queryset.filter(
            start_date__gte=date.today() - timedelta(days=30)
        ).count()
        
        upcoming_contract_endings = queryset.filter(
            contract_end_date__lte=date.today() + timedelta(days=30),
            contract_end_date__gte=date.today()
        ).count()
        
        # Status update analysis
        try:
            from .status_management import EmployeeStatusManager
            employees_needing_updates = EmployeeStatusManager.get_employees_needing_update()
            status_update_stats = {
                'employees_needing_updates': len(employees_needing_updates),
                'status_transitions': {}
            }
            
            for update_info in employees_needing_updates:
                transition = f"{update_info['current_status']} → {update_info['required_status']}"
                status_update_stats['status_transitions'][transition] = status_update_stats['status_transitions'].get(transition, 0) + 1
        except Exception as e:
            status_update_stats = {
                'employees_needing_updates': 0,
                'status_transitions': {},
                'error': str(e)
            }
        
        return Response({
            'total_employees': total_employees,
            'active_employees': active_employees,
            'inactive_employees': total_employees - active_employees,
            'by_status': status_stats,
            'by_business_function': function_stats,
            'by_position_group': position_stats,
            'by_contract_duration': contract_stats,
            'recent_hires_30_days': recent_hires,
            'upcoming_contract_endings_30_days': upcoming_contract_endings,
            'status_update_analysis': status_update_stats
        })
   
    @action(detail=True, methods=['get'])
    def activities(self, request, pk=None):
        """Get employee activity history"""
        employee = self.get_object()
        activities = employee.activities.all()[:50]  # Last 50 activities
        serializer = EmployeeActivitySerializer(activities, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def status_preview(self, request, pk=None):
        """Get status preview for individual employee"""
        employee = self.get_object()
        preview = employee.get_status_preview()
        
        return Response({
            'employee_id': employee.employee_id,
            'employee_name': employee.full_name,
            'preview': preview
        })
    
    @action(detail=True, methods=['get'])
    def direct_reports(self, request, pk=None):
        """Get direct reports for an employee (NEW)"""
        employee = self.get_object()
        reports = employee.direct_reports.filter(
            status__affects_headcount=True,
            is_deleted=False
        ).select_related('status', 'position_group', 'department')
        
        serializer = EmployeeListSerializer(reports, many=True)
        return Response({
            'manager': {
                'id': employee.id,
                'employee_id': employee.employee_id,
                'name': employee.full_name,
                'job_title': employee.job_title
            },
            'direct_reports_count': reports.count(),
            'direct_reports': serializer.data
        })
    
    @action(detail=False, methods=['get'])
    def organizational_hierarchy(self, request):
        """Get organizational hierarchy data (NEW)"""
        # Get top-level managers (no line manager)
        top_managers = Employee.objects.filter(
            line_manager__isnull=True,
            status__affects_headcount=True,
            is_deleted=False
        ).select_related('position_group', 'department', 'business_function').order_by('position_group__hierarchy_level')
        
        hierarchy_data = []
        for manager in top_managers:
            manager_data = {
                'employee': EmployeeListSerializer(manager).data,
                'direct_reports_count': manager.get_direct_reports_count(),
                'hierarchy_level': 0
            }
            hierarchy_data.append(manager_data)
        
        return Response({
            'top_level_managers': len(hierarchy_data),
            'hierarchy': hierarchy_data
        })



class BulkEmployeeUploadViewSet(viewsets.ViewSet):
    """Ayrı ViewSet yalnız file upload üçün"""
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]  # Yalnız file upload
    
    @swagger_auto_schema(
        operation_description="Bulk create employees from uploaded Excel file",
        manual_parameters=[
            openapi.Parameter(
                'file',
                openapi.IN_FORM,
                description='Excel file (.xlsx, .xls) containing employee data',
                type=openapi.TYPE_FILE,
                required=True
            )
        ],
        consumes=['multipart/form-data'],
        responses={
            200: openapi.Response(
                description="File processed successfully",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'message': openapi.Schema(type=openapi.TYPE_STRING),
                        'total_rows': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'successful': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'failed': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'errors': openapi.Schema(
                            type=openapi.TYPE_ARRAY, 
                            items=openapi.Schema(type=openapi.TYPE_STRING)
                        ),
                        'created_employees': openapi.Schema(
                            type=openapi.TYPE_ARRAY,
                            items=openapi.Schema(
                                type=openapi.TYPE_OBJECT,
                                properties={
                                    'employee_id': openapi.Schema(type=openapi.TYPE_STRING),
                                    'name': openapi.Schema(type=openapi.TYPE_STRING),
                                    'email': openapi.Schema(type=openapi.TYPE_STRING)
                                }
                            )
                        ),
                        'filename': openapi.Schema(type=openapi.TYPE_STRING)
                    }
                )
            ),
            400: openapi.Response(
                description="Bad request - file validation error",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'error': openapi.Schema(type=openapi.TYPE_STRING)
                    }
                )
            )
        }
    )
    def create(self, request):
        """Bulk create employees from uploaded Excel file"""
        
        try:
            # Log incoming request
            logger.info(f"Bulk upload request received from user: {request.user}")
            logger.info(f"Request FILES: {list(request.FILES.keys())}")
            logger.info(f"Request data: {request.data}")
            
            # Check if file exists
            if 'file' not in request.FILES:
                logger.warning("No file in request.FILES")
                return Response(
                    {'error': 'No file uploaded. Please select an Excel file.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            file = request.FILES['file']
            logger.info(f"File received: {file.name}, size: {file.size}")
            
            # Validate file format
            if not file.name.endswith(('.xlsx', '.xls')):
                logger.warning(f"Invalid file format: {file.name}")
                return Response(
                    {'error': 'Invalid file format. Please upload Excel file (.xlsx or .xls)'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Validate file size (max 10MB)
            if file.size > 10 * 1024 * 1024:
                logger.warning(f"File too large: {file.size} bytes")
                return Response(
                    {'error': 'File too large. Maximum size is 10MB'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Read Excel file with better error handling
            try:
                # Try multiple engines
                try:
                    df = pd.read_excel(file, sheet_name=0, engine='openpyxl')
                except:
                    try:
                        df = pd.read_excel(file, sheet_name=0, engine='xlrd')
                    except:
                        df = pd.read_excel(file, sheet_name=0)
                
                logger.info(f"Excel file read successfully. Shape: {df.shape}")
                logger.info(f"Columns: {list(df.columns)}")
                
            except Exception as e:
                logger.error(f"Failed to read Excel file: {str(e)}")
                return Response(
                    {'error': f'Failed to read Excel file: {str(e)}. Please check file format and content.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Remove completely empty rows
            df = df.dropna(how='all')
            
            # Check if file has data
            if df.empty:
                logger.warning("Excel file is empty after removing empty rows")
                return Response(
                    {'error': 'Excel file is empty or has no valid data'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            logger.info(f"Processing Excel file '{file.name}' with {len(df)} rows")
            
            # Process the data - call EmployeeViewSet method
            employee_viewset = EmployeeViewSet()
            
            # Make sure the viewset has the method
            if not hasattr(employee_viewset, '_process_bulk_employee_data_from_excel'):
                logger.error("EmployeeViewSet missing _process_bulk_employee_data_from_excel method")
                return Response(
                    {'error': 'Server configuration error. Please contact administrator.'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            result = employee_viewset._process_bulk_employee_data_from_excel(df, request.user)
            
            logger.info(f"Bulk upload completed. Success: {result['successful']}, Failed: {result['failed']}")
            
            return Response({
                'message': f'File processed successfully. {result["successful"]} employees created, {result["failed"]} failed.',
                'total_rows': result['total_rows'],
                'successful': result['successful'],
                'failed': result['failed'],
                'errors': result['errors'],
                'created_employees': result['created_employees'],
                'filename': file.name
            })
            
        except Exception as e:
            logger.error(f"Bulk employee creation failed for file: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return Response(
                {'error': f'Failed to process request: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @swagger_auto_schema(
        operation_description="Download Excel template for bulk employee creation",
        responses={
            200: openapi.Response(
                description="Excel template file",
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
        }
    )
    @action(detail=False, methods=['get'])
    def download_template(self, request):
        """Download Excel template for bulk employee creation"""
        try:
            logger.info(f"Template download request from user: {request.user}")
            
            # Call EmployeeViewSet template method
            employee_viewset = EmployeeViewSet()
            
            # Make sure the method exists
            if not hasattr(employee_viewset, '_generate_bulk_template'):
                logger.error("EmployeeViewSet missing _generate_bulk_template method")
                return Response(
                    {'error': 'Template generation not available. Please contact administrator.'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            response = employee_viewset._generate_bulk_template()
            logger.info("Template generated successfully")
            return response
            
        except Exception as e:
            logger.error(f"Template generation failed: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return Response(
                {'error': f'Failed to generate template: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )    
class EmployeeGradingViewSet(viewsets.ViewSet):
    """ViewSet for employee grading integration"""
    permission_classes = [IsAuthenticated]
    
    def list(self, request):
        """Get employees with grading information"""
        employees = Employee.objects.select_related(
            'position_group'
        ).filter(status__affects_headcount=True)
        
        serializer = EmployeeGradingListSerializer(employees, many=True)
        return Response({
            'count': employees.count(),
            'employees': serializer.data
        })
        
    @swagger_auto_schema(
        method='post',
        operation_description="Bulk update employee grades and grading levels",
        request_body=BulkEmployeeGradingUpdateSerializer,
        responses={
            200: openapi.Response(
                description="Successfully updated grades",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'message': openapi.Schema(type=openapi.TYPE_STRING),
                        'updated_count': openapi.Schema(type=openapi.TYPE_INTEGER)
                    }
                )
            ),
            400: openapi.Response(
                description="Bad request - validation errors",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'error': openapi.Schema(type=openapi.TYPE_STRING)
                    }
                )
            )
        }
    )
    
    @action(detail=False, methods=['post'])
    def bulk_update_grades(self, request):
        """Bulk update employee grades"""
        serializer = BulkEmployeeGradingUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        updates = serializer.validated_data['updates']
        
        if not updates:
            return Response(
                {'error': 'updates list is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            with transaction.atomic():
                updated_count = 0
                
                for update in updates:
                    employee_id = update['employee_id']
                    grading_level = update.get('grading_level')
                    
                    try:
                        employee = Employee.objects.get(id=employee_id)
                        
                        changes = []
                        if grading_level and employee.grading_level != grading_level:
                            old_level = employee.grading_level
                            employee.grading_level = grading_level
                            changes.append(f"Grading Level: {old_level} → {grading_level}")
                        
                        if changes:
                            employee.save()
                            updated_count += 1
                            
                            # Log activity
                            EmployeeActivity.objects.create(
                                employee=employee,
                                activity_type='GRADE_CHANGED',
                                description=f"Grading updated: {'; '.join(changes)}",
                                performed_by=request.user,
                                metadata={'changes': changes}
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

    
    

# Replace the ContractStatusManagementViewSet with this corrected version:
class ContractStatusManagementViewSet(viewsets.ViewSet):
    """ViewSet for contract status management operations"""
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def employees_needing_updates(self, request):
        """Get employees whose status needs to be updated"""
        try:
            needing_updates = EmployeeStatusManager.get_employees_needing_update()
            
            # Convert to serializable format
            employees_data = []
            for employee_info in needing_updates:
                employee = employee_info['employee']
                employees_data.append({
                    'employee_id': employee.employee_id,
                    'employee_name': employee.full_name,
                    'current_status': employee_info['current_status'],
                    'required_status': employee_info['required_status'],
                    'reason': employee_info['reason'],
                    'contract_type': employee.contract_duration,
                    'days_since_start': (date.today() - employee.start_date).days,
                    'department': employee.department.name,
                    'business_function': employee.business_function.name,
                    'line_manager': employee.line_manager.full_name if employee.line_manager else None
                })
            
            return Response({
                'count': len(employees_data),
                'employees': employees_data
            })
            
        except Exception as e:
            logger.error(f"Error getting employees needing updates: {str(e)}")
            return Response(
                {'error': f'Failed to get employees needing updates: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
 
   
    @action(detail=False, methods=['get'])
    def status_analysis(self, request):
        """Get comprehensive status analysis"""
        try:
            analytics = EmployeeStatusManager.get_status_transition_analytics()
            
            return Response(analytics)
            
        except Exception as e:
            logger.error(f"Error getting status analysis: {str(e)}")
            return Response(
                {'error': f'Failed to get status analysis: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
  
  
   
# NEW: Enhanced Employee Analytics ViewSet
class EmployeeAnalyticsViewSet(viewsets.ViewSet):
    """ViewSet for detailed employee analytics and reporting"""
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def demographic_analysis(self, request):
        """Get demographic analysis of employees"""
        active_employees = Employee.objects.filter(
            status__affects_headcount=True,
            is_deleted=False
        )
        
        # Gender distribution
        gender_stats = {}
        for gender_choice in Employee.GENDER_CHOICES:
            count = active_employees.filter(gender=gender_choice[0]).count()
            gender_stats[gender_choice[1]] = count
        
        # Age distribution (approximate)
        from datetime import date
        import datetime
        
        age_groups = {
            '20-25': 0,
            '26-30': 0,
            '31-35': 0,
            '36-40': 0,
            '41-45': 0,
            '46-50': 0,
            '50+': 0,
            'Unknown': 0
        }
        
        for employee in active_employees:
            if employee.date_of_birth:
                age = (date.today() - employee.date_of_birth).days // 365
                if 20 <= age <= 25:
                    age_groups['20-25'] += 1
                elif 26 <= age <= 30:
                    age_groups['26-30'] += 1
                elif 31 <= age <= 35:
                    age_groups['31-35'] += 1
                elif 36 <= age <= 40:
                    age_groups['36-40'] += 1
                elif 41 <= age <= 45:
                    age_groups['41-45'] += 1
                elif 46 <= age <= 50:
                    age_groups['46-50'] += 1
                elif age > 50:
                    age_groups['50+'] += 1
            else:
                age_groups['Unknown'] += 1
        
        # Years of service distribution
        service_groups = {
            '0-1 year': 0,
            '1-3 years': 0,
            '3-5 years': 0,
            '5-10 years': 0,
            '10+ years': 0
        }
        
        for employee in active_employees:
            years = employee.years_of_service
            if years <= 1:
                service_groups['0-1 year'] += 1
            elif years <= 3:
                service_groups['1-3 years'] += 1
            elif years <= 5:
                service_groups['3-5 years'] += 1
            elif years <= 10:
                service_groups['5-10 years'] += 1
            else:
                service_groups['10+ years'] += 1
        
        return Response({
            'total_active_employees': active_employees.count(),
            'gender_distribution': gender_stats,
            'age_distribution': age_groups,
            'service_years_distribution': service_groups
        })
    
    @action(detail=False, methods=['get'])
    def contract_trends(self, request):
        """Analyze contract trends and patterns"""
        all_employees = Employee.objects.filter(is_deleted=False)
        
        # Contract type distribution
        contract_distribution = {}
        for contract_choice in Employee.contract_duration:
            count = all_employees.filter(contract_duration=contract_choice[0]).count()
            contract_distribution[contract_choice[1]] = count
        
        # Contract extensions analysis
        extension_stats = {
            'employees_with_extensions': all_employees.filter(contract_extensions__gt=0).count(),
            'total_extensions': sum(all_employees.values_list('contract_extensions', flat=True)),
            'avg_extensions_per_employee': 0
        }
        
        employees_with_extensions = all_employees.filter(contract_extensions__gt=0)
        if employees_with_extensions.exists():
            extension_stats['avg_extensions_per_employee'] = round(
                sum(employees_with_extensions.values_list('contract_extensions', flat=True)) / employees_with_extensions.count(), 2
            )
        
        # Contract renewal status
        renewal_distribution = {}
        for renewal_choice in Employee.RENEWAL_STATUS_CHOICES:
            count = all_employees.filter(renewal_status=renewal_choice[0]).count()
            renewal_distribution[renewal_choice[1]] = count
        
        # Upcoming contract endings
        upcoming_endings = {}
        for days in [7, 14, 30, 60, 90]:
            count = all_employees.filter(
                contract_end_date__lte=date.today() + timedelta(days=days),
                contract_end_date__gte=date.today(),
                contract_duration__in=['3_MONTHS', '6_MONTHS', '1_YEAR', '2_YEARS', '3_YEARS']
            ).count()
            upcoming_endings[f'{days}_days'] = count
        
        return Response({
            'contract_type_distribution': contract_distribution,
            'extension_statistics': extension_stats,
            'renewal_status_distribution': renewal_distribution,
            'upcoming_contract_endings': upcoming_endings
        })
    
    @action(detail=False, methods=['get'])
    def performance_indicators(self, request):
        """Get HR performance indicators"""
        active_employees = Employee.objects.filter(
            status__affects_headcount=True,
            is_deleted=False
        )
        
        # Hiring trends (last 12 months)
        hiring_trends = {}
        for i in range(12):
            month_date = date.today().replace(day=1) - timedelta(days=i*30)
            month_name = month_date.strftime('%Y-%m')
            
            hires_count = Employee.objects.filter(
                start_date__year=month_date.year,
                start_date__month=month_date.month
            ).count()
            
            hiring_trends[month_name] = hires_count
        
        # Turnover indicators
        departed_employees = Employee.objects.filter(
            end_date__isnull=False,
            end_date__gte=date.today() - timedelta(days=365)  # Last year
        ).count()
        
        turnover_rate = round((departed_employees / active_employees.count()) * 100, 2) if active_employees.count() > 0 else 0
        
        # Status distribution trends
        status_health = {}
        for emp_status in EmployeeStatus.objects.filter(is_active=True):
            count = Employee.objects.filter(status=emp_status, is_deleted=False).count()
            status_health[emp_status.name] = {
                'count': count,
                'percentage': round((count / Employee.objects.filter(is_deleted=False).count()) * 100, 1) if Employee.objects.filter(is_deleted=False).count() > 0 else 0
            }
        
        return Response({
            'active_headcount': active_employees.count(),
            'hiring_trends_12_months': hiring_trends,
            'annual_turnover_rate': turnover_rate,
            'departed_employees_last_year': departed_employees,
            'status_distribution_health': status_health,
            'management_coverage': {
                'with_line_manager': active_employees.filter(line_manager__isnull=False).count(),
                'without_line_manager': active_employees.filter(line_manager__isnull=True).count()
            }
        })
    
    

# Enhanced Organizational Chart ViewSet with Full Data
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
    
    @swagger_auto_schema(
        method='get',
        operation_description="Get complete organizational chart tree with all employee data",
        responses={
            200: openapi.Response(
                description="Organizational chart data retrieved successfully",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'org_chart': openapi.Schema(
                            type=openapi.TYPE_ARRAY,
                            items=openapi.Schema(
                                type=openapi.TYPE_OBJECT,
                                properties={
                                    'id': openapi.Schema(type=openapi.TYPE_INTEGER),
                                    'employee_id': openapi.Schema(type=openapi.TYPE_STRING),
                                    'name': openapi.Schema(type=openapi.TYPE_STRING),
                                    'job_title': openapi.Schema(type=openapi.TYPE_STRING),
                                    'position_group': openapi.Schema(type=openapi.TYPE_INTEGER),
                                    'position_level': openapi.Schema(type=openapi.TYPE_INTEGER),
                                    'department': openapi.Schema(type=openapi.TYPE_INTEGER),
                                    'department_name': openapi.Schema(type=openapi.TYPE_STRING),
                                    'business_function': openapi.Schema(type=openapi.TYPE_INTEGER),
                                    'business_function_name': openapi.Schema(type=openapi.TYPE_STRING),
                                    'status_color': openapi.Schema(type=openapi.TYPE_STRING),
                                    'grading_display': openapi.Schema(type=openapi.TYPE_STRING),
                                    'children': openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Schema(type=openapi.TYPE_OBJECT))
                                }
                            )
                        ),
                        'total_employees': openapi.Schema(type=openapi.TYPE_INTEGER)
                    }
                )
            )
        }
    )
    @action(detail=False, methods=['get'])
    def full_tree(self, request):
        """Get complete organizational chart tree"""
        top_level = self.get_queryset()
        serializer = self.get_serializer(top_level, many=True)
        
        # Add total employee count
        total_employees = Employee.objects.filter(
            status__allows_org_chart=True,
            is_visible_in_org_chart=True,
            is_deleted=False
        ).count()
        
        return Response({
            'org_chart': serializer.data,
            'total_employees': total_employees,
            'generated_at': timezone.now(),
            'filters_applied': {
                'allows_org_chart': True,
                'is_visible': True,
                'is_deleted': False
            }
        })
    
    @action(detail=False, methods=['get'])
    def by_department(self, request):
        """Get organizational chart by department"""
        department_id = request.query_params.get('department_id')
        if not department_id:
            return Response(
                {'error': 'department_id parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            department = Department.objects.get(id=department_id)
            employees = Employee.objects.filter(
                department=department,
                status__allows_org_chart=True,
                is_visible_in_org_chart=True,
                is_deleted=False
            ).select_related(
                'business_function', 'department', 'position_group', 'status', 'line_manager'
            ).order_by('position_group__hierarchy_level', 'employee_id')
            
            # Build hierarchy within department
            department_hierarchy = self._build_department_hierarchy(employees)
            
            return Response({
                'department': {
                    'id': department.id,
                    'name': department.name,
                    'business_function': department.business_function.name
                },
                'org_chart': department_hierarchy,
                'total_employees': employees.count()
            })
        except Department.DoesNotExist:
            return Response(
                {'error': 'Department not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    def _build_department_hierarchy(self, employees):
        """Build hierarchical structure for department employees"""
        employees_dict = {emp.id: emp for emp in employees}
        hierarchy = []
        
        # Find top-level employees in department (no line manager or line manager outside department)
        for employee in employees:
            if not employee.line_manager or employee.line_manager not in employees_dict.values():
                emp_data = OrgChartNodeSerializer(employee).data
                # Get direct reports within department
                emp_data['children'] = self._get_department_children(employee, employees_dict)
                hierarchy.append(emp_data)
        
        return hierarchy
    
    def _get_department_children(self, manager, employees_dict):
        """Get direct reports for manager within department"""
        children = []
        for employee in employees_dict.values():
            if employee.line_manager and employee.line_manager.id == manager.id:
                child_data = OrgChartNodeSerializer(employee).data
                child_data['children'] = self._get_department_children(employee, employees_dict)
                children.append(child_data)
        return children



   