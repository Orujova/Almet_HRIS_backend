# api/timeoff_views.py
"""
Time Off System Views - COMPLETE WITH FULL RBAC PERMISSIONS
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Sum, Q, Count
from django.utils import timezone

import logging

from .timeoff_models import (
    TimeOffBalance, TimeOffRequest, TimeOffSettings, TimeOffActivity
)
from .timeoff_serializers import (
    TimeOffBalanceSerializer, TimeOffRequestSerializer,
    TimeOffRequestCreateSerializer, TimeOffApproveSerializer,
    TimeOffRejectSerializer, TimeOffSettingsSerializer,
    TimeOffActivitySerializer
)
from .models import Employee
from .notification_service import notification_service
from .token_helpers import extract_graph_token_from_request
from .timeoff_permissions import (
    has_timeoff_permission, has_any_timeoff_permission,
    check_timeoff_permission, can_approve_timeoff, can_view_timeoff_request,get_user_timeoff_permissions
)

logger = logging.getLogger(__name__)


class TimeOffBalanceViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Time Off Balance ViewSet - WITH FULL RBAC
    Read-only - balances are automatically managed
    """
    queryset = TimeOffBalance.objects.all()
    serializer_class = TimeOffBalanceSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter by user and permissions"""
        queryset = super().get_queryset()
        user = self.request.user
        
        # Check if user can view all balances
        has_view_all, employee = check_timeoff_permission(user, 'timeoff.balance.view_all')
        
        if has_view_all:
            # Can view all balances
            return queryset
        
        # Can only view own balance
        has_view_own, employee = check_timeoff_permission(user, 'timeoff.balance.view_own')
        
        if has_view_own and employee:
            return queryset.filter(employee=employee)
        
        # No permission
        return queryset.none()
    
    def list(self, request, *args, **kwargs):
        """List balances - requires permission"""
        has_perm, _ = check_timeoff_permission(
            request.user, 
            'timeoff.balance.view_all'
        )
        
        if not has_perm:
            return Response(
                {
                    'error': 'Permission required',
                    'required_permission': 'timeoff.balance.view_all',
                    'detail': 'You can only view your own balance via /my_balance/'
                },
                status=status.HTTP_403_FORBIDDEN
            )
        
        return super().list(request, *args, **kwargs)
    
    @action(detail=False, methods=['get'])
    @has_timeoff_permission('timeoff.balance.view_own')
    def my_balance(self, request):
        """
        Get own balance
        Required: timeoff.balance.view_own
        """
        if not hasattr(request.user, 'employee_profile'):
            return Response(
                {'error': 'No employee profile found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        employee = request.user.employee_profile
        balance = TimeOffBalance.get_or_create_for_employee(employee)
        serializer = self.get_serializer(balance)
        
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    @has_timeoff_permission('timeoff.balance.reset')
    def reset_monthly_balances(self, request):
        """
        Reset monthly balances for all employees
        Required: timeoff.balance.reset (Admin/HR only)
        """
        reset_count = 0
        failed_count = 0
        results = []
        
        for balance in TimeOffBalance.objects.all():
            try:
                if balance.check_and_reset_monthly():
                    reset_count += 1
                    results.append({
                        'employee_id': balance.employee.employee_id,
                        'employee_name': balance.employee.full_name,
                        'new_balance': float(balance.current_balance_hours),
                        'status': 'reset'
                    })
            except Exception as e:
                failed_count += 1
                results.append({
                    'employee_id': balance.employee.employee_id,
                    'employee_name': balance.employee.full_name,
                    'status': 'failed',
                    'error': str(e)
                })
        
        return Response({
            'success': True,
            'message': f'{reset_count} balances reset successfully',
            'reset_count': reset_count,
            'failed_count': failed_count,
            'results': results
        })
    
    @action(detail=True, methods=['post'])
    @has_timeoff_permission('timeoff.balance.update')
    def update_balance(self, request, pk=None):
        """
        Update employee balance manually
        Required: timeoff.balance.update (HR/Admin only)
        """
        balance = self.get_object()
        
        new_balance = request.data.get('new_balance')
        reason = request.data.get('reason', 'Manual adjustment')
        
        if new_balance is None:
            return Response(
                {'error': 'new_balance is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            from decimal import Decimal
            old_balance = balance.current_balance_hours
            balance.current_balance_hours = Decimal(str(new_balance))
            balance.save()
            
            # Log activity
            TimeOffActivity.objects.create(
                request=None,
                activity_type='BALANCE_UPDATED',
                description=f"Balance updated from {old_balance}h to {new_balance}h. Reason: {reason}",
                performed_by=request.user,
                metadata={
                    'employee_id': balance.employee.employee_id,
                    'old_balance': float(old_balance),
                    'new_balance': float(new_balance),
                    'reason': reason
                }
            )
            
            return Response({
                'success': True,
                'message': 'Balance updated successfully',
                'old_balance': float(old_balance),
                'new_balance': float(new_balance)
            })
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
   

class TimeOffRequestViewSet(viewsets.ModelViewSet):
    """
    Time Off Request ViewSet - WITH FULL RBAC
    Complete CRUD + Approve/Reject/Cancel actions
    """
    queryset = TimeOffRequest.objects.all()
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return TimeOffRequestCreateSerializer
        elif self.action == 'approve':
            return TimeOffApproveSerializer
        elif self.action == 'reject':
            return TimeOffRejectSerializer
        return TimeOffRequestSerializer
    
    def get_queryset(self):
        """Filter requests based on permissions"""
        queryset = super().get_queryset().select_related(
            'employee', 'employee__user', 'line_manager', 
            'approved_by', 'created_by'
        )
        
        user = self.request.user
        
        # Filter parameters
        status_filter = self.request.query_params.get('status')
        employee_id = self.request.query_params.get('employee_id')
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')
        
        # Apply filters
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if employee_id:
            queryset = queryset.filter(employee__employee_id=employee_id)
        if date_from:
            queryset = queryset.filter(date__gte=date_from)
        if date_to:
            queryset = queryset.filter(date__lte=date_to)
        
        # Permission-based filtering
        has_view_all, employee = check_timeoff_permission(user, 'timeoff.request.view_all')
        
        if has_view_all:
            # Can view all requests
            return queryset.order_by('-created_at')
        
        # Check team permission
        has_view_team, employee = check_timeoff_permission(user, 'timeoff.request.view_team')
        
        if has_view_team and employee:
            # Can view team requests (as line manager)
            if self.request.query_params.get('for_approval') == 'true':
                # Only pending approvals
                queryset = queryset.filter(
                    line_manager=employee,
                    status='PENDING'
                )
            else:
                # All team requests
                queryset = queryset.filter(line_manager=employee)
        else:
            # Can only view own requests
            has_view_own, employee = check_timeoff_permission(user, 'timeoff.request.view_own')
            
            if has_view_own and employee:
                queryset = queryset.filter(employee=employee)
            else:
                # No permission
                return queryset.none()
        
        return queryset.order_by('-created_at')
    
    def list(self, request, *args, **kwargs):
        """
        List requests
        Required: timeoff.request.view_own OR timeoff.request.view_team OR timeoff.request.view_all
        """
        # Check if user has any view permission
        has_any_perm, _ = check_timeoff_permission(
            request.user,
            'timeoff.request.view_own'
        )
        
        if not has_any_perm:
            has_any_perm, _ = check_timeoff_permission(
                request.user,
                'timeoff.request.view_team'
            )
        
        if not has_any_perm:
            has_any_perm, _ = check_timeoff_permission(
                request.user,
                'timeoff.request.view_all'
            )
        
        if not has_any_perm:
            return Response(
                {
                    'error': 'No view permission',
                    'required_permissions': [
                        'timeoff.request.view_own',
                        'timeoff.request.view_team',
                        'timeoff.request.view_all'
                    ]
                },
                status=status.HTTP_403_FORBIDDEN
            )
        
        return super().list(request, *args, **kwargs)
    
    def retrieve(self, request, *args, **kwargs):
        """
        Get single request
        Required: Appropriate view permission based on request ownership
        """
        instance = self.get_object()
        
        # Check if user can view this specific request
        can_view, reason = can_view_timeoff_request(request.user, instance)
        
        if not can_view:
            return Response(
                {'error': 'Cannot view this request', 'reason': reason},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
    
    @has_timeoff_permission('timeoff.request.create_own')
    def create(self, request, *args, **kwargs):
        """
        Create time off request
        Required: timeoff.request.create_own
        """
        # Get employee from request user
        if not hasattr(request.user, 'employee_profile'):
            return Response(
                {'error': 'No employee profile found'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        employee = request.user.employee_profile
        
        # Create with employee
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Force employee to be the logged-in user
        instance = serializer.save(
            employee=employee,
            created_by=request.user
        )
        
        # Send notification to line manager
        self._send_line_manager_notification(instance, request)
        
        # Return created request
        response_serializer = TimeOffRequestSerializer(instance)
        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED
        )
    
    @has_timeoff_permission('timeoff.request.update_own')
    def update(self, request, *args, **kwargs):
        """
        Update time off request
        Required: timeoff.request.update_own (only if PENDING)
        """
        instance = self.get_object()
        
        # Can only update own requests
        if not hasattr(request.user, 'employee_profile'):
            return Response(
                {'error': 'No employee profile found'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if instance.employee != request.user.employee_profile:
            return Response(
                {'error': 'Can only update your own requests'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Can only update pending requests
        if instance.status != 'PENDING':
            return Response(
                {'error': f'Cannot update request with status: {instance.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        return super().update(request, *args, **kwargs)
    
    @has_timeoff_permission('timeoff.request.delete_own')
    def destroy(self, request, *args, **kwargs):
        """
        Delete time off request
        Required: timeoff.request.delete_own (only if PENDING)
        """
        instance = self.get_object()
        
        # Can only delete own requests
        if not hasattr(request.user, 'employee_profile'):
            return Response(
                {'error': 'No employee profile found'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if instance.employee != request.user.employee_profile:
            return Response(
                {'error': 'Can only delete your own requests'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Can only delete pending requests
        if instance.status != 'PENDING':
            return Response(
                {'error': f'Cannot delete request with status: {instance.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        return super().destroy(request, *args, **kwargs)
    
    @action(detail=True, methods=['post'])
    @has_any_timeoff_permission(['timeoff.request.approve_as_manager', 'timeoff.request.approve_as_hr'])
    def approve(self, request, pk=None):
        """
        Approve time off request
        Required: timeoff.request.approve_as_manager OR timeoff.request.approve_as_hr
        """
        request_obj = self.get_object()
        
        # Permission və authorization yoxla
        can_approve, reason = can_approve_timeoff(request.user, request_obj)
        
        if not can_approve:
            return Response(
                {'error': 'Cannot approve this request', 'reason': reason},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if request_obj.status != 'PENDING':
            return Response(
                {'error': f'Cannot approve request with status: {request_obj.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Approve
            request_obj.approve(request.user)
            
            # Activity log
            TimeOffActivity.objects.create(
                request=request_obj,
                activity_type='APPROVED',
                description=f"Approved by {request.user.get_full_name()}",
                performed_by=request.user,
                metadata={
                    'approved_at': timezone.now().isoformat(),
                    'balance_deducted': True,
                    'approved_by_role': reason
                }
            )
            
            # Send notifications
            self._send_employee_notification(request_obj, 'approved', request)
            self._send_hr_notification(request_obj, request)
            
            serializer = self.get_serializer(request_obj)
            return Response({
                'success': True,
                'message': 'Request approved successfully',
                'request': serializer.data
            })
            
        except Exception as e:
            logger.error(f"Approve failed: {e}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    @has_any_timeoff_permission(['timeoff.request.reject_as_manager'])
    def reject(self, request, pk=None):
        """
        Reject time off request
        Required: timeoff.request.reject_as_manager
        """
        request_obj = self.get_object()
        
        # Permission və authorization yoxla
        can_approve, reason = can_approve_timeoff(request.user, request_obj)
        
        if not can_approve:
            return Response(
                {'error': 'Cannot reject this request', 'reason': reason},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if request_obj.status != 'PENDING':
            return Response(
                {'error': f'Cannot reject request with status: {request_obj.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        rejection_reason = serializer.validated_data['rejection_reason']
        
        try:
            # Reject
            request_obj.reject(rejection_reason, request.user)
            
            # Activity log
            TimeOffActivity.objects.create(
                request=request_obj,
                activity_type='REJECTED',
                description=f"Rejected by {request.user.get_full_name()}: {rejection_reason}",
                performed_by=request.user,
                metadata={
                    'rejected_at': timezone.now().isoformat(),
                    'rejection_reason': rejection_reason
                }
            )
            
            # Send notification to employee
            self._send_employee_notification(request_obj, 'rejected', request)
            
            serializer = TimeOffRequestSerializer(request_obj)
            return Response({
                'success': True,
                'message': 'Request rejected',
                'request': serializer.data
            })
            
        except Exception as e:
            logger.error(f"Reject failed: {e}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    @has_timeoff_permission('timeoff.request.cancel_own')
    def cancel(self, request, pk=None):
        """
        Cancel time off request
        Required: timeoff.request.cancel_own (only own requests)
        """
        request_obj = self.get_object()
        
        # Check if user can cancel this request
        if not hasattr(request.user, 'employee_profile'):
            return Response(
                {'error': 'No employee profile found'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Only own requests can be cancelled
        if request_obj.employee != request.user.employee_profile:
            return Response(
                {'error': 'Can only cancel your own requests'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if request_obj.status not in ['PENDING', 'APPROVED']:
            return Response(
                {'error': f'Cannot cancel request with status: {request_obj.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Cancel
            request_obj.cancel()
            
            # Activity log
            TimeOffActivity.objects.create(
                request=request_obj,
                activity_type='CANCELLED',
                description=f"Cancelled by {request.user.get_full_name()}",
                performed_by=request.user,
                metadata={
                    'cancelled_at': timezone.now().isoformat()
                }
            )
            
            serializer = self.get_serializer(request_obj)
            return Response({
                'success': True,
                'message': 'Request cancelled successfully',
                'request': serializer.data
            })
            
        except Exception as e:
            logger.error(f"Cancel failed: {e}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['get'])
    @has_timeoff_permission('timeoff.request.view_own')
    def my_requests(self, request):
        """
        Get own time off requests
        Required: timeoff.request.view_own
        """
        if not hasattr(request.user, 'employee_profile'):
            return Response(
                {'error': 'No employee profile found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        employee = request.user.employee_profile
        requests = TimeOffRequest.objects.filter(employee=employee).order_by('-created_at')
        
        serializer = self.get_serializer(requests, many=True)
        return Response({
            'count': requests.count(),
            'requests': serializer.data
        })
    
    @action(detail=False, methods=['get'])
    @has_any_timeoff_permission(['timeoff.request.view_team', 'timeoff.request.approve_as_manager', 'timeoff.request.approve_as_hr'])
    def pending_approvals(self, request):
        """
        Get pending approvals
        - HR/Admin: All pending requests
        - Line Manager: Only their team's pending requests
        Required: timeoff.request.view_team OR timeoff.request.approve_as_manager OR timeoff.request.approve_as_hr
        """
        if not hasattr(request.user, 'employee_profile'):
            return Response(
                {'error': 'No employee profile found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        employee = request.user.employee_profile
        
        # Check if user has HR approval permission or is admin
        from .business_trip_permissions import is_admin_user
        has_hr_perm, _ = check_timeoff_permission(request.user, 'timeoff.request.approve_as_hr')
        is_admin = is_admin_user(request.user)
        
        # Debug log
        logger.info(f"Pending approvals request by: {employee.employee_id} - {employee.full_name}")
        logger.info(f"Is Admin: {is_admin}, Has HR Perm: {has_hr_perm}")
        
        if is_admin or has_hr_perm:
            # Admin/HR can see ALL pending requests
            requests = TimeOffRequest.objects.filter(
                status='PENDING'
            ).select_related(
                'employee', 
                'employee__user',
                'employee__department',
                'line_manager'
            ).order_by('-created_at')
            
            logger.info(f"Admin/HR view: Found {requests.count()} total pending requests")
        else:
            # Line manager can only see their team's pending requests
            requests = TimeOffRequest.objects.filter(
                line_manager=employee,
                status='PENDING'
            ).select_related(
                'employee', 
                'employee__user',
                'employee__department',
                'line_manager'
            ).order_by('-created_at')
            
            logger.info(f"Line manager view: Found {requests.count()} pending requests for their team")
        
        serializer = self.get_serializer(requests, many=True)
        
        return Response({
            'count': requests.count(),
            'requests': serializer.data,
            'view_type': 'admin_or_hr' if (is_admin or has_hr_perm) else 'line_manager',
            'debug_info': {
                'user_id': employee.employee_id,
                'user_name': employee.full_name,
                'is_admin': is_admin,
                'has_hr_permission': has_hr_perm,
                'is_line_manager_for': Employee.objects.filter(
                    line_manager=employee,
                    is_deleted=False
                ).count()
            }
        })    
        
  
    # ==================== NOTIFICATION HELPERS ====================
    
    def _send_line_manager_notification(self, request_obj, request):
        """Send notification to line manager"""
        if not request_obj.line_manager or not request_obj.line_manager.email:
            logger.warning(f"No line manager email for request {request_obj.id}")
            return
        
        try:
            access_token = extract_graph_token_from_request(request)
            if not access_token:
                logger.error("No Graph token for notification")
                return
            
            subject = f"[TIME OFF REQUEST] {request_obj.employee.full_name} - {request_obj.date}"
            
            body_html = f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px;">
                <h2 style="color: #2563EB;">Time Off Request - Approval Needed</h2>
                
                <div style="background-color: #F3F4F6; padding: 20px; border-radius: 8px; margin: 20px 0;">
                    <h3 style="margin-top: 0;">Request Details</h3>
                    <p><strong>Employee:</strong> {request_obj.employee.full_name}</p>
                    <p><strong>Employee ID:</strong> {request_obj.employee.employee_id}</p>
                    <p><strong>Date:</strong> {request_obj.date.strftime('%B %d, %Y')}</p>
                    <p><strong>Time:</strong> {request_obj.start_time.strftime('%H:%M')} - {request_obj.end_time.strftime('%H:%M')}</p>
                    <p><strong>Duration:</strong> {request_obj.duration_hours} hours</p>
                    <p><strong>Reason:</strong> {request_obj.reason}</p>
                </div>
                
                <p style="color: #DC2626; font-weight: bold;">
                    ⚠️ This request requires your approval.
                </p>
                
                <p>Please log in to the system to approve or reject this request.</p>
            </div>
            """
            
            notification_service.send_email(
                recipient_email=request_obj.line_manager.email,
                subject=subject,
                body_html=body_html,
                access_token=access_token,
                related_model='TimeOffRequest',
                related_object_id=str(request_obj.id),
                sent_by=request.user
            )
            
            logger.info(f"Line manager notification sent for request {request_obj.id}")
            
        except Exception as e:
            logger.error(f"Failed to send line manager notification: {e}")
    
    def _send_hr_notification(self, request_obj, request):
        """Send notification to HR"""
        settings = TimeOffSettings.get_settings()
        hr_emails = settings.get_hr_emails_list()
        
        if not hr_emails:
            logger.warning("No HR emails configured")
            return
        
        try:
            access_token = extract_graph_token_from_request(request)
            if not access_token:
                logger.error("No Graph token for HR notification")
                return
            
            subject = f"[TIME OFF APPROVED] {request_obj.employee.full_name} - {request_obj.date}"
            
            body_html = f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px;">
                <h2 style="color: #10B981;">Time Off Approved - HR Notification</h2>
                
                <div style="background-color: #F3F4F6; padding: 20px; border-radius: 8px; margin: 20px 0;">
                    <h3 style="margin-top: 0;">Request Details</h3>
                    <p><strong>Employee:</strong> {request_obj.employee.full_name}</p>
                    <p><strong>Employee ID:</strong> {request_obj.employee.employee_id}</p>
                    <p><strong>Department:</strong> {request_obj.employee.department.name if request_obj.employee.department else 'N/A'}</p>
                    <p><strong>Date:</strong> {request_obj.date.strftime('%B %d, %Y')}</p>
                    <p><strong>Time:</strong> {request_obj.start_time.strftime('%H:%M')} - {request_obj.end_time.strftime('%H:%M')}</p>
                    <p><strong>Duration:</strong> {request_obj.duration_hours} hours</p>
                    <p><strong>Reason:</strong> {request_obj.reason}</p>
                </div>
                
                <div style="background-color: #ECFDF5; padding: 15px; border-radius: 8px; border-left: 4px solid #10B981;">
                    <p style="margin: 0;"><strong>Approved by:</strong> {request_obj.line_manager.full_name if request_obj.line_manager else 'N/A'}</p>
                    <p style="margin: 5px 0 0 0;"><strong>Approved at:</strong> {request_obj.approved_at.strftime('%B %d, %Y %H:%M') if request_obj.approved_at else 'N/A'}</p>
                </div>
                
                <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #E5E7EB;">
                    <p style="color: #6B7280; font-size: 12px;">
                        This is an automated notification from HR Management System.
                    </p>
                </div>
            </div>
            """
            
            # Send to all HR emails
            for hr_email in hr_emails:
                notification_service.send_email(
                    recipient_email=hr_email,
                    subject=subject,
                    body_html=body_html,
                    access_token=access_token,
                    related_model='TimeOffRequest',
                    related_object_id=str(request_obj.id),
                    sent_by=request.user
                )
            
            # Mark as notified
            request_obj.hr_notified = True
            request_obj.hr_notified_at = timezone.now()
            request_obj.save()
            
            logger.info(f"HR notification sent for request {request_obj.id}")
            
        except Exception as e:
            logger.error(f"Failed to send HR notification: {e}")
    
    def _send_employee_notification(self, request_obj, notification_type, request):
        """Send notification to employee"""
        if not request_obj.employee.email:
            logger.warning(f"No employee email for request {request_obj.id}")
            return
        
        try:
            access_token = extract_graph_token_from_request(request)
            if not access_token:
                logger.error("No Graph token for employee notification")
                return
            
            if notification_type == 'approved':
                subject = f"[TIME OFF APPROVED] Your request for {request_obj.date}"
                color = "#10B981"
                status_text = "APPROVED ✓"
                message = "Your time off request has been approved by your line manager."
            else:  # rejected
                subject = f"[TIME OFF REJECTED] Your request for {request_obj.date}"
                color = "#EF4444"
                status_text = "REJECTED ✗"
                message = "Your time off request has been rejected by your line manager."
            
            body_html = f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px;">
                <h2 style="color: {color};">Time Off Request {status_text}</h2>
                
                <p>{message}</p>
                
                <div style="background-color: #F3F4F6; padding: 20px; border-radius: 8px; margin: 20px 0;">
                    <h3 style="margin-top: 0;">Your Request Details</h3>
                    <p><strong>Date:</strong> {request_obj.date.strftime('%B %d, %Y')}</p>
                    <p><strong>Time:</strong> {request_obj.start_time.strftime('%H:%M')} - {request_obj.end_time.strftime('%H:%M')}</p>
                    <p><strong>Duration:</strong> {request_obj.duration_hours} hours</p>
                    <p><strong>Reason:</strong> {request_obj.reason}</p>
                </div>
            """
            
            if notification_type == 'rejected' and request_obj.rejection_reason:
                body_html += f"""
                <div style="background-color: #FEE2E2; padding: 15px; border-radius: 8px; border-left: 4px solid #EF4444;">
                    <p style="margin: 0;"><strong>Rejection Reason:</strong></p>
                    <p style="margin: 5px 0 0 0;">{request_obj.rejection_reason}</p>
                </div>
                """
            
            body_html += """
                <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #E5E7EB;">
                    <p style="color: #6B7280; font-size: 12px;">
                        This is an automated notification from HR Management System.
                    </p>
                </div>
            </div>
            """
            
            notification_service.send_email(
                recipient_email=request_obj.employee.email,
                subject=subject,
                body_html=body_html,
                access_token=access_token,
                related_model='TimeOffRequest',
                related_object_id=str(request_obj.id),
                sent_by=request.user
            )
            
            logger.info(f"Employee notification ({notification_type}) sent for request {request_obj.id}")
            
        except Exception as e:
            logger.error(f"Failed to send employee notification: {e}")


