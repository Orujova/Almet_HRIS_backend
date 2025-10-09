# api/job_description_views.py - UPDATED: Smart employee selection based on organizational hierarchy

# api/job_description_views.py - IMPORT SECTION UPDATE

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Count
from django.db import transaction
from django.utils import timezone
from django.http import HttpResponse, JsonResponse
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
import logging
import uuid
from datetime import datetime
from io import BytesIO
import traceback
from rest_framework import serializers

# Reportlab imports
try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch, cm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False

# Openpyxl imports for Excel operations
try:
    from openpyxl import load_workbook, Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False

logger = logging.getLogger(__name__)

# Job Description Models - CRITICAL IMPORTS
from .job_description_models import (
    JobDescription, 
    JobDescriptionSection, 
    JobDescriptionSkill,
    JobDescriptionBehavioralCompetency, 
    JobBusinessResource, 
    AccessMatrix,
    CompanyBenefit, 
    JobDescriptionBusinessResource, 
    JobDescriptionAccessMatrix,
    JobDescriptionCompanyBenefit, 
    JobDescriptionActivity
)

# Job Description Serializers - ALL SERIALIZERS
from .job_description_serializers import (
    JobDescriptionListSerializer, 
    JobDescriptionDetailSerializer,
    JobDescriptionCreateUpdateSerializer, 
    JobDescriptionApprovalSerializer,
    JobDescriptionRejectionSerializer, 
    JobDescriptionSubmissionSerializer,
    JobBusinessResourceSerializer, 
    AccessMatrixSerializer, 
    CompanyBenefitSerializer, 
    JobDescriptionActivitySerializer,
    EligibleEmployeesSerializer, 
    EmployeeBasicSerializer,
    JobDescriptionExportSerializer,
    JobDescriptionBulkUploadSerializer,  # NEW - Bulk Upload
    JobDescriptionBulkUploadResultSerializer  # NEW - Bulk Upload Result
)

# Competency and Skill Models
from .competency_models import Skill, BehavioralCompetency

# Core Models
from .models import (
    BusinessFunction, 
    Department, 
    Unit, 
    PositionGroup, 
    Employee, 
    JobFunction,
    VacantPosition
)
from .competency_models import Skill, BehavioralCompetency
from .models import BusinessFunction, Department, Unit, PositionGroup, Employee, JobFunction,VacantPosition
from .job_description_serializers import JobDescriptionExportSerializer

from openpyxl import load_workbook, Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from django.core.files.base import ContentFile
import io

class JobDescriptionFilter:
    """Advanced filtering for job descriptions"""
    
    def __init__(self, queryset, params):
        self.queryset = queryset
        if hasattr(params, 'dict'):
            self.params = params.dict()
        else:
            self.params = dict(params)
    
    def get_list_values(self, param_name):
        """Get list values from query params safely"""
        value = self.params.get(param_name)
        if not value:
            return []
        
        if isinstance(value, str):
            return [v.strip() for v in value.split(',') if v.strip()]
        elif isinstance(value, list):
            return value
        else:
            return [str(value)]
    
    def get_int_list_values(self, param_name):
        """Get integer list values"""
        string_values = self.get_list_values(param_name)
        int_values = []
        for val in string_values:
            try:
                int_values.append(int(val))
            except (ValueError, TypeError):
                continue
        return int_values
    
    def filter(self):
        queryset = self.queryset
        
        # Search filter
        search = self.params.get('search')
        if search:
            queryset = queryset.filter(
                Q(job_title__icontains=search) |
                Q(job_purpose__icontains=search) |
                Q(business_function__name__icontains=search) |
                Q(department__name__icontains=search) |
                Q(job_function__name__icontains=search) |
                Q(assigned_employee__full_name__icontains=search) |
                Q(assigned_employee__employee_id__icontains=search)
            )
        
        # Status filter
        status_values = self.get_list_values('status')
        if status_values:
            queryset = queryset.filter(status__in=status_values)
        
        # Business function filter
        business_function_ids = self.get_int_list_values('business_function')
        if business_function_ids:
            queryset = queryset.filter(business_function__id__in=business_function_ids)
        
        # Department filter
        department_ids = self.get_int_list_values('department')
        if department_ids:
            queryset = queryset.filter(department__id__in=department_ids)
        
        # Job function filter
        job_function_ids = self.get_int_list_values('job_function')
        if job_function_ids:
            queryset = queryset.filter(job_function__id__in=job_function_ids)
        
        # Position group filter
        position_group_ids = self.get_int_list_values('position_group')
        if position_group_ids:
            queryset = queryset.filter(position_group__id__in=position_group_ids)
        
        # Employee filter
        employee_search = self.params.get('employee_search')
        if employee_search:
            queryset = queryset.filter(
                Q(assigned_employee__full_name__icontains=employee_search) |
                Q(assigned_employee__employee_id__icontains=employee_search)
            )
        
        # Manager filter
        manager_search = self.params.get('manager_search')
        if manager_search:
            queryset = queryset.filter(
                Q(reports_to__full_name__icontains=manager_search) |
                Q(reports_to__employee_id__icontains=manager_search)
            )
        
        # Created date range
        created_date_from = self.params.get('created_date_from')
        created_date_to = self.params.get('created_date_to')
        if created_date_from:
            try:
                from django.utils.dateparse import parse_date
                date_from = parse_date(created_date_from)
                if date_from:
                    queryset = queryset.filter(created_at__date__gte=date_from)
            except:
                pass
        if created_date_to:
            try:
                from django.utils.dateparse import parse_date
                date_to = parse_date(created_date_to)
                if date_to:
                    queryset = queryset.filter(created_at__date__lte=date_to)
            except:
                pass
        
        
        
        return queryset


from drf_yasg.utils import swagger_auto_schema, no_body
from drf_yasg import openapi

# At the top of your ViewSet, override the schema
from rest_framework.schemas.openapi import AutoSchema

class FileUploadAutoSchema(AutoSchema):
    """Custom schema for file upload endpoints - prevents ModelSerializer fields from appearing"""
    
    def get_serializer(self, path, method):
        """Don't use ModelSerializer for schema generation in file upload actions"""
        view = self.view
        
        # For these actions, don't auto-generate schema from serializer
        if hasattr(view, 'action') and view.action in ['bulk_upload', 'download_template', 'export_to_excel']:
            return None
        
        return super().get_serializer(path, method)
    
    def get_request_serializer(self, path, method):
        """Override to prevent request body schema for file upload actions"""
        view = self.view
        
        if hasattr(view, 'action') and view.action in ['bulk_upload', 'download_template', 'export_to_excel']:
            return None
        
        return super().get_request_serializer(path, method)

