# api/job_description_views.py - UPDATED: Auto manager assignment and optional employee

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
from .job_description_models import (
    JobDescription, JobDescriptionSection, JobDescriptionSkill,
    JobDescriptionBehavioralCompetency, JobBusinessResource, AccessMatrix,
    CompanyBenefit, JobDescriptionActivity
)
from .job_description_serializers import (
    JobDescriptionListSerializer, JobDescriptionDetailSerializer,
    JobDescriptionCreateUpdateSerializer, JobDescriptionApprovalSerializer,
    JobDescriptionRejectionSerializer, JobDescriptionSubmissionSerializer,
    JobBusinessResourceSerializer, AccessMatrixSerializer, 
    CompanyBenefitSerializer, JobDescriptionActivitySerializer
)
from .competency_models import Skill, BehavioralCompetency
from .models import BusinessFunction, Department, Unit, PositionGroup, Employee, JobFunction
from .job_description_serializers import JobDescriptionExportSerializer




class JobDescriptionFilter:
    """Advanced filtering for job descriptions"""
    
    def __init__(self, queryset, params):
        self.queryset = queryset
        # Convert QueryDict to regular dict to avoid immutable issues
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
            # Handle comma-separated values
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
        
        print(f"🔍 JOB DESCRIPTION FILTER DEBUG: Raw params = {self.params}")
        
        # Search filter
        search = self.params.get('search')
        if search:
            print(f"🔍 Applying job description search: {search}")
            queryset = queryset.filter(
                Q(job_title__icontains=search) |
                Q(job_purpose__icontains=search) |
                Q(business_function__name__icontains=search) |
                Q(department__name__icontains=search) |
                Q(job_function__name__icontains=search) |  # ADDED
                Q(assigned_employee__full_name__icontains=search) |
                Q(assigned_employee__employee_id__icontains=search) |
                Q(manual_employee_name__icontains=search)
            )
        
        # Status filter
        status_values = self.get_list_values('status')
        if status_values:
            print(f"🎯 Applying status filter: {status_values}")
            queryset = queryset.filter(status__in=status_values)
        
        # Business function filter
        business_function_ids = self.get_int_list_values('business_function')
        if business_function_ids:
            print(f"🏭 Applying business function filter: {business_function_ids}")
            queryset = queryset.filter(business_function__id__in=business_function_ids)
        
        # Department filter
        department_ids = self.get_int_list_values('department')
        if department_ids:
            print(f"🏢 Applying department filter: {department_ids}")
            queryset = queryset.filter(department__id__in=department_ids)
        
        # ADDED: Job function filter
        job_function_ids = self.get_int_list_values('job_function')
        if job_function_ids:
            print(f"💼 Applying job function filter: {job_function_ids}")
            queryset = queryset.filter(job_function__id__in=job_function_ids)
        
        # Position group filter
        position_group_ids = self.get_int_list_values('position_group')
        if position_group_ids:
            print(f"📊 Applying position group filter: {position_group_ids}")
            queryset = queryset.filter(position_group__id__in=position_group_ids)
        
        # Employee filter (assigned_employee or manual)
        employee_search = self.params.get('employee_search')
        if employee_search:
            print(f"👤 Applying employee search: {employee_search}")
            queryset = queryset.filter(
                Q(assigned_employee__full_name__icontains=employee_search) |
                Q(assigned_employee__employee_id__icontains=employee_search) |
                Q(manual_employee_name__icontains=employee_search)
            )
        
        # Manager filter
        manager_search = self.params.get('manager_search')
        if manager_search:
            print(f"👨‍💼 Applying manager search: {manager_search}")
            queryset = queryset.filter(
                Q(reports_to__full_name__icontains=manager_search) |
                Q(reports_to__employee_id__icontains=manager_search)
            )
        
        # ADDED: Vacant positions filter
        vacant_only = self.params.get('vacant_only')
        if vacant_only and vacant_only.lower() == 'true':
            print(f"🔲 Showing vacant positions only")
            queryset = queryset.filter(assigned_employee__isnull=True)
        
        # ADDED: Assigned positions filter
        assigned_only = self.params.get('assigned_only')
        if assigned_only and assigned_only.lower() == 'true':
            print(f"👥 Showing assigned positions only")
            queryset = queryset.filter(assigned_employee__isnull=False)
        
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
        
        # Active only filter
        active_only = self.params.get('active_only')
        if active_only and active_only.lower() == 'true':
            queryset = queryset.filter(is_active=True)
        
        # Pending approval for current user
        pending_for_user = self.params.get('pending_approval_for_user')
        if pending_for_user and pending_for_user.lower() == 'true':
            user = self.params.get('request_user')
            if user:
                queryset = queryset.filter(
                    Q(status='PENDING_LINE_MANAGER', reports_to__user=user) |
                    Q(status='PENDING_EMPLOYEE', assigned_employee__user=user)
                )
        
        final_count = queryset.count()
        print(f"✅ JOB DESCRIPTION FILTER COMPLETE: {final_count} job descriptions after filtering")
        
        return queryset

