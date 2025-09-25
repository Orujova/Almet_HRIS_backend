# api/business_trip_views.py
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Count, Sum
from django.utils import timezone
from django.db import transaction
from datetime import datetime, timedelta, date
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
import logging

from .models import Employee
from .business_trip_models import (
    TravelType, TransportType, TripPurpose, ApprovalWorkflow, ApprovalStep,
    BusinessTripRequest, TripSchedule, TripHotel, TripApproval, TripNotification,
    create_default_trip_settings
)
from .business_trip_serializers import (
    TravelTypeSerializer, TransportTypeSerializer, TripPurposeSerializer,
    ApprovalWorkflowSerializer, BusinessTripRequestListSerializer,
    BusinessTripRequestDetailSerializer, BusinessTripRequestCreateSerializer,
    BusinessTripRequestUpdateSerializer, TripApprovalActionSerializer,
    TripStatisticsSerializer, EmployeeOptionSerializer, PendingApprovalSerializer,
    TripNotificationSerializer
)

logger = logging.getLogger(__name__)

class TravelTypeViewSet(viewsets.ModelViewSet):
    """ViewSet for managing travel types (Domestic, Overseas)"""
    queryset = TravelType.objects.filter(is_deleted=False)
    serializer_class = TravelTypeSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['is_active']
    search_fields = ['name', 'code']
    ordering = ['name']

    def get_queryset(self):
        return self.queryset.filter(is_active=True)

class TransportTypeViewSet(viewsets.ModelViewSet):
    """ViewSet for managing transport types (Taxi, Train, Airplane, etc.)"""
    queryset = TransportType.objects.filter(is_deleted=False)
    serializer_class = TransportTypeSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['is_active']
    search_fields = ['name', 'code']
    ordering = ['name']

    def get_queryset(self):
        return self.queryset.filter(is_active=True)

class TripPurposeViewSet(viewsets.ModelViewSet):
    """ViewSet for managing trip purposes (Conference, Meeting, Training, etc.)"""
    queryset = TripPurpose.objects.filter(is_deleted=False)
    serializer_class = TripPurposeSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['is_active']
    search_fields = ['name', 'code']
    ordering = ['name']

    def get_queryset(self):
        return self.queryset.filter(is_active=True)

class ApprovalWorkflowViewSet(viewsets.ModelViewSet):
    """ViewSet for managing approval workflows"""
    queryset = ApprovalWorkflow.objects.filter(is_deleted=False)
    serializer_class = ApprovalWorkflowSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['is_active', 'is_default', 'applies_to_domestic', 'applies_to_overseas']
    search_fields = ['name', 'description']
    ordering = ['name']

