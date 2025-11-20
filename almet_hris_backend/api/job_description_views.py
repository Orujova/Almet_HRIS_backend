# api/job_description_views.py - UPDATED: Multiple employee assignment support
# PART 1: Imports, Filters, and Main ViewSet

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

logger = logging.getLogger(__name__)

# Job Description Models
from .job_description_models import (
    JobDescription, JobDescriptionAssignment,
    JobBusinessResource, AccessMatrix, CompanyBenefit,
    JobBusinessResourceItem, AccessMatrixItem, CompanyBenefitItem,
    normalize_grading_level
)

# Job Description Serializers
from .job_description_serializers import (
    JobDescriptionListSerializer, JobDescriptionDetailSerializer,
    JobDescriptionCreateUpdateSerializer, JobDescriptionApprovalSerializer,
    JobDescriptionRejectionSerializer, JobDescriptionSubmissionSerializer,
    JobBusinessResourceSerializer, AccessMatrixSerializer, CompanyBenefitSerializer,
    EmployeeBasicSerializer, JobBusinessResourceItemSerializer,
    AccessMatrixItemSerializer, CompanyBenefitItemSerializer,
    JobDescriptionAssignmentListSerializer, JobDescriptionAssignmentDetailSerializer,
    AddAssignmentSerializer, ReassignEmployeeSerializer
)

# Core Models
from .models import BusinessFunction, Department, Unit, PositionGroup, JobFunction, VacantPosition, Employee


class JobDescriptionFilter:
    """Advanced filtering for job descriptions"""
    
    def __init__(self, queryset, params):
        self.queryset = queryset
        if hasattr(params, 'dict'):
            self.params = params.dict()
        else:
            self.params = dict(params)
    
    def get_list_values(self, param_name):
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
                Q(job_function__name__icontains=search)
            )
        
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