class JobDescriptionViewSet(viewsets.ModelViewSet):
    """UPDATED: ViewSet for Job Description management with auto manager assignment"""
    
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['job_title', 'job_purpose', 'business_function__name', 'department__name', 'job_function__name']
    ordering_fields = ['job_title', 'created_at', 'status', 'business_function__name']
    ordering = ['-created_at']
    
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
        if self.action == 'list':
            return JobDescriptionListSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return JobDescriptionCreateUpdateSerializer
        else:
            return JobDescriptionDetailSerializer
    
    def get_object(self):
        """Override get_object to handle UUID properly"""
        queryset = self.filter_queryset(self.get_queryset())
        
        # Get the lookup value
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        assert lookup_url_kwarg in self.kwargs, (
            'Expected view %s to be called with a URL keyword argument '
            'named "%s". Fix your URL conf, or set the `.lookup_field` '
            'attribute on the view correctly.' %
            (self.__class__.__name__, lookup_url_kwarg)
        )
        
        lookup_value = self.kwargs[lookup_url_kwarg]
        
        # Handle both UUID and integer lookup
        try:
            # Try to parse as UUID first
            if len(lookup_value) == 36 and '-' in lookup_value:
                # Looks like UUID
                uuid_obj = uuid.UUID(lookup_value)
                filter_kwargs = {'id': uuid_obj}
            else:
                # Try as integer (fallback)
                filter_kwargs = {'id': int(lookup_value)}
        except (ValueError, TypeError):
            # If all else fails, try string lookup
            filter_kwargs = {'id': lookup_value}
        
        try:
            obj = queryset.get(**filter_kwargs)
        except JobDescription.DoesNotExist:
            logger.error(f"JobDescription not found with lookup: {lookup_value}")
            from rest_framework.exceptions import NotFound
            raise NotFound('Job description not found.')
        except JobDescription.MultipleObjectsReturned:
            logger.error(f"Multiple JobDescriptions found with lookup: {lookup_value}")
            from rest_framework.exceptions import ValidationError
            raise ValidationError('Multiple job descriptions found.')
        
        # May raise a permission denied
        self.check_object_permissions(self.request, obj)
        
        return obj
    
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
        """UPDATED: Submit job description for approval with enhanced validation"""
        try:
            logger.info(f"Submit for approval request - User: {request.user.username}, JD ID: {pk}")
            logger.info(f"Request data: {request.data}")
            
            # Get the job description object
            job_description = self.get_object()
            logger.info(f"Job description found: {job_description.job_title}, Status: {job_description.status}")
            
          
            
            # Check valid status for submission
            if job_description.status not in ['DRAFT', 'REVISION_REQUIRED']:
                logger.warning(f"Invalid status for submission: {job_description.status}")
                return Response(
                    {'error': f'Cannot submit job description with status: {job_description.get_status_display()}. Only DRAFT or REVISION_REQUIRED can be submitted.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # UPDATED: For vacant positions, check if we have a manager to approve
            if not job_description.assigned_employee:
                # This is a vacant position - we can submit it but check for manager
                if not job_description.reports_to:
                    logger.warning(f"Vacant position JD {job_description.id} has no manager assigned")
                    return Response(
                        {'error': 'Vacant position job description must have a manager (reports_to) set before submission'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            else:
                # This has an assigned employee - validate manager was auto-assigned
                if not job_description.reports_to:
                    logger.warning(f"Assigned employee JD {job_description.id} has no manager - this should auto-assign")
                    return Response(
                        {'error': 'Job description must have a line manager. Please ensure the assigned employee has a line manager set.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            # Validate request data
            serializer = JobDescriptionSubmissionSerializer(data=request.data)
            if not serializer.is_valid():
                logger.error(f"Serializer validation failed: {serializer.errors}")
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
            logger.info("Starting job description submission transaction...")
            
            with transaction.atomic():
                # Update status to pending line manager approval
                old_status = job_description.status
                job_description.status = 'PENDING_LINE_MANAGER'
                job_description.save(update_fields=['status'])
                
                logger.info(f"Status updated from {old_status} to {job_description.status}")
                
                # Log activity
                employee_info = job_description.get_employee_info()
                description = f"Job description submitted for approval by {request.user.get_full_name()}"
                if employee_info['type'] == 'vacant':
                    description += " (Vacant Position)"
                elif employee_info['type'] == 'existing':
                    description += f" for {employee_info['name']}"
                elif employee_info['type'] == 'manual':
                    description += f" for {employee_info['name']} (Manual Entry)"
                
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
                        'employee_type': employee_info['type'],
                        'reports_to_id': job_description.reports_to.id if job_description.reports_to else None,
                        'reports_to_name': job_description.reports_to.full_name if job_description.reports_to else None
                    }
                )
                
                logger.info(f"Activity logged: {activity.id}")
                logger.info(f"Job description {job_description.id} submitted successfully")
                
                # Prepare response data
                next_step = "pending_line_manager_approval"
                if employee_info['type'] == 'vacant':
                    next_step = "pending_line_manager_approval_vacant_position"
                
                response_data = {
                    'success': True,
                    'message': 'Job description submitted for approval successfully',
                    'job_description_id': str(job_description.id),
                    'status': job_description.get_status_display(),
                    'next_approver': job_description.reports_to.full_name if job_description.reports_to else 'N/A',
                    'workflow_step': next_step,
                    'employee_info': employee_info,
                    'manager_info': job_description.get_manager_info(),
                    'is_vacant_position': employee_info['type'] == 'vacant'
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
    operation_description="Approve job description as line manager - ANY USER CAN APPROVE",
    request_body=JobDescriptionApprovalSerializer,
    responses={200: "Approved successfully"}
)
    @action(detail=True, methods=['post'])
    def approve_by_line_manager(self, request, pk=None):
        """ANY USER CAN APPROVE - No permission restrictions"""
        try:
            logger.info(f"Line manager approval by {request.user.username} for JD {pk}")
            
            # Get the job description object
            job_description = self.get_object()
            
            # Validate request data
            serializer = JobDescriptionApprovalSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
            # Only check status - NO USER PERMISSION CHECKS
            if job_description.status != 'PENDING_LINE_MANAGER':
                return Response(
                    {'error': f'Job description is not pending line manager approval. Current status: {job_description.get_status_display()}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            with transaction.atomic():
                # Update approval fields - ANY USER CAN APPROVE
                job_description.line_manager_approved_by = request.user
                job_description.line_manager_approved_at = timezone.now()
                job_description.line_manager_comments = serializer.validated_data.get('comments', '')
                
                # Handle signature if provided
                signature = serializer.validated_data.get('signature')
                if signature:
                    job_description.line_manager_signature = signature
                
                # Move to appropriate next status
                if job_description.assigned_employee:
                    # If there's an assigned employee, move to employee approval
                    job_description.status = 'PENDING_EMPLOYEE'
                    next_step = 'pending_employee_approval'
                    message = 'Job description approved by line manager - now pending employee approval'
                else:
                    # If it's a vacant position, directly approve
                    job_description.status = 'APPROVED'
                    next_step = 'fully_approved'
                    message = 'Job description fully approved (vacant position)'
                
                job_description.save()
                
                # Log activity
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
                        'employee_type': employee_info['type'],
                        'next_step': next_step
                    }
                )
                
                logger.info(f"Line manager approval successful for JD {job_description.id}")
                
                return Response({
                    'success': True,
                    'message': message,
                    'job_description_id': str(job_description.id),
                    'status': job_description.get_status_display(),
                    'next_step': next_step,
                    'approved_by': request.user.get_full_name(),
                    'employee_info': employee_info,
                    'is_fully_approved': job_description.status == 'APPROVED'
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
        operation_description="Approve job description as employee - ANY USER CAN APPROVE",
        request_body=JobDescriptionApprovalSerializer,
        responses={200: "Approved successfully"}
    )
    @action(detail=True, methods=['post'])
    def approve_as_employee(self, request, pk=None):
        """ANY USER CAN APPROVE AS EMPLOYEE - No permission restrictions"""
        try:
            job_description = self.get_object()
            
            # Only check status - NO USER PERMISSION CHECKS
            if job_description.status != 'PENDING_EMPLOYEE':
                return Response(
                    {'error': f'Job description is not pending employee approval. Current status: {job_description.get_status_display()}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            serializer = JobDescriptionApprovalSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
            with transaction.atomic():
                # Update approval fields - ANY USER CAN APPROVE
                job_description.employee_approved_by = request.user
                job_description.employee_approved_at = timezone.now()
                job_description.employee_comments = serializer.validated_data.get('comments', '')
                job_description.status = 'APPROVED'  # Fully approved
                
                # Handle signature if provided
                signature = serializer.validated_data.get('signature')
                if signature:
                    job_description.employee_signature = signature
                
                job_description.save()
                
                # Log activity
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
        operation_description="Reject job description - ANY USER CAN REJECT",
        request_body=JobDescriptionRejectionSerializer,
        responses={200: "Rejected successfully"}
    )
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """ANY USER CAN REJECT - No permission restrictions"""
        try:
            job_description = self.get_object()
            
            # Only check if it's in a rejectable state - NO USER PERMISSION CHECKS
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
                
                # Log activity
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
        """UPDATED: Request revision for job description - NO ROLE RESTRICTIONS"""
        try:
            job_description = self.get_object()
            
            # Check if user can request revision (any authenticated user can request for pending approvals)
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
                
                # Log activity
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

    def _create_simplified_professional_pdf(self, job_description, buffer):
        """Sadə, anlaşıqlı və professional PDF"""
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch, cm
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
            from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
            from django.utils import timezone
            from datetime import datetime
            
            logger.info("Starting simplified professional PDF creation")
            
            # Document setup - daha kiçik margin
            doc = SimpleDocTemplate(
                buffer,
                pagesize=A4,
                rightMargin=1.5*cm,
                leftMargin=1.5*cm,
                topMargin=2*cm,
                bottomMargin=1.5*cm
            )
            
            # Sadə və təmiz styles
            styles = self._create_simplified_styles()
            story = []
            
            # 1. DOCUMENT HEADER - sadə və professional
            self._add_simple_header(story, job_description, styles)
            
            # 2. BASIC INFORMATION - kompakt table
            self._add_compact_basic_info(story, job_description, styles)
            
            # 3. JOB PURPOSE - sadə format
            if hasattr(job_description, 'job_purpose') and job_description.job_purpose:
                self._add_simple_job_purpose(story, job_description, styles)
            
            # 4. JOB SECTIONS - kiçik fontlar
            if hasattr(job_description, 'sections') and job_description.sections.exists():
                self._add_compact_sections(story, job_description, styles)
            
            # 5. SKILLS & COMPETENCIES - kompakt tables
            self._add_compact_skills_competencies(story, job_description, styles)
            
            # 6. APPROVAL SECTION - sadə format
            if job_description.status == 'APPROVED':
                self._add_simple_approval_section(story, job_description, styles)
            
            # 7. FOOTER
            self._add_simple_footer(story, job_description, styles)
            
            # Build PDF
            doc.build(story)
            logger.info("Simplified PDF created successfully")
            
            return buffer
            
        except Exception as e:
            logger.error(f"Simplified PDF creation failed: {str(e)}")
            raise
    
    def _create_simplified_styles(self):
        """Sadə və anlaşıqlı styles"""
        
        styles = getSampleStyleSheet()
        
        # Main title - sadə
        styles.add(ParagraphStyle(
            name='SimpleTitle',
            parent=styles['Title'],
            fontSize=18,  # Kiçildilmiş
            spaceAfter=15,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#2c3e50'),  # Sadə boz
            fontName='Helvetica-Bold'
        ))
        
        # Job title 
        styles.add(ParagraphStyle(
            name='JobTitle',
            parent=styles['Heading1'],
            fontSize=16,  # Kiçildilmiş
            spaceAfter=12,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#34495e'),
            fontName='Helvetica-Bold'
        ))
        
        # Section headers - sadə
        styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=styles['Heading2'],
            fontSize=12,  # Kiçildilmiş
            spaceBefore=15,
            spaceAfter=8,
            textColor=colors.HexColor('#2980b9'),  # Sadə mavi
            fontName='Helvetica-Bold',
            leftIndent=0
        ))
        
        # Subsection headers
        styles.add(ParagraphStyle(
            name='SubHeader',
            parent=styles['Heading3'],
            fontSize=11,  # Kiçildilmiş
            spaceBefore=10,
            spaceAfter=6,
            textColor=colors.HexColor('#34495e'),
            fontName='Helvetica-Bold'
        ))
        
        # Normal text - kiçik
        styles.add(ParagraphStyle(
            name='SimpleNormal',
            parent=styles['Normal'],
            fontSize=9,  # Kiçildilmiş
            leading=12,
            spaceAfter=4,
            fontName='Helvetica',
            alignment=TA_JUSTIFY
        ))
        
        # Table text - çox kiçik
        styles.add(ParagraphStyle(
            name='TableText',
            parent=styles['Normal'],
            fontSize=8,  # Çox kiçik
            leading=10,
            fontName='Helvetica'
        ))
        
        # Status badge - sadə
        styles.add(ParagraphStyle(
            name='SimpleStatus',
            parent=styles['Normal'],
            fontSize=10,
            alignment=TA_CENTER,
            textColor=colors.white,
            fontName='Helvetica-Bold',
            spaceAfter=12
        ))
        
        # Important info - minimal
        styles.add(ParagraphStyle(
            name='InfoBox',
            parent=styles['Normal'],
            fontSize=9,
            fontName='Helvetica',
            textColor=colors.HexColor('#2c3e50'),
            backColor=colors.HexColor('#ecf0f1'),  # Çox açıq boz
            borderWidth=1,
            borderColor=colors.HexColor('#bdc3c7'),
            borderPadding=6,
            spaceAfter=10
        ))
        
        return styles
    
    def _add_simple_header(self, story, job_description, styles):
        """Sadə header section"""
        
        # Main title
        story.append(Paragraph("JOB DESCRIPTION", styles['SimpleTitle']))
        story.append(Spacer(1, 0.15*inch))
        
        # Status - sadə rəng
        status_colors = {
            'DRAFT': colors.HexColor('#95a5a6'),
            'PENDING_LINE_MANAGER': colors.HexColor('#f39c12'),
            'PENDING_EMPLOYEE': colors.HexColor('#3498db'),
            'APPROVED': colors.HexColor("#afdbc2"),
            'REJECTED': colors.HexColor('#e74c3c'),
            'REVISION_REQUIRED': colors.HexColor('#9b59b6'),
        }
        
        status_style = ParagraphStyle(
            'StatusBadge',
            parent=styles['SimpleStatus'],
            backColor=status_colors.get(job_description.status, colors.gray),
            borderWidth=1,
            borderColor=status_colors.get(job_description.status, colors.gray),
            borderPadding=6
        )
        
        story.append(Paragraph(f"Status: {job_description.get_status_display()}", status_style))
        
        # Job title
        story.append(Paragraph(job_description.job_title, styles['JobTitle']))
        story.append(Spacer(1, 0.1*inch))
    
    def _add_compact_basic_info(self, story, job_description, styles):
        """Kompakt basic information"""
        
        story.append(Paragraph("Basic Information", styles['SectionHeader']))
        
        # Employee və manager info
        employee_info = job_description.get_employee_info()
        manager_info = job_description.get_manager_info()
        
        # Kompakt 3 sütunlu table
        basic_data = [
            # Row 1
            ['Business Function:', 
             job_description.business_function.name if job_description.business_function else 'N/A',
             'Department:',
             job_description.department.name if job_description.department else 'N/A'],
            
            # Row 2
            ['Job Function:',
             job_description.job_function.name if job_description.job_function else 'N/A',
             'Position Group:',
             job_description.position_group.name if job_description.position_group else 'N/A'],
            
            # Row 3
            ['Grading Level:',
             job_description.grading_level or 'N/A',
             'Employee:',
             employee_info.get('name', 'Vacant Position')],
            
            # Row 4
            ['Reports To:',
             manager_info.get('name', 'N/A') if manager_info else 'N/A',
             'Created Date:',
             job_description.created_at.strftime('%d/%m/%Y') if job_description.created_at else 'N/A']
        ]
        
        basic_table = Table(basic_data, colWidths=[3*cm, 4*cm, 3*cm, 4*cm])
        basic_table.setStyle(TableStyle([
            # Label columns (0, 2) - açıq boz background
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f8f9fa')),
            ('BACKGROUND', (2, 0), (2, -1), colors.HexColor('#f8f9fa')),
            
            # Label font - bold
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
            
            # Data font - normal
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTNAME', (3, 0), (3, -1), 'Helvetica'),
            
            # Kiçik font
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            
            # Alignment
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            
            # Minimal grid
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dee2e6')),
            
            # Minimal padding
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        
        story.append(basic_table)
        story.append(Spacer(1, 0.12*inch))
    
    def _add_simple_job_purpose(self, story, job_description, styles):
        """Sadə job purpose"""
        
        story.append(Paragraph("Job Purpose", styles['SectionHeader']))
        
        purpose_style = ParagraphStyle(
            'Purpose',
            parent=styles['SimpleNormal'],
            backColor=colors.HexColor('#f8f9fa'),
            borderWidth=1,
            borderColor=colors.HexColor('#dee2e6'),
            borderPadding=8,
            spaceAfter=12
        )
        
        story.append(Paragraph(job_description.job_purpose, purpose_style))
    
    def _add_compact_sections(self, story, job_description, styles):
        """FIXED: Kompakt job sections with proper text wrapping"""
        
        story.append(Paragraph("Job Sections", styles['SectionHeader']))
        
        for section in job_description.sections.all():
            # Section title style
            section_style = ParagraphStyle(
                'SectionTitle',
                parent=styles['SubHeader'],
                fontSize=10,
                textColor=colors.HexColor('#2980b9'),
                spaceAfter=6,
                spaceBefore=8
            )
            
            # FIXED: Content style with proper wrapping
            content_style = ParagraphStyle(
                'SectionContent',
                parent=styles['SimpleNormal'],
                fontSize=8,
                leftIndent=10,
                spaceAfter=10,
                alignment=TA_JUSTIFY,  # Justify text for better appearance
                wordWrap='LTR',        # Enable word wrapping
                leading=10             # Line spacing
            )
            
            story.append(Paragraph(f"• {section.title}", section_style))
            
            # FIXED: Split long content into paragraphs if needed
            content_text = section.content.strip()
            
            # If content is very long, split by sentences for better formatting
            if len(content_text) > 500:
                sentences = content_text.split('. ')
                current_paragraph = ""
                
                for sentence in sentences:
                    if len(current_paragraph + sentence) > 400:  # Break at ~400 chars
                        if current_paragraph:
                            story.append(Paragraph(current_paragraph.strip() + '.', content_style))
                            current_paragraph = sentence
                        else:
                            story.append(Paragraph(sentence + '.', content_style))
                            current_paragraph = ""
                    else:
                        current_paragraph += sentence + '. '
                
                # Add remaining content
                if current_paragraph.strip():
                    story.append(Paragraph(current_paragraph.strip(), content_style))
            else:
                story.append(Paragraph(content_text, content_style))
            
            # Add small spacer between sections
            story.append(Spacer(1, 0.05*inch))


    def _add_compact_skills_competencies(self, story, job_description, styles):
        """FIXED: Kompakt skills with better table formatting"""
        
        # Skills
        if hasattr(job_description, 'required_skills') and job_description.required_skills.exists():
            story.append(Paragraph("Required Skills", styles['SectionHeader']))
            
            skills_data = [['Skill', 'Level', 'Required']]
            
            for skill_req in job_description.required_skills.all():
                # FIXED: Better text wrapping for skill names
                skill_name = skill_req.skill.name
                if len(skill_name) > 30:
                    skill_name = skill_name[:27] + '...'
                
                skills_data.append([
                    skill_name,
                    skill_req.get_proficiency_level_display()[:12],  # Limit level text
                    'Yes' if skill_req.is_mandatory else 'No'
                ])
            
            # FIXED: Better column widths
            skills_table = Table(skills_data, colWidths=[8*cm, 3*cm, 2*cm])
            skills_table.setStyle(TableStyle([
                # Header styling
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                
                # Data styling
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                
                # Grid and colors
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#bdc3c7')),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
                
                # FIXED: Better padding for text wrapping
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                
                # FIXED: Word wrap for long text
                ('WORDWRAP', (0, 0), (-1, -1), True),
            ]))
            
            story.append(skills_table)
            story.append(Spacer(1, 0.1*inch))
        
        # FIXED: Similar improvements for Behavioral Competencies
        if hasattr(job_description, 'behavioral_competencies') and job_description.behavioral_competencies.exists():
            story.append(Paragraph("Behavioral Competencies", styles['SectionHeader']))
            
            comp_data = [['Competency', 'Level', 'Required']]
            
            for comp_req in job_description.behavioral_competencies.all():
                comp_name = comp_req.competency.name
                if len(comp_name) > 30:
                    comp_name = comp_name[:27] + '...'
                
                comp_data.append([
                    comp_name,
                    comp_req.get_proficiency_level_display()[:12],
                    'Yes' if comp_req.is_mandatory else 'No'
                ])
            
            comp_table = Table(comp_data, colWidths=[8*cm, 3*cm, 2*cm])
            comp_table.setStyle(TableStyle([
                # Same styling as skills table but with green header
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#27ae60')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#bdc3c7')),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                ('WORDWRAP', (0, 0), (-1, -1), True),
            ]))
            
            story.append(comp_table)
            story.append(Spacer(1, 0.1*inch))
    def _add_simple_approval_section(self, story, job_description, styles):
        """Sadə approval section"""
        
        story.append(PageBreak())
        story.append(Paragraph("Document Approval", styles['SectionHeader']))
        
        # Approval status - sadə
        approval_style = ParagraphStyle(
            'ApprovalStatus',
            parent=styles['InfoBox'],
            fontSize=10,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#27ae60'),
            backColor=colors.HexColor('#d5f4e6'),
            borderColor=colors.HexColor('#27ae60'),
            spaceAfter=15
        )
        
        story.append(Paragraph("✓ DOCUMENT APPROVED", approval_style))
        
        # Approval details - kompakt table
        approval_data = []
        employee_info = job_description.get_employee_info()
        manager_info = job_description.get_manager_info()
        # Line Manager
        if hasattr(job_description, 'line_manager_approved_by') and job_description.line_manager_approved_by:
            approval_data.extend([
                ['Line Manager:', manager_info.get('name', 'N/A') if manager_info else 'N/A'],
                # ['Line Manager:', job_description.line_manager_approved_by.get_full_name()],
                ['Approval Date:', job_description.line_manager_approved_at.strftime('%d/%m/%Y %H:%M') if job_description.line_manager_approved_at else 'N/A'],
                ['Comments:', getattr(job_description, 'line_manager_comments', 'No comments')[:50] + '...' if len(getattr(job_description, 'line_manager_comments', '')) > 50 else getattr(job_description, 'line_manager_comments', 'No comments')],
            ])

        
        # Employee (if exists)
        if hasattr(job_description, 'employee_approved_by') and job_description.employee_approved_by:
            if approval_data:  # Add separator if line manager data exists
                approval_data.append(['', ''])
            
            approval_data.extend([
                ['Employee:', employee_info.get('name', 'Vacant Position')],
                # ['Employee:', job_description.employee_approved_by.get_full_name()],
                ['Approval Date:', job_description.employee_approved_at.strftime('%d/%m/%Y %H:%M') if job_description.employee_approved_at else 'N/A'],
                ['Comments:', getattr(job_description, 'employee_comments', 'No comments')[:50] + '...' if len(getattr(job_description, 'employee_comments', '')) > 50 else getattr(job_description, 'employee_comments', 'No comments')],
            ])
        else:
            if approval_data:
                approval_data.append(['', ''])
            approval_data.append(['Employee:', 'N/A (Vacant Position)'])
        
        approval_table = Table(approval_data, colWidths=[3*cm, 11*cm])
        approval_table.setStyle(TableStyle([
            # Label column
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f8f9fa')),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dee2e6')),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ]))
        
        story.append(approval_table)
        story.append(Spacer(1, 0.15*inch))
        
        # Digital signature note - kiçik
        signature_style = ParagraphStyle(
            'Signature',
            parent=styles['SimpleNormal'],
            fontSize=8,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#7f8c8d'),
            fontStyle='Italic'
        )
        
        story.append(Paragraph("This document has been digitally signed and approved.", signature_style))
    
    def _add_simple_footer(self, story, job_description, styles):
        """Sadə footer"""
        
        story.append(Spacer(1, 0.2*inch))
        
        # Simple line
        from reportlab.platypus.flowables import HRFlowable
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#bdc3c7')))
        
        # Footer info - kiçik
        footer_style = ParagraphStyle(
            'Footer',
            parent=styles['SimpleNormal'],
            fontSize=7,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#7f8c8d'),
            spaceAfter=5
        )
        
        story.append(Paragraph(f"Generated: {datetime.now().strftime('%d/%m/%Y %H:%M')} | Document ID: {str(job_description.id)[:8]}", footer_style))
        story.append(Paragraph("HRIS - Job Description Management System", footer_style))

    @action(detail=True, methods=['get'])
    def download_pdf(self, request, pk=None):
        """Sadə və anlaşıqlı PDF download"""
        
        if not HAS_REPORTLAB:
            return HttpResponse("PDF library not available", status=500, content_type='text/plain')
        
        try:
            job_description = self.get_object()
            logger.info(f"Creating simplified PDF for: {job_description.job_title}")
            
            buffer = BytesIO()
            
            # Use simplified PDF creation
            try:
                self._create_simplified_professional_pdf(job_description, buffer)
                logger.info("Simplified PDF created successfully")
            except Exception as pdf_error:
                logger.error(f"Simplified PDF failed, using fallback: {str(pdf_error)}")
                buffer = BytesIO()  # Reset
                self._create_simple_fallback_pdf(job_description, buffer)
            
            # Validate buffer
            buffer.seek(0)
            pdf_data = buffer.getvalue()
            
            if len(pdf_data) == 0:
                return HttpResponse("PDF creation failed", status=500, content_type='text/plain')
            
            # Safe filename
            safe_title = "".join(c for c in job_description.job_title if c.isalnum() or c in (' ', '-', '_'))
            safe_title = safe_title.strip()[:25]
            
            status_suffix = ""
            if job_description.status == 'APPROVED':
                status_suffix = "_APPROVED"
            elif job_description.status in ['PENDING_LINE_MANAGER', 'PENDING_EMPLOYEE']:
                status_suffix = "_PENDING"
            
            filename = f"JD_{safe_title}{status_suffix}_{datetime.now().strftime('%Y%m%d')}.pdf"
            
            # Response
            response = HttpResponse(pdf_data, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            response['Content-Length'] = len(pdf_data)
            response['Cache-Control'] = 'no-cache'
            
            logger.info(f"PDF response created: {filename} ({len(pdf_data)} bytes)")
            return response
            
        except Exception as e:
            logger.error(f"PDF error: {str(e)}")
            return HttpResponse(f"PDF Error: {str(e)}", status=500, content_type='text/plain')
    
    @action(detail=False, methods=['post'], url_path='export-bulk-pdf')
    def export_bulk_pdf(self, request):
        """Multiple job descriptions-ı bir PDF-də export etmək"""
        if not HAS_REPORTLAB:
            return Response(
                {'error': 'PDF export not available. Please install reportlab'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        try:
            # Request data
            job_description_ids = request.data.get('job_description_ids', [])
            include_approvals = request.data.get('include_approvals', True)
            
            if not job_description_ids:
                # Əgər ID-lər verilməyibsə, filterlənmiş nəticələri al
                queryset = self.filter_queryset(self.get_queryset())
                job_descriptions = queryset[:20]  # Maksimum 20 JD
            else:
                # Specific ID-lər
                job_descriptions = JobDescription.objects.filter(id__in=job_description_ids)
            
            if not job_descriptions.exists():
                return Response(
                    {'error': 'No job descriptions found to export'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Bulk PDF yaradırıq
            buffer = BytesIO()
            self._create_bulk_pdf(job_descriptions, buffer, include_approvals)
            
            buffer.seek(0)
            
            response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
            filename = f"Job_Descriptions_Bulk_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            response['Content-Length'] = len(buffer.getvalue())
            
            return response
            
        except Exception as e:
            logger.error(f"Error generating bulk PDF: {str(e)}")
            return Response(
                {'error': f'Failed to generate bulk PDF: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _create_bulk_pdf(self, job_descriptions, buffer, include_approvals=True):
        """Multiple job descriptions üçün comprehensive PDF"""
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch, cm
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
            from reportlab.lib.enums import TA_LEFT, TA_CENTER
            from datetime import datetime
            
            doc = SimpleDocTemplate(
                buffer, 
                pagesize=A4, 
                rightMargin=2*cm, 
                leftMargin=2*cm, 
                topMargin=2*cm, 
                bottomMargin=2*cm
            )
            
            styles = getSampleStyleSheet()
            story = []
            
            # Title page with enhanced styling
            title_style = ParagraphStyle(
                'BulkTitle', 
                parent=styles['Heading1'], 
                fontSize=28, 
                alignment=TA_CENTER, 
                spaceAfter=40,
                textColor=colors.HexColor('#1e3a8a'),
                fontName='Helvetica-Bold',
                borderWidth=3,
                borderColor=colors.HexColor('#3b82f6'),
                borderPadding=20,
                backColor=colors.HexColor('#eff6ff')
            )
            
            subtitle_style = ParagraphStyle(
                'Subtitle',
                parent=styles['Normal'],
                fontSize=14,
                alignment=TA_CENTER,
                spaceAfter=20,
                textColor=colors.HexColor('#374151')
            )
            
            story.append(Paragraph("📚 JOB DESCRIPTIONS COLLECTION", title_style))
            story.append(Spacer(1, 0.3*inch))
            
            # Summary information
            total_count = job_descriptions.count()
            approved_count = job_descriptions.filter(status='APPROVED').count()
            pending_count = job_descriptions.filter(status__in=['PENDING_LINE_MANAGER', 'PENDING_EMPLOYEE']).count()
            draft_count = job_descriptions.filter(status='DRAFT').count()
            
            summary_data = [
                ['Total Documents:', str(total_count)],
                ['Approved Documents:', str(approved_count)],
                ['Pending Approval:', str(pending_count)],
                ['Draft Documents:', str(draft_count)],
                ['Generated Date:', datetime.now().strftime('%B %d, %Y at %H:%M')],
                ['Include Approvals:', 'Yes' if include_approvals else 'No']
            ]
            
            summary_table = Table(summary_data, colWidths=[5*cm, 6*cm])
            summary_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f3f4f6')),
                ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#374151')),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 12),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#d1d5db')),
                ('LEFTPADDING', (0, 0), (-1, -1), 10),
                ('RIGHTPADDING', (0, 0), (-1, -1), 10),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8)
            ]))
            
            story.append(summary_table)
            story.append(Spacer(1, 0.4*inch))
            
            # Table of contents
            toc_style = ParagraphStyle(
                'TOCTitle',
                parent=styles['Heading2'],
                fontSize=18,
                alignment=TA_CENTER,
                spaceAfter=20,
                textColor=colors.HexColor('#1e40af'),
                fontName='Helvetica-Bold'
            )
            
            story.append(Paragraph("📑 TABLE OF CONTENTS", toc_style))
            
            toc_data = [['#', 'Job Title', 'Department', 'Status', 'Page']]
            
            for i, jd in enumerate(job_descriptions, 1):
                page_num = i + 1  # Approximate page number
                toc_data.append([
                    str(i),
                    str(jd.job_title)[:40] + '...' if len(str(jd.job_title)) > 40 else str(jd.job_title),
                    str(jd.department.name) if jd.department else 'N/A',
                    jd.get_status_display(),
                    str(page_num)
                ])
            
            toc_table = Table(toc_data, colWidths=[1*cm, 6*cm, 3*cm, 3*cm, 2*cm])
            toc_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e40af')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#1e40af')),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#f8fafc'), colors.white])
            ]))
            
            story.append(toc_table)
            story.append(PageBreak())
            
            # Individual job descriptions
            for i, jd in enumerate(job_descriptions):
                if i > 0:
                    story.append(PageBreak())
                
                # JD Header
                jd_header_style = ParagraphStyle(
                    'JDHeader',
                    parent=styles['Heading1'],
                    fontSize=20,
                    alignment=TA_CENTER,
                    spaceAfter=20,
                    textColor=colors.HexColor('#1f2937'),
                    fontName='Helvetica-Bold',
                    borderWidth=2,
                    borderColor=colors.HexColor('#6b7280'),
                    borderPadding=15,
                    backColor=colors.HexColor('#f9fafb')
                )
                
                story.append(Paragraph(f"Job Description {i+1}: {jd.job_title}", jd_header_style))
                story.append(Spacer(1, 0.2*inch))
                
                # Status badge
                status_colors = {
                    'DRAFT': colors.HexColor('#6b7280'),
                    'PENDING_LINE_MANAGER': colors.HexColor('#f59e0b'),
                    'PENDING_EMPLOYEE': colors.HexColor('#3b82f6'),
                    'APPROVED': colors.HexColor('#10b981'),
                    'REJECTED': colors.HexColor('#ef4444'),
                    'REVISION_REQUIRED': colors.HexColor('#8b5cf6'),
                }
                
                status_style = ParagraphStyle(
                    'StatusBadge',
                    parent=styles['Normal'],
                    fontSize=12,
                    alignment=TA_CENTER,
                    textColor=colors.white,
                    backColor=status_colors.get(jd.status, colors.gray),
                    borderWidth=2,
                    borderColor=status_colors.get(jd.status, colors.gray),
                    borderPadding=8,
                    spaceAfter=20
                )
                
                story.append(Paragraph(f"STATUS: {jd.get_status_display()}", status_style))
                
                # Basic info
                employee_info = jd.get_employee_info() if hasattr(jd, 'get_employee_info') else {'name': 'Vacant'}
                manager_info = jd.get_manager_info() if hasattr(jd, 'get_manager_info') else None
                
                info_data = [
                    ['Business Function:', jd.business_function.name if jd.business_function else 'N/A'],
                    ['Department:', jd.department.name if jd.department else 'N/A'],
                    ['Job Function:', jd.job_function.name if jd.job_function else 'N/A'],
                    ['Position Group:', jd.position_group.name if jd.position_group else 'N/A'],
                    ['Grading Level:', str(jd.grading_level) if jd.grading_level else 'N/A'],
                    ['Employee:', employee_info.get('name', 'Vacant Position')],
                    ['Reports To:', manager_info['name'] if manager_info else 'No Manager'],
                    ['Created:', jd.created_at.strftime('%B %d, %Y') if jd.created_at else 'N/A'],
                    ['Document ID:', str(jd.id)[:8].upper()]
                ]
                
                info_table = Table(info_data, colWidths=[4*cm, 8*cm])
                info_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#eff6ff')),
                    ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#1e40af')),
                    ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                    ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 0), (-1, -1), 10),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#3b82f6')),
                    ('LEFTPADDING', (0, 0), (-1, -1), 8),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                    ('TOPPADDING', (0, 0), (-1, -1), 6),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 6)
                ]))
                
                story.append(info_table)
                story.append(Spacer(1, 0.2*inch))
                
                # Job purpose
                if hasattr(jd, 'job_purpose') and jd.job_purpose:
                    purpose_style = ParagraphStyle(
                        'Purpose',
                        parent=styles['Normal'],
                        fontSize=11,
                        leading=16,
                        spaceAfter=15,
                        backColor=colors.HexColor('#fefce8'),
                        borderWidth=1,
                        borderColor=colors.HexColor('#eab308'),
                        borderPadding=10
                    )
                    
                    story.append(Paragraph("🎯 Job Purpose:", styles['Heading3']))
                    story.append(Paragraph(str(jd.job_purpose), purpose_style))
                    story.append(Spacer(1, 0.15*inch))
                
                # Approval information for approved documents
                if include_approvals and jd.status == 'APPROVED':
                    approval_style = ParagraphStyle(
                        'ApprovalInfo',
                        parent=styles['Normal'],
                        fontSize=10,
                        backColor=colors.HexColor('#d4edda'),
                        borderWidth=1,
                        borderColor=colors.HexColor('#28a745'),
                        borderPadding=10,
                        spaceAfter=15
                    )
                    
                    approval_text = "✅ <b>APPROVAL STATUS: FULLY APPROVED</b><br/>"
                    
                    if hasattr(jd, 'line_manager_approved_by') and jd.line_manager_approved_by:
                        approval_text += f"Line Manager: {jd.line_manager_approved_by.get_full_name()}"
                        if jd.line_manager_approved_at:
                            approval_text += f" ({jd.line_manager_approved_at.strftime('%B %d, %Y')})"
                        approval_text += "<br/>"
                    
                    if hasattr(jd, 'employee_approved_by') and jd.employee_approved_by:
                        approval_text += f"Employee: {jd.employee_approved_by.get_full_name()}"
                        if jd.employee_approved_at:
                            approval_text += f" ({jd.employee_approved_at.strftime('%B %d, %Y')})"
                    else:
                        approval_text += "Employee: N/A (Vacant Position)"
                    
                    story.append(Paragraph(approval_text, approval_style))
                
                # Add space before next document
                if i < len(job_descriptions) - 1:
                    story.append(Spacer(1, 0.3*inch))
            
            # Summary footer
            story.append(PageBreak())
            
            footer_style = ParagraphStyle(
                'Footer',
                parent=styles['Normal'],
                fontSize=10,
                alignment=TA_CENTER,
                textColor=colors.HexColor('#6b7280'),
                spaceAfter=20
            )
            
            story.append(Paragraph("📊 BULK EXPORT SUMMARY", styles['Heading2']))
            story.append(Spacer(1, 0.2*inch))
            
            summary_text = f"""
            Total Documents Exported: {total_count}<br/>
            Approved Documents: {approved_count}<br/>
            Pending Documents: {pending_count}<br/>
            Draft Documents: {draft_count}<br/>
            Export Date: {datetime.now().strftime('%B %d, %Y at %H:%M:%S')}<br/>
            Generated by: ALMET HRIS System
            """
            
            story.append(Paragraph(summary_text, footer_style))
            
            # Build the PDF
            doc.build(story)
            return buffer
            
        except Exception as e:
            logger.error(f"Error creating bulk PDF: {str(e)}")
            # Fallback to simple bulk PDF
            return self._create_simple_bulk_pdf(job_descriptions, buffer)
    
    def _create_simple_bulk_pdf(self, job_descriptions, buffer):
        """Simple fallback bulk PDF"""
        try:
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.units import inch, cm
            from reportlab.lib import colors
            from reportlab.lib.enums import TA_CENTER
            from datetime import datetime
            
            doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
            styles = getSampleStyleSheet()
            story = []
            
         
            
            # Simple job descriptions
            for i, jd in enumerate(job_descriptions):
                if i > 0:
                    story.append(PageBreak())
                
                story.append(Paragraph(f"Job Description {i+1}: {jd.job_title}", styles['Heading1']))
                story.append(Spacer(1, 0.1*inch))
                
                # Basic info table
                info_data = [
                    ['Department:', jd.department.name if jd.department else 'N/A'],
                    ['Status:', jd.get_status_display()],
                    ['Created:', jd.created_at.strftime('%B %d, %Y') if jd.created_at else 'N/A']
                ]
                
                info_table = Table(info_data, colWidths=[4*cm, 8*cm])
                info_table.setStyle(TableStyle([
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                    ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
                    ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold')
                ]))
                
                story.append(info_table)
                story.append(Spacer(1, 0.2*inch))
                
                # Job purpose if available
                if hasattr(jd, 'job_purpose') and jd.job_purpose:
                    story.append(Paragraph("Job Purpose:", styles['Heading3']))
                    story.append(Paragraph(str(jd.job_purpose)[:200] + '...' if len(str(jd.job_purpose)) > 200 else str(jd.job_purpose), styles['Normal']))
                    story.append(Spacer(1, 0.1*inch))
            
            doc.build(story)
            return buffer
            
        except Exception as e:
            logger.error(f"Even simple bulk PDF failed: {str(e)}")
            # Create minimal text response
            buffer = BytesIO()
            buffer.write(b"Bulk PDF creation completely failed. Check server logs.")
            return buffer
  
