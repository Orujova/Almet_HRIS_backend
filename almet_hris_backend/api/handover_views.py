# api/handover_views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db.models import Q
from django.utils import timezone

from .handover_models import (
    HandoverType, HandoverRequest, HandoverTask,
    HandoverImportantDate, HandoverActivity, HandoverAttachment
)
from .handover_serializers import (
    HandoverTypeSerializer, HandoverRequestSerializer,
    HandoverRequestCreateSerializer, HandoverTaskSerializer,
    HandoverImportantDateSerializer, HandoverActivitySerializer,
    HandoverAttachmentSerializer
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
    """Handover Request əsas ViewSet"""
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
        """User-specific queryset"""
        employee = self.get_employee()
        
        if not employee:
            return HandoverRequest.objects.none()
        
        # User özü təhvil verən, təhvil alan və ya line manager olarsa görə bilər
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
        if self.action == 'create':
            return HandoverRequestCreateSerializer
        return HandoverRequestSerializer
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    @action(detail=False, methods=['get'])
    def my_handovers(self, request):
        """Mənim təhvil verdiyim və aldığım handoverlər"""
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
        """Təsdiq gözləyən handoverlər"""
        employee = self.get_employee()
        
        if not employee:
            return Response(
                {'error': 'Employee profile not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Handing Over olaraq - imzalamağı gözləyir
        ho_pending = Q(
            handing_over_employee=employee,
            status='CREATED',
            ho_signed=False
        )
        
        # Taking Over olaraq - imzalamağı gözləyir
        to_pending = Q(
            taking_over_employee=employee,
            status='SIGNED_BY_HANDING_OVER',
            to_signed=False
        )
        
        # Line Manager olaraq - təsdiq gözləyir
        lm_pending = Q(
            line_manager=employee,
            status='SIGNED_BY_TAKING_OVER',
            lm_approved=False
        )
        
        # Need Clarification - HO cavab verməli
        clarification_pending = Q(
            handing_over_employee=employee,
            status='NEED_CLARIFICATION'
        )
        
        # Approved - TO təhvil almalı
        takeover_pending = Q(
            taking_over_employee=employee,
            status='APPROVED_BY_LINE_MANAGER',
            taken_over=False
        )
        
        # Taken Over - HO geri götürməli
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
        """Təhvil verən imzalayır"""
        handover = self.get_object()
        employee = self.get_employee()
        
        if not employee:
            return Response(
                {'error': 'Employee profile not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if handover.handing_over_employee != employee:
            return Response(
                {'error': 'Sizin bu əməliyyatı yerinə yetirməyə icazəniz yoxdur'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if handover.status != 'CREATED':
            return Response(
                {'error': 'Status uyğun deyil'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            comment = request.data.get('comment', '')
            handover.sign_by_handing_over(request.user)
            serializer = self.get_serializer(handover)
            return Response({
                'message': 'Handover uğurla imzalandı',
                'data': serializer.data
            })
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def sign_to(self, request, pk=None):
        """Təhvil alan imzalayır"""
        handover = self.get_object()
        employee = self.get_employee()
        
        if not employee:
            return Response(
                {'error': 'Employee profile not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if handover.taking_over_employee != employee:
            return Response(
                {'error': 'Sizin bu əməliyyatı yerinə yetirməyə icazəniz yoxdur'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if handover.status != 'SIGNED_BY_HANDING_OVER':
            return Response(
                {'error': 'Status uyğun deyil'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            comment = request.data.get('comment', '')
            handover.sign_by_taking_over(request.user)
            serializer = self.get_serializer(handover)
            return Response({
                'message': 'Handover təhvil alan tərəfindən imzalandı',
                'data': serializer.data
            })
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def approve_lm(self, request, pk=None):
        """Line Manager təsdiq edir"""
        handover = self.get_object()
        employee = self.get_employee()
        
        if not employee:
            return Response(
                {'error': 'Employee profile not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if handover.line_manager != employee:
            return Response(
                {'error': 'Sizin bu əməliyyatı yerinə yetirməyə icazəniz yoxdur'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if handover.status != 'SIGNED_BY_TAKING_OVER':
            return Response(
                {'error': 'Status uyğun deyil'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        comment = request.data.get('comment', '')
        
        try:
            handover.approve_by_line_manager(request.user, comment)
            serializer = self.get_serializer(handover)
            return Response({
                'message': 'Handover təsdiqləndi',
                'data': serializer.data
            })
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def reject_lm(self, request, pk=None):
        """Line Manager rədd edir"""
        handover = self.get_object()
        employee = self.get_employee()
        
        if not employee:
            return Response(
                {'error': 'Employee profile not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if handover.line_manager != employee:
            return Response(
                {'error': 'Sizin bu əməliyyatı yerinə yetirməyə icazəniz yoxdur'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if handover.status != 'SIGNED_BY_TAKING_OVER':
            return Response(
                {'error': 'Status uyğun deyil'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        reason = request.data.get('reason', '')
        if not reason:
            return Response(
                {'error': 'Rədd səbəbi qeyd edilməlidir'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            handover.reject_by_line_manager(request.user, reason)
            serializer = self.get_serializer(handover)
            return Response({
                'message': 'Handover rədd edildi',
                'data': serializer.data
            })
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def request_clarification(self, request, pk=None):
        """Line Manager aydınlaşdırma tələb edir"""
        handover = self.get_object()
        employee = self.get_employee()
        
        if not employee:
            return Response(
                {'error': 'Employee profile not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if handover.line_manager != employee:
            return Response(
                {'error': 'Sizin bu əməliyyatı yerinə yetirməyə icazəniz yoxdur'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if handover.status != 'SIGNED_BY_TAKING_OVER':
            return Response(
                {'error': 'Status uyğun deyil'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        clarification_comment = request.data.get('clarification_comment', '')
        if not clarification_comment:
            return Response(
                {'error': 'Aydınlaşdırma mətni qeyd edilməlidir'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            handover.request_clarification(request.user, clarification_comment)
            serializer = self.get_serializer(handover)
            return Response({
                'message': 'Aydınlaşdırma tələb edildi',
                'data': serializer.data
            })
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def resubmit(self, request, pk=None):
        """Təhvil verən aydınlaşdırmadan sonra yenidən göndərir"""
        handover = self.get_object()
        employee = self.get_employee()
        
        if not employee:
            return Response(
                {'error': 'Employee profile not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if handover.handing_over_employee != employee:
            return Response(
                {'error': 'Sizin bu əməliyyatı yerinə yetirməyə icazəniz yoxdur'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if handover.status != 'NEED_CLARIFICATION':
            return Response(
                {'error': 'Status uyğun deyil'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        response_comment = request.data.get('response_comment', '')
        if not response_comment:
            return Response(
                {'error': 'Aydınlaşdırmaya cavab qeyd edilməlidir'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            handover.resubmit_after_clarification(request.user, response_comment)
            serializer = self.get_serializer(handover)
            return Response({
                'message': 'Handover yenidən göndərildi',
                'data': serializer.data
            })
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def takeover(self, request, pk=None):
        """Təhvil alan təhvil alır"""
        handover = self.get_object()
        employee = self.get_employee()
        
        if not employee:
            return Response(
                {'error': 'Employee profile not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if handover.taking_over_employee != employee:
            return Response(
                {'error': 'Sizin bu əməliyyatı yerinə yetirməyə icazəniz yoxdur'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if handover.status != 'APPROVED_BY_LINE_MANAGER':
            return Response(
                {'error': 'Status uyğun deyil'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        comment = request.data.get('comment', '')
        
        try:
            handover.takeover(request.user, comment)
            serializer = self.get_serializer(handover)
            return Response({
                'message': 'Handover təhvil alındı',
                'data': serializer.data
            })
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def takeback(self, request, pk=None):
        """Təhvil verən geri götürür"""
        handover = self.get_object()
        employee = self.get_employee()
        
        if not employee:
            return Response(
                {'error': 'Employee profile not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if handover.handing_over_employee != employee:
            return Response(
                {'error': 'Sizin bu əməliyyatı yerinə yetirməyə icazəniz yoxdur'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if handover.status != 'TAKEN_OVER':
            return Response(
                {'error': 'Status uyğun deyil'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        comment = request.data.get('comment', '')
        
        try:
            handover.takeback(request.user, comment)
            serializer = self.get_serializer(handover)
            return Response({
                'message': 'Handover geri götürüldü',
                'data': serializer.data
            })
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['get'])
    def activity_log(self, request, pk=None):
        """Handover activity log"""
        handover = self.get_object()
        activities = handover.activity_log.all()
        serializer = HandoverActivitySerializer(activities, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Statistika"""
        employee = self.get_employee()
        
        if not employee:
            return Response(
                {'error': 'Employee profile not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Əsas queryset
        my_handovers = self.get_queryset().filter(
            Q(handing_over_employee=employee) |
            Q(taking_over_employee=employee) |
            Q(line_manager=employee)
        )
        
        # Pending - təsdiq gözləyən
        pending = my_handovers.filter(
            Q(handing_over_employee=employee, status='CREATED', ho_signed=False) |
            Q(taking_over_employee=employee, status='SIGNED_BY_HANDING_OVER', to_signed=False) |
            Q(line_manager=employee, status='SIGNED_BY_TAKING_OVER', lm_approved=False) |
            Q(handing_over_employee=employee, status='NEED_CLARIFICATION') |
            Q(taking_over_employee=employee, status='APPROVED_BY_LINE_MANAGER', taken_over=False) |
            Q(handing_over_employee=employee, status='TAKEN_OVER', taken_back=False)
        ).count()
        
        # Active - aktiv handoverlər
        active = my_handovers.exclude(
            status__in=['REJECTED', 'TAKEN_BACK']
        ).count()
        
        # Completed - tamamlanmış
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
        """Get employee instance from request user"""
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
        """User-in görə biləcəyi tasklar"""
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
        """Task statusunu yenilə"""
        task = self.get_object()
        employee = self.get_employee()
        
        if not employee:
            return Response(
                {'error': 'Employee profile not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if task.handover.taking_over_employee != employee:
            return Response(
                {'error': 'Yalnız təhvil alan task statusunu yeniləyə bilər'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if task.handover.status in ['TAKEN_OVER', 'TAKEN_BACK', 'REJECTED']:
            return Response(
                {'error': 'Handover artıq tamamlanıb/rədd edilib'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        new_status = request.data.get('status')
        comment = request.data.get('comment', '')
        
        if not new_status:
            return Response(
                {'error': 'Status qeyd edilməlidir'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            task.update_status(request.user, new_status, comment)
            serializer = self.get_serializer(task)
            return Response({
                'message': 'Task statusu yeniləndi',
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
        """Get employee instance from request user"""
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
        """User-in görə biləcəyi attachmentlər"""
        employee = self.get_employee()
        
        if not employee:
            return HandoverAttachment.objects.none()
        
        return HandoverAttachment.objects.filter(
            Q(handover__handing_over_employee=employee) |
            Q(handover__taking_over_employee=employee) |
            Q(handover__line_manager=employee)
        ).select_related('handover', 'uploaded_by')
    
    def perform_create(self, serializer):
        file = self.request.FILES.get('file')
        if file:
            serializer.save(
                uploaded_by=self.request.user,
                original_filename=file.name,
                file_size=file.size,
                file_type=file.content_type
            )
        else:
            serializer.save(uploaded_by=self.request.user)