class JobDescriptionViewSet(viewsets.ModelViewSet):
    """ViewSet with enhanced employee selection logic"""
    
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['job_title', 'job_purpose', 'business_function__name', 'department__name']
    ordering_fields = ['job_title', 'created_at', 'status', 'business_function__name']
    ordering = ['-created_at']
    
    # IMPORTANT: Set default parser classes at class level
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    
    # Use custom schema
    schema = FileUploadAutoSchema()
    
    def get_queryset(self):
        return JobDescription.objects.select_related(
            'business_function', 'department', 'unit', 'job_function', 'position_group',
            'reports_to', 'assigned_employee', 'created_by', 'updated_by',
            'line_manager_approved_by', 'employee_approved_by'
        ).prefetch_related(
            'sections', 'required_skills__skill', 'behavioral_competencies__competency',
            'business_resources__resource', 'access_rights__access_matrix',
            'company_benefits__benefit'
        ).all()
    
    def get_serializer_class(self):
        """Return appropriate serializer for each action"""
        action = getattr(self, 'action', None)
        
        if action == 'list':
            return JobDescriptionListSerializer
        elif action in ['create', 'update', 'partial_update']:
            return JobDescriptionCreateUpdateSerializer
        else:
            return JobDescriptionDetailSerializer
        
    def create(self, request, *args, **kwargs):
        """ENHANCED: Create with employee selection workflow"""
        
        serializer = self.get_serializer(data=request.data)
        
        try:
            serializer.is_valid(raise_exception=True)
            instance = serializer.save()
            
            # Enhanced response
            response_data = serializer.data
            
            # Add summary information
            total_created = getattr(instance, '_created_job_descriptions', [instance])
            response_data['summary'] = {
                'total_job_descriptions_created': len(total_created),
                'assignment_mode': 'multiple' if len(total_created) > 1 else 'single',
                'message': f'Successfully created {len(total_created)} job description(s)'
            }
            
            headers = self.get_success_headers(response_data)
            return Response(response_data, status=status.HTTP_201_CREATED, headers=headers)
            
        except serializers.ValidationError as e:
            # Check if this is an employee selection requirement
            if isinstance(e.detail, dict) and e.detail.get('requires_employee_selection'):
                # Return special response for employee selection
                return Response({
                    'requires_employee_selection': True,
                    'message': e.detail['message'],
                    'eligible_employees': e.detail['eligible_employees'],
                    'eligible_count': e.detail['eligible_count'],
                    'instruction': e.detail['instruction'],
                    'next_step': 'Resubmit the same request with "selected_employee_ids" field containing the IDs of employees you want to assign'
                }, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
            else:
                # Regular validation error
                raise
    
    @swagger_auto_schema(
    method='post',
    operation_description="Preview employees and vacant positions that would be assigned based on criteria",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=['job_title', 'business_function', 'department', 'job_function', 'position_group', 'grading_level'],
        properties={
            'job_title': openapi.Schema(type=openapi.TYPE_STRING),
            'business_function': openapi.Schema(type=openapi.TYPE_INTEGER),
            'department': openapi.Schema(type=openapi.TYPE_INTEGER),
            'unit': openapi.Schema(type=openapi.TYPE_INTEGER),
            'job_function': openapi.Schema(type=openapi.TYPE_INTEGER),
            'position_group': openapi.Schema(type=openapi.TYPE_INTEGER),
            'grading_level': openapi.Schema(type=openapi.TYPE_STRING),
            'max_preview': openapi.Schema(type=openapi.TYPE_INTEGER, default=50),
            'include_vacancies': openapi.Schema(type=openapi.TYPE_BOOLEAN, default=True)
        }
    ),
    responses={
        200: openapi.Response(
            description="Eligible employees and vacancies found",
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'eligible_employees_count': openapi.Schema(type=openapi.TYPE_INTEGER),
                    'eligible_vacancies_count': openapi.Schema(type=openapi.TYPE_INTEGER),
                    'total_eligible_count': openapi.Schema(type=openapi.TYPE_INTEGER),
                    'employees': openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Schema(type=openapi.TYPE_OBJECT)),
                    'vacancies': openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Schema(type=openapi.TYPE_OBJECT)),
                    'unified_list': openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Schema(type=openapi.TYPE_OBJECT)),
                    'assignment_strategy': openapi.Schema(type=openapi.TYPE_STRING),
                    'requires_manual_selection': openapi.Schema(type=openapi.TYPE_BOOLEAN)
                }
            )
        )
    }
)
    @action(detail=False, methods=['post'])
    def preview_eligible_employees(self, request):
        """ENHANCED: Preview which employees AND vacant positions would be assigned and what strategy would be used"""
        try:
            job_title = request.data.get('job_title')
            business_function_id = request.data.get('business_function')
            department_id = request.data.get('department')
            unit_id = request.data.get('unit')
            job_function_id = request.data.get('job_function')
            position_group_id = request.data.get('position_group')
            grading_level = request.data.get('grading_level')
            max_preview = request.data.get('max_preview', 50)
            include_vacancies = request.data.get('include_vacancies', True)
            
            # Validate required fields
            required_fields = {
                'job_title': job_title,
                'business_function': business_function_id,
                'department': department_id,
                'job_function': job_function_id,
                'position_group': position_group_id,
                'grading_level': grading_level
            }
            
            missing_fields = [field for field, value in required_fields.items() if not value]
            if missing_fields:
                return Response(
                    {'error': f'Missing required fields: {", ".join(missing_fields)}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Get eligible employees (existing logic)
            eligible_employees = JobDescription.get_eligible_employees_with_priority(
                job_title=job_title,
                business_function_id=business_function_id,
                department_id=department_id,
                unit_id=unit_id,
                job_function_id=job_function_id,
                position_group_id=position_group_id,
                grading_level=grading_level
            )
            
            # NEW: Get eligible vacant positions
            eligible_vacancies = self._get_eligible_vacant_positions(
                job_title=job_title,
                business_function_id=business_function_id,
                department_id=department_id,
                unit_id=unit_id,
                job_function_id=job_function_id,
                position_group_id=position_group_id,
                grading_level=grading_level
            ) if include_vacancies else VacantPosition.objects.none()
            
            # Apply limits
            limited_employees = eligible_employees[:max_preview//2] if include_vacancies else eligible_employees[:max_preview]
            limited_vacancies = eligible_vacancies[:max_preview//2] if include_vacancies else eligible_vacancies.none()
            
            # Serialize data
            employees_serializer = EmployeeBasicSerializer(limited_employees, many=True)
            employees_data = employees_serializer.data
            
            vacancies_data = []
            if include_vacancies:
                for vacancy in limited_vacancies:
                    vacancy_data = self._convert_vacancy_to_employee_preview_format(vacancy)
                    vacancies_data.append(vacancy_data)
            
            # Create unified list for frontend
            unified_list = []
            unified_list.extend(employees_data)
            unified_list.extend(vacancies_data)
            
            # Determine assignment strategy
            total_eligible = eligible_employees.count() + (eligible_vacancies.count() if include_vacancies else 0)
            employee_count = eligible_employees.count()
            vacancy_count = eligible_vacancies.count() if include_vacancies else 0
            
            if total_eligible == 0:
                assignment_strategy = "no_matches_found"
                requires_manual_selection = False
                strategy_message = "No employees or vacant positions match the criteria"
            elif total_eligible == 1:
                assignment_strategy = "auto_assign_single"
                requires_manual_selection = False
                if employee_count == 1:
                    strategy_message = "Will automatically assign to the single matching employee"
                else:
                    strategy_message = "Will automatically convert the single matching vacant position"
            else:
                assignment_strategy = "manual_selection_required"
                requires_manual_selection = True
                strategy_message = f"Found {total_eligible} matching positions ({employee_count} employees, {vacancy_count} vacant positions) - you must select which ones to use"
            
            # Get organizational info for response
            try:
                business_function = BusinessFunction.objects.get(id=business_function_id)
                department = Department.objects.get(id=department_id)
                job_function = JobFunction.objects.get(id=job_function_id)
                position_group = PositionGroup.objects.get(id=position_group_id)
                unit = Unit.objects.get(id=unit_id) if unit_id else None
            except:
                return Response(
                    {'error': 'Invalid organizational structure IDs provided'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            response_data = {
                'eligible_employees_count': employee_count,
                'eligible_vacancies_count': vacancy_count,
                'total_eligible_count': total_eligible,
                'employees': employees_data,
                'vacancies': vacancies_data,
                'unified_list': unified_list,
                'assignment_strategy': assignment_strategy,
                'requires_manual_selection': requires_manual_selection,
                'strategy_message': strategy_message,
                'criteria': {
                    'job_title': job_title,
                    'business_function': {'id': business_function.id, 'name': business_function.name},
                    'department': {'id': department.id, 'name': department.name},
                    'unit': {'id': unit.id, 'name': unit.name} if unit else None,
                    'job_function': {'id': job_function.id, 'name': job_function.name},
                    'position_group': {'id': position_group.id, 'name': position_group.name},
                    'grading_level': grading_level
                },
                'next_steps': {
                    'if_single_match': 'Submit job description - will auto-assign',
                    'if_multiple_matches': 'Submit job description with "selected_employee_ids" and/or "selected_vacancy_ids" fields',
                    'if_no_matches': 'Adjust criteria to find matching positions',
                    'mixed_results': f'Found both employees ({employee_count}) and vacant positions ({vacancy_count}) - choose which to use'
                },
                'includes_vacancies': include_vacancies
            }
            
            return Response(response_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error in preview_eligible_employees: {str(e)}")
            return Response(
                {'error': f'Failed to preview positions: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _get_eligible_vacant_positions(self, job_title=None, business_function_id=None, 
                                     department_id=None, unit_id=None, job_function_id=None, 
                                     position_group_id=None, grading_level=None):
        """Get vacant positions matching job description criteria"""
        from .models import VacantPosition
        
        # Start with unfilled, active vacant positions
        queryset = VacantPosition.objects.filter(
            is_filled=False,
            is_deleted=False,
            include_in_headcount=True
        ).select_related(
            'business_function', 'department', 'unit', 'job_function', 
            'position_group', 'vacancy_status'
        )
        
        logger.info(f"Starting vacant position search with {queryset.count()} unfilled positions")
        
        # 1. JOB TITLE FILTER
        if job_title:
            job_title_clean = job_title.strip()
            queryset = queryset.filter(job_title__iexact=job_title_clean)
            logger.info(f"After job_title '{job_title_clean}' filter: {queryset.count()}")
        
        # 2. BUSINESS FUNCTION FILTER
        if business_function_id:
            queryset = queryset.filter(business_function_id=business_function_id)
            logger.info(f"After business_function filter: {queryset.count()}")
        
        # 3. DEPARTMENT FILTER
        if department_id:
            queryset = queryset.filter(department_id=department_id)
            logger.info(f"After department filter: {queryset.count()}")
        
        # 4. UNIT FILTER (optional)
        if unit_id:
            queryset = queryset.filter(unit_id=unit_id)
            logger.info(f"After unit filter: {queryset.count()}")
        
        # 5. JOB FUNCTION FILTER
        if job_function_id:
            queryset = queryset.filter(job_function_id=job_function_id)
            logger.info(f"After job_function filter: {queryset.count()}")
        
        # 6. POSITION GROUP FILTER
        if position_group_id:
            queryset = queryset.filter(position_group_id=position_group_id)
            logger.info(f"After position_group filter: {queryset.count()}")
        
        # 7. GRADING LEVEL FILTER
        if grading_level:
            from .job_description_models import normalize_grading_level
            grading_level_clean = grading_level.strip()
            normalized_target = normalize_grading_level(grading_level_clean)
            
            logger.info(f"Target grading level: '{grading_level_clean}' (normalized: '{normalized_target}')")
            
            # Get all vacancies and filter manually for smart comparison
            all_vacancies = list(queryset)
            matching_vacancies = []
            
            for vacancy in all_vacancies:
                vac_grade = vacancy.grading_level.strip() if vacancy.grading_level else ""
                vac_normalized = normalize_grading_level(vac_grade)
                
                if vac_normalized == normalized_target:
                    matching_vacancies.append(vacancy.id)
                    logger.info(f"Vacancy match: {vacancy.position_id} - '{vac_grade}' (normalized: '{vac_normalized}')")
            
            queryset = queryset.filter(id__in=matching_vacancies)
            logger.info(f"After grading_level filter: {queryset.count()}")
        
        return queryset.order_by('position_id')
    
    def _convert_vacancy_to_employee_preview_format(self, vacancy):
        """Convert vacancy to employee-like format for preview"""
        return {
            'id': vacancy.original_employee_pk or f"vacancy_{vacancy.id}",  # Use original PK if available
            'employee_id': vacancy.position_id,
            'name': "VACANT POSITION",
            'full_name': f"[VACANT] {vacancy.job_title}",
            'email': None,
            'father_name': None,
            'date_of_birth': None,
            'gender': None,
            'phone': None,
            'business_function_name': vacancy.business_function.name if vacancy.business_function else 'N/A',
            'business_function_code': vacancy.business_function.code if vacancy.business_function else 'N/A',
            'business_function_id': vacancy.business_function.id if vacancy.business_function else None,
            'department_name': vacancy.department.name if vacancy.department else 'N/A',
            'department_id': vacancy.department.id if vacancy.department else None,
            'unit_name': vacancy.unit.name if vacancy.unit else None,
            'unit_id': vacancy.unit.id if vacancy.unit else None,
            'job_function_name': vacancy.job_function.name if vacancy.job_function else 'N/A',
            'job_function_id': vacancy.job_function.id if vacancy.job_function else None,
            'job_title': vacancy.job_title,
            'position_group_name': vacancy.position_group.get_name_display() if vacancy.position_group else 'N/A',
            'position_group_level': vacancy.position_group.hierarchy_level if vacancy.position_group else 0,
            'position_group_id': vacancy.position_group.id if vacancy.position_group else None,
            'grading_level': vacancy.grading_level,
            'line_manager_name': vacancy.reporting_to.full_name if vacancy.reporting_to else None,
            'line_manager_hc_number': vacancy.reporting_to.employee_id if vacancy.reporting_to else None,
            'status_name': 'VACANT',
            'status_color': '#F97316',
            'organizational_path': self._get_vacancy_organizational_path(vacancy),
            'matching_score': 100,
            'has_line_manager': bool(vacancy.reporting_to),
            'is_vacancy': True,
            'record_type': 'vacancy',
            'vacancy_details': {
                'internal_id': vacancy.id,
                'position_id': vacancy.position_id,
                'include_in_headcount': vacancy.include_in_headcount,
                'is_filled': vacancy.is_filled,
                'filled_date': vacancy.filled_date,
                'notes': vacancy.notes,
                'original_employee_pk': vacancy.original_employee_pk,
                'can_be_converted': True
            }
        }
    
    def _get_vacancy_organizational_path(self, vacancy):
        """Get organizational path for vacancy"""
        path_parts = []
        
        if vacancy.business_function:
            path_parts.append(vacancy.business_function.name)
        if vacancy.department:
            path_parts.append(vacancy.department.name)
        if vacancy.unit:
            path_parts.append(vacancy.unit.name)
        if vacancy.job_function:
            path_parts.append(f"Function: {vacancy.job_function.name}")
        if vacancy.position_group:
            path_parts.append(f"Grade: {vacancy.grading_level}")
        
        return " > ".join(path_parts)
    @swagger_auto_schema(
        method='post',
        operation_description="Submit job description for approval workflow",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'submit_to_line_manager': openapi.Schema(
                    type=openapi.TYPE_BOOLEAN, 
                    default=True,
                    description='Submit to line manager for approval'
                ),
                'comments': openapi.Schema(
                    type=openapi.TYPE_STRING, 
                    description='Optional comments'
                )
            },
        ),
        responses={
            200: openapi.Response(
                description="Submitted successfully",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'success': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                        'message': openapi.Schema(type=openapi.TYPE_STRING),
                        'job_description_id': openapi.Schema(type=openapi.TYPE_STRING),
                        'status': openapi.Schema(type=openapi.TYPE_STRING),
                        'next_approver': openapi.Schema(type=openapi.TYPE_STRING),
                        'workflow_step': openapi.Schema(type=openapi.TYPE_STRING)
                    }
                )
            ),
            400: openapi.Response(description="Bad request"),
            403: openapi.Response(description="Permission denied"),
            404: openapi.Response(description="Job description not found")
        }
    )
    @action(detail=True, methods=['post'])
    def submit_for_approval(self, request, pk=None):
        """Submit job description for approval workflow"""
        try:
            logger.info(f"Submit for approval request - User: {request.user.username}, JD ID: {pk}")
            logger.info(f"Request data: {request.data}")
            
            job_description = self.get_object()
            logger.info(f"Job description found: {job_description.job_title}, Status: {job_description.status}")
            
            if job_description.status not in ['DRAFT', 'REVISION_REQUIRED']:
                logger.warning(f"Invalid status for submission: {job_description.status}")
                return Response(
                    {'error': f'Cannot submit job description with status: {job_description.get_status_display()}. Only DRAFT or REVISION_REQUIRED can be submitted.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Validate that we have an assigned employee and manager
            if not job_description.assigned_employee:
                return Response(
                    {'error': 'Job description must have an assigned employee before submission'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if not job_description.reports_to:
                return Response(
                    {'error': 'Job description must have a line manager. Please ensure the assigned employee has a line manager set.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            serializer = JobDescriptionSubmissionSerializer(data=request.data)
            if not serializer.is_valid():
                logger.error(f"Serializer validation failed: {serializer.errors}")
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
            logger.info("Starting job description submission transaction...")
            
            with transaction.atomic():
                old_status = job_description.status
                job_description.status = 'PENDING_LINE_MANAGER'
                job_description.save(update_fields=['status'])
                
                logger.info(f"Status updated from {old_status} to {job_description.status}")
                
                employee_info = job_description.get_employee_info()
                description = f"Job description submitted for approval by {request.user.get_full_name()}"
                description += f" for {employee_info['name']}"
                
                activity = JobDescriptionActivity.objects.create(
                    job_description=job_description,
                    activity_type='SUBMITTED_FOR_APPROVAL',
                    description=description,
                    performed_by=request.user,
                    metadata={
                        'comments': serializer.validated_data.get('comments', ''),
                        'submit_to_line_manager': serializer.validated_data.get('submit_to_line_manager', True),
                        'old_status': old_status,
                        'new_status': job_description.status,
                        'employee_info': employee_info,
                        'reports_to_id': job_description.reports_to.id if job_description.reports_to else None,
                        'reports_to_name': job_description.reports_to.full_name if job_description.reports_to else None
                    }
                )
                
                logger.info(f"Activity logged: {activity.id}")
                logger.info(f"Job description {job_description.id} submitted successfully")
                
                response_data = {
                    'success': True,
                    'message': 'Job description submitted for approval successfully',
                    'job_description_id': str(job_description.id),
                    'status': job_description.get_status_display(),
                    'next_approver': job_description.reports_to.full_name if job_description.reports_to else 'N/A',
                    'workflow_step': 'pending_line_manager_approval',
                    'employee_info': employee_info,
                    'manager_info': job_description.get_manager_info()
                }
                
                logger.info(f"Returning success response for JD {job_description.id}")
                return Response(response_data, status=status.HTTP_200_OK)
                
        except JobDescription.DoesNotExist:
            logger.error(f"Job description not found: {pk}")
            return Response(
                {'error': 'Job description not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error submitting job description {pk}: {str(e)}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return Response(
                {'error': f'Failed to submit job description: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @swagger_auto_schema(
        method='post',
        operation_description="Approve job description as line manager",
        request_body=JobDescriptionApprovalSerializer,
        responses={200: "Approved successfully"}
    )
    @action(detail=True, methods=['post'])
    def approve_by_line_manager(self, request, pk=None):
        """Approve job description as line manager"""
        try:
            logger.info(f"Line manager approval by {request.user.username} for JD {pk}")
            
            job_description = self.get_object()
            
            serializer = JobDescriptionApprovalSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
            if job_description.status != 'PENDING_LINE_MANAGER':
                return Response(
                    {'error': f'Job description is not pending line manager approval. Current status: {job_description.get_status_display()}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            with transaction.atomic():
                job_description.line_manager_approved_by = request.user
                job_description.line_manager_approved_at = timezone.now()
                job_description.line_manager_comments = serializer.validated_data.get('comments', '')
                
                signature = serializer.validated_data.get('signature')
                if signature:
                    job_description.line_manager_signature = signature
                
                # Move to employee approval
                job_description.status = 'PENDING_EMPLOYEE'
                job_description.save()
                
                employee_info = job_description.get_employee_info()
                description = f"Approved by {request.user.get_full_name()} as line manager"
                
                JobDescriptionActivity.objects.create(
                    job_description=job_description,
                    activity_type='APPROVED_BY_LINE_MANAGER',
                    description=description,
                    performed_by=request.user,
                    metadata={
                        'comments': serializer.validated_data.get('comments', ''),
                        'has_signature': bool(signature),
                        'next_status': job_description.status,
                        'employee_info': employee_info,
                        'next_step': 'pending_employee_approval'
                    }
                )
                
                logger.info(f"Line manager approval successful for JD {job_description.id}")
                
                return Response({
                    'success': True,
                    'message': 'Job description approved by line manager - now pending employee approval',
                    'job_description_id': str(job_description.id),
                    'status': job_description.get_status_display(),
                    'next_step': 'pending_employee_approval',
                    'approved_by': request.user.get_full_name(),
                    'employee_info': employee_info,
                    'is_fully_approved': False
                }, status=status.HTTP_200_OK)
                
        except Exception as e:
            logger.error(f"Error in approve_by_line_manager: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return Response(
                {'error': f'Failed to approve: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @swagger_auto_schema(
        method='post',
        operation_description="Approve job description as employee",
        request_body=JobDescriptionApprovalSerializer,
        responses={200: "Approved successfully"}
    )
    @action(detail=True, methods=['post'])
    def approve_as_employee(self, request, pk=None):
        """Approve job description as employee"""
        try:
            job_description = self.get_object()
            
            if job_description.status != 'PENDING_EMPLOYEE':
                return Response(
                    {'error': f'Job description is not pending employee approval. Current status: {job_description.get_status_display()}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            serializer = JobDescriptionApprovalSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
            with transaction.atomic():
                job_description.employee_approved_by = request.user
                job_description.employee_approved_at = timezone.now()
                job_description.employee_comments = serializer.validated_data.get('comments', '')
                job_description.status = 'APPROVED'  # Fully approved
                
                signature = serializer.validated_data.get('signature')
                if signature:
                    job_description.employee_signature = signature
                
                job_description.save()
                
                JobDescriptionActivity.objects.create(
                    job_description=job_description,
                    activity_type='APPROVED_BY_EMPLOYEE',
                    description=f"Approved by {request.user.get_full_name()} as employee - Fully approved",
                    performed_by=request.user,
                    metadata={
                        'comments': serializer.validated_data.get('comments', ''),
                        'has_signature': bool(signature),
                        'final_approval': True
                    }
                )
                
                return Response({
                    'success': True,
                    'message': 'Job description fully approved',
                    'job_description_id': str(job_description.id),
                    'status': job_description.get_status_display(),
                    'approved_by': request.user.get_full_name(),
                    'completion': 'Job description approval process completed'
                })
                
        except Exception as e:
            logger.error(f"Error approving as employee: {str(e)}")
            return Response(
                {'error': f'Failed to approve: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @swagger_auto_schema(
        method='post',
        operation_description="Reject job description",
        request_body=JobDescriptionRejectionSerializer,
        responses={200: "Rejected successfully"}
    )
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Reject job description"""
        try:
            job_description = self.get_object()
            
            if job_description.status not in ['PENDING_LINE_MANAGER', 'PENDING_EMPLOYEE']:
                return Response(
                    {'error': f'Job description cannot be rejected in current status: {job_description.get_status_display()}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            serializer = JobDescriptionRejectionSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
            with transaction.atomic():
                job_description.status = 'REJECTED'
                job_description.save()
                
                JobDescriptionActivity.objects.create(
                    job_description=job_description,
                    activity_type='REJECTED',
                    description=f"Rejected by {request.user.get_full_name()}",
                    performed_by=request.user,
                    metadata={'rejection_reason': serializer.validated_data['reason']}
                )
                
                return Response({
                    'success': True,
                    'message': 'Job description rejected',
                    'job_description_id': str(job_description.id),
                    'status': job_description.get_status_display(),
                    'rejected_by': request.user.get_full_name(),
                    'reason': serializer.validated_data['reason']
                })
                
        except Exception as e:
            logger.error(f"Error rejecting job description: {str(e)}")
            return Response(
                {'error': f'Failed to reject: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def request_revision(self, request, pk=None):
        """Request revision for job description"""
        try:
            job_description = self.get_object()
            
            can_request = (
                job_description.status in ['PENDING_LINE_MANAGER', 'PENDING_EMPLOYEE'] 
            )
            
            if not can_request:
                return Response(
                    {'error': 'You are not authorized to request revision for this job description'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            serializer = JobDescriptionRejectionSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
            with transaction.atomic():
                job_description.request_revision(
                    reason=serializer.validated_data['reason']
                )
                
                JobDescriptionActivity.objects.create(
                    job_description=job_description,
                    activity_type='REVISION_REQUESTED',
                   
                    metadata={'revision_reason': serializer.validated_data['reason']}
                )
                
                return Response({
                    'success': True,
                    'message': 'Revision requested',
                    'job_description_id': str(job_description.id),
                    'status': job_description.get_status_display(),
                    'reason': serializer.validated_data['reason']
                })
                
        except Exception as e:
            logger.error(f"Error requesting revision: {str(e)}")
            return Response(
                {'error': f'Failed to request revision: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def activities(self, request, pk=None):
        """Get activity history for job description"""
        try:
            job_description = self.get_object()
            activities = job_description.activities.all()[:50]  # Last 50 activities
            serializer = JobDescriptionActivitySerializer(activities, many=True)
            return Response({
                'job_description_id': str(job_description.id),
                'activities': serializer.data
            })
        except Exception as e:
            logger.error(f"Error getting activities: {str(e)}")
            return Response(
                {'error': f'Failed to get activities: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @swagger_auto_schema(
    method='post',
    operation_description="Bulk upload job descriptions from Excel file",
    request_body=no_body,  # CRITICAL: Prevent automatic body schema generation
    manual_parameters=[
        openapi.Parameter(
            'file',
            openapi.IN_FORM,
            description="Excel file (.xlsx or .xls)",
            type=openapi.TYPE_FILE,
            required=True
        ),
        openapi.Parameter(
            'validate_only',
            openapi.IN_FORM,
            description="Dry run - validate without creating",
            type=openapi.TYPE_BOOLEAN,
            default=False,
            required=False
        ),
        openapi.Parameter(
            'auto_assign_employees',
            openapi.IN_FORM,
            description="Auto-assign to all matching positions",
            type=openapi.TYPE_BOOLEAN,
            default=True,
            required=False
        ),
        openapi.Parameter(
            'skip_duplicates',
            openapi.IN_FORM,
            description="Skip existing job descriptions",
            type=openapi.TYPE_BOOLEAN,
            default=True,
            required=False
        ),
    ],
    responses={
        200: openapi.Response(
            description="Bulk upload completed successfully",
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'total_rows': openapi.Schema(
                        type=openapi.TYPE_INTEGER,
                        description='Total number of rows processed'
                    ),
                    'successful': openapi.Schema(
                        type=openapi.TYPE_INTEGER,
                        description='Number of successfully created job descriptions'
                    ),
                    'failed': openapi.Schema(
                        type=openapi.TYPE_INTEGER,
                        description='Number of failed rows'
                    ),
                    'skipped': openapi.Schema(
                        type=openapi.TYPE_INTEGER,
                        description='Number of skipped rows (duplicates)'
                    ),
                    'created_job_descriptions': openapi.Schema(
                        type=openapi.TYPE_ARRAY,
                        items=openapi.Schema(type=openapi.TYPE_OBJECT)
                    ),
                    'errors': openapi.Schema(
                        type=openapi.TYPE_ARRAY,
                        items=openapi.Schema(type=openapi.TYPE_OBJECT)
                    ),
                    'warnings': openapi.Schema(
                        type=openapi.TYPE_ARRAY,
                        items=openapi.Schema(type=openapi.TYPE_OBJECT)
                    ),
                }
            )
        ),
        400: openapi.Response(description="Bad request - invalid file or parameters"),
        500: openapi.Response(description="Server error during processing")
    },
    consumes=['multipart/form-data']
)
    @action(
        detail=False,
        methods=['post'],
        parser_classes=[MultiPartParser, FormParser],
        url_path='bulk-upload',
        url_name='bulk-upload'
    )
    def bulk_upload(self, request):
        """Bulk upload job descriptions from Excel"""
        try:
            # Direct file access from request.FILES
            excel_file = request.FILES.get('file')
            if not excel_file:
                return Response(
                    {'error': 'No file provided. Please upload an Excel file using the "file" parameter.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Validate file extension
            if not excel_file.name.endswith(('.xlsx', '.xls')):
                return Response(
                    {'error': 'Invalid file format. Please upload an Excel file (.xlsx or .xls)'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Get boolean parameters from request.data
            # Handle string values from form data ('true'/'false' strings)
            validate_only_param = request.data.get('validate_only', 'false')
            validate_only = str(validate_only_param).lower() in ['true', '1', 'yes']
            
            auto_assign_param = request.data.get('auto_assign_employees', 'true')
            auto_assign = str(auto_assign_param).lower() in ['true', '1', 'yes']
            
            skip_duplicates_param = request.data.get('skip_duplicates', 'true')
            skip_duplicates = str(skip_duplicates_param).lower() in ['true', '1', 'yes']
            
            logger.info(f"Bulk upload started by {request.user.username}")
            logger.info(f"File: {excel_file.name}, Size: {excel_file.size} bytes")
            logger.info(f"Parameters: validate_only={validate_only}, auto_assign={auto_assign}, skip_duplicates={skip_duplicates}")
            
            # Check if openpyxl is available
            if not HAS_OPENPYXL:
                return Response(
                    {'error': 'Excel library (openpyxl) is not installed. Please contact administrator.'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            # Load workbook
            try:
                wb = load_workbook(excel_file, data_only=True)
                ws = wb.active
                logger.info(f"Workbook loaded successfully. Active sheet: {ws.title}")
            except Exception as e:
                logger.error(f"Failed to read Excel file: {str(e)}")
                return Response(
                    {'error': f'Failed to read Excel file: {str(e)}. Please ensure it is a valid Excel file.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Process the rows
            results = self._process_bulk_upload_rows(
                ws,
                validate_only=validate_only,
                auto_assign=auto_assign,
                skip_duplicates=skip_duplicates,
                user=request.user
            )
            
            logger.info(f"Bulk upload completed: {results['successful']} successful, {results['failed']} failed, {results['skipped']} skipped")
            
            return Response(results, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Bulk upload error: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return Response(
                {'error': f'Bulk upload failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    
    def _process_bulk_upload_rows(self, worksheet, validate_only=False, auto_assign=True, 
                                  skip_duplicates=True, user=None):
        """Process Excel rows and create job descriptions"""
        
        results = {
            'total_rows': 0,
            'successful': 0,
            'failed': 0,
            'skipped': 0,
            'created_job_descriptions': [],
            'errors': [],
            'warnings': [],
            'validation_summary': {}
        }
        
        # Expected column mapping
        COLUMNS = {
            'A': 'job_title',
            'B': 'business_function_code',
            'C': 'department_code',
            'D': 'unit_code',
            'E': 'job_function_code',
            'F': 'position_group_code',
            'G': 'grading_level',
            'H': 'employee_id',
            'I': 'job_purpose',
            'J': 'critical_duties',
            'K': 'main_kpis',
            'L': 'job_duties',
            'M': 'requirements',
            'N': 'skills',
            'O': 'competencies',
            'P': 'business_resources',
            'Q': 'access_rights',
            'R': 'company_benefits'
        }
        
        # Skip header row
        rows = list(worksheet.iter_rows(min_row=2, values_only=True))
        results['total_rows'] = len(rows)
        
        for row_num, row in enumerate(rows, start=2):
            try:
                # Extract data from row
                row_data = {}
                for col_idx, col_letter in enumerate(COLUMNS.keys()):
                    field_name = COLUMNS[col_letter]
                    cell_value = row[col_idx] if col_idx < len(row) else None
                    row_data[field_name] = str(cell_value).strip() if cell_value else None
                
                logger.info(f"Processing row {row_num}: {row_data.get('job_title')}")
                
                # Validate required fields
                required_fields = ['job_title', 'business_function_code', 'department_code', 
                                 'job_function_code', 'position_group_code', 'grading_level', 'job_purpose']
                
                missing_fields = [f for f in required_fields if not row_data.get(f)]
                if missing_fields:
                    results['failed'] += 1
                    results['errors'].append({
                        'row': row_num,
                        'job_title': row_data.get('job_title', 'N/A'),
                        'error': f"Missing required fields: {', '.join(missing_fields)}"
                    })
                    continue
                
                # Check for duplicates
                if skip_duplicates and row_data.get('employee_id'):
                    existing = JobDescription.objects.filter(
                        job_title__iexact=row_data['job_title'],
                        assigned_employee__employee_id=row_data['employee_id']
                    ).exists()
                    
                    if existing:
                        results['skipped'] += 1
                        results['warnings'].append({
                            'row': row_num,
                            'job_title': row_data['job_title'],
                            'message': f"Skipped - already exists for employee {row_data['employee_id']}"
                        })
                        continue
                
                # Resolve organizational structure
                try:
                    org_data = self._resolve_organizational_structure(row_data)
                except Exception as e:
                    results['failed'] += 1
                    results['errors'].append({
                        'row': row_num,
                        'job_title': row_data['job_title'],
                        'error': f"Organizational structure error: {str(e)}"
                    })
                    continue
                
                # Find employee (if auto_assign or employee_id provided)
                assigned_employee = None
                if row_data.get('employee_id'):
                    try:
                        assigned_employee = Employee.objects.get(
                            employee_id=row_data['employee_id'],
                            is_deleted=False
                        )
                    except Employee.DoesNotExist:
                        results['warnings'].append({
                            'row': row_num,
                            'job_title': row_data['job_title'],
                            'message': f"Employee {row_data['employee_id']} not found"
                        })
                
                elif auto_assign:
                    # Try to find matching employee
                    eligible_employees = JobDescription.get_eligible_employees_with_priority(
                        job_title=row_data['job_title'],
                        business_function_id=org_data['business_function'].id,
                        department_id=org_data['department'].id,
                        unit_id=org_data['unit'].id if org_data.get('unit') else None,
                        job_function_id=org_data['job_function'].id,
                        position_group_id=org_data['position_group'].id,
                        grading_level=row_data['grading_level']
                    )
                    
                    if eligible_employees.count() == 1:
                        assigned_employee = eligible_employees.first()
                        logger.info(f"Auto-assigned employee: {assigned_employee.full_name}")
                    elif eligible_employees.count() > 1:
                        results['warnings'].append({
                            'row': row_num,
                            'job_title': row_data['job_title'],
                            'message': f"Multiple employees match criteria ({eligible_employees.count()}). Skipping auto-assignment."
                        })
                
                if validate_only:
                    results['successful'] += 1
                    results['created_job_descriptions'].append({
                        'row': row_num,
                        'job_title': row_data['job_title'],
                        'status': 'validated',
                        'employee': assigned_employee.full_name if assigned_employee else 'No assignment'
                    })
                    continue
                
                # Create job description
                with transaction.atomic():
                    jd = JobDescription.objects.create(
                        job_title=row_data['job_title'],
                        business_function=org_data['business_function'],
                        department=org_data['department'],
                        unit=org_data.get('unit'),
                        job_function=org_data['job_function'],
                        position_group=org_data['position_group'],
                        grading_level=row_data['grading_level'],
                        assigned_employee=assigned_employee,
                        job_purpose=row_data['job_purpose'],
                        status='DRAFT',
                        created_by=user
                    )
                    
                    # Create sections
                    section_order = 1
                    section_mappings = [
                        ('critical_duties', 'CRITICAL_DUTIES', 'Critical Duties'),
                        ('main_kpis', 'MAIN_KPIS', 'Main KPIs'),
                        ('job_duties', 'JOB_DUTIES', 'Job Duties'),
                        ('requirements', 'REQUIREMENTS', 'Requirements')
                    ]
                    
                    for field_name, section_type, section_title in section_mappings:
                        content = row_data.get(field_name)
                        if content:
                            # Split by pipe separator and format
                            items = [item.strip() for item in content.split('|') if item.strip()]
                            formatted_content = '\n'.join([f"• {item}" for item in items])
                            
                            JobDescriptionSection.objects.create(
                                job_description=jd,
                                section_type=section_type,
                                title=section_title,
                                content=formatted_content,
                                order=section_order
                            )
                            section_order += 1
                    
                    # Add skills
                    if row_data.get('skills'):
                        self._add_skills_from_string(jd, row_data['skills'])
                    
                    # Add competencies
                    if row_data.get('competencies'):
                        self._add_competencies_from_string(jd, row_data['competencies'])
                    
                    # Add business resources
                    if row_data.get('business_resources'):
                        self._add_resources_from_string(jd, row_data['business_resources'], 'business')
                    
                    # Add access rights
                    if row_data.get('access_rights'):
                        self._add_resources_from_string(jd, row_data['access_rights'], 'access')
                    
                    # Add company benefits
                    if row_data.get('company_benefits'):
                        self._add_resources_from_string(jd, row_data['company_benefits'], 'benefits')
                    
                    # Log activity
                    JobDescriptionActivity.objects.create(
                        job_description=jd,
                        activity_type='CREATED',
                        description=f"Job description created via bulk upload (Row {row_num})",
                        performed_by=user,
                        metadata={
                            'source': 'bulk_upload',
                            'row_number': row_num,
                            'auto_assigned': bool(assigned_employee)
                        }
                    )
                    
                    results['successful'] += 1
                    results['created_job_descriptions'].append({
                        'row': row_num,
                        'job_description_id': str(jd.id),
                        'job_title': jd.job_title,
                        'employee': assigned_employee.full_name if assigned_employee else 'Not assigned',
                        'status': jd.get_status_display()
                    })
                    
                    logger.info(f"Successfully created JD from row {row_num}: {jd.job_title}")
            
            except Exception as e:
                results['failed'] += 1
                results['errors'].append({
                    'row': row_num,
                    'job_title': row_data.get('job_title', 'N/A'),
                    'error': str(e)
                })
                logger.error(f"Error processing row {row_num}: {str(e)}")
                logger.error(traceback.format_exc())
        
        # Validation summary
        results['validation_summary'] = {
            'total_processed': results['total_rows'],
            'success_rate': f"{(results['successful'] / results['total_rows'] * 100):.1f}%" if results['total_rows'] > 0 else "0%",
            'mode': 'validation_only' if validate_only else 'creation',
            'auto_assignment_enabled': auto_assign,
            'skip_duplicates_enabled': skip_duplicates
        }
        
        return results
    
    def _resolve_organizational_structure(self, row_data):
        """Resolve organizational structure from codes/names - FLEXIBLE matching"""
        result = {}
        
        # Business Function - try CODE first, then NAME
        try:
            try:
                result['business_function'] = BusinessFunction.objects.get(
                    code=row_data['business_function_code'],
                    is_active=True
                )
            except BusinessFunction.DoesNotExist:
                # Try by name if code doesn't work
                result['business_function'] = BusinessFunction.objects.get(
                    name__iexact=row_data['business_function_code'],
                    is_active=True
                )
        except BusinessFunction.DoesNotExist:
            raise ValueError(f"Business Function not found with code or name: '{row_data['business_function_code']}'")
        
        # Department - SMART matching with debug info
        dept_search_value = row_data['department_code'].strip()
        logger.info(f"Searching for department: '{dept_search_value}' in business function: {result['business_function'].name}")
        
        try:
            result['department'] = Department.objects.get(
                business_function=result['business_function'],
                name__iexact=dept_search_value,
                is_active=True
            )
            logger.info(f"✅ Department found: {result['department'].name} (ID: {result['department'].id})")
        except Department.DoesNotExist:
            # Show available departments for debugging
            available_depts = list(Department.objects.filter(
                business_function=result['business_function'],
                is_active=True
            ).values('id', 'name'))
            
            logger.error(f"❌ Department '{dept_search_value}' not found. Available: {available_depts}")
            raise ValueError(
                f"Department not found: '{dept_search_value}'. "
                f"Available departments in {result['business_function'].name}: "
                f"{[d['name'] for d in available_depts]}"
            )
        
        # Unit (optional) - SMART matching with detailed debugging
        if row_data.get('unit_code'):
            unit_search_value = row_data['unit_code'].strip()
            logger.info(f"Searching for unit: '{unit_search_value}' in department: {result['department'].name} (ID: {result['department'].id})")
            
            try:
                result['unit'] = Unit.objects.get(
                    department=result['department'],
                    name__iexact=unit_search_value,
                    is_active=True
                )
                logger.info(f"✅ Unit found: {result['unit'].name} (ID: {result['unit'].id}, Dept ID: {result['unit'].department_id})")
            except Unit.DoesNotExist:
                # Show ALL units with this name across all departments for debugging
                all_matching_units = Unit.objects.filter(
                    name__iexact=unit_search_value,
                    is_active=True
                ).select_related('department', 'department__business_function')
                
                if all_matching_units.exists():
                    unit_details = []
                    for u in all_matching_units:
                        unit_details.append({
                            'unit_id': u.id,
                            'unit_name': u.name,
                            'department_id': u.department_id,
                            'department_name': u.department.name,
                            'business_function': u.department.business_function.name
                        })
                    
                    logger.error(f"❌ Unit '{unit_search_value}' found in other departments: {unit_details}")
                    logger.error(f"Looking for department_id={result['department'].id}, but units belong to: {[u['department_id'] for u in unit_details]}")
                    
                    raise ValueError(
                        f"Unit '{unit_search_value}' exists but not in department '{result['department'].name}'. "
                        # f"Found in: {[f\"{u['department_name']} (ID: {u['department_id']})\" for u in unit_details]}. "
                        f"Expected department ID: {result['department'].id}"
                    )
                else:
                    # Show available units in the correct department
                    available_units = list(Unit.objects.filter(
                        department=result['department'],
                        is_active=True
                    ).values('id', 'name'))
                    
                    logger.error(f"❌ Unit '{unit_search_value}' not found at all. Available units in {result['department'].name}: {available_units}")
                    
                    raise ValueError(
                        f"Unit not found: '{unit_search_value}'. "
                        f"Available units in {result['department'].name}: "
                        f"{[u['name'] for u in available_units]}"
                    )
        else:
            result['unit'] = None
            logger.info("No unit specified - continuing without unit")
        
        # Job Function - try NAME or CODE
        try:
            result['job_function'] = JobFunction.objects.get(
                name__iexact=row_data['job_function_code'],
                is_active=True
            )
        except JobFunction.DoesNotExist:
            # Show available job functions
            available_jfs = JobFunction.objects.filter(is_active=True).values_list('name', flat=True)
            raise ValueError(f"Job Function not found: '{row_data['job_function_code']}'. Available: {list(available_jfs)}")
        
        # Position Group - try NAME
        try:
            result['position_group'] = PositionGroup.objects.get(
                name__iexact=row_data['position_group_code'],
                is_active=True
            )
        except PositionGroup.DoesNotExist:
            # Show available position groups
            available_pgs = PositionGroup.objects.filter(is_active=True).values_list('name', flat=True)
            raise ValueError(f"Position Group not found: '{row_data['position_group_code']}'. Available: {list(available_pgs)}")
        
        return result
    def _add_skills_from_string(self, job_description, skills_string):
        """Add skills from formatted string: SkillCode:ProfLevel:Mandatory|SkillCode2:..."""
        try:
            skill_items = skills_string.split('|')
            for item in skill_items:
                parts = item.split(':')
                if len(parts) >= 2:
                    skill_code = parts[0].strip()
                    prof_level = parts[1].strip().upper()
                    is_mandatory = parts[2].strip().lower() == 'true' if len(parts) > 2 else True
                    
                    try:
                        skill = Skill.objects.get(name__iexact=skill_code, is_active=True)
                        JobDescriptionSkill.objects.create(
                            job_description=job_description,
                            skill=skill,
                            proficiency_level=prof_level if prof_level in ['BASIC', 'INTERMEDIATE', 'ADVANCED', 'EXPERT'] else 'INTERMEDIATE',
                            is_mandatory=is_mandatory
                        )
                    except Skill.DoesNotExist:
                        logger.warning(f"Skill not found: {skill_code}")
        except Exception as e:
            logger.error(f"Error adding skills: {str(e)}")
    
    def _add_competencies_from_string(self, job_description, competencies_string):
        """Add competencies from formatted string"""
        try:
            comp_items = competencies_string.split('|')
            for item in comp_items:
                parts = item.split(':')
                if len(parts) >= 2:
                    comp_code = parts[0].strip()
                    prof_level = parts[1].strip().upper()
                    is_mandatory = parts[2].strip().lower() == 'true' if len(parts) > 2 else True
                    
                    try:
                        competency = BehavioralCompetency.objects.get(name__iexact=comp_code, is_active=True)
                        JobDescriptionBehavioralCompetency.objects.create(
                            job_description=job_description,
                            competency=competency,
                            proficiency_level=prof_level if prof_level in ['BASIC', 'INTERMEDIATE', 'ADVANCED', 'EXPERT'] else 'INTERMEDIATE',
                            is_mandatory=is_mandatory
                        )
                    except BehavioralCompetency.DoesNotExist:
                        logger.warning(f"Competency not found: {comp_code}")
        except Exception as e:
            logger.error(f"Error adding competencies: {str(e)}")
    
    def _add_resources_from_string(self, job_description, resources_string, resource_type):
        """Add resources from comma-separated string"""
        try:
            resource_names = [name.strip() for name in resources_string.split(',') if name.strip()]
            
            for name in resource_names:
                try:
                    if resource_type == 'business':
                        resource = JobBusinessResource.objects.get(name__iexact=name, is_active=True)
                        JobDescriptionBusinessResource.objects.create(
                            job_description=job_description,
                            resource=resource
                        )
                    elif resource_type == 'access':
                        access = AccessMatrix.objects.get(name__iexact=name, is_active=True)
                        JobDescriptionAccessMatrix.objects.create(
                            job_description=job_description,
                            access_matrix=access
                        )
                    elif resource_type == 'benefits':
                        benefit = CompanyBenefit.objects.get(name__iexact=name, is_active=True)
                        JobDescriptionCompanyBenefit.objects.create(
                            job_description=job_description,
                            benefit=benefit
                        )
                except Exception as e:
                    logger.warning(f"{resource_type} not found: {name}")
        except Exception as e:
            logger.error(f"Error adding {resource_type}: {str(e)}")
    
    @swagger_auto_schema(
    method='get',
    operation_description="""
    Download Excel template for bulk job description upload
    
    """,
    responses={
        200: openapi.Response(
            description="Excel template file",
            schema=openapi.Schema(
                type=openapi.TYPE_FILE,
                format='binary'
            )
        ),
        500: "Server error"
    }
)
    @action(detail=False, methods=['get'])
    def download_template(self, request):
        """Download Excel template for bulk upload"""
        try:
            # Check if openpyxl is available
            if not HAS_OPENPYXL:
                return Response(
                    {'error': 'Excel library (openpyxl) is not installed. Please contact administrator.'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            buffer = io.BytesIO()
            wb = Workbook()
            ws = wb.active
            ws.title = "Job Descriptions"
            
            # Define headers
            headers = [
                'Job Title*',
                'Business Function Code*',
                'Department Code*',
                'Unit Code',
                'Job Function Code*',
                'Position Group Code*',
                'Grading Level*',
                'Employee ID',
                'Job Purpose*',
                'Critical Duties (pipe | separated)',
                'Main KPIs (pipe | separated)',
                'Job Duties (pipe | separated)',
                'Requirements (pipe | separated)',
                'Skills (Code:Level:Mandatory|Code2:...)',
                'Competencies (Code:Level:Mandatory|Code2:...)',
                'Business Resources (comma separated)',
                'Access Rights (comma separated)',
                'Company Benefits (comma separated)'
            ]
            
            # Style the header row
            header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
            header_font = Font(bold=True, color="FFFFFF", size=11)
            header_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            border = Border(
                left=Side(style='thin'),
                right=Side(style='thin'),
                top=Side(style='thin'),
                bottom=Side(style='thin')
            )
            
            # Write and style headers
            for col_num, header in enumerate(headers, 1):
                cell = ws.cell(row=1, column=col_num)
                cell.value = header
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = header_alignment
                cell.border = border
            
            # Add sample data row
            sample_data = [
                'Senior Software Engineer',
                'IT',
                'Software Development',
                'Backend Team',
                'Engineering',
                'Senior',
                'G7',
                '',  # Empty Employee ID = auto-assign to all matching
                'Lead backend development and architecture decisions for enterprise applications',
                'Design system architecture|Lead code reviews|Mentor junior developers|Define technical standards',
                'Code quality > 90%|Sprint completion rate > 95%|Technical debt reduction by 20%',
                'Develop REST APIs|Database optimization|Unit testing|CI/CD pipeline management',
                "Bachelor's in CS|5+ years experience|Strong Python skills|Cloud experience required",
                'Python:EXPERT:true|SQL:ADVANCED:true|Docker:INTERMEDIATE:false|AWS:ADVANCED:true',
                'Leadership:ADVANCED:true|Communication:ADVANCED:true|Problem Solving:EXPERT:true',
                'Laptop,IDE License,Cloud Access',
                'GitHub Admin,AWS Console,Database Write',
                'Health Insurance,Annual Leave,Learning Budget,Remote Work'
            ]
            
            for col_num, value in enumerate(sample_data, 1):
                cell = ws.cell(row=2, column=col_num)
                cell.value = value
                cell.border = border
                cell.alignment = Alignment(wrap_text=True, vertical="top")
            
            # Set column widths
            column_widths = [25, 20, 20, 15, 20, 20, 12, 12, 40, 40, 40, 40, 40, 40, 40, 30, 30, 30]
            for col_num, width in enumerate(column_widths, 1):
                ws.column_dimensions[get_column_letter(col_num)].width = width
            
            # Set row heights
            ws.row_dimensions[1].height = 40
            ws.row_dimensions[2].height = 120
            
            # Add Instructions sheet
            ws_instructions = wb.create_sheet("Instructions")
            
            # FIXED: All rows must have exactly 2 columns
            instructions = [
                ["JOB DESCRIPTION BULK UPLOAD INSTRUCTIONS", ""],
                ["", ""],
                ["OVERVIEW", ""],
                ["", "This template allows you to create multiple job descriptions at once."],
                ["", "The system will automatically find and assign matching employees and vacant positions."],
                ["", ""],
                ["REQUIRED FIELDS (marked with *)", ""],
                ["Job Title", "The official job title (must match employee records exactly)"],
                ["Business Function Code", "Code of business function (e.g., IT, HR, FIN, OPS)"],
                ["Department Code", "Department name that exists in the system"],
                ["Job Function Code", "Job function name (e.g., Engineering, Management, Support)"],
                ["Position Group Code", "Position group/hierarchy name (e.g., Senior, Junior, Manager)"],
                ["Grading Level", "Grading level code (e.g., G1, G2, M, S, E)"],
                ["Job Purpose", "Main purpose and objectives of the role (minimum 5 characters)"],
                ["", ""],
                ["OPTIONAL FIELDS", ""],
                ["Unit Code", "Unit name if applicable (can be left empty)"],
                ["Employee ID", "IMPORTANT: If empty, creates JD for ALL matching employees + vacant positions!"],
                ["", "If filled, creates JD only for this specific employee"],
                ["Critical Duties", "Pipe-separated list: Duty1|Duty2|Duty3"],
                ["Main KPIs", "Pipe-separated list of key performance indicators"],
                ["Job Duties", "Pipe-separated list of daily duties"],
                ["Requirements", "Pipe-separated list: Bachelor's degree|5 years experience|Certification"],
                ["Skills", "Format: SkillName:Level:Mandatory|Skill2:Level:Mandatory"],
                ["", "Levels: BASIC, INTERMEDIATE, ADVANCED, EXPERT"],
                ["", "Mandatory: true or false"],
                ["", "Example: Python:EXPERT:true|SQL:ADVANCED:true"],
                ["Competencies", "Same format as Skills"],
                ["", "Example: Leadership:ADVANCED:true|Communication:EXPERT:true"],
                ["Business Resources", "Comma-separated: Laptop,Software License,Mobile Phone"],
                ["Access Rights", "Comma-separated: System Admin,Database Access,Report Viewer"],
                ["Company Benefits", "Comma-separated: Health Insurance,Bonus,Car Allowance"],
                ["", ""],
                ["AUTO-ASSIGNMENT LOGIC", ""],
                ["", "When Employee ID is EMPTY, the system will:"],
                ["1.", "Find ALL employees matching these criteria:"],
                ["", "  - Job Title (exact match, case-insensitive)"],
                ["", "  - Business Function"],
                ["", "  - Department"],
                ["", "  - Unit (if provided)"],
                ["", "  - Job Function"],
                ["", "  - Position Group"],
                ["", "  - Grading Level"],
                ["2.", "Find ALL vacant positions matching the same criteria"],
                ["3.", "Create one job description for EACH matching position"],
                ["", ""],
                ["Example:", "If 5 employees + 2 vacant positions match"],
                ["", "System creates 7 job descriptions from one row!"],
                ["", ""],
                ["IMPORTANT NOTES", ""],
                ["1.", "All codes must match existing records in the system exactly"],
                ["2.", "Job Title must match employee records exactly (case-insensitive)"],
                ["3.", "Leave Employee ID empty to auto-assign to all matching positions"],
                ["4.", "Fill Employee ID to assign to a specific employee only"],
                ["5.", "Delete the sample data row before uploading"],
                ["6.", "Upload options available:"],
                ["", "  - validate_only: Check data without creating (dry run)"],
                ["", "  - auto_assign_employees: Enable/disable auto-assignment"],
                ["", "  - skip_duplicates: Skip job descriptions that already exist"],
                ["", ""],
                ["UPLOAD PROCESS", ""],
                ["1.", "Fill in your data (one job description per row)"],
                ["2.", "Save the file"],
                ["3.", "Use POST /job-descriptions/bulk-upload/"],
                ["4.", "Select your file and set options"],
                ["5.", "Click Execute"],
                ["6.", "Review the results - success/failed/skipped counts"],
                ["", ""],
                ["TROUBLESHOOTING", ""],
                ["Department not found", "Check department name spelling"],
                ["No employees match", "Verify all criteria (job title, function, etc.)"],
                ["Multiple employees match", "This is OK! JDs created for all"],
                ["Skill not found", "Check skill names in system"],
                ["", ""],
                ["SUPPORT", ""],
                ["", "For questions, contact your HRIS administrator."],
            ]
            
            # Style instructions
            title_font = Font(bold=True, size=14, color="366092")
            section_font = Font(bold=True, size=11, color="2E7D32")
            
            for row_num, row_data in enumerate(instructions, 1):
                # Ensure we have exactly 2 columns
                col1 = row_data[0] if len(row_data) > 0 else ""
                col2 = row_data[1] if len(row_data) > 1 else ""
                
                ws_instructions.cell(row=row_num, column=1).value = col1
                ws_instructions.cell(row=row_num, column=2).value = col2
                
                # Apply formatting
                if row_num == 1:
                    ws_instructions.cell(row=row_num, column=1).font = title_font
                elif col1 in ["OVERVIEW", "REQUIRED FIELDS (marked with *)", "OPTIONAL FIELDS", 
                             "AUTO-ASSIGNMENT LOGIC", "IMPORTANT NOTES", "UPLOAD PROCESS", 
                             "TROUBLESHOOTING", "SUPPORT"]:
                    ws_instructions.cell(row=row_num, column=1).font = section_font
            
            ws_instructions.column_dimensions['A'].width = 30
            ws_instructions.column_dimensions['B'].width = 70
            
            # Save workbook
            wb.save(buffer)
            buffer.seek(0)
            
            # Create response
            response = HttpResponse(
                buffer.getvalue(),
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            filename = f"Job_Description_Bulk_Upload_Template_{datetime.now().strftime('%Y%m%d')}.xlsx"
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            
            logger.info(f"Template downloaded by {request.user.username}: {filename}")
            return response
            
        except Exception as e:
            logger.error(f"Error generating template: {str(e)}")
            logger.error(traceback.format_exc())
            return Response(
                {'error': f'Failed to generate template: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @swagger_auto_schema(
        method='post',
        operation_description="Export job descriptions to Excel",
        request_body=JobDescriptionExportSerializer,
        responses={
            200: openapi.Response(
                description="Excel file with job descriptions",
                schema=openapi.Schema(type=openapi.TYPE_FILE)
            )
        }
    )
    @action(detail=False, methods=['post'])
    def export_to_excel(self, request):
        """Export job descriptions to Excel"""
        try:
            serializer = JobDescriptionExportSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
            job_description_ids = serializer.validated_data.get('job_description_ids', [])
            include_details = serializer.validated_data.get('include_signatures', True)
            
            # Get queryset
            if job_description_ids:
                queryset = JobDescription.objects.filter(id__in=job_description_ids)
            else:
                queryset = self.filter_queryset(self.get_queryset())
            
            queryset = queryset.select_related(
                'business_function', 'department', 'unit', 'job_function', 
                'position_group', 'assigned_employee', 'reports_to',
                'created_by', 'line_manager_approved_by', 'employee_approved_by'
            ).prefetch_related(
                'sections', 'required_skills__skill', 
                'behavioral_competencies__competency',
                'business_resources__resource', 
                'access_rights__access_matrix',
                'company_benefits__benefit'
            )
            
            logger.info(f"Exporting {queryset.count()} job descriptions to Excel")
            
            # Create workbook
            buffer = io.BytesIO()
            wb = Workbook()
            
            # Summary sheet
            ws_summary = wb.active
            ws_summary.title = "Summary"
            self._create_summary_sheet(ws_summary, queryset)
            
            # Job Descriptions sheet
            ws_jd = wb.create_sheet("Job Descriptions")
            self._create_job_descriptions_sheet(ws_jd, queryset, include_details)
            
            # Skills sheet
            ws_skills = wb.create_sheet("Skills")
            self._create_skills_sheet(ws_skills, queryset)
            
            # Competencies sheet
            ws_comp = wb.create_sheet("Competencies")
            self._create_competencies_sheet(ws_comp, queryset)
            
            # Approval Status sheet
            if include_details:
                ws_approval = wb.create_sheet("Approval Status")
                self._create_approval_sheet(ws_approval, queryset)
            
            # Save workbook
            wb.save(buffer)
            buffer.seek(0)
            
            # Create response
            response = HttpResponse(
                buffer.getvalue(),
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            filename = f"Job_Descriptions_Export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            
            logger.info(f"Export completed: {filename}")
            return response
            
        except Exception as e:
            logger.error(f"Export error: {str(e)}")
            logger.error(traceback.format_exc())
            return Response(
                {'error': f'Export failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _create_summary_sheet(self, worksheet, queryset):
        """Create summary sheet with statistics"""
        # Title
        worksheet['A1'] = "JOB DESCRIPTIONS EXPORT SUMMARY"
        worksheet['A1'].font = Font(bold=True, size=14, color="366092")
        worksheet.merge_cells('A1:B1')
        
        # Statistics
        stats = [
            ["Export Date", datetime.now().strftime('%Y-%m-%d %H:%M:%S')],
            ["Total Job Descriptions", queryset.count()],
            ["", ""],
            ["By Status:", ""],
            ["Draft", queryset.filter(status='DRAFT').count()],
            ["Pending Line Manager", queryset.filter(status='PENDING_LINE_MANAGER').count()],
            ["Pending Employee", queryset.filter(status='PENDING_EMPLOYEE').count()],
            ["Approved", queryset.filter(status='APPROVED').count()],
            ["Rejected", queryset.filter(status='REJECTED').count()],
            ["Revision Required", queryset.filter(status='REVISION_REQUIRED').count()],
            ["", ""],
            ["By Assignment:", ""],
            ["With Employee", queryset.filter(assigned_employee__isnull=False).count()],
            ["Without Employee", queryset.filter(assigned_employee__isnull=True).count()],
        ]
        
        for row_num, (label, value) in enumerate(stats, 3):
            worksheet.cell(row=row_num, column=1).value = label
            worksheet.cell(row=row_num, column=2).value = value
            
            if label and not value:  # Section headers
                worksheet.cell(row=row_num, column=1).font = Font(bold=True)
        
        worksheet.column_dimensions['A'].width = 30
        worksheet.column_dimensions['B'].width = 20
    
    def _create_job_descriptions_sheet(self, worksheet, queryset, include_details):
        """Create main job descriptions sheet"""
        headers = [
            'Job Title', 'Business Function', 'Department', 'Unit', 
            'Job Function', 'Position Group', 'Grading Level',
            'Employee ID', 'Employee Name', 'Reports To',
            'Status', 'Job Purpose', 'Created Date', 'Created By'
        ]
        
        # Style header
        header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
        header_font = Font(bold=True, color="FFFFFF")
        
        for col_num, header in enumerate(headers, 1):
            cell = worksheet.cell(row=1, column=col_num)
            cell.value = header
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center")
        
        # Data rows
        for row_num, jd in enumerate(queryset, 2):
            data = [
                jd.job_title,
                jd.business_function.name if jd.business_function else '',
                jd.department.name if jd.department else '',
                jd.unit.name if jd.unit else '',
                jd.job_function.name if jd.job_function else '',
                jd.position_group.name if jd.position_group else '',
                jd.grading_level or '',
                jd.assigned_employee.employee_id if jd.assigned_employee else '',
                jd.assigned_employee.full_name if jd.assigned_employee else '',
                jd.reports_to.full_name if jd.reports_to else '',
                jd.get_status_display(),
                jd.job_purpose[:200] + '...' if len(jd.job_purpose) > 200 else jd.job_purpose,
                jd.created_at.strftime('%Y-%m-%d') if jd.created_at else '',
                jd.created_by.get_full_name() if jd.created_by else ''
            ]
            
            for col_num, value in enumerate(data, 1):
                worksheet.cell(row=row_num, column=col_num).value = value
        
        # Auto-adjust column widths
        for col_num in range(1, len(headers) + 1):
            worksheet.column_dimensions[get_column_letter(col_num)].width = 20
    
    def _create_skills_sheet(self, worksheet, queryset):
        """Create skills sheet"""
        headers = ['Job Title', 'Employee', 'Skill Name', 'Skill Group', 
                   'Proficiency Level', 'Mandatory']
        
        # Style header
        header_fill = PatternFill(start_color="2E7D32", end_color="2E7D32", fill_type="solid")
        header_font = Font(bold=True, color="FFFFFF")
        
        for col_num, header in enumerate(headers, 1):
            cell = worksheet.cell(row=1, column=col_num)
            cell.value = header
            cell.fill = header_fill
            cell.font = header_font
        
        # Data rows
        row_num = 2
        for jd in queryset:
            for skill_req in jd.required_skills.select_related('skill', 'skill__group').all():
                worksheet.cell(row=row_num, column=1).value = jd.job_title
                worksheet.cell(row=row_num, column=2).value = jd.assigned_employee.full_name if jd.assigned_employee else 'N/A'
                worksheet.cell(row=row_num, column=3).value = skill_req.skill.name
                worksheet.cell(row=row_num, column=4).value = skill_req.skill.group.name if skill_req.skill.group else 'N/A'
                worksheet.cell(row=row_num, column=5).value = skill_req.get_proficiency_level_display()
                worksheet.cell(row=row_num, column=6).value = 'Yes' if skill_req.is_mandatory else 'No'
                row_num += 1
        
        for col_num in range(1, len(headers) + 1):
            worksheet.column_dimensions[get_column_letter(col_num)].width = 20
    
    def _create_competencies_sheet(self, worksheet, queryset):
        """Create competencies sheet"""
        headers = ['Job Title', 'Employee', 'Competency Name', 'Competency Group', 
                   'Proficiency Level', 'Mandatory']
        
        # Style header
        header_fill = PatternFill(start_color="6A1B9A", end_color="6A1B9A", fill_type="solid")
        header_font = Font(bold=True, color="FFFFFF")
        
        for col_num, header in enumerate(headers, 1):
            cell = worksheet.cell(row=1, column=col_num)
            cell.value = header
            cell.fill = header_fill
            cell.font = header_font
        
        # Data rows
        row_num = 2
        for jd in queryset:
            for comp_req in jd.behavioral_competencies.select_related('competency', 'competency__group').all():
                worksheet.cell(row=row_num, column=1).value = jd.job_title
                worksheet.cell(row=row_num, column=2).value = jd.assigned_employee.full_name if jd.assigned_employee else 'N/A'
                worksheet.cell(row=row_num, column=3).value = comp_req.competency.name
                worksheet.cell(row=row_num, column=4).value = comp_req.competency.group.name if comp_req.competency.group else 'N/A'
                worksheet.cell(row=row_num, column=5).value = comp_req.get_proficiency_level_display()
                worksheet.cell(row=row_num, column=6).value = 'Yes' if comp_req.is_mandatory else 'No'
                row_num += 1
        
        for col_num in range(1, len(headers) + 1):
            worksheet.column_dimensions[get_column_letter(col_num)].width = 20
    
    def _create_approval_sheet(self, worksheet, queryset):
        """Create approval status sheet"""
        headers = ['Job Title', 'Employee', 'Status', 
                   'Line Manager Approved', 'LM Approved By', 'LM Approved Date',
                   'Employee Approved', 'Emp Approved By', 'Emp Approved Date']
        
        # Style header
        header_fill = PatternFill(start_color="1565C0", end_color="1565C0", fill_type="solid")
        header_font = Font(bold=True, color="FFFFFF")
        
        for col_num, header in enumerate(headers, 1):
            cell = worksheet.cell(row=1, column=col_num)
            cell.value = header
            cell.fill = header_fill
            cell.font = header_font
        
        # Data rows
        for row_num, jd in enumerate(queryset, 2):
            worksheet.cell(row=row_num, column=1).value = jd.job_title
            worksheet.cell(row=row_num, column=2).value = jd.assigned_employee.full_name if jd.assigned_employee else 'N/A'
            worksheet.cell(row=row_num, column=3).value = jd.get_status_display()
            worksheet.cell(row=row_num, column=4).value = 'Yes' if jd.line_manager_approved_at else 'No'
            worksheet.cell(row=row_num, column=5).value = jd.line_manager_approved_by.get_full_name() if jd.line_manager_approved_by else ''
            worksheet.cell(row=row_num, column=6).value = jd.line_manager_approved_at.strftime('%Y-%m-%d') if jd.line_manager_approved_at else ''
            worksheet.cell(row=row_num, column=7).value = 'Yes' if jd.employee_approved_at else 'No'
            worksheet.cell(row=row_num, column=8).value = jd.employee_approved_by.get_full_name() if jd.employee_approved_by else ''
            worksheet.cell(row=row_num, column=9).value = jd.employee_approved_at.strftime('%Y-%m-%d') if jd.employee_approved_at else ''
        
        for col_num in range(1, len(headers) + 1):
            worksheet.column_dimensions[get_column_letter(col_num)].width = 20
    
    @action(detail=False, methods=['get'])
    def pending_approvals(self, request):
        """Get job descriptions pending approval for current user"""
        try:
            user = request.user
            
            logger.info(f"Getting pending approvals for user: {user.username} (ID: {user.id})")
            
            # Get employee record for this user (if exists)
            employee = None
            try:
                employee = user.employee_profile
                logger.info(f"Found employee profile: {employee.employee_id} - {employee.full_name}")
            except:
                logger.warning(f"No employee profile found for user {user.username}")
            
            # Job descriptions where user is the reports_to manager and needs to approve
            line_manager_pending = JobDescription.objects.filter(
                status='PENDING_LINE_MANAGER',
                reports_to__user=user
            ).select_related('business_function', 'department', 'job_function', 'assigned_employee', 'created_by')
            
            logger.info(f"Line manager pending count: {line_manager_pending.count()}")
            
            # Job descriptions where user is the assigned employee and needs to approve
            employee_pending = JobDescription.objects.none()  # Default to empty queryset
            if employee:
                employee_pending = JobDescription.objects.filter(
                    status='PENDING_EMPLOYEE',
                    assigned_employee__user=user
                ).select_related('business_function', 'department', 'job_function', 'assigned_employee', 'created_by')
            
            logger.info(f"Employee pending count: {employee_pending.count()}")
            
            # Use proper serializer
            line_manager_serializer = JobDescriptionListSerializer(
                line_manager_pending, 
                many=True, 
                context={'request': request}
            )
            employee_serializer = JobDescriptionListSerializer(
                employee_pending, 
                many=True, 
                context={'request': request}
            )
            
            response_data = {
                'pending_as_line_manager': {
                    'count': line_manager_pending.count(),
                    'job_descriptions': line_manager_serializer.data
                },
                'pending_as_employee': {
                    'count': employee_pending.count(),
                    'job_descriptions': employee_serializer.data
                },
                'total_pending': line_manager_pending.count() + employee_pending.count(),
                'user_info': {
                    'user_id': user.id,
                    'username': user.username,
                    'employee_id': employee.employee_id if employee else None,
                    'employee_name': employee.full_name if employee else None,
                    'has_employee_profile': employee is not None
                }
            }
            
            logger.info(f"Returning pending approvals response: {response_data['total_pending']} total")
            
            return Response(response_data)
            
        except Exception as e:
            logger.error(f"Error getting pending approvals: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return Response(
                {'error': f'Failed to get pending approvals: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def perform_create(self, serializer):
        """Set created_by when creating"""
        serializer.save(created_by=self.request.user)
    
    def perform_update(self, serializer):
        """Set updated_by when updating"""
        serializer.save(updated_by=self.request.user)


    def _create_enhanced_pdf(self, job_description, buffer):
        """Create an enhanced, comprehensive PDF for job description with better formatting"""
        try:
            # Enhanced page setup with better margins
            doc = SimpleDocTemplate(
                buffer,
                pagesize=A4,
                rightMargin=1.5*cm,
                leftMargin=1.5*cm,
                topMargin=2*cm,
                bottomMargin=2*cm,
                title=f"Job Description - {job_description.job_title}"
            )
            
            # Enhanced styles
            styles = getSampleStyleSheet()
            
            # Custom styles for better formatting
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=18,
                spaceAfter=20,
                alignment=TA_CENTER,
                textColor=colors.darkblue,
                fontName='Helvetica-Bold'
            )
            
            section_header_style = ParagraphStyle(
                'SectionHeader',
                parent=styles['Heading2'],
                fontSize=14,
                spaceAfter=12,
                spaceBefore=16,
                textColor=colors.darkblue,
                fontName='Helvetica-Bold',
                borderWidth=1,
                borderColor=colors.darkblue,
                borderPadding=5
            )
            
            subsection_header_style = ParagraphStyle(
                'SubsectionHeader',
                parent=styles['Heading3'],
                fontSize=12,
                spaceAfter=8,
                spaceBefore=12,
                textColor=colors.darkgreen,
                fontName='Helvetica-Bold'
            )
            
            content_style = ParagraphStyle(
                'ContentStyle',
                parent=styles['Normal'],
                fontSize=10,
                spaceAfter=8,
                alignment=TA_JUSTIFY,
                fontName='Helvetica'
            )
            
            bullet_style = ParagraphStyle(
                'BulletStyle',
                parent=styles['Normal'],
                fontSize=10,
                spaceAfter=6,
                leftIndent=20,
                fontName='Helvetica'
            )
            
            small_text_style = ParagraphStyle(
                'SmallText',
                parent=styles['Normal'],
                fontSize=9,
                spaceAfter=4,
                fontName='Helvetica'
            )
            
            story = []
            
            # HEADER SECTION
            story.append(Paragraph("JOB DESCRIPTION", title_style))
            story.append(Spacer(1, 0.3*inch))
            
            # Job title with styling
            job_title_style = ParagraphStyle(
                'JobTitle',
                parent=styles['Heading1'],
                fontSize=16,
                alignment=TA_CENTER,
                textColor=colors.darkred,
                fontName='Helvetica-Bold',
                spaceAfter=20
            )
            story.append(Paragraph(job_description.job_title, job_title_style))
            
            # Status badge
            status_color = self._get_status_color(job_description.status)
            status_style = ParagraphStyle(
                'StatusBadge',
                parent=styles['Normal'],
                fontSize=10,
                alignment=TA_CENTER,
                backColor=status_color,
                textColor=colors.white if status_color != colors.yellow else colors.black,
                borderWidth=1,
                borderColor=colors.black,
                borderPadding=5
            )
            story.append(Paragraph(f"Status: {job_description.get_status_display()}", status_style))
            story.append(Spacer(1, 0.2*inch))
            
            # ORGANIZATIONAL INFORMATION
            story.append(Paragraph("ORGANIZATIONAL INFORMATION", section_header_style))
            
            employee_info = job_description.get_employee_info()
            manager_info = job_description.get_manager_info()
            
            org_data = [
                ['Field', 'Information'],
                ['Job Title', job_description.job_title],
                ['Business Function', job_description.business_function.name if job_description.business_function else 'N/A'],
                ['Department', job_description.department.name if job_description.department else 'N/A'],
                ['Unit', job_description.unit.name if job_description.unit else 'N/A'],
                ['Job Function', job_description.job_function.name if job_description.job_function else 'N/A'],
                ['Position Group', job_description.position_group.name if job_description.position_group else 'N/A'],
                ['Grading Level', job_description.grading_level or 'N/A'],
                ['Employee', f"{employee_info['name']} ({employee_info['employee_id']})" if employee_info else 'No Employee Assigned'],
                ['Reports To', manager_info['name'] if manager_info else 'N/A'],
                ['Created Date', job_description.created_at.strftime('%d/%m/%Y') if job_description.created_at else 'N/A']
            ]
            
            org_table = Table(org_data, colWidths=[4*cm, 12*cm])
            org_table.setStyle(TableStyle([
                # Header row
                ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 11),
                
                # Data rows
                ('BACKGROUND', (0, 1), (0, -1), colors.lightgrey),
                ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
                ('FONTNAME', (1, 1), (1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 10),
                
                # Alignment and padding
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                
                # Grid
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                
                # Alternating row colors for better readability
                ('BACKGROUND', (0, 2), (-1, 2), colors.white),
                ('BACKGROUND', (0, 4), (-1, 4), colors.white),
                ('BACKGROUND', (0, 6), (-1, 6), colors.white),
                ('BACKGROUND', (0, 8), (-1, 8), colors.white),
                ('BACKGROUND', (0, 10), (-1, 10), colors.white),
            ]))
            
            story.append(org_table)
            story.append(Spacer(1, 0.2*inch))
            
            # JOB PURPOSE
            if job_description.job_purpose:
                story.append(Paragraph("JOB PURPOSE", section_header_style))
                formatted_purpose = self._format_long_text(job_description.job_purpose, content_style)
                story.append(formatted_purpose)
                story.append(Spacer(1, 0.15*inch))
            
            # JOB DESCRIPTION SECTIONS (ENHANCED WITH BETTER FORMATTING)
            if hasattr(job_description, 'sections') and job_description.sections.exists():
                story.append(Paragraph("JOB DUTIES", section_header_style))
                
                # Group sections by type for better organization
                sections_by_type = {}
                for section in job_description.sections.all().order_by('order'):
                    section_type = section.get_section_type_display()
                    if section_type not in sections_by_type:
                        sections_by_type[section_type] = []
                    sections_by_type[section_type].append(section)
                
                # Render grouped sections
                for section_type, sections in sections_by_type.items():
                    story.append(Paragraph(section_type.upper(), subsection_header_style))
                    
                    for section in sections:
                        # Parse content into bullet points if it contains bullets
                        content = section.content.strip()
                        
                        # Split by common bullet indicators
                        import re
                        bullet_points = re.split(r'[•●▪︎\-]\s*', content)
                        bullet_points = [bp.strip() for bp in bullet_points if bp.strip()]
                        
                        if len(bullet_points) > 1:
                            # Multiple bullet points found
                            for point in bullet_points:
                                if point:
                                    bullet_text = f"• {point}"
                                    story.append(Paragraph(bullet_text, bullet_style))
                        else:
                            # Single paragraph
                            formatted_content = self._format_long_text(content, content_style)
                            story.append(formatted_content)
                        
                        story.append(Spacer(1, 0.1*inch))
            
            # REQUIREMENTS SECTION (ENHANCED)
            story.append(Paragraph("REQUIREMENTS", section_header_style))
            
            # Create a structured requirements table
            req_data = []
            
            # Educational Requirements
            if job_description.business_function or job_description.department:
                story.append(Paragraph("Educational Qualifications", subsection_header_style))
                
                # Parse requirements from job description sections
                requirements_section = job_description.sections.filter(section_type='REQUIREMENTS').first()
                if requirements_section:
                    req_content = requirements_section.content.strip()
                    req_bullets = re.split(r'[•●▪︎\-]\s*', req_content)
                    req_bullets = [rb.strip() for rb in req_bullets if rb.strip()]
                    
                    for req in req_bullets:
                        if req:
                            story.append(Paragraph(f"• {req}", bullet_style))
                
                story.append(Spacer(1, 0.1*inch))
            
            # REQUIRED SKILLS
            if hasattr(job_description, 'required_skills') and job_description.required_skills.exists():
                story.append(Paragraph("REQUIRED SKILLS", section_header_style))
                
                skills_data = [['Skill Name', 'Skill Group', 'Proficiency Level', 'Mandatory']]
                
                for skill_req in job_description.required_skills.select_related('skill', 'skill__group').all():
                    skills_data.append([
                        skill_req.skill.name,
                        skill_req.skill.group.name if skill_req.skill.group else 'N/A',
                        skill_req.get_proficiency_level_display(),
                        'Yes' if skill_req.is_mandatory else 'No'
                    ])
                
                skills_table = Table(skills_data, colWidths=[5*cm, 3.5*cm, 3*cm, 2*cm])
                skills_table.setStyle(TableStyle([
                    # Header
                    ('BACKGROUND', (0, 0), (-1, 0), colors.darkgreen),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    
                    # Data
                    ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 1), (-1, -1), 9),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('LEFTPADDING', (0, 0), (-1, -1), 6),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                    ('TOPPADDING', (0, 0), (-1, -1), 4),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                    
                    # Zebra striping
                    *[('BACKGROUND', (0, i), (-1, i), colors.lightgrey if i % 2 == 0 else colors.white)
                      for i in range(1, len(skills_data))]
                ]))
                
                story.append(skills_table)
                story.append(Spacer(1, 0.15*inch))
            
            # BEHAVIORAL COMPETENCIES
            if hasattr(job_description, 'behavioral_competencies') and job_description.behavioral_competencies.exists():
                story.append(Paragraph("BEHAVIORAL COMPETENCIES", section_header_style))
                
                comp_data = [['Competency Name', 'Competency Group', 'Proficiency Level', 'Mandatory']]
                
                for comp_req in job_description.behavioral_competencies.select_related('competency', 'competency__group').all():
                    comp_data.append([
                        comp_req.competency.name,
                        comp_req.competency.group.name if comp_req.competency.group else 'N/A',
                        comp_req.get_proficiency_level_display(),
                        'Yes' if comp_req.is_mandatory else 'No'
                    ])
                
                comp_table = Table(comp_data, colWidths=[5*cm, 3.5*cm, 3*cm, 2*cm])
                comp_table.setStyle(TableStyle([
                    # Header
                    ('BACKGROUND', (0, 0), (-1, 0), colors.purple),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    
                    # Data
                    ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 1), (-1, -1), 9),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('LEFTPADDING', (0, 0), (-1, -1), 6),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                    ('TOPPADDING', (0, 0), (-1, -1), 4),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                    
                    # Zebra striping
                    *[('BACKGROUND', (0, i), (-1, i), colors.lightgrey if i % 2 == 0 else colors.white)
                      for i in range(1, len(comp_data))]
                ]))
                
                story.append(comp_table)
                story.append(Spacer(1, 0.15*inch))
            
            # BUSINESS RESOURCES
            resources_sections = []
            
            # Business Resources
            if hasattr(job_description, 'business_resources') and job_description.business_resources.exists():
                business_resources = [br.resource.name for br in job_description.business_resources.select_related('resource').all()]
                if business_resources:
                    resources_sections.append(('Business Resources', business_resources))
            
            # Access Rights
            if hasattr(job_description, 'access_rights') and job_description.access_rights.exists():
                access_rights = [ar.access_matrix.name for ar in job_description.access_rights.select_related('access_matrix').all()]
                if access_rights:
                    resources_sections.append(('Access Rights', access_rights))
            
            # Company Benefits
            if hasattr(job_description, 'company_benefits') and job_description.company_benefits.exists():
                benefits = [cb.benefit.name for cb in job_description.company_benefits.select_related('benefit').all()]
                if benefits:
                    resources_sections.append(('Company Benefits', benefits))
            
            if resources_sections:
                story.append(Paragraph("RESOURCES & BENEFITS", section_header_style))
                
                for section_name, items in resources_sections:
                    story.append(Paragraph(section_name, subsection_header_style))
                    
                    for item in items:
                        bullet_text = f"• {item}"
                        story.append(Paragraph(bullet_text, bullet_style))
                    
                    story.append(Spacer(1, 0.1*inch))
            
            # APPROVAL INFORMATION
            story.append(Paragraph("APPROVAL INFORMATION", section_header_style))
            
            approval_data = [
                ['Approval Stage', 'Status', 'Approved By', 'Date', 'Comments']
            ]
            
            # Line Manager Approval
            lm_status = 'Approved' if job_description.line_manager_approved_at else 'Pending'
            lm_by = job_description.line_manager_approved_by.get_full_name() if job_description.line_manager_approved_by else 'N/A'
            lm_date = job_description.line_manager_approved_at.strftime('%d/%m/%Y') if job_description.line_manager_approved_at else 'N/A'
            lm_comments = job_description.line_manager_comments[:50] + '...' if len(job_description.line_manager_comments) > 50 else job_description.line_manager_comments
            
            approval_data.append(['Line Manager', lm_status, lm_by, lm_date, lm_comments or 'N/A'])
            
            # Employee Approval
            emp_status = 'Approved' if job_description.employee_approved_at else 'Pending'
            emp_by = job_description.employee_approved_by.get_full_name() if job_description.employee_approved_by else 'N/A'
            emp_date = job_description.employee_approved_at.strftime('%d/%m/%Y') if job_description.employee_approved_at else 'N/A'
            emp_comments = job_description.employee_comments[:50] + '...' if len(job_description.employee_comments) > 50 else job_description.employee_comments
            
            approval_data.append(['Employee', emp_status, emp_by, emp_date, emp_comments or 'N/A'])
            
            approval_table = Table(approval_data, colWidths=[3*cm, 2.5*cm, 4*cm, 3*cm, 4*cm])
            approval_table.setStyle(TableStyle([
                # Header
                ('BACKGROUND', (0, 0), (-1, 0), colors.navy),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                
                # Data
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                
                # Status-specific coloring
                ('BACKGROUND', (1, 1), (1, 1), colors.lightgreen if lm_status == 'Approved' else colors.lightyellow),
                ('BACKGROUND', (1, 2), (1, 2), colors.lightgreen if emp_status == 'Approved' else colors.lightyellow),
            ]))
            
            story.append(approval_table)
            story.append(Spacer(1, 0.2*inch))
            
            # DOCUMENT INFORMATION
            story.append(Paragraph("DOCUMENT INFORMATION", section_header_style))
            
            doc_info_data = [
                ['Document ID', str(job_description.id)[:8] + '...'],
                ['Created By', job_description.created_by.get_full_name() if job_description.created_by else 'System'],
                ['Created Date', job_description.created_at.strftime('%d/%m/%Y %H:%M') if job_description.created_at else 'N/A'],
                ['Last Updated', job_description.updated_at.strftime('%d/%m/%Y %H:%M') if job_description.updated_at else 'N/A'],
                ['Updated By', job_description.updated_by.get_full_name() if job_description.updated_by else 'N/A'],
                ['Generated', datetime.now().strftime('%d/%m/%Y %H:%M')],
                ['Status', f"{job_description.get_status_display()} ({job_description.status})"]
            ]
            
            doc_info_table = Table(doc_info_data, colWidths=[4*cm, 10*cm])
            doc_info_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.lightblue),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ]))
            
            story.append(doc_info_table)
            
            # Page break before signatures if approved
            if job_description.status == 'APPROVED':
                story.append(PageBreak())
                
                # SIGNATURES PAGE
                story.append(Paragraph("DIGITAL SIGNATURES", section_header_style))
                story.append(Spacer(1, 0.3*inch))
                
                signature_data = []
                
                # Line Manager Signature
                if job_description.line_manager_approved_by:
                    signature_data.append([
                        'Line Manager Approval:',
                        f"{job_description.line_manager_approved_by.get_full_name()}\n"
                        f"Date: {job_description.line_manager_approved_at.strftime('%d/%m/%Y %H:%M')}\n"
                        f"{'Signature on file' if job_description.line_manager_signature else 'No signature file'}"
                    ])
                
                # Employee Signature
                if job_description.employee_approved_by:
                    signature_data.append([
                        'Employee Approval:',
                        f"{job_description.employee_approved_by.get_full_name()}\n"
                        f"Date: {job_description.employee_approved_at.strftime('%d/%m/%Y %H:%M')}\n"
                        f"{'Signature on file' if job_description.employee_signature else 'No signature file'}"
                    ])
                
                if signature_data:
                    signature_table = Table(signature_data, colWidths=[4*cm, 10*cm], rowHeights=[3*cm] * len(signature_data))
                    signature_table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (0, -1), colors.lightgreen),
                        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
                        ('FONTSIZE', (0, 0), (-1, -1), 10),
                        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                        ('LEFTPADDING', (0, 0), (-1, -1), 8),
                        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                        ('TOPPADDING', (0, 0), (-1, -1), 8),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                        ('GRID', (0, 0), (-1, -1), 2, colors.darkgreen),
                    ]))
                    
                    story.append(signature_table)
            
            # Build the PDF
            doc.build(story)
            return buffer
            
        except Exception as e:
            logger.error(f"Error creating enhanced PDF: {str(e)}")
            raise
    def _format_long_text(self, text, style, max_line_length=80):
        """Format long text to prevent layout issues"""
        if not text:
            return Paragraph("N/A", style)
        
        # Clean and prepare text
        text = str(text).strip()
        
        # Replace multiple spaces and line breaks
        import re
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\n+', '<br/>', text)
        
        # If text is very long, add line breaks at natural points
        if len(text) > max_line_length:
            words = text.split(' ')
            formatted_lines = []
            current_line = []
            current_length = 0
            
            for word in words:
                word_length = len(word)
                if current_length + word_length + 1 <= max_line_length:
                    current_line.append(word)
                    current_length += word_length + 1
                else:
                    if current_line:
                        formatted_lines.append(' '.join(current_line))
                    current_line = [word]
                    current_length = word_length
            
            if current_line:
                formatted_lines.append(' '.join(current_line))
            
            text = '<br/>'.join(formatted_lines)
        
        return Paragraph(text, style)
    
    def _get_status_color(self, status):
        """Get color for status"""
        status_colors = {
            'DRAFT': colors.grey,
            'PENDING_LINE_MANAGER': colors.orange,
            'PENDING_EMPLOYEE': colors.blue,
            'APPROVED': colors.green,
            'REJECTED': colors.red,
            'REVISION_REQUIRED': colors.purple,
        }
        return status_colors.get(status, colors.grey)
    
    # Update the download_pdf method in your ViewSet
    @action(detail=True, methods=['get'])
    def download_pdf(self, request, pk=None):
        """Download job description as enhanced PDF"""
        
        if not HAS_REPORTLAB:
            return HttpResponse("PDF library not available", status=500, content_type='text/plain')
        
        try:
            job_description = self.get_object()
            logger.info(f"Creating enhanced PDF for: {job_description.job_title}")
            
            buffer = BytesIO()
            
            try:
                # Use the enhanced PDF generator
                self._create_enhanced_pdf(job_description, buffer)
                logger.info("Enhanced PDF created successfully")
            except Exception as pdf_error:
                logger.error(f"Enhanced PDF creation failed: {str(pdf_error)}")
                # Fallback to simple PDF
                try:
                    self._create_simple_pdf(job_description, buffer)
                    logger.info("Fallback to simple PDF successful")
                except:
                    return HttpResponse("PDF creation failed", status=500, content_type='text/plain')
            
            buffer.seek(0)
            pdf_data = buffer.getvalue()
            
            if len(pdf_data) == 0:
                return HttpResponse("PDF creation failed", status=500, content_type='text/plain')
            
            # Enhanced filename with more info
            safe_title = "".join(c for c in job_description.job_title if c.isalnum() or c in (' ', '-', '_'))
            safe_title = safe_title.strip()[:30]
            
            employee_info = job_description.get_employee_info()
            employee_part = ""
            if employee_info:
                safe_employee = "".join(c for c in employee_info['name'] if c.isalnum() or c in (' ', '-', '_'))
                employee_part = f"_{safe_employee.replace(' ', '_')[:20]}"
            
            status_suffix = ""
            if job_description.status == 'APPROVED':
                status_suffix = "_APPROVED"
            elif job_description.status in ['PENDING_LINE_MANAGER', 'PENDING_EMPLOYEE']:
                status_suffix = "_PENDING"
            elif job_description.status == 'DRAFT':
                status_suffix = "_DRAFT"
            
            filename = f"JD_{safe_title.replace(' ', '_')}{employee_part}{status_suffix}_{datetime.now().strftime('%Y%m%d')}.pdf"
            
            response = HttpResponse(pdf_data, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            response['Content-Length'] = len(pdf_data)
            response['Cache-Control'] = 'no-cache'
            
            logger.info(f"Enhanced PDF response created: {filename} ({len(pdf_data)} bytes)")
            return response
            
        except Exception as e:
            logger.error(f"PDF error: {str(e)}")
            return HttpResponse(f"PDF Error: {str(e)}", status=500, content_type='text/plain')
    

class JobBusinessResourceViewSet(viewsets.ModelViewSet):
    """ViewSet for Job Business Resources"""
    
    queryset = JobBusinessResource.objects.all()
    serializer_class = JobBusinessResourceSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['is_active']
    search_fields = ['name', 'description']
    ordering = ['name']
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class AccessMatrixViewSet(viewsets.ModelViewSet):
    """ViewSet for Access Matrix"""
    
    queryset = AccessMatrix.objects.all()
    serializer_class = AccessMatrixSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['is_active']
    search_fields = ['name', 'description']
    ordering = ['name']
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class CompanyBenefitViewSet(viewsets.ModelViewSet):
    """ViewSet for Company Benefits"""
    
    queryset = CompanyBenefit.objects.all()
    serializer_class = CompanyBenefitSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['is_active']
    search_fields = ['name', 'description']
    ordering = ['name']
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class JobDescriptionStatsViewSet(viewsets.ViewSet):
    """ViewSet for Job Description Statistics"""
    
    permission_classes = [IsAuthenticated]
    
    def list(self, request):
        """Get comprehensive statistics"""
        queryset = JobDescription.objects.all()
        
        # Apply filters if provided
        jd_filter = JobDescriptionFilter(queryset, request.query_params)
        queryset = jd_filter.filter()
        
        total_job_descriptions = queryset.count()
        
        # By status
        status_stats = {}
        for status_choice in JobDescription.STATUS_CHOICES:
            status_code = status_choice[0]
            count = queryset.filter(status=status_code).count()
            if count > 0:
                status_stats[status_choice[1]] = count
        
        # By department
        department_stats = {}
        dept_counts = queryset.values('department__name').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        for item in dept_counts:
            if item['department__name']:
                department_stats[item['department__name']] = item['count']
        
        # By business function
        function_stats = {}
        func_counts = queryset.values('business_function__name').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        for item in func_counts:
            if item['business_function__name']:
                function_stats[item['business_function__name']] = item['count']
        
        # By job function
        job_function_stats = {}
        jf_counts = queryset.values('job_function__name').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        for item in jf_counts:
            if item['job_function__name']:
                job_function_stats[item['job_function__name']] = item['count']
        
        # Pending approvals by type
        pending_line_manager = queryset.filter(status='PENDING_LINE_MANAGER').count()
        pending_employee = queryset.filter(status='PENDING_EMPLOYEE').count()
        
        # Employee assignment breakdown
        total_assigned = queryset.filter(assigned_employee__isnull=False).count()
        
        # Recent activities
        recent_activities = JobDescriptionActivity.objects.select_related(
            'job_description', 'performed_by'
        ).order_by('-performed_at')[:10]
        
        return Response({
            'total_job_descriptions': total_job_descriptions,
            'status_breakdown': status_stats,
            'department_breakdown': department_stats,
            'business_function_breakdown': function_stats,
            'job_function_breakdown': job_function_stats,
            'assignment_breakdown': {
                'total_assigned': total_assigned,
            },
            'pending_approvals': {
                'total': pending_line_manager + pending_employee,
                'pending_line_manager': pending_line_manager,
                'pending_employee': pending_employee
            },
            'recent_activities': JobDescriptionActivitySerializer(recent_activities, many=True).data,
            'approval_workflow_summary': {
                'draft': queryset.filter(status='DRAFT').count(),
                'pending_line_manager': pending_line_manager,
                'pending_employee': pending_employee,
                'approved': queryset.filter(status='APPROVED').count(),
                'rejected': queryset.filter(status='REJECTED').count(),
                'revision_required': queryset.filter(status='REVISION_REQUIRED').count()
            }
        })