class JobBusinessResourceViewSet(viewsets.ModelViewSet):
    """ViewSet for Job Business Resources"""
    
    queryset = JobBusinessResource.objects.all()
    serializer_class = JobBusinessResourceSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = [ 'is_active']
    search_fields = ['name', 'description' ]
    ordering = [ 'name', 'description']
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    
class AccessMatrixViewSet(viewsets.ModelViewSet):
    """ViewSet for Access Matrix"""
    
    queryset = AccessMatrix.objects.all()
    serializer_class = AccessMatrixSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = [ 'is_active']
    search_fields = ['name', 'description', ]
    ordering = [ 'name','description']
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class CompanyBenefitViewSet(viewsets.ModelViewSet):
    """ViewSet for Company Benefits"""
    
    queryset = CompanyBenefit.objects.all()
    serializer_class = CompanyBenefitSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = [ 'is_active']
    search_fields = ['name', 'description', ]
    ordering = [ 'name', 'description']
    
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
        
        # ADDED: By job function
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
        
        # ADDED: Vacant vs Assigned breakdown
        vacant_positions = queryset.filter(assigned_employee__isnull=True).count()
        assigned_positions = queryset.filter(assigned_employee__isnull=False).count()
        
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
                'vacant_positions': vacant_positions,
                'assigned_positions': assigned_positions
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