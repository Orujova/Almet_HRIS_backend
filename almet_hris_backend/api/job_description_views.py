# api/job_description_views.py - UPDATED: Smart employee selection based on organizational hierarchy

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
from datetime import datetime
from io import BytesIO
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

    from openpyxl.utils import get_column_letter
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False

logger = logging.getLogger(__name__)

# Job Description Models - CRITICAL IMPORTS
from .job_description_models import (
    JobDescription, 
    JobBusinessResource, 
    AccessMatrix,
    CompanyBenefit, 
    JobBusinessResourceItem,
AccessMatrixItem,
    CompanyBenefitItem, 
   normalize_grading_level
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
    EmployeeBasicSerializer,
JobBusinessResourceItemSerializer,AccessMatrixItemSerializer,CompanyBenefitItemSerializer
)


# Core Models
from .models import (
    BusinessFunction, 
    Department, 
    Unit, 
    PositionGroup, 
    JobFunction,
    VacantPosition
)

from .models import BusinessFunction, Department, Unit, PositionGroup, JobFunction,VacantPosition


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
        """FIXED: Include nested items in prefetch"""
        return JobDescription.objects.select_related(
            'business_function', 'department', 'unit', 'job_function', 'position_group',
            'reports_to', 'assigned_employee', 'created_by', 'updated_by',
            'line_manager_approved_by', 'employee_approved_by'
        ).prefetch_related(
            'sections',
            'required_skills__skill__group',
            'behavioral_competencies__competency__group',
            
            # 🔥 FIX: Prefetch with nested items
            'business_resources__resource__items',
            'business_resources__specific_items',  # ✅ Add this
            
            'access_rights__access_matrix__items',
            'access_rights__specific_items',  # ✅ Add this
            
            'company_benefits__benefit__items',
            'company_benefits__specific_items'  # ✅ Add this
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
            grading_levels = request.data.get('grading_levels')
            if isinstance(grading_levels, str):
                grading_levels = [grading_levels]
            elif not isinstance(grading_levels, list):
                grading_levels = []
            max_preview = request.data.get('max_preview', 50)
            include_vacancies = request.data.get('include_vacancies', True)
            
            # Validate required fields
            required_fields = {
                'job_title': job_title,
                'business_function': business_function_id,
                'department': department_id,
                'job_function': job_function_id,
                'position_group': position_group_id,
                'grading_levels': grading_levels
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
                grading_levels=grading_levels 
            )
            
            # NEW: Get eligible vacant positions
            eligible_vacancies = self._get_eligible_vacant_positions(
                job_title=job_title,
                business_function_id=business_function_id,
                department_id=department_id,
                unit_id=unit_id,
                job_function_id=job_function_id,
                position_group_id=position_group_id,
                grading_levels=grading_levels 
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
                    'grading_levels': grading_levels
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
                                     position_group_id=None, grading_levels=None):
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
        if grading_levels:
            if isinstance(grading_levels, str):
                grading_levels = [grading_levels]
            
            normalized_targets = [normalize_grading_level(gl.strip()) for gl in grading_levels]
            
            logger.info(f"Target grading levels: {grading_levels} (normalized: {normalized_targets})")
            
            all_vacancies = list(queryset)
            matching_vacancies = []
            
            for vacancy in all_vacancies:
                vac_grade = vacancy.grading_level.strip() if vacancy.grading_level else ""
                vac_normalized = normalize_grading_level(vac_grade)
                
                if vac_normalized in normalized_targets:
                    matching_vacancies.append(vacancy.id)
                    logger.info(f"Vacancy match: {vacancy.position_id} - '{vac_grade}' IN {normalized_targets}")
            
            queryset = queryset.filter(id__in=matching_vacancies)
            logger.info(f"After grading_levels filter: {queryset.count()}")
        
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
    """UPDATED: Business resources with nested items support"""
    
    queryset = JobBusinessResource.objects.all()
    serializer_class = JobBusinessResourceSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['is_active']
    search_fields = ['name', 'description']
    ordering = ['name']
    
    def get_queryset(self):
        """Include items in queryset"""
        return JobBusinessResource.objects.prefetch_related('items').all()
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    @action(detail=True, methods=['get'])
    def items(self, request, pk=None):
        """🆕 Get all items for a resource"""
        resource = self.get_object()
        items = resource.items.filter(is_active=True)
        serializer = JobBusinessResourceItemSerializer(items, many=True)
        return Response({
            'resource': JobBusinessResourceSerializer(resource).data,
            'items': serializer.data,
            'total_items': items.count()
        })
    
    
    @action(detail=True, methods=['post'])
    def add_item(self, request, pk=None):
        """🆕 Add a new item to this resource"""
        resource = self.get_object()
        
        data = request.data.copy()
        data['resource'] = resource.id
        
        serializer = JobBusinessResourceItemSerializer(data=data)
        if serializer.is_valid():
            serializer.save(created_by=request.user)
            return Response({
                'success': True,
                'message': f'Item added to {resource.name}',
                'item': serializer.data
            }, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    # In JobBusinessResourceViewSet class
    @action(detail=True, methods=['delete'])
    def delete_item(self, request, pk=None):
        """🆕 Delete a specific item from this resource"""
        resource = self.get_object()
        item_id = request.data.get('item_id')
        
        if not item_id:
            return Response({'error': 'item_id required'}, status=400)
        
        try:
            item = JobBusinessResourceItem.objects.get(
                id=item_id,
                resource=resource
            )
            item_name = item.name
            item.delete()
            
            return Response({
                'success': True,
                'message': f'Item "{item_name}" deleted from {resource.name}'
            }, status=status.HTTP_200_OK)
        except JobBusinessResourceItem.DoesNotExist:
            return Response(
                {'error': 'Item not found in this resource'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=True, methods=['put'])
    def update_item(self, request, pk=None):
        """🆕 Update a specific item in this resource"""
        resource = self.get_object()
        item_id = request.data.get('item_id')
        
        if not item_id:
            return Response({'error': 'item_id required'}, status=400)
        
        try:
            item = JobBusinessResourceItem.objects.get(
                id=item_id,
                resource=resource
            )
            
            # Update fields
            if 'name' in request.data:
                item.name = request.data['name']
            if 'description' in request.data:
                item.description = request.data['description']
            if 'is_active' in request.data:
                item.is_active = request.data['is_active']
            
            item.save()
            
            serializer = JobBusinessResourceItemSerializer(item)
            return Response({
                'success': True,
                'message': f'Item updated in {resource.name}',
                'item': serializer.data
            }, status=status.HTTP_200_OK)
            
        except JobBusinessResourceItem.DoesNotExist:
            return Response(
                {'error': 'Item not found in this resource'},
                status=status.HTTP_404_NOT_FOUND
            )

class JobBusinessResourceItemViewSet(viewsets.ModelViewSet):
    """🆕 CRUD for business resource items"""
    
    queryset = JobBusinessResourceItem.objects.select_related('resource').all()
    serializer_class = JobBusinessResourceItemSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['resource', 'is_active']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at']
    ordering = ['resource__name', 'name']
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    @action(detail=False, methods=['get'])
    def by_resource(self, request):
        """Get items grouped by resource"""
        resource_id = request.query_params.get('resource_id')
        if not resource_id:
            return Response({'error': 'resource_id required'}, status=400)
        
        items = self.queryset.filter(resource_id=resource_id, is_active=True)
        serializer = self.get_serializer(items, many=True)
        return Response({
            'items': serializer.data,
            'count': items.count()
        })

class AccessMatrixViewSet(viewsets.ModelViewSet):
    """UPDATED: Access matrix with nested items support"""
    
    queryset = AccessMatrix.objects.all()
    serializer_class = AccessMatrixSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['is_active']
    search_fields = ['name', 'description']
    ordering = ['name']
    
    def get_queryset(self):
        return AccessMatrix.objects.prefetch_related('items').all()
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    @action(detail=True, methods=['get'])
    def items(self, request, pk=None):
        """🆕 Get all items for an access matrix"""
        access_matrix = self.get_object()
        items = access_matrix.items.filter(is_active=True)
        serializer = AccessMatrixItemSerializer(items, many=True)
        return Response({
            'access_matrix': AccessMatrixSerializer(access_matrix).data,
            'items': serializer.data,
            'total_items': items.count()
        })
    
    @action(detail=True, methods=['post'])
    def add_item(self, request, pk=None):
 
        access_matrix = self.get_object()
        
        data = request.data.copy()
        data['access_matrix'] = access_matrix.id
        
        serializer = AccessMatrixItemSerializer(data=data)
        if serializer.is_valid():
            serializer.save(created_by=request.user)
            return Response({
                'success': True,
                'message': f'Access item added to {access_matrix.name}',
                'item': serializer.data
            }, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    
    # In AccessMatrixViewSet class
    @action(detail=True, methods=['delete'])
    def delete_item(self, request, pk=None):
        """🆕 Delete a specific access item"""
        access_matrix = self.get_object()
        item_id = request.data.get('item_id')
        
        if not item_id:
            return Response({'error': 'item_id required'}, status=400)
        
        try:
            item = AccessMatrixItem.objects.get(
                id=item_id,
                access_matrix=access_matrix
            )
            item_name = item.name
            item.delete()
            
            return Response({
                'success': True,
                'message': f'Access item "{item_name}" deleted from {access_matrix.name}'
            }, status=status.HTTP_200_OK)
        except AccessMatrixItem.DoesNotExist:
            return Response(
                {'error': 'Access item not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=True, methods=['put'])
    def update_item(self, request, pk=None):
        """🆕 Update a specific access item"""
        access_matrix = self.get_object()
        item_id = request.data.get('item_id')
        
        if not item_id:
            return Response({'error': 'item_id required'}, status=400)
        
        try:
            item = AccessMatrixItem.objects.get(
                id=item_id,
                access_matrix=access_matrix
            )
            
            if 'name' in request.data:
                item.name = request.data['name']
            if 'description' in request.data:
                item.description = request.data['description']
            if 'is_active' in request.data:
                item.is_active = request.data['is_active']
            
            item.save()
            
            serializer = AccessMatrixItemSerializer(item)
            return Response({
                'success': True,
                'message': f'Access item updated in {access_matrix.name}',
                'item': serializer.data
            }, status=status.HTTP_200_OK)
            
        except AccessMatrixItem.DoesNotExist:
            return Response(
                {'error': 'Access item not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
class AccessMatrixItemViewSet(viewsets.ModelViewSet):

    
    queryset = AccessMatrixItem.objects.select_related('access_matrix').all()
    serializer_class = AccessMatrixItemSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['access_matrix',  'is_active']
    search_fields = ['name', 'description']
    ordering_fields = ['name',  'created_at']
    ordering = ['access_matrix__name', 'name']
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

class CompanyBenefitViewSet(viewsets.ModelViewSet):
    """UPDATED: Company benefits with nested items support"""
    
    queryset = CompanyBenefit.objects.all()
    serializer_class = CompanyBenefitSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['is_active']
    search_fields = ['name', 'description']
    ordering = ['name']
    
    def get_queryset(self):
        return CompanyBenefit.objects.prefetch_related('items').all()
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    @action(detail=True, methods=['get'])
    def items(self, request, pk=None):
        """🆕 Get all items for a benefit"""
        benefit = self.get_object()
        items = benefit.items.filter(is_active=True)
   
        return Response({
            'benefit': CompanyBenefitSerializer(benefit).data,
   
            'total_items': items.count()
        })
    
    @action(detail=True, methods=['post'])
    def add_item(self, request, pk=None):
        """🆕 Add a new benefit item"""
        benefit = self.get_object()
        
        data = request.data.copy()
        data['benefit'] = benefit.id
        
        serializer = CompanyBenefitItemSerializer(data=data)
        if serializer.is_valid():
            serializer.save(created_by=request.user)
            return Response({
                'success': True,
                'message': f'Benefit item added to {benefit.name}',
                'item': serializer.data
            }, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    # In CompanyBenefitViewSet class
    @action(detail=True, methods=['delete'])
    def delete_item(self, request, pk=None):
        """🆕 Delete a specific benefit item"""
        benefit = self.get_object()
        item_id = request.data.get('item_id')
        
        if not item_id:
            return Response({'error': 'item_id required'}, status=400)
        
        try:
            item = CompanyBenefitItem.objects.get(
                id=item_id,
                benefit=benefit
            )
            item_name = item.name
            item.delete()
            
            return Response({
                'success': True,
                'message': f'Benefit item "{item_name}" deleted from {benefit.name}'
            }, status=status.HTTP_200_OK)
        except CompanyBenefitItem.DoesNotExist:
            return Response(
                {'error': 'Benefit item not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=True, methods=['put'])
    def update_item(self, request, pk=None):
        """🆕 Update a specific benefit item"""
        benefit = self.get_object()
        item_id = request.data.get('item_id')
        
        if not item_id:
            return Response({'error': 'item_id required'}, status=400)
        
        try:
            item = CompanyBenefitItem.objects.get(
                id=item_id,
                benefit=benefit
            )
            
            if 'name' in request.data:
                item.name = request.data['name']
            if 'description' in request.data:
                item.description = request.data['description']
            if 'is_active' in request.data:
                item.is_active = request.data['is_active']
            
            item.save()
            
            serializer = CompanyBenefitItemSerializer(item)
            return Response({
                'success': True,
                'message': f'Benefit item updated in {benefit.name}',
                'item': serializer.data
            }, status=status.HTTP_200_OK)
            
        except CompanyBenefitItem.DoesNotExist:
            return Response(
                {'error': 'Benefit item not found'},
                status=status.HTTP_404_NOT_FOUND
            )
class CompanyBenefitItemViewSet(viewsets.ModelViewSet):
    """🆕 CRUD for company benefit items"""
    
    queryset = CompanyBenefitItem.objects.select_related('benefit').all()
    serializer_class = CompanyBenefitItemSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['benefit', 'is_active']
    search_fields = ['name', 'description', 'value']
    ordering_fields = ['name', 'created_at']
    ordering = ['benefit__name', 'name']
    
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
          
            'approval_workflow_summary': {
                'draft': queryset.filter(status='DRAFT').count(),
                'pending_line_manager': pending_line_manager,
                'pending_employee': pending_employee,
                'approved': queryset.filter(status='APPROVED').count(),
                'rejected': queryset.filter(status='REJECTED').count(),
                'revision_required': queryset.filter(status='REVISION_REQUIRED').count()
            }
        })