class TimeOffSettingsViewSet(viewsets.ModelViewSet):
    """
    Time Off Settings ViewSet - WITH FULL RBAC
    Only admin/HR can modify
    """
    queryset = TimeOffSettings.objects.all()
    serializer_class = TimeOffSettingsSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        # Only 1 settings object exists
        return TimeOffSettings.objects.all()[:1]
    
    def list(self, request, *args, **kwargs):
        """
        List settings
        Required: timeoff.settings.view
        """
        has_perm, _ = check_timeoff_permission(request.user, 'timeoff.settings.view')
        
        if not has_perm:
            return Response(
                {
                    'error': 'Permission required',
                    'required_permission': 'timeoff.settings.view'
                },
                status=status.HTTP_403_FORBIDDEN
            )
        
        return super().list(request, *args, **kwargs)
    
    def retrieve(self, request, *args, **kwargs):
        """
        Get settings detail
        Required: timeoff.settings.view
        """
        has_perm, _ = check_timeoff_permission(request.user, 'timeoff.settings.view')
        
        if not has_perm:
            return Response(
                {
                    'error': 'Permission required',
                    'required_permission': 'timeoff.settings.view'
                },
                status=status.HTTP_403_FORBIDDEN
            )
        
        return super().retrieve(request, *args, **kwargs)
    
    @action(detail=False, methods=['get'])
    @has_timeoff_permission('timeoff.settings.view')
    def current(self, request):
        """
        Get current settings
        Required: timeoff.settings.view
        """
        settings = TimeOffSettings.get_settings()
        serializer = self.get_serializer(settings)
        return Response(serializer.data)
    
    @has_timeoff_permission('timeoff.settings.update')
    def update(self, request, *args, **kwargs):
        """
        Update settings
        Required: timeoff.settings.update
        """
        return super().update(request, *args, **kwargs)
    
  
    
    @action(detail=True, methods=['post'])
    @has_timeoff_permission('timeoff.settings.manage_hr_emails')
    def update_hr_emails(self, request, pk=None):
        """
        Update HR notification emails
        Required: timeoff.settings.manage_hr_emails
        """
        settings = self.get_object()
        
        hr_emails = request.data.get('hr_notification_emails')
        if not hr_emails:
            return Response(
                {'error': 'hr_notification_emails is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        settings.hr_notification_emails = hr_emails
        settings.save()
        
        return Response({
            'success': True,
            'message': 'HR emails updated successfully',
            'hr_emails': settings.get_hr_emails_list()
        })


class TimeOffActivityViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Time Off Activity ViewSet - WITH FULL RBAC
    Read-only - activities are auto-created
    """
    queryset = TimeOffActivity.objects.all()
    serializer_class = TimeOffActivitySerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter activities based on permissions"""
        queryset = super().get_queryset().select_related(
            'request', 'request__employee', 'performed_by'
        )
        
        user = self.request.user
        
        # Check if user can view all activities
        has_view_all, employee = check_timeoff_permission(user, 'timeoff.activity.view_all')
        
        if has_view_all:
            # Can view all activities
            return queryset.order_by('-created_at')
        
        # Can only view own activities
        has_view_own, employee = check_timeoff_permission(user, 'timeoff.activity.view_own')
        
        if has_view_own and employee:
            # Filter activities related to own requests
            return queryset.filter(
                request__employee=employee
            ).order_by('-created_at')
        
        # No permission
        return queryset.none()
    
    def list(self, request, *args, **kwargs):
        """
        List activities
        Required: timeoff.activity.view_own OR timeoff.activity.view_all
        """
        has_any_perm, _ = check_timeoff_permission(
            request.user,
            'timeoff.activity.view_own'
        )
        
        if not has_any_perm:
            has_any_perm, _ = check_timeoff_permission(
                request.user,
                'timeoff.activity.view_all'
            )
        
        if not has_any_perm:
            return Response(
                {
                    'error': 'No view permission',
                    'required_permissions': [
                        'timeoff.activity.view_own',
                        'timeoff.activity.view_all'
                    ]
                },
                status=status.HTTP_403_FORBIDDEN
            )
        
        return super().list(request, *args, **kwargs)
    
    @action(detail=False, methods=['get'])
    @has_timeoff_permission('timeoff.activity.view_own')
    def my_activities(self, request):
        """
        Get own activities
        Required: timeoff.activity.view_own
        """
        if not hasattr(request.user, 'employee_profile'):
            return Response(
                {'error': 'No employee profile found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        employee = request.user.employee_profile
        activities = TimeOffActivity.objects.filter(
            request__employee=employee
        ).order_by('-created_at')
        
        serializer = self.get_serializer(activities, many=True)
        return Response({
            'count': activities.count(),
            'activities': serializer.data
        })
    
    @action(detail=False, methods=['get'])
    @has_timeoff_permission('timeoff.activity.view_all')
    def by_request(self, request):
        """
        Get activities for specific request
        Required: timeoff.activity.view_all
        """
        request_id = request.query_params.get('request_id')
        
        if not request_id:
            return Response(
                {'error': 'request_id parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        activities = TimeOffActivity.objects.filter(
            request_id=request_id
        ).order_by('created_at')
        
        serializer = self.get_serializer(activities, many=True)
        return Response({
            'request_id': request_id,
            'count': activities.count(),
            'activities': serializer.data
        })


# ==================== DASHBOARD VIEW ====================

class TimeOffDashboardViewSet(viewsets.ViewSet):
    """
    Time Off Dashboard ViewSet - WITH FULL RBAC
    Provides dashboard data and statistics
    """
    permission_classes = [IsAuthenticated]
    @action(detail=False, methods=['get'])
    def my_permissions(self, request):
        """
        Get my time off permissions
        No permission required - everyone can check their own permissions
        """
        from .role_models import EmployeeRole
        
        user = request.user
        
        # Check if admin
        from .business_trip_permissions import is_admin_user
        is_admin = is_admin_user(user)
        
        # Get all permissions
        permissions = get_user_timeoff_permissions(user)
        
        # Get user roles
        try:
            emp = Employee.objects.get(user=user, is_deleted=False)
            roles = list(EmployeeRole.objects.filter(
                employee=emp,
                is_active=True
            ).select_related('role').values_list('role__name', flat=True))
        except Employee.DoesNotExist:
            roles = []
            emp = None
        
        # Get employee info
        employee_info = None
        if emp:
            employee_info = {
                'id': emp.id,
                'employee_id': emp.employee_id,
                'full_name': emp.full_name,
                'email': emp.email,
                'department': emp.department.name if emp.department else None,
                'line_manager': emp.line_manager.full_name if emp.line_manager else None
            }
        
        # Categorize permissions
        permission_categories = {
            'balance': [],
            'request': [],
            'settings': [],
            'activity': [],
            'dashboard': []
        }
        
        for perm in permissions:
            if 'balance' in perm:
                permission_categories['balance'].append(perm)
            elif 'request' in perm:
                permission_categories['request'].append(perm)
            elif 'settings' in perm:
                permission_categories['settings'].append(perm)
            elif 'activity' in perm:
                permission_categories['activity'].append(perm)
            elif 'dashboard' in perm:
                permission_categories['dashboard'].append(perm)
        
        # ✅ COMPLETE CAPABILITIES - ALL POSSIBLE PERMISSIONS
        capabilities = {
            # Balance Permissions
            'can_view_own_balance': 'timeoff.balance.view_own' in permissions or is_admin,
            'can_view_all_balances': 'timeoff.balance.view_all' in permissions or is_admin,
            'can_update_balance': 'timeoff.balance.update' in permissions or is_admin,
            'can_reset_balances': 'timeoff.balance.reset' in permissions or is_admin,
            
            # Request Permissions - Create
            'can_create_request': 'timeoff.request.create_own' in permissions or is_admin,
            'can_create_for_employee': 'timeoff.request.create_for_employee' in permissions or is_admin,
            
            # Request Permissions - View
            'can_view_own_requests': 'timeoff.request.view_own' in permissions or is_admin,
            'can_view_team_requests': 'timeoff.request.view_team' in permissions or is_admin,
            'can_view_all_requests': 'timeoff.request.view_all' in permissions or is_admin,
            
            # Request Permissions - Update/Delete
            'can_update_own_request': 'timeoff.request.update_own' in permissions or is_admin,
            'can_delete_own_request': 'timeoff.request.delete_own' in permissions or is_admin,
            'can_cancel_own_request': 'timeoff.request.cancel_own' in permissions or is_admin,
            
            # Request Permissions - Approve/Reject
            'can_approve_as_manager': 'timeoff.request.approve_as_manager' in permissions or is_admin,
            'can_approve_as_hr': 'timeoff.request.approve_as_hr' in permissions or is_admin,
            'can_reject_as_manager': 'timeoff.request.reject_as_manager' in permissions or is_admin,
            
            # Settings Permissions
            'can_view_settings': 'timeoff.settings.view' in permissions or is_admin,
            'can_update_settings': 'timeoff.settings.update' in permissions or is_admin,
            'can_manage_hr_emails': 'timeoff.settings.manage_hr_emails' in permissions or is_admin,
            
            # Activity Permissions
            'can_view_own_activities': 'timeoff.activity.view_own' in permissions or is_admin,
            'can_view_all_activities': 'timeoff.activity.view_all' in permissions or is_admin,
            
            # Dashboard Permissions
            'can_view_own_dashboard': 'timeoff.dashboard.view_own' in permissions or is_admin,
            'can_view_team_dashboard': 'timeoff.dashboard.view_team' in permissions or is_admin,
            'can_view_full_dashboard': 'timeoff.dashboard.view' in permissions or is_admin,
            'can_view_statistics': 'timeoff.dashboard.view_statistics' in permissions or is_admin,
        }
        
        return Response({
            'is_admin': is_admin,
            'employee_info': employee_info,
            'roles': roles,
            'roles_count': len(roles),
            'permissions': permissions,
            'permissions_count': len(permissions),
            'permission_categories': permission_categories,
            'capabilities': capabilities
        })
        
    @action(detail=False, methods=['get'])
    @has_any_timeoff_permission(['timeoff.dashboard.view', 'timeoff.dashboard.view_own'])
    def overview(self, request):
        """
        Get dashboard overview
        Required: timeoff.dashboard.view OR timeoff.dashboard.view_own
        """
        user = request.user
        
        # Check permissions
        has_view_all, employee = check_timeoff_permission(user, 'timeoff.dashboard.view')
        
        if has_view_all:
            # Full dashboard for HR/Admin
            return self._get_full_dashboard(request)
        else:
            # Personal dashboard for employee
            return self._get_personal_dashboard(request)
    
    def _get_personal_dashboard(self, request):
        """Personal dashboard for employee"""
        if not hasattr(request.user, 'employee_profile'):
            return Response(
                {'error': 'No employee profile found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        employee = request.user.employee_profile
        
        # Get balance
        balance = TimeOffBalance.get_or_create_for_employee(employee)
        
        # Get requests
        my_requests = TimeOffRequest.objects.filter(employee=employee)
        
        # Statistics
        dashboard_data = {
            'balance': {
                'current_balance': float(balance.current_balance_hours),
                'monthly_allowance': float(balance.monthly_allowance_hours),
                'used_this_month': float(balance.used_hours_this_month),
                'last_reset': balance.last_reset_date.isoformat()
            },
            'requests': {
                'total': my_requests.count(),
                'pending': my_requests.filter(status='PENDING').count(),
                'approved': my_requests.filter(status='APPROVED').count(),
                'rejected': my_requests.filter(status='REJECTED').count(),
            },
            'recent_requests': TimeOffRequestSerializer(
                my_requests.order_by('-created_at')[:5],
                many=True
            ).data
        }
        
        return Response(dashboard_data)
    
    def _get_full_dashboard(self, request):
        """Full dashboard for HR/Admin"""
        # System-wide statistics
        all_balances = TimeOffBalance.objects.all()
        all_requests = TimeOffRequest.objects.all()
        
        dashboard_data = {
            'system_stats': {
                'total_employees': all_balances.count(),
                'total_balance_hours': float(all_balances.aggregate(
                    total=Sum('current_balance_hours')
                )['total'] or 0),
                'average_balance': float(all_balances.aggregate(
                    avg=Sum('current_balance_hours')
                )['avg'] or 0) / max(all_balances.count(), 1),
            },
            'requests': {
                'total': all_requests.count(),
                'pending': all_requests.filter(status='PENDING').count(),
                'approved': all_requests.filter(status='APPROVED').count(),
                'rejected': all_requests.filter(status='REJECTED').count(),
                'cancelled': all_requests.filter(status='CANCELLED').count(),
            },
            'recent_requests': TimeOffRequestSerializer(
                all_requests.order_by('-created_at')[:10],
                many=True
            ).data,
            'pending_approvals': TimeOffRequestSerializer(
                all_requests.filter(status='PENDING').order_by('-created_at')[:10],
                many=True
            ).data
        }
        
        return Response(dashboard_data)
    
    @action(detail=False, methods=['get'])
    @has_timeoff_permission('timeoff.dashboard.view_team')
    def team_overview(self, request):
        """
        Get team dashboard for line manager
        Required: timeoff.dashboard.view_team
        """
        if not hasattr(request.user, 'employee_profile'):
            return Response(
                {'error': 'No employee profile found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        employee = request.user.employee_profile
        
        # Get team requests (where user is line manager)
        team_requests = TimeOffRequest.objects.filter(line_manager=employee)
        
        dashboard_data = {
            'team_stats': {
                'total_requests': team_requests.count(),
                'pending_approvals': team_requests.filter(status='PENDING').count(),
                'approved': team_requests.filter(status='APPROVED').count(),
                'rejected': team_requests.filter(status='REJECTED').count(),
            },
            'pending_approvals': TimeOffRequestSerializer(
                team_requests.filter(status='PENDING').order_by('-created_at'),
                many=True
            ).data,
            'recent_approvals': TimeOffRequestSerializer(
                team_requests.filter(status__in=['APPROVED', 'REJECTED']).order_by('-updated_at')[:10],
                many=True
            ).data
        }
        
        return Response(dashboard_data)