class JobDescriptionViewSet(viewsets.ModelViewSet):
    """ViewSet with multiple employee assignment support"""
    
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['job_title', 'job_purpose', 'business_function__name', 'department__name']
    ordering_fields = ['job_title', 'created_at', 'business_function__name']
    ordering = ['-created_at']
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    
    def get_queryset(self):
        return JobDescription.objects.select_related(
            'business_function', 'department', 'unit', 'job_function', 'position_group',
            'created_by', 'updated_by'
        ).prefetch_related(
            'assignments__employee',
            'assignments__reports_to',
            'assignments__vacancy_position',
            'sections',
            'required_skills__skill__group',
            'behavioral_competencies__competency__group',
            'business_resources__resource__items',
            'business_resources__specific_items',
            'access_rights__access_matrix__items',
            'access_rights__specific_items',
            'company_benefits__benefit__items',
            'company_benefits__specific_items'
        ).all()
    
    def get_serializer_class(self):
        action = getattr(self, 'action', None)
        
        if action == 'list':
            return JobDescriptionListSerializer
        elif action in ['create', 'update', 'partial_update']:
            return JobDescriptionCreateUpdateSerializer
        else:
            return JobDescriptionDetailSerializer
    
    def create(self, request, *args, **kwargs):
        """Create with employee selection workflow"""
        
        serializer = self.get_serializer(data=request.data)
        
        try:
            serializer.is_valid(raise_exception=True)
            instance = serializer.save()
            
            response_data = serializer.data
            
            total_created = len(getattr(instance, '_assignments_created', []))
            response_data['summary'] = {
                'total_assignments_created': total_created,
                'message': f'Job description created with {total_created} assignment(s)'
            }
            
            headers = self.get_success_headers(response_data)
            return Response(response_data, status=status.HTTP_201_CREATED, headers=headers)
            
        except serializers.ValidationError as e:
            if isinstance(e.detail, dict) and e.detail.get('requires_selection'):
                return Response({
                    'requires_selection': True,
                    'message': e.detail.get('message'),
                    'eligible_employees': e.detail.get('eligible_employees', []),
                    'eligible_vacancies': e.detail.get('eligible_vacancies', []),
                    'instruction': 'Resubmit with selected_employee_ids'
                }, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
            raise
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)
    
    # ==================== ASSIGNMENT MANAGEMENT ACTIONS ====================
    
    @swagger_auto_schema(
        method='get',
        operation_description="Get all assignments for this job description",
        responses={200: JobDescriptionAssignmentListSerializer(many=True)}
    )
    @action(detail=True, methods=['get'])
    def assignments(self, request, pk=None):
        """Get all assignments for this job description"""
        job_description = self.get_object()
        assignments = job_description.assignments.filter(is_active=True).select_related(
            'employee', 'reports_to', 'vacancy_position'
        )
        
        # Filter by status if provided
        status_filter = request.query_params.get('status')
        if status_filter:
            assignments = assignments.filter(status=status_filter)
        
        serializer = JobDescriptionAssignmentListSerializer(assignments, many=True)
        
        return Response({
            'job_description_id': str(job_description.id),
            'job_title': job_description.job_title,
            'total_assignments': assignments.count(),
            'summary': job_description.get_assignments_summary(),
            'assignments': serializer.data
        })
    
    @swagger_auto_schema(
        method='post',
        operation_description="Add new assignments to existing job description",
        request_body=AddAssignmentSerializer,
        responses={201: "Assignments added successfully"}
    )
    @action(detail=True, methods=['post'])
    def add_assignments(self, request, pk=None):
        """Add new employees/vacancies to this job description"""
        job_description = self.get_object()
        
        serializer = AddAssignmentSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        employee_ids = serializer.validated_data.get('employee_ids', [])
        vacancy_ids = serializer.validated_data.get('vacancy_ids', [])
        
        with transaction.atomic():
            assignments_created = []
            
            # Add employees
            for emp_id in employee_ids:
                try:
                    employee = Employee.objects.get(id=emp_id, is_deleted=False)
                    
                    # Check if already assigned
                    if job_description.assignments.filter(employee=employee, is_active=True).exists():
                        continue
                    
                    assignment = JobDescriptionAssignment.objects.create(
                        job_description=job_description,
                        employee=employee,
                        is_vacancy=False,
                        reports_to=employee.line_manager
                    )
                    assignments_created.append(assignment)
                except Employee.DoesNotExist:
                    pass
            
            # Add vacancies
            for vac_id in vacancy_ids:
                try:
                    vacancy = VacantPosition.objects.get(id=vac_id, is_filled=False)
                    
                    # Check if already assigned
                    if job_description.assignments.filter(vacancy_position=vacancy, is_active=True).exists():
                        continue
                    
                    assignment = JobDescriptionAssignment.objects.create(
                        job_description=job_description,
                        employee=None,
                        is_vacancy=True,
                        vacancy_position=vacancy,
                        reports_to=vacancy.reporting_to
                    )
                    assignments_created.append(assignment)
                except VacantPosition.DoesNotExist:
                    pass
        
        return Response({
            'success': True,
            'message': f'Added {len(assignments_created)} new assignment(s)',
            'assignments_created': [
                {
                    'id': str(a.id),
                    'name': a.get_display_name(),
                    'is_vacancy': a.is_vacancy
                }
                for a in assignments_created
            ]
        }, status=status.HTTP_201_CREATED)
    
    @swagger_auto_schema(
        method='post',
        operation_description="Remove an assignment from job description",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'assignment_id': openapi.Schema(type=openapi.TYPE_STRING, format='uuid')
            }
        )
    )
    @action(detail=True, methods=['post'])
    def remove_assignment(self, request, pk=None):
        """Remove/deactivate an assignment"""
        job_description = self.get_object()
        assignment_id = request.data.get('assignment_id')
        
        if not assignment_id:
            return Response({'error': 'assignment_id required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            assignment = job_description.assignments.get(id=assignment_id)
            assignment.is_active = False
            assignment.save()
            
            return Response({
                'success': True,
                'message': f'Assignment removed: {assignment.get_display_name()}'
            })
        except JobDescriptionAssignment.DoesNotExist:
            return Response({'error': 'Assignment not found'}, status=status.HTTP_404_NOT_FOUND)
    
    @swagger_auto_schema(
        method='post',
        operation_description="Reassign employee to a vacant assignment",
        request_body=ReassignEmployeeSerializer
    )
    @action(detail=True, methods=['post'])
    def reassign_employee(self, request, pk=None):
        """Assign a new employee to a vacant assignment"""
        job_description = self.get_object()
        
        serializer = ReassignEmployeeSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        assignment_id = serializer.validated_data['assignment_id']
        employee_id = serializer.validated_data['employee_id']
        
        try:
            assignment = job_description.assignments.get(id=assignment_id, is_vacancy=True)
            employee = Employee.objects.get(id=employee_id, is_deleted=False)
            
            assignment.assign_new_employee(employee)
            
            return Response({
                'success': True,
                'message': f'Employee {employee.full_name} assigned to position',
                'assignment': JobDescriptionAssignmentDetailSerializer(
                    assignment, context={'request': request}
                ).data
            })
        except JobDescriptionAssignment.DoesNotExist:
            return Response({'error': 'Vacant assignment not found'}, status=status.HTTP_404_NOT_FOUND)
        except Employee.DoesNotExist:
            return Response({'error': 'Employee not found'}, status=status.HTTP_404_NOT_FOUND)


    # ==================== APPROVAL WORKFLOW ACTIONS ====================
    
    @swagger_auto_schema(
        method='post',
        operation_description="Submit assignment for approval",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'assignment_id': openapi.Schema(type=openapi.TYPE_STRING, format='uuid'),
                'comments': openapi.Schema(type=openapi.TYPE_STRING)
            }
        )
    )
    @action(detail=True, methods=['post'])
    def submit_assignment_for_approval(self, request, pk=None):
        """Submit a specific assignment for approval"""
        job_description = self.get_object()
        assignment_id = request.data.get('assignment_id')
        comments = request.data.get('comments', '')
        
        if not assignment_id:
            return Response({'error': 'assignment_id required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            assignment = job_description.assignments.get(id=assignment_id, is_active=True)
            
            if assignment.status not in ['DRAFT', 'REVISION_REQUIRED']:
                return Response({
                    'error': f'Cannot submit assignment with status: {assignment.get_status_display()}'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            if not assignment.reports_to:
                return Response({
                    'error': 'Assignment has no line manager assigned'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            assignment.status = 'PENDING_LINE_MANAGER'
            assignment.save()
            
            logger.info(f"Assignment {assignment_id} submitted for approval")
            
            return Response({
                'success': True,
                'message': 'Assignment submitted for approval',
                'assignment_id': str(assignment.id),
                'status': assignment.get_status_display(),
                'next_approver': assignment.reports_to.full_name if assignment.reports_to else None
            })
            
        except JobDescriptionAssignment.DoesNotExist:
            return Response({'error': 'Assignment not found'}, status=status.HTTP_404_NOT_FOUND)
    
    @swagger_auto_schema(
        method='post',
        operation_description="Submit all draft assignments for approval",
        responses={200: "Submitted successfully"}
    )
    @action(detail=True, methods=['post'])
    def submit_all_for_approval(self, request, pk=None):
        """Submit all draft assignments for approval"""
        job_description = self.get_object()
        
        draft_assignments = job_description.assignments.filter(
            is_active=True,
            status__in=['DRAFT', 'REVISION_REQUIRED']
        )
        
        submitted_count = 0
        errors = []
        
        for assignment in draft_assignments:
            if not assignment.reports_to:
                errors.append(f"{assignment.get_display_name()}: No line manager")
                continue
            
            assignment.status = 'PENDING_LINE_MANAGER'
            assignment.save()
            submitted_count += 1
        
        return Response({
            'success': True,
            'message': f'Submitted {submitted_count} assignment(s) for approval',
            'submitted_count': submitted_count,
            'errors': errors if errors else None
        })
    
    @swagger_auto_schema(
        method='post',
        operation_description="Approve assignment as line manager",
        request_body=JobDescriptionApprovalSerializer
    )
    @action(detail=True, methods=['post'])
    def approve_assignment_by_line_manager(self, request, pk=None):
        """Approve a specific assignment as line manager"""
        job_description = self.get_object()
        assignment_id = request.data.get('assignment_id')
        
        if not assignment_id:
            return Response({'error': 'assignment_id required'}, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = JobDescriptionApprovalSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            assignment = job_description.assignments.get(id=assignment_id, is_active=True)
            
            if assignment.status != 'PENDING_LINE_MANAGER':
                return Response({
                    'error': f'Assignment is not pending line manager approval. Status: {assignment.get_status_display()}'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            if not assignment.can_be_approved_by_line_manager(request.user):
                return Response({
                    'error': 'You are not authorized to approve this assignment as line manager'
                }, status=status.HTTP_403_FORBIDDEN)
            
            with transaction.atomic():
                assignment.line_manager_approved_by = request.user
                assignment.line_manager_approved_at = timezone.now()
                assignment.line_manager_comments = serializer.validated_data.get('comments', '')
                
                signature = serializer.validated_data.get('signature')
                if signature:
                    assignment.line_manager_signature = signature
                
                # Move to employee approval (if not vacancy)
                if assignment.is_vacancy:
                    assignment.status = 'APPROVED'  # Vacancies don't need employee approval
                else:
                    assignment.status = 'PENDING_EMPLOYEE'
                
                assignment.save()
            
            logger.info(f"Assignment {assignment_id} approved by line manager {request.user.username}")
            
            return Response({
                'success': True,
                'message': 'Assignment approved by line manager',
                'assignment_id': str(assignment.id),
                'status': assignment.get_status_display(),
                'is_fully_approved': assignment.status == 'APPROVED'
            })
            
        except JobDescriptionAssignment.DoesNotExist:
            return Response({'error': 'Assignment not found'}, status=status.HTTP_404_NOT_FOUND)
    
    @swagger_auto_schema(
        method='post',
        operation_description="Approve assignment as employee",
        request_body=JobDescriptionApprovalSerializer
    )
    @action(detail=True, methods=['post'])
    def approve_assignment_as_employee(self, request, pk=None):
        """Approve a specific assignment as employee"""
        job_description = self.get_object()
        assignment_id = request.data.get('assignment_id')
        
        if not assignment_id:
            return Response({'error': 'assignment_id required'}, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = JobDescriptionApprovalSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            assignment = job_description.assignments.get(id=assignment_id, is_active=True)
            
            if assignment.status != 'PENDING_EMPLOYEE':
                return Response({
                    'error': f'Assignment is not pending employee approval. Status: {assignment.get_status_display()}'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            if not assignment.can_be_approved_by_employee(request.user):
                return Response({
                    'error': 'You are not authorized to approve this assignment as employee'
                }, status=status.HTTP_403_FORBIDDEN)
            
            with transaction.atomic():
                assignment.employee_approved_by = request.user
                assignment.employee_approved_at = timezone.now()
                assignment.employee_comments = serializer.validated_data.get('comments', '')
                assignment.status = 'APPROVED'
                
                signature = serializer.validated_data.get('signature')
                if signature:
                    assignment.employee_signature = signature
                
                assignment.save()
            
            logger.info(f"Assignment {assignment_id} approved by employee {request.user.username}")
            
            return Response({
                'success': True,
                'message': 'Assignment fully approved',
                'assignment_id': str(assignment.id),
                'status': assignment.get_status_display()
            })
            
        except JobDescriptionAssignment.DoesNotExist:
            return Response({'error': 'Assignment not found'}, status=status.HTTP_404_NOT_FOUND)
    
    @swagger_auto_schema(
        method='post',
        operation_description="Reject assignment",
        request_body=JobDescriptionRejectionSerializer
    )
    @action(detail=True, methods=['post'])
    def reject_assignment(self, request, pk=None):
        """Reject a specific assignment"""
        job_description = self.get_object()
        assignment_id = request.data.get('assignment_id')
        
        if not assignment_id:
            return Response({'error': 'assignment_id required'}, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = JobDescriptionRejectionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            assignment = job_description.assignments.get(id=assignment_id, is_active=True)
            
            if assignment.status not in ['PENDING_LINE_MANAGER', 'PENDING_EMPLOYEE']:
                return Response({
                    'error': f'Assignment cannot be rejected in status: {assignment.get_status_display()}'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            with transaction.atomic():
                assignment.status = 'REJECTED'
                if assignment.status == 'PENDING_LINE_MANAGER':
                    assignment.line_manager_comments = serializer.validated_data['reason']
                else:
                    assignment.employee_comments = serializer.validated_data['reason']
                assignment.save()
            
            return Response({
                'success': True,
                'message': 'Assignment rejected',
                'assignment_id': str(assignment.id),
                'status': assignment.get_status_display(),
                'reason': serializer.validated_data['reason']
            })
            
        except JobDescriptionAssignment.DoesNotExist:
            return Response({'error': 'Assignment not found'}, status=status.HTTP_404_NOT_FOUND)
    
    @swagger_auto_schema(
        method='post',
        operation_description="Request revision for assignment"
    )
    @action(detail=True, methods=['post'])
    def request_assignment_revision(self, request, pk=None):
        """Request revision for an assignment"""
        job_description = self.get_object()
        assignment_id = request.data.get('assignment_id')
        reason = request.data.get('reason', '')
        
        if not assignment_id:
            return Response({'error': 'assignment_id required'}, status=status.HTTP_400_BAD_REQUEST)
        
        if not reason:
            return Response({'error': 'reason required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            assignment = job_description.assignments.get(id=assignment_id, is_active=True)
            
            if assignment.status not in ['PENDING_LINE_MANAGER', 'PENDING_EMPLOYEE']:
                return Response({
                    'error': f'Cannot request revision for status: {assignment.get_status_display()}'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            assignment.status = 'REVISION_REQUIRED'
            if assignment.line_manager_approved_at:
                assignment.employee_comments = reason
            else:
                assignment.line_manager_comments = reason
            assignment.save()
            
            return Response({
                'success': True,
                'message': 'Revision requested',
                'assignment_id': str(assignment.id),
                'status': assignment.get_status_display()
            })
            
        except JobDescriptionAssignment.DoesNotExist:
            return Response({'error': 'Assignment not found'}, status=status.HTTP_404_NOT_FOUND)
    
    @action(detail=False, methods=['get'])
    def pending_approvals(self, request):
        """Get all assignments pending approval for current user"""
        try:
            user = request.user
            
            logger.info(f"Getting pending approvals for user: {user.username}")
            
            # Get employee record
            employee = None
            try:
                employee = user.employee_profile
            except:
                pass
            
            # Pending line manager approval
            line_manager_pending = JobDescriptionAssignment.objects.filter(
                status='PENDING_LINE_MANAGER',
                reports_to__user=user,
                is_active=True
            ).select_related(
                'job_description', 'employee', 'reports_to'
            )
            
            # Pending employee approval
            employee_pending = JobDescriptionAssignment.objects.none()
            if employee:
                employee_pending = JobDescriptionAssignment.objects.filter(
                    status='PENDING_EMPLOYEE',
                    employee__user=user,
                    is_active=True
                ).select_related(
                    'job_description', 'employee', 'reports_to'
                )
            
            lm_serializer = JobDescriptionAssignmentListSerializer(line_manager_pending, many=True)
            emp_serializer = JobDescriptionAssignmentListSerializer(employee_pending, many=True)
            
            return Response({
                'pending_as_line_manager': {
                    'count': line_manager_pending.count(),
                    'assignments': lm_serializer.data
                },
                'pending_as_employee': {
                    'count': employee_pending.count(),
                    'assignments': emp_serializer.data
                },
                'total_pending': line_manager_pending.count() + employee_pending.count(),
                'user_info': {
                    'user_id': user.id,
                    'username': user.username,
                    'employee_id': employee.employee_id if employee else None,
                    'employee_name': employee.full_name if employee else None
                }
            })
            
        except Exception as e:
            logger.error(f"Error getting pending approvals: {str(e)}")
            return Response(
                {'error': f'Failed to get pending approvals: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )    
    

    # ==================== PREVIEW AND UTILITY ACTIONS ====================
    
    @swagger_auto_schema(
        method='post',
        operation_description="Preview eligible employees and vacancies with assignment strategy",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['job_title', 'business_function', 'department', 'job_function', 'position_group', 'grading_levels'],
            properties={
                'job_title': openapi.Schema(type=openapi.TYPE_STRING),
                'business_function': openapi.Schema(type=openapi.TYPE_INTEGER),
                'department': openapi.Schema(type=openapi.TYPE_INTEGER),
                'unit': openapi.Schema(type=openapi.TYPE_INTEGER),
                'job_function': openapi.Schema(type=openapi.TYPE_INTEGER),
                'position_group': openapi.Schema(type=openapi.TYPE_INTEGER),
                'grading_levels': openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Schema(type=openapi.TYPE_STRING)),
                'max_preview': openapi.Schema(type=openapi.TYPE_INTEGER, default=50),
                'include_vacancies': openapi.Schema(type=openapi.TYPE_BOOLEAN, default=True)
            }
        )
    )
    @action(detail=False, methods=['post'])
    def preview_eligible_employees(self, request):
        """Preview which employees and vacancies would be assigned"""
        try:
            job_title = request.data.get('job_title')
            business_function_id = request.data.get('business_function')
            department_id = request.data.get('department')
            unit_id = request.data.get('unit')
            job_function_id = request.data.get('job_function')
            position_group_id = request.data.get('position_group')
            grading_levels = request.data.get('grading_levels', [])
            max_preview = request.data.get('max_preview', 50)
            include_vacancies = request.data.get('include_vacancies', True)
            
            if isinstance(grading_levels, str):
                grading_levels = [grading_levels]
            
            # Validate
            required = {
                'job_title': job_title,
                'business_function': business_function_id,
                'department': department_id,
                'job_function': job_function_id,
                'position_group': position_group_id,
                'grading_levels': grading_levels
            }
            
            missing = [f for f, v in required.items() if not v]
            if missing:
                return Response(
                    {'error': f'Missing required fields: {", ".join(missing)}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Get eligible employees
            eligible_employees = JobDescription.get_eligible_employees_with_priority(
                job_title=job_title,
                business_function_id=business_function_id,
                department_id=department_id,
                unit_id=unit_id,
                job_function_id=job_function_id,
                position_group_id=position_group_id,
                grading_levels=grading_levels
            )
            
            # Get eligible vacancies
            eligible_vacancies = []
            vacancies_count = 0
            if include_vacancies:
                eligible_vacancies = self._get_eligible_vacant_positions(
                    job_title=job_title,
                    business_function_id=business_function_id,
                    department_id=department_id,
                    unit_id=unit_id,
                    job_function_id=job_function_id,
                    position_group_id=position_group_id,
                    grading_levels=grading_levels
                )
                vacancies_count = eligible_vacancies.count()
            
            employees_count = eligible_employees.count()
            total_count = employees_count + vacancies_count
            
            # Determine assignment strategy
            strategy = None
            strategy_message = ""
            requires_manual_selection = False
            
            if total_count == 0:
                strategy = "no_employees_found"
                strategy_message = "No matching employees or vacant positions found. Job description will be created as unassigned."
            elif total_count == 1:
                strategy = "auto_assign_single"
                if employees_count == 1:
                    strategy_message = "One matching employee found. Job description will be automatically assigned to this employee."
                else:
                    strategy_message = "One vacant position found. Job description will be assigned to this vacant position."
            else:
                strategy = "manual_selection_required"
                strategy_message = f"Multiple matches found ({employees_count} employees, {vacancies_count} vacancies). Please select which positions to assign during creation."
                requires_manual_selection = True
            
            # Serialize employees
            employees_data = EmployeeBasicSerializer(
                eligible_employees[:max_preview], 
                many=True
            ).data
            
            # Serialize vacancies
            vacancies_data = []
            if include_vacancies:
                for v in eligible_vacancies[:max_preview]:
                    vacancies_data.append({
                        'id': v.original_employee_pk or v.id,
                        'employee_id': v.position_id,
                        'full_name': f"VACANT - {v.position_id}",
                        'name': f"VACANT - {v.position_id}",
                        'position_id': v.position_id,
                        'job_title': v.job_title,
                        'is_vacancy': True,
                        'record_type': 'vacancy',
                        'reports_to': v.reporting_to.full_name if v.reporting_to else None,
                        'line_manager_name': v.reporting_to.full_name if v.reporting_to else None,
                        'line_manager_id': v.reporting_to.id if v.reporting_to else None,
                        'grading_level': v.grading_level,
                        'business_function_name': v.business_function.name if v.business_function else None,
                        'department_name': v.department.name if v.department else None,
                        'unit_name': v.unit.name if v.unit else None,
                        'job_function_name': v.job_function.name if v.job_function else None,
                        'position_group_name': v.position_group.name if v.position_group else None,
                        'vacancy_details': {
                            'created_at': v.created_at.isoformat() if v.created_at else None,
                            'notes': getattr(v, 'notes', '')
                        }
                    })
            
            # Mark records as vacancy
            for emp in employees_data:
                emp['is_vacancy'] = False
                emp['record_type'] = 'employee'
            
            # Unified list for frontend
            unified_list = employees_data + vacancies_data
            
            # Build criteria info
            criteria_info = {
                'job_title': job_title,
                'business_function_id': business_function_id,
                'department_id': department_id,
                'unit_id': unit_id,
                'job_function_id': job_function_id,
                'position_group_id': position_group_id,
                'grading_levels': grading_levels
            }
            
            response_data = {
                # Strategy info
                'assignment_strategy': strategy,
                'strategy': strategy,
                'strategy_message': strategy_message,
                'message': strategy_message,
                'requires_manual_selection': requires_manual_selection,
                
                # Counts
                'total_eligible_count': total_count,
                'total_eligible': total_count,
                'eligible_employees_count': employees_count,
                'employees_count': employees_count,
                'eligible_vacancies_count': vacancies_count,
                'vacancies_count': vacancies_count,
                
                # Data arrays
                'employees': employees_data,
                'vacancies': vacancies_data,
                'unified_list': unified_list,
                
                # Metadata
                'criteria': criteria_info,
                'max_preview': max_preview,
                'showing_all': total_count <= max_preview,
                
                # Next steps guidance
                'next_steps': {
                    'strategy': strategy,
                    'action_required': requires_manual_selection,
                    'can_auto_assign': strategy == 'auto_assign_single',
                    'instruction': (
                        'Select employees to assign' if requires_manual_selection
                        else 'Proceed with creation' if strategy == 'auto_assign_single'
                        else 'Job description will be created without assignments'
                    )
                }
            }
            
            logger.info(f"Preview completed: strategy={strategy}, total={total_count}, employees={employees_count}, vacancies={vacancies_count}")
            
            return Response(response_data)
            
        except Exception as e:
            logger.error(f"Error in preview: {str(e)}", exc_info=True)
            return Response(
                {
                    'error': f'Preview failed: {str(e)}',
                    'strategy': 'error',
                    'message': 'Failed to load preview'
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    def _get_eligible_vacant_positions(self, **kwargs):
        """Get eligible vacant positions"""
        queryset = VacantPosition.objects.filter(
            is_filled=False,
            is_deleted=False,
            include_in_headcount=True
        )
        
        if kwargs.get('job_title'):
            queryset = queryset.filter(job_title__iexact=kwargs['job_title'].strip())
        
        if kwargs.get('business_function_id'):
            queryset = queryset.filter(business_function_id=kwargs['business_function_id'])
        
        if kwargs.get('department_id'):
            queryset = queryset.filter(department_id=kwargs['department_id'])
        
        if kwargs.get('unit_id'):
            queryset = queryset.filter(unit_id=kwargs['unit_id'])
        
        if kwargs.get('job_function_id'):
            queryset = queryset.filter(job_function_id=kwargs['job_function_id'])
        
        if kwargs.get('position_group_id'):
            queryset = queryset.filter(position_group_id=kwargs['position_group_id'])
        
        grading_levels = kwargs.get('grading_levels', [])
        if grading_levels:
            if isinstance(grading_levels, str):
                grading_levels = [grading_levels]
            
            normalized = [normalize_grading_level(gl) for gl in grading_levels]
            matching = [v.id for v in queryset if normalize_grading_level(v.grading_level or '') in normalized]
            queryset = queryset.filter(id__in=matching)
        
        return queryset
    
    @action(detail=True, methods=['get'])
    def download_pdf(self, request, pk=None):
        """Download job description as PDF"""
        if not HAS_REPORTLAB:
            return HttpResponse("PDF library not available", status=500)
        
        try:
            job_description = self.get_object()
            buffer = BytesIO()
            
            # Simple PDF generation
            doc = SimpleDocTemplate(buffer, pagesize=A4)
            styles = getSampleStyleSheet()
            story = []
            
            # Title
            story.append(Paragraph(f"Job Description: {job_description.job_title}", styles['Title']))
            story.append(Spacer(1, 0.5*inch))
            
            # Assignments
            story.append(Paragraph("Assigned To:", styles['Heading2']))
            for assignment in job_description.assignments.filter(is_active=True):
                story.append(Paragraph(
                    f"• {assignment.get_display_name()} - {assignment.get_status_display()}",
                    styles['Normal']
                ))
            
            story.append(Spacer(1, 0.3*inch))
            
            # Purpose
            story.append(Paragraph("Job Purpose:", styles['Heading2']))
            story.append(Paragraph(job_description.job_purpose, styles['Normal']))
            
            doc.build(story)
            buffer.seek(0)
            
            filename = f"JD_{job_description.job_title.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.pdf"
            
            response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response
            
        except Exception as e:
            logger.error(f"PDF error: {str(e)}")
            return HttpResponse(f"PDF Error: {str(e)}", status=500)


# ==================== RESOURCE VIEWSETS ====================

class JobBusinessResourceViewSet(viewsets.ModelViewSet):
    """Business resources with nested items"""
    
    queryset = JobBusinessResource.objects.prefetch_related('items').all()
    serializer_class = JobBusinessResourceSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['is_active']
    search_fields = ['name', 'description']
    ordering = ['name']
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    @action(detail=True, methods=['get'])
    def items(self, request, pk=None):
        resource = self.get_object()
        items = resource.items.filter(is_active=True)
        serializer = JobBusinessResourceItemSerializer(items, many=True)
        return Response({
            'resource': JobBusinessResourceSerializer(resource).data,
            'items': serializer.data
        })
    
    @action(detail=True, methods=['post'])
    def add_item(self, request, pk=None):
        resource = self.get_object()
        data = request.data.copy()
        data['resource'] = resource.id
        
        serializer = JobBusinessResourceItemSerializer(data=data)
        if serializer.is_valid():
            serializer.save(created_by=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['delete'])
    def delete_item(self, request, pk=None):
        resource = self.get_object()
        item_id = request.data.get('item_id')
        
        if not item_id:
            return Response({'error': 'item_id required'}, status=400)
        
        try:
            item = JobBusinessResourceItem.objects.get(id=item_id, resource=resource)
            item.delete()
            return Response({'success': True})
        except JobBusinessResourceItem.DoesNotExist:
            return Response({'error': 'Item not found'}, status=404)


class JobBusinessResourceItemViewSet(viewsets.ModelViewSet):
    queryset = JobBusinessResourceItem.objects.select_related('resource').all()
    serializer_class = JobBusinessResourceItemSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['resource', 'is_active']
    search_fields = ['name', 'description']
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class AccessMatrixViewSet(viewsets.ModelViewSet):
    queryset = AccessMatrix.objects.prefetch_related('items').all()
    serializer_class = AccessMatrixSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['is_active']
    search_fields = ['name', 'description']
    ordering = ['name']
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    @action(detail=True, methods=['get'])
    def items(self, request, pk=None):
        access_matrix = self.get_object()
        items = access_matrix.items.filter(is_active=True)
        serializer = AccessMatrixItemSerializer(items, many=True)
        return Response({
            'access_matrix': AccessMatrixSerializer(access_matrix).data,
            'items': serializer.data
        })
    
    @action(detail=True, methods=['post'])
    def add_item(self, request, pk=None):
        access_matrix = self.get_object()
        data = request.data.copy()
        data['access_matrix'] = access_matrix.id
        
        serializer = AccessMatrixItemSerializer(data=data)
        if serializer.is_valid():
            serializer.save(created_by=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['delete'])
    def delete_item(self, request, pk=None):
        access_matrix = self.get_object()
        item_id = request.data.get('item_id')
        
        if not item_id:
            return Response({'error': 'item_id required'}, status=400)
        
        try:
            item = AccessMatrixItem.objects.get(id=item_id, access_matrix=access_matrix)
            item.delete()
            return Response({'success': True})
        except AccessMatrixItem.DoesNotExist:
            return Response({'error': 'Item not found'}, status=404)


class AccessMatrixItemViewSet(viewsets.ModelViewSet):
    queryset = AccessMatrixItem.objects.select_related('access_matrix').all()
    serializer_class = AccessMatrixItemSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['access_matrix', 'is_active']
    search_fields = ['name', 'description']
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class CompanyBenefitViewSet(viewsets.ModelViewSet):
    queryset = CompanyBenefit.objects.prefetch_related('items').all()
    serializer_class = CompanyBenefitSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['is_active']
    search_fields = ['name', 'description']
    ordering = ['name']
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    @action(detail=True, methods=['get'])
    def items(self, request, pk=None):
        benefit = self.get_object()
        items = benefit.items.filter(is_active=True)
        serializer = CompanyBenefitItemSerializer(items, many=True)
        return Response({
            'benefit': CompanyBenefitSerializer(benefit).data,
            'items': serializer.data
        })
    
    @action(detail=True, methods=['post'])
    def add_item(self, request, pk=None):
        benefit = self.get_object()
        data = request.data.copy()
        data['benefit'] = benefit.id
        
        serializer = CompanyBenefitItemSerializer(data=data)
        if serializer.is_valid():
            serializer.save(created_by=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['delete'])
    def delete_item(self, request, pk=None):
        benefit = self.get_object()
        item_id = request.data.get('item_id')
        
        if not item_id:
            return Response({'error': 'item_id required'}, status=400)
        
        try:
            item = CompanyBenefitItem.objects.get(id=item_id, benefit=benefit)
            item.delete()
            return Response({'success': True})
        except CompanyBenefitItem.DoesNotExist:
            return Response({'error': 'Item not found'}, status=404)


class CompanyBenefitItemViewSet(viewsets.ModelViewSet):
    queryset = CompanyBenefitItem.objects.select_related('benefit').all()
    serializer_class = CompanyBenefitItemSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['benefit', 'is_active']
    search_fields = ['name', 'description']
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class JobDescriptionStatsViewSet(viewsets.ViewSet):
    """Statistics for job descriptions"""
    
    permission_classes = [IsAuthenticated]
    
    def list(self, request):
        """Get comprehensive statistics"""
        
        total_jds = JobDescription.objects.count()
        total_assignments = JobDescriptionAssignment.objects.filter(is_active=True).count()
        
        # Assignment status breakdown
        assignment_stats = {}
        for status_choice in JobDescriptionAssignment.STATUS_CHOICES:
            code = status_choice[0]
            count = JobDescriptionAssignment.objects.filter(
                is_active=True, status=code
            ).count()
            if count > 0:
                assignment_stats[status_choice[1]] = count
        
        # By department
        dept_stats = {}
        dept_counts = JobDescription.objects.values('department__name').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        for item in dept_counts:
            if item['department__name']:
                dept_stats[item['department__name']] = item['count']
        
        # Employee vs Vacancy
        employee_assignments = JobDescriptionAssignment.objects.filter(
            is_active=True, is_vacancy=False
        ).count()
        vacancy_assignments = JobDescriptionAssignment.objects.filter(
            is_active=True, is_vacancy=True
        ).count()
        
        return Response({
            'total_job_descriptions': total_jds,
            'total_assignments': total_assignments,
            'assignment_status_breakdown': assignment_stats,
            'department_breakdown': dept_stats,
            'assignment_type_breakdown': {
                'employees': employee_assignments,
                'vacancies': vacancy_assignments
            },
            'pending_approvals': {
                'total': JobDescriptionAssignment.objects.filter(
                    is_active=True,
                    status__in=['PENDING_LINE_MANAGER', 'PENDING_EMPLOYEE']
                ).count(),
                'pending_line_manager': JobDescriptionAssignment.objects.filter(
                    is_active=True, status='PENDING_LINE_MANAGER'
                ).count(),
                'pending_employee': JobDescriptionAssignment.objects.filter(
                    is_active=True, status='PENDING_EMPLOYEE'
                ).count()
            }
        })        