# api/job_description_views.py - FIXED: Complete file with proper error handling

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Count
from django.db import transaction
from django.utils import timezone
from django.http import HttpResponse
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
import logging
import uuid

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
from .models import BusinessFunction, Department, Unit, PositionGroup, Employee
from .job_description_serializers import JobDescriptionExportSerializer

logger = logging.getLogger(__name__)


class JobDescriptionFilter:
    """FIXED: Advanced filtering for job descriptions"""
    
    def __init__(self, queryset, params):
        self.queryset = queryset
        # FIXED: Convert QueryDict to regular dict to avoid immutable issues
        if hasattr(params, 'dict'):
            self.params = params.dict()
        else:
            self.params = dict(params)
    
    def get_list_values(self, param_name):
        """FIXED: Get list values from query params safely"""
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
    """FIXED: ViewSet for Job Description management"""
    
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['job_title', 'job_purpose', 'business_function__name', 'department__name']
    ordering_fields = ['job_title', 'created_at', 'status', 'business_function__name']
    ordering = ['-created_at']
    
    def get_queryset(self):
        return JobDescription.objects.select_related(
            'business_function', 'department', 'unit', 'position_group',
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
        """FIXED: Override get_object to handle UUID properly"""
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
        
        # FIXED: Handle both UUID and integer lookup
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
        """FIXED: Submit job description for approval with enhanced error handling"""
        try:
            logger.info(f"Submit for approval request - User: {request.user.username}, JD ID: {pk}")
            logger.info(f"Request data: {request.data}")
            
            # Get the job description object using the fixed get_object method
            job_description = self.get_object()
            logger.info(f"Job description found: {job_description.job_title}, Status: {job_description.status}")
            logger.info(f"Created by: {job_description.created_by.username if job_description.created_by else 'None'}")
            logger.info(f"Reports to: {job_description.reports_to.full_name if job_description.reports_to else 'None'}")
            
            # FIXED: Check if user can submit (creator or admin)
            if job_description.created_by != request.user and not request.user.is_staff:
                logger.warning(f"Permission denied - User {request.user.username} is not creator or admin")
                return Response(
                    {'error': 'Only the creator or admin can submit job description for approval'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # FIXED: Check valid status for submission
            if job_description.status not in ['DRAFT', 'REVISION_REQUIRED']:
                logger.warning(f"Invalid status for submission: {job_description.status}")
                return Response(
                    {'error': f'Cannot submit job description with status: {job_description.get_status_display()}. Only DRAFT or REVISION_REQUIRED can be submitted.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # FIXED: Validate that reports_to is set
            if not job_description.reports_to:
                logger.warning(f"No reports_to set for job description {job_description.id}")
                return Response(
                    {'error': 'Job description must have a line manager (reports_to) set before submission'},
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
                activity = JobDescriptionActivity.objects.create(
                    job_description=job_description,
                    activity_type='SUBMITTED_FOR_APPROVAL',
                    description=f"Job description submitted for approval by {request.user.get_full_name()}",
                    performed_by=request.user,
                    metadata={
                        'comments': serializer.validated_data.get('comments', ''),
                        'submit_to_line_manager': serializer.validated_data.get('submit_to_line_manager', True),
                        'old_status': old_status,
                        'new_status': job_description.status,
                        'reports_to_id': job_description.reports_to.id if job_description.reports_to else None,
                        'reports_to_name': job_description.reports_to.full_name if job_description.reports_to else None
                    }
                )
                
                logger.info(f"Activity logged: {activity.id}")
                logger.info(f"Job description {job_description.id} submitted successfully")
                
                # Prepare response data
                response_data = {
                    'success': True,
                    'message': 'Job description submitted for approval successfully',
                    'job_description_id': str(job_description.id),
                    'status': job_description.get_status_display(),
                    'next_approver': job_description.reports_to.full_name if job_description.reports_to else 'N/A',
                    'workflow_step': 'pending_line_manager_approval',
                    'employee_info': job_description.get_employee_info(),
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
    def approve_as_line_manager(self, request, pk=None):
        """Approve job description as line manager"""
        try:
            job_description = self.get_object()
            
            if not job_description.can_be_approved_by_line_manager(request.user):
                return Response(
                    {'error': 'You are not authorized to approve this job description as line manager'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            serializer = JobDescriptionApprovalSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
            with transaction.atomic():
                job_description.approve_by_line_manager(
                    user=request.user,
                    comments=serializer.validated_data.get('comments', ''),
                    signature=serializer.validated_data.get('signature')
                )
                
                # Log activity
                JobDescriptionActivity.objects.create(
                    job_description=job_description,
                    activity_type='APPROVED_BY_LINE_MANAGER',
                    description=f"Approved by line manager: {request.user.get_full_name()}",
                    performed_by=request.user,
                    metadata={
                        'comments': serializer.validated_data.get('comments', ''),
                        'has_signature': bool(serializer.validated_data.get('signature'))
                    }
                )
                
                return Response({
                    'success': True,
                    'message': 'Job description approved by line manager',
                    'job_description_id': str(job_description.id),
                    'status': job_description.get_status_display(),
                    'next_step': 'Waiting for employee approval'
                })
                
        except Exception as e:
            logger.error(f"Error approving as line manager: {str(e)}")
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
            
            if not job_description.can_be_approved_by_employee(request.user):
                return Response(
                    {'error': 'You are not authorized to approve this job description as employee'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            serializer = JobDescriptionApprovalSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
            with transaction.atomic():
                job_description.approve_by_employee(
                    user=request.user,
                    comments=serializer.validated_data.get('comments', ''),
                    signature=serializer.validated_data.get('signature')
                )
                
                # Log activity
                JobDescriptionActivity.objects.create(
                    job_description=job_description,
                    activity_type='APPROVED_BY_EMPLOYEE',
                    description=f"Approved by employee: {request.user.get_full_name()}",
                    performed_by=request.user,
                    metadata={
                        'comments': serializer.validated_data.get('comments', ''),
                        'has_signature': bool(serializer.validated_data.get('signature'))
                    }
                )
                
                return Response({
                    'success': True,
                    'message': 'Job description fully approved',
                    'job_description_id': str(job_description.id),
                    'status': job_description.get_status_display(),
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
            
            # Check if user can reject
            can_reject = (
                job_description.can_be_approved_by_line_manager(request.user) or
                job_description.can_be_approved_by_employee(request.user)
            )
            
            if not can_reject:
                return Response(
                    {'error': 'You are not authorized to reject this job description'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            serializer = JobDescriptionRejectionSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
            with transaction.atomic():
                job_description.reject(
                    user=request.user,
                    reason=serializer.validated_data['reason']
                )
                
                # Log activity
                JobDescriptionActivity.objects.create(
                    job_description=job_description,
                    activity_type='REJECTED',
                    description=f"Rejected by {request.user.get_full_name()}: {serializer.validated_data['reason']}",
                    performed_by=request.user,
                    metadata={'rejection_reason': serializer.validated_data['reason']}
                )
                
                return Response({
                    'success': True,
                    'message': 'Job description rejected',
                    'job_description_id': str(job_description.id),
                    'status': job_description.get_status_display(),
                    'reason': serializer.validated_data['reason']
                })
                
        except Exception as e:
            logger.error(f"Error rejecting job description: {str(e)}")
            return Response(
                {'error': f'Failed to reject: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @swagger_auto_schema(
        method='post',
        operation_description="Request revision for job description",
        request_body=JobDescriptionRejectionSerializer,
        responses={200: "Revision requested successfully"}
    )
    @action(detail=True, methods=['post'])
    def request_revision(self, request, pk=None):
        """Request revision for job description"""
        try:
            job_description = self.get_object()
            
            # Check if user can request revision
            can_request = (
                job_description.can_be_approved_by_line_manager(request.user) or
                job_description.can_be_approved_by_employee(request.user)
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
                    user=request.user,
                    reason=serializer.validated_data['reason']
                )
                
                # Log activity
                JobDescriptionActivity.objects.create(
                    job_description=job_description,
                    activity_type='REVISION_REQUESTED',
                    description=f"Revision requested by {request.user.get_full_name()}: {serializer.validated_data['reason']}",
                    performed_by=request.user,
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
            # Don't require employee profile for line manager approvals
            line_manager_pending = JobDescription.objects.filter(
                status='PENDING_LINE_MANAGER',
                reports_to__user=user
            ).select_related('business_function', 'department', 'assigned_employee', 'created_by')
            
            logger.info(f"Line manager pending count: {line_manager_pending.count()}")
            
            # Job descriptions where user is the assigned employee and needs to approve
            # This requires an employee profile
            employee_pending = JobDescription.objects.none()  # Default to empty queryset
            if employee:
                employee_pending = JobDescription.objects.filter(
                    status='PENDING_EMPLOYEE',
                    assigned_employee__user=user
                ).select_related('business_function', 'department', 'assigned_employee', 'created_by')
            
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
    
    # Business Resource ViewSets
class JobBusinessResourceViewSet(viewsets.ModelViewSet):
    """ViewSet for Job Business Resources"""
    
    queryset = JobBusinessResource.objects.all()
    serializer_class = JobBusinessResourceSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['category', 'is_active']
    search_fields = ['name', 'description', 'category']
    ordering = ['category', 'name']
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class AccessMatrixViewSet(viewsets.ModelViewSet):
    """ViewSet for Access Matrix"""
    
    queryset = AccessMatrix.objects.all()
    serializer_class = AccessMatrixSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['access_level', 'is_active']
    search_fields = ['name', 'description', 'access_level']
    ordering = ['access_level', 'name']
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class CompanyBenefitViewSet(viewsets.ModelViewSet):
    """ViewSet for Company Benefits"""
    
    queryset = CompanyBenefit.objects.all()
    serializer_class = CompanyBenefitSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['benefit_type', 'is_active']
    search_fields = ['name', 'description', 'benefit_type']
    ordering = ['benefit_type', 'name']
    
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
        
        # Pending approvals by type
        pending_line_manager = queryset.filter(status='PENDING_LINE_MANAGER').count()
        pending_employee = queryset.filter(status='PENDING_EMPLOYEE').count()
        
        # Recent activities
        recent_activities = JobDescriptionActivity.objects.select_related(
            'job_description', 'performed_by'
        ).order_by('-performed_at')[:10]
        
        return Response({
            'total_job_descriptions': total_job_descriptions,
            'status_breakdown': status_stats,
            'department_breakdown': department_stats,
            'business_function_breakdown': function_stats,
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