# api/handover_views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db.models import Q
from django.utils import timezone

from .handover_models import (
    HandoverType, HandoverRequest, HandoverTask, HandoverAttachment
)
from .handover_serializers import (
    HandoverTypeSerializer, HandoverRequestSerializer,
    HandoverRequestCreateSerializer, HandoverRequestUpdateSerializer,
    HandoverTaskSerializer, HandoverImportantDateSerializer, 
    HandoverActivitySerializer, HandoverAttachmentSerializer
)
from .models import Employee


class HandoverTypeViewSet(viewsets.ModelViewSet):
    """Handover Type CRUD"""
    queryset = HandoverType.objects.filter(is_active=True)
    serializer_class = HandoverTypeSerializer
    permission_classes = [IsAuthenticated]
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)


class HandoverRequestViewSet(viewsets.ModelViewSet):
    """Handover Request Main ViewSet"""
    permission_classes = [IsAuthenticated]
    
    def get_employee(self):
        """Get employee instance from request user"""
        user = self.request.user
        
        # Try to get employee by user relationship
        try:
            return user.employee
        except AttributeError:
            pass
        
        # Try to get employee by email
        try:
            return Employee.objects.get(email=user.email)
        except Employee.DoesNotExist:
            pass
        
        # Try to get employee by username as email
        try:
            return Employee.objects.get(email=user.username)
        except Employee.DoesNotExist:
            return None
    
    def get_queryset(self):
        """User-specific queryset with proper filtering"""
        employee = self.get_employee()
        
        if not employee:
            return HandoverRequest.objects.none()
        
        # User can see handovers where they are HO, TO, or LM
        return HandoverRequest.objects.filter(
            Q(handing_over_employee=employee) |
            Q(taking_over_employee=employee) |
            Q(line_manager=employee)
        ).select_related(
            'handing_over_employee', 'taking_over_employee',
            'line_manager', 'handover_type', 'created_by'
        ).prefetch_related(
            'tasks', 'important_dates', 'activity_log', 'attachments'
        ).distinct().order_by('-created_at')
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'create':
            return HandoverRequestCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return HandoverRequestUpdateSerializer
        return HandoverRequestSerializer
    
    def perform_create(self, serializer):
        """Create with user context"""
        serializer.save(created_by=self.request.user)
    
    def create(self, request, *args, **kwargs):
        """Enhanced create with better error handling"""
        serializer = self.get_serializer(data=request.data)
        
        try:
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
            
            # Get full handover data for response
            handover = serializer.instance
            response_serializer = HandoverRequestSerializer(
                handover, 
                context={'request': request}
            )
            
            headers = self.get_success_headers(response_serializer.data)
            return Response(
                response_serializer.data,
                status=status.HTTP_201_CREATED,
                headers=headers
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['get'])
    def my_handovers(self, request):
        """Get handovers where I am HO or TO"""
        employee = self.get_employee()
        
        if not employee:
            return Response(
                {'error': 'Employee profile not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        handovers = self.get_queryset().filter(
            Q(handing_over_employee=employee) |
            Q(taking_over_employee=employee)
        )
        
        serializer = self.get_serializer(handovers, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def pending_approval(self, request):
        """Get handovers pending my action"""
        employee = self.get_employee()
        
        if not employee:
            return Response(
                {'error': 'Employee profile not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Pending as Handing Over - need to sign
        ho_pending = Q(
            handing_over_employee=employee,
            status='CREATED',
            ho_signed=False
        )
        
        # Pending as Taking Over - need to sign
        to_pending = Q(
            taking_over_employee=employee,
            status='SIGNED_BY_HANDING_OVER',
            to_signed=False
        )
        
        # Pending as Line Manager - need to approve
        lm_pending = Q(
            line_manager=employee,
            status='SIGNED_BY_TAKING_OVER',
            lm_approved=False
        )
        
        # Need Clarification - HO must respond
        clarification_pending = Q(
            handing_over_employee=employee,
            status='NEED_CLARIFICATION'
        )
        
        # Approved - TO must takeover
        takeover_pending = Q(
            taking_over_employee=employee,
            status='APPROVED_BY_LINE_MANAGER',
            taken_over=False
        )
        
        # Taken Over - HO must takeback
        takeback_pending = Q(
            handing_over_employee=employee,
            status='TAKEN_OVER',
            taken_back=False
        )
        
        handovers = self.get_queryset().filter(
            ho_pending | to_pending | lm_pending | 
            clarification_pending | takeover_pending | takeback_pending
        )
        
        serializer = self.get_serializer(handovers, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def sign_ho(self, request, pk=None):
        """Sign as Handing Over employee"""
        handover = self.get_object()
        employee = self.get_employee()
        
        if not employee:
            return Response(
                {'error': 'Employee profile not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if handover.handing_over_employee != employee:
            return Response(
                {'error': 'You are not authorized to perform this action'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if handover.status != 'CREATED':
            return Response(
                {'error': 'Status is not appropriate for this action'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            comment = request.data.get('comment', '')
            handover.sign_by_handing_over(request.user)
            serializer = self.get_serializer(handover)
            return Response({
                'message': 'Handover signed successfully',
                'data': serializer.data
            })
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def sign_to(self, request, pk=None):
        """Sign as Taking Over employee"""
        handover = self.get_object()
        employee = self.get_employee()
        
        if not employee:
            return Response(
                {'error': 'Employee profile not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if handover.taking_over_employee != employee:
            return Response(
                {'error': 'You are not authorized to perform this action'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if handover.status != 'SIGNED_BY_HANDING_OVER':
            return Response(
                {'error': 'Status is not appropriate for this action'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            comment = request.data.get('comment', '')
            handover.sign_by_taking_over(request.user)
            serializer = self.get_serializer(handover)
            return Response({
                'message': 'Handover signed successfully',
                'data': serializer.data
            })
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def approve_lm(self, request, pk=None):
        """Approve as Line Manager"""
        handover = self.get_object()
        employee = self.get_employee()
        
        if not employee:
            return Response(
                {'error': 'Employee profile not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if handover.line_manager != employee:
            return Response(
                {'error': 'You are not authorized to perform this action'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if handover.status != 'SIGNED_BY_TAKING_OVER':
            return Response(
                {'error': 'Status is not appropriate for this action'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        comment = request.data.get('comment', '')
        
        try:
            handover.approve_by_line_manager(request.user, comment)
            serializer = self.get_serializer(handover)
            return Response({
                'message': 'Handover approved successfully',
                'data': serializer.data
            })
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def reject_lm(self, request, pk=None):
        """Reject as Line Manager"""
        handover = self.get_object()
        employee = self.get_employee()
        
        if not employee:
            return Response(
                {'error': 'Employee profile not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if handover.line_manager != employee:
            return Response(
                {'error': 'You are not authorized to perform this action'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if handover.status != 'SIGNED_BY_TAKING_OVER':
            return Response(
                {'error': 'Status is not appropriate for this action'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        reason = request.data.get('reason', '')
        if not reason:
            return Response(
                {'error': 'Rejection reason is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            handover.reject_by_line_manager(request.user, reason)
            serializer = self.get_serializer(handover)
            return Response({
                'message': 'Handover rejected',
                'data': serializer.data
            })
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def request_clarification(self, request, pk=None):
        """Request clarification as Line Manager"""
        handover = self.get_object()
        employee = self.get_employee()
        
        if not employee:
            return Response(
                {'error': 'Employee profile not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if handover.line_manager != employee:
            return Response(
                {'error': 'You are not authorized to perform this action'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if handover.status != 'SIGNED_BY_TAKING_OVER':
            return Response(
                {'error': 'Status is not appropriate for this action'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        clarification_comment = request.data.get('clarification_comment', '')
        if not clarification_comment:
            return Response(
                {'error': 'Clarification comment is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            handover.request_clarification(request.user, clarification_comment)
            serializer = self.get_serializer(handover)
            return Response({
                'message': 'Clarification requested',
                'data': serializer.data
            })
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def resubmit(self, request, pk=None):
        """Resubmit after clarification"""
        handover = self.get_object()
        employee = self.get_employee()
        
        if not employee:
            return Response(
                {'error': 'Employee profile not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if handover.handing_over_employee != employee:
            return Response(
                {'error': 'You are not authorized to perform this action'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if handover.status != 'NEED_CLARIFICATION':
            return Response(
                {'error': 'Status is not appropriate for this action'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        response_comment = request.data.get('response_comment', '')
        if not response_comment:
            return Response(
                {'error': 'Response comment is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            handover.resubmit_after_clarification(request.user, response_comment)
            serializer = self.get_serializer(handover)
            return Response({
                'message': 'Handover resubmitted',
                'data': serializer.data
            })
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def takeover(self, request, pk=None):
        """Take over responsibilities"""
        handover = self.get_object()
        employee = self.get_employee()
        
        if not employee:
            return Response(
                {'error': 'Employee profile not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if handover.taking_over_employee != employee:
            return Response(
                {'error': 'You are not authorized to perform this action'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if handover.status != 'APPROVED_BY_LINE_MANAGER':
            return Response(
                {'error': 'Status is not appropriate for this action'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        comment = request.data.get('comment', '')
        
        try:
            handover.takeover(request.user, comment)
            serializer = self.get_serializer(handover)
            return Response({
                'message': 'Handover taken over',
                'data': serializer.data
            })
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def takeback(self, request, pk=None):
        """Take back responsibilities"""
        handover = self.get_object()
        employee = self.get_employee()
        
        if not employee:
            return Response(
                {'error': 'Employee profile not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if handover.handing_over_employee != employee:
            return Response(
                {'error': 'You are not authorized to perform this action'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if handover.status != 'TAKEN_OVER':
            return Response(
                {'error': 'Status is not appropriate for this action'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        comment = request.data.get('comment', '')
        
        try:
            handover.takeback(request.user, comment)
            serializer = self.get_serializer(handover)
            return Response({
                'message': 'Handover taken back',
                'data': serializer.data
            })
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['get'])
    def activity_log(self, request, pk=None):
        """Get handover activity log"""
        handover = self.get_object()
        activities = handover.activity_log.all()
        serializer = HandoverActivitySerializer(activities, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get handover statistics"""
        employee = self.get_employee()
        
        if not employee:
            return Response(
                {'error': 'Employee profile not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Base queryset
        my_handovers = self.get_queryset().filter(
            Q(handing_over_employee=employee) |
            Q(taking_over_employee=employee) |
            Q(line_manager=employee)
        )
        
        # Pending - awaiting action
        pending = my_handovers.filter(
            Q(handing_over_employee=employee, status='CREATED', ho_signed=False) |
            Q(taking_over_employee=employee, status='SIGNED_BY_HANDING_OVER', to_signed=False) |
            Q(line_manager=employee, status='SIGNED_BY_TAKING_OVER', lm_approved=False) |
            Q(handing_over_employee=employee, status='NEED_CLARIFICATION') |
            Q(taking_over_employee=employee, status='APPROVED_BY_LINE_MANAGER', taken_over=False) |
            Q(handing_over_employee=employee, status='TAKEN_OVER', taken_back=False)
        ).count()
        
        # Active - not rejected or completed
        active = my_handovers.exclude(
            status__in=['REJECTED', 'TAKEN_BACK']
        ).count()
        
        # Completed
        completed = my_handovers.filter(
            status='TAKEN_BACK'
        ).count()
        
        return Response({
            'pending': pending,
            'active': active,
            'completed': completed
        })


class HandoverTaskViewSet(viewsets.ModelViewSet):
    """Handover Task CRUD"""
    serializer_class = HandoverTaskSerializer
    permission_classes = [IsAuthenticated]
    
    def get_employee(self):
        """Get employee instance"""
        user = self.request.user
        try:
            return user.employee
        except AttributeError:
            pass
        try:
            return Employee.objects.get(email=user.email)
        except Employee.DoesNotExist:
            pass
        try:
            return Employee.objects.get(email=user.username)
        except Employee.DoesNotExist:
            return None
    
    def get_queryset(self):
        """User-visible tasks"""
        employee = self.get_employee()
        
        if not employee:
            return HandoverTask.objects.none()
        
        return HandoverTask.objects.filter(
            Q(handover__handing_over_employee=employee) |
            Q(handover__taking_over_employee=employee) |
            Q(handover__line_manager=employee)
        ).select_related('handover').prefetch_related('activity_log')
    
    @action(detail=True, methods=['post'])
    def update_status(self, request, pk=None):
        """Update task status"""
        task = self.get_object()
        employee = self.get_employee()
        
        if not employee:
            return Response(
                {'error': 'Employee profile not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if task.handover.taking_over_employee != employee:
            return Response(
                {'error': 'Only taking over employee can update task status'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if task.handover.status in ['TAKEN_OVER', 'TAKEN_BACK', 'REJECTED']:
            return Response(
                {'error': 'Handover already completed/rejected'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        new_status = request.data.get('status')
        comment = request.data.get('comment', '')
        
        if not new_status:
            return Response(
                {'error': 'Status is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            task.update_status(request.user, new_status, comment)
            serializer = self.get_serializer(task)
            return Response({
                'message': 'Task status updated',
                'data': serializer.data
            })
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class HandoverAttachmentViewSet(viewsets.ModelViewSet):
    """Handover Attachment CRUD"""
    serializer_class = HandoverAttachmentSerializer
    permission_classes = [IsAuthenticated]
    
    def get_employee(self):
        """Get employee instance"""
        user = self.request.user
        try:
            return user.employee
        except AttributeError:
            pass
        try:
            return Employee.objects.get(email=user.email)
        except Employee.DoesNotExist:
            pass
        try:
            return Employee.objects.get(email=user.username)
        except Employee.DoesNotExist:
            return None
    
    def get_queryset(self):
        """User-visible attachments"""
        employee = self.get_employee()
        
        if not employee:
            return HandoverAttachment.objects.none()
        
        return HandoverAttachment.objects.filter(
            Q(handover__handing_over_employee=employee) |
            Q(handover__taking_over_employee=employee) |
            Q(handover__line_manager=employee)
        ).select_related('handover', 'uploaded_by')
    
    def perform_create(self, serializer):
        """Create attachment with file info"""
        file = self.request.FILES.get('file')
        if file:
            serializer.save(
                uploaded_by=self.request.user,
             
                file_size=file.size,
                file_type=file.content_type
            )
        else:
            serializer.save(uploaded_by=self.request.user)