class BusinessTripRequestViewSet(viewsets.ModelViewSet):
    """Main ViewSet for Business Trip Requests"""
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = [
        'status', 'travel_type', 'transport_type', 'purpose', 'employee',
        'requested_by', 'line_manager', 'finance_approver', 'hr_approver'
    ]
    search_fields = [
        'request_id', 'employee__full_name', 'employee__employee_id',
        'requested_by__full_name', 'notes'
    ]
    ordering_fields = ['created_at', 'start_date', 'end_date', 'submitted_at', 'status']
    ordering = ['-created_at']

    def get_queryset(self):
        """Filter queryset based on user permissions"""
        user = self.request.user
        
        try:
            employee = Employee.objects.get(user=user)
            
            # Get requests where user is involved
            queryset = BusinessTripRequest.objects.filter(
                Q(employee=employee) |  # User's own requests
                Q(requested_by=employee) |  # Requests made by user for others
                Q(line_manager=employee) |  # User is line manager
                Q(finance_approver=employee) |  # User is finance approver
                Q(hr_approver=employee)  # User is HR approver
            ).select_related(
                'employee', 'requested_by', 'travel_type', 'transport_type',
                'purpose', 'line_manager', 'finance_approver', 'hr_approver',
                'workflow', 'current_step'
            ).prefetch_related(
                'schedules', 'hotels', 'approvals'
            ).distinct()
            
            return queryset
            
        except Employee.DoesNotExist:
            # Return empty queryset if user has no employee profile
            return BusinessTripRequest.objects.none()

    def get_serializer_class(self):
        if self.action == 'list':
            return BusinessTripRequestListSerializer
        elif self.action in ['create']:
            return BusinessTripRequestCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return BusinessTripRequestUpdateSerializer
        else:
            return BusinessTripRequestDetailSerializer

    @swagger_auto_schema(
        method='get',
        operation_description="Get trip statistics for current user",
        responses={
            200: openapi.Response(description="Statistics retrieved successfully")
        }
    )
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get trip statistics for the current user"""
        try:
            employee = Employee.objects.get(user=request.user)
            current_year = datetime.now().year
            
            # Base queryset for user's trips
            user_trips = BusinessTripRequest.objects.filter(employee=employee)
            
            stats = {
                'pending_requests': user_trips.filter(
                    status__in=['SUBMITTED', 'IN_PROGRESS', 'PENDING_LINE_MANAGER', 
                               'PENDING_FINANCE', 'PENDING_HR', 'PENDING_CHRO']
                ).count(),
                
                'approved_trips': user_trips.filter(status='APPROVED').count(),
                
                'total_days_this_year': user_trips.filter(
                    start_date__year=current_year,
                    status='APPROVED'
                ).aggregate(
                    total=Sum('duration_days')
                )['total'] or 0,
                
                'upcoming_trips': user_trips.filter(
                    status='APPROVED',
                    start_date__gte=date.today()
                ).count(),
                
                # Status breakdown
                'by_status': {},
                
                # Travel type breakdown
                'by_travel_type': {},
                
                # Recent activity
                'recent_submissions': user_trips.filter(
                    submitted_at__gte=timezone.now() - timedelta(days=30)
                ).count(),
                
                'recent_approvals': user_trips.filter(
                    completed_at__gte=timezone.now() - timedelta(days=30),
                    status='APPROVED'
                ).count(),
            }
            
            # Status breakdown
            status_counts = user_trips.values('status').annotate(count=Count('id'))
            for item in status_counts:
                status_display = dict(BusinessTripRequest.STATUS_CHOICES).get(item['status'], item['status'])
                stats['by_status'][status_display] = item['count']
            
            # Travel type breakdown
            travel_type_counts = user_trips.select_related('travel_type').values(
                'travel_type__name'
            ).annotate(count=Count('id'))
            for item in travel_type_counts:
                if item['travel_type__name']:
                    stats['by_travel_type'][item['travel_type__name']] = item['count']
            
            return Response(stats)
            
        except Employee.DoesNotExist:
            return Response(
                {'error': 'Employee profile not found'},
                status=status.HTTP_404_NOT_FOUND
            )

    @swagger_auto_schema(
        method='post',
        operation_description="Submit a draft trip request for approval",
        responses={
            200: openapi.Response(description="Request submitted successfully"),
            400: "Bad request - validation errors"
        }
    )
    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """Submit a draft trip request"""
        trip_request = self.get_object()
        
        # Check if user can submit this request
        try:
            employee = Employee.objects.get(user=request.user)
            if trip_request.requested_by != employee:
                return Response(
                    {'error': 'You can only submit requests you created'},
                    status=status.HTTP_403_FORBIDDEN
                )
        except Employee.DoesNotExist:
            return Response(
                {'error': 'Employee profile not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if trip_request.status != 'DRAFT':
            return Response(
                {'error': f'Only draft requests can be submitted. Current status: {trip_request.get_status_display()}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            trip_request.submit_request()
            
            # Send notification to approver
            current_approver = trip_request.get_current_approver()
            if current_approver:
                self._send_approval_notification(trip_request, current_approver)
            
            serializer = self.get_serializer(trip_request)
            return Response({
                'message': 'Trip request submitted successfully',
                'trip_request': serializer.data
            })
            
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @swagger_auto_schema(
        method='post',
        operation_description="Approve or reject a trip request",
        request_body=TripApprovalActionSerializer,
        responses={
            200: openapi.Response(description="Action completed successfully"),
            400: "Bad request - validation errors",
            403: "Forbidden - user cannot approve this request"
        }
    )
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve or reject a trip request"""
        trip_request = self.get_object()
        
        # Check if user can approve this request
        try:
            employee = Employee.objects.get(user=request.user)
            current_approver = trip_request.get_current_approver()
            
            if current_approver != employee:
                return Response(
                    {'error': 'You are not authorized to approve this request at this stage'},
                    status=status.HTTP_403_FORBIDDEN
                )
        except Employee.DoesNotExist:
            return Response(
                {'error': 'Employee profile not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = TripApprovalActionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        action = serializer.validated_data['action']
        amount = serializer.validated_data.get('amount')
        notes = serializer.validated_data.get('notes', '')
        
        try:
            with transaction.atomic():
                if action == 'APPROVE':
                    trip_request.approve_current_step(employee, amount, notes)
                    
                    # Send notification to employee
                    if trip_request.status == 'APPROVED':
                        # Final approval - notify employee
                        self._send_approval_notification(trip_request, trip_request.employee, final=True)
                    else:
                        # Intermediate approval - notify next approver
                        next_approver = trip_request.get_current_approver()
                        if next_approver:
                            self._send_approval_notification(trip_request, next_approver)
                    
                    message = 'Trip request approved successfully'
                    
                elif action == 'REJECT':
                    trip_request.reject_current_step(employee, notes)
                    
                    # Send rejection notification to employee
                    self._send_rejection_notification(trip_request, trip_request.employee, notes)
                    
                    message = 'Trip request rejected'
            
            serializer = self.get_serializer(trip_request)
            return Response({
                'message': message,
                'trip_request': serializer.data
            })
            
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @swagger_auto_schema(
        method='get',
        operation_description="Get pending approvals for current user",
        responses={
            200: openapi.Response(description="Pending approvals retrieved successfully")
        }
    )
    @action(detail=False, methods=['get'])
    def pending_approvals(self, request):
        """Get trip requests pending approval by current user"""
        try:
            employee = Employee.objects.get(user=request.user)
            
            # Get requests where current user is the current approver
            pending_requests = BusinessTripRequest.objects.filter(
                Q(line_manager=employee, status='PENDING_LINE_MANAGER') |
                Q(finance_approver=employee, status='PENDING_FINANCE') |
                Q(hr_approver=employee, status='PENDING_HR')
            ).select_related(
                'employee', 'travel_type', 'transport_type', 'purpose', 'workflow'
            ).order_by('submitted_at')
            
            serializer = PendingApprovalSerializer(
                pending_requests, 
                many=True, 
                context={'request': request}
            )
            
            return Response({
                'count': pending_requests.count(),
                'pending_approvals': serializer.data
            })
            
        except Employee.DoesNotExist:
            return Response(
                {'error': 'Employee profile not found'},
                status=status.HTTP_404_NOT_FOUND
            )

    @swagger_auto_schema(
        method='get',
        operation_description="Get approval history for current user",
        responses={
            200: openapi.Response(description="Approval history retrieved successfully")
        }
    )
    @action(detail=False, methods=['get'])
    def approval_history(self, request):
        """Get trip requests previously approved/rejected by current user"""
        try:
            employee = Employee.objects.get(user=request.user)
            
            # Get completed approvals by current user
            completed_approvals = TripApproval.objects.filter(
                approver=employee,
                decision__in=['APPROVED', 'REJECTED']
            ).select_related(
                'trip_request__employee', 'trip_request__travel_type'
            ).order_by('-created_at')
            
            history_data = []
            for approval in completed_approvals:
                trip = approval.trip_request
                history_data.append({
                    'id': trip.id,
                    'request_id': trip.request_id,
                    'employee_name': trip.employee.full_name,
                    'travel_type': trip.travel_type.name,
                    'destination': f"{trip.start_date} to {trip.end_date}",
                    'status': approval.decision,
                    'amount': approval.amount,
                    'approved_at': approval.created_at,
                    'notes': approval.notes
                })
            
            return Response({
                'count': len(history_data),
                'approval_history': history_data
            })
            
        except Employee.DoesNotExist:
            return Response(
                {'error': 'Employee profile not found'},
                status=status.HTTP_404_NOT_FOUND
            )

    @swagger_auto_schema(
        method='post',
        operation_description="Cancel a trip request",
        responses={
            200: openapi.Response(description="Request cancelled successfully"),
            400: "Bad request - cannot cancel request"
        }
    )
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel a trip request"""
        trip_request = self.get_object()
        
        # Check if user can cancel this request
        try:
            employee = Employee.objects.get(user=request.user)
            if trip_request.requested_by != employee and trip_request.employee != employee:
                return Response(
                    {'error': 'You can only cancel your own requests'},
                    status=status.HTTP_403_FORBIDDEN
                )
        except Employee.DoesNotExist:
            return Response(
                {'error': 'Employee profile not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Only allow cancellation of non-finalized requests
        if trip_request.status in ['APPROVED', 'REJECTED', 'CANCELLED', 'COMPLETED']:
            return Response(
                {'error': f'Cannot cancel request with status: {trip_request.get_status_display()}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        trip_request.status = 'CANCELLED'
        trip_request.completed_at = timezone.now()
        trip_request.save()
        
        # Send cancellation notifications to current approver if exists
        current_approver = trip_request.get_current_approver()
        if current_approver:
            self._send_cancellation_notification(trip_request, current_approver)
        
        serializer = self.get_serializer(trip_request)
        return Response({
            'message': 'Trip request cancelled successfully',
            'trip_request': serializer.data
        })

    @swagger_auto_schema(
        method='get',
        operation_description="Get employee options for approvers",
        responses={
            200: openapi.Response(description="Employee options retrieved successfully")
        }
    )
    @action(detail=False, methods=['get'])
    def employee_options(self, request):
        """Get employee options for approver selection"""
        employee_type = request.query_params.get('type', 'all')
        
        queryset = Employee.objects.filter(
            status__affects_headcount=True,
            is_deleted=False
        ).select_related('department', 'job_function').order_by('full_name')
        
        if employee_type == 'finance':
            # Filter finance/accounting employees
            queryset = queryset.filter(
                Q(job_function__name__icontains='finance') |
                Q(job_function__name__icontains='accounting') |
                Q(department__name__icontains='finance') |
                Q(department__name__icontains='accounting')
            )
        elif employee_type == 'hr':
            # Filter HR employees
            queryset = queryset.filter(
                Q(job_function__name__icontains='hr') |
                Q(job_function__name__icontains='human') |
                Q(department__name__icontains='hr') |
                Q(department__name__icontains='human')
            )
        elif employee_type == 'managers':
            # Filter employees who are managers (have direct reports)
            queryset = queryset.annotate(
                direct_reports_count=Count('direct_reports')
            ).filter(direct_reports_count__gt=0)
        
        serializer = EmployeeOptionSerializer(queryset, many=True)
        return Response({
            'employees': serializer.data
        })

    @swagger_auto_schema(
        method='post',
        operation_description="Initialize default trip settings",
        responses={
            200: openapi.Response(description="Default settings created successfully")
        }
    )
    @action(detail=False, methods=['post'])
    def initialize_defaults(self, request):
        """Initialize default trip settings (travel types, transport types, etc.)"""
        try:
            create_default_trip_settings()
            return Response({
                'message': 'Default trip settings initialized successfully'
            })
        except Exception as e:
            logger.error(f"Error initializing default trip settings: {str(e)}")
            return Response(
                {'error': f'Failed to initialize default settings: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _send_approval_notification(self, trip_request, recipient, final=False):
        """Send approval notification"""
        try:
            if final:
                subject = f"Trip Request {trip_request.request_id} Approved"
                message = f"Your trip request to {trip_request.purpose.name} has been approved."
                template = 'TRIP_APPROVED'
            else:
                subject = f"Trip Request {trip_request.request_id} - Approval Required"
                message = f"Trip request from {trip_request.employee.full_name} requires your approval."
                template = 'APPROVAL_PENDING'
            
            TripNotification.objects.create(
                trip_request=trip_request,
                recipient=recipient,
                notification_type='SYSTEM',
                template=template,
                subject=subject,
                message=message,
                metadata={
                    'current_step': trip_request.current_step.step_name if trip_request.current_step else None,
                    'final_approval': final
                }
            )
            
        except Exception as e:
            logger.error(f"Error sending approval notification: {str(e)}")

    def _send_rejection_notification(self, trip_request, recipient, reason):
        """Send rejection notification"""
        try:
            subject = f"Trip Request {trip_request.request_id} Rejected"
            message = f"Your trip request has been rejected. Reason: {reason}"
            
            TripNotification.objects.create(
                trip_request=trip_request,
                recipient=recipient,
                notification_type='SYSTEM',
                template='TRIP_REJECTED',
                subject=subject,
                message=message,
                metadata={'rejection_reason': reason}
            )
            
        except Exception as e:
            logger.error(f"Error sending rejection notification: {str(e)}")

    def _send_cancellation_notification(self, trip_request, recipient):
        """Send cancellation notification"""
        try:
            subject = f"Trip Request {trip_request.request_id} Cancelled"
            message = f"Trip request from {trip_request.employee.full_name} has been cancelled."
            
            TripNotification.objects.create(
                trip_request=trip_request,
                recipient=recipient,
                notification_type='SYSTEM',
                template='TRIP_CANCELLED',
                subject=subject,
                message=message,
                metadata={'cancelled_by': trip_request.requested_by.full_name}
            )
            
        except Exception as e:
            logger.error(f"Error sending cancellation notification: {str(e)}")

class TripNotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for trip notifications"""
    serializer_class = TripNotificationSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['notification_type', 'template', 'is_sent']
    ordering = ['-created_at']

    def get_queryset(self):
        """Filter notifications for current user"""
        try:
            employee = Employee.objects.get(user=self.request.user)
            return TripNotification.objects.filter(
                recipient=employee
            ).select_related('trip_request', 'recipient')
        except Employee.DoesNotExist:
            return TripNotification.objects.none()

    @action(detail=True, methods=['post'])
    def mark_as_read(self, request, pk=None):
        """Mark notification as read"""
        notification = self.get_object()
        
        # Update metadata to mark as read
        if 'read_at' not in notification.metadata:
            notification.metadata['read_at'] = timezone.now().isoformat()
            notification.metadata['read_by'] = request.user.username
            notification.save()
        
        return Response({'message': 'Notification marked as read'})

class TripSettingsViewSet(viewsets.ViewSet):
    """ViewSet for trip management settings and configurations"""
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'])
    def all_options(self, request):
        """Get all configuration options for trip forms"""
        travel_types = TravelTypeSerializer(
            TravelType.objects.filter(is_active=True), many=True
        ).data
        
        transport_types = TransportTypeSerializer(
            TransportType.objects.filter(is_active=True), many=True
        ).data
        
        trip_purposes = TripPurposeSerializer(
            TripPurpose.objects.filter(is_active=True), many=True
        ).data
        
        workflows = ApprovalWorkflowSerializer(
            ApprovalWorkflow.objects.filter(is_active=True), many=True
        ).data
        
        return Response({
            'travel_types': travel_types,
            'transport_types': transport_types,
            'trip_purposes': trip_purposes,
            'approval_workflows': workflows
        })

    @action(detail=False, methods=['get'])
    def user_defaults(self, request):
        """Get default values for current user"""
        try:
            employee = Employee.objects.get(user=request.user)
            
            defaults = {
                'employee_name': employee.full_name,
                'function': employee.job_function.name if employee.job_function else '',
                'department': employee.department.name if employee.department else '',
                'division': employee.unit.name if employee.unit else '',
                'phone_number': employee.phone or '',
                'line_manager': {
                    'id': employee.line_manager.id if employee.line_manager else None,
                    'name': employee.line_manager.full_name if employee.line_manager else '',
                    'employee_id': employee.line_manager.employee_id if employee.line_manager else ''
                }
            }
            
            return Response(defaults)
            
        except Employee.DoesNotExist:
            return Response(
                {'error': 'Employee profile not found'},
                status=status.HTTP_404_NOT_FOUND
            )