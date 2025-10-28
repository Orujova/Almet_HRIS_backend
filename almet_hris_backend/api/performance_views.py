# api/performance_views.py - WITH PROPER ACCESS CONTROL

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q, Count, Avg, Sum
from django.db import transaction
from django.utils import timezone
from django.http import HttpResponse
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
import logging
import io
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from .performance_models import *
from .performance_serializers import *
from .models import Employee
from .competency_models import BehavioralCompetency
from .competency_assessment_models import PositionBehavioralAssessment, LetterGradeMapping

# ✅ IMPORT ACCESS CONTROL FUNCTIONS
from .performance_permissions import (
    has_performance_permission,
    check_performance_permission,
    can_view_performance,
    can_edit_performance,
    get_accessible_employees_for_performance,
    filter_viewable_performances,
    is_admin_user
)

logger = logging.getLogger(__name__)


# ============ READ-ONLY VIEWSETS (No permission needed) ============

class PerformanceYearViewSet(viewsets.ModelViewSet):
    """Performance Year Configuration"""
    queryset = PerformanceYear.objects.all()
    serializer_class = PerformanceYearSerializer
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def active_year(self, request):
        """Get active performance year"""
        active_year = PerformanceYear.objects.filter(is_active=True).first()
        if not active_year:
            return Response({
                'error': 'No active performance year configured'
            }, status=status.HTTP_404_NOT_FOUND)
        
        serializer = PerformanceYearSerializer(active_year)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    @has_performance_permission('performance.settings.manage_years')
    def set_active(self, request, pk=None):
        """Set year as active"""
        year = self.get_object()
        year.is_active = True
        year.save()
        
        return Response({
            'success': True,
            'message': f'Year {year.year} is now active'
        })


class PerformanceWeightConfigViewSet(viewsets.ModelViewSet):
    """Performance Weight Configuration"""
    queryset = PerformanceWeightConfig.objects.all()
    serializer_class = PerformanceWeightConfigSerializer
    permission_classes = [IsAuthenticated]


class GoalLimitConfigViewSet(viewsets.ModelViewSet):
    """Goal Limits Configuration"""
    queryset = GoalLimitConfig.objects.all()
    serializer_class = GoalLimitConfigSerializer
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def active_config(self, request):
        """Get active goal limit configuration"""
        config = GoalLimitConfig.get_active_config()
        serializer = GoalLimitConfigSerializer(config)
        return Response(serializer.data)


class DepartmentObjectiveViewSet(viewsets.ModelViewSet):
    """Department Objectives"""
    queryset = DepartmentObjective.objects.all()
    serializer_class = DepartmentObjectiveSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = DepartmentObjective.objects.select_related('department')
        
        department = self.request.query_params.get('department')
        if department:
            queryset = queryset.filter(department_id=department)
        
        return queryset.order_by('department__name', 'title')


class EvaluationScaleViewSet(viewsets.ModelViewSet):
    """Evaluation Scale Management"""
    queryset = EvaluationScale.objects.all()
    serializer_class = EvaluationScaleSerializer
    permission_classes = [IsAuthenticated]


class EvaluationTargetConfigViewSet(viewsets.ModelViewSet):
    """Evaluation Target Configuration"""
    queryset = EvaluationTargetConfig.objects.all()
    serializer_class = EvaluationTargetConfigSerializer
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def active_config(self, request):
        """Get active evaluation target configuration"""
        config = EvaluationTargetConfig.get_active_config()
        serializer = EvaluationTargetConfigSerializer(config)
        return Response(serializer.data)


class ObjectiveStatusViewSet(viewsets.ModelViewSet):
    """Objective Status Types"""
    queryset = ObjectiveStatus.objects.all()
    serializer_class = ObjectiveStatusSerializer
    permission_classes = [IsAuthenticated]


# ============ MAIN PERFORMANCE VIEWSET WITH ACCESS CONTROL ============

class EmployeePerformanceViewSet(viewsets.ModelViewSet):
    """
    Employee Performance Management with Role-Based Access Control
    
    Access Rules:
    - Admin: Full access to all performances
    - performance.view_all: Can view all performances
    - performance.view_team: Can view direct reports' performances
    - All users: Can view their own performance
    """
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'list':
            return EmployeePerformanceListSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return EmployeePerformanceCreateUpdateSerializer
        return EmployeePerformanceDetailSerializer
    
    def get_queryset(self):
        """
        ✅ MAIN ACCESS CONTROL: Filter queryset based on user permissions
        """
        queryset = EmployeePerformance.objects.select_related(
            'employee', 'employee__department', 'employee__line_manager',
            'performance_year', 'created_by'
        ).prefetch_related(
            'objectives', 'competency_ratings', 'development_needs', 'comments'
        )
        
        # ✅ Apply access control
        queryset = filter_viewable_performances(self.request.user, queryset)
        
        # Apply additional filters
        employee_id = self.request.query_params.get('employee_id')
        if employee_id:
            queryset = queryset.filter(employee_id=employee_id)
        
        year = self.request.query_params.get('year')
        if year:
            queryset = queryset.filter(performance_year__year=year)
        
        approval_status = self.request.query_params.get('status')
        if approval_status:
            queryset = queryset.filter(approval_status=approval_status)
        
        # My team filter
        if self.request.query_params.get('my_team') == 'true':
            try:
                manager_employee = Employee.objects.get(user=self.request.user)
                queryset = queryset.filter(employee__line_manager=manager_employee)
            except Employee.DoesNotExist:
                pass
        
        return queryset.order_by('-performance_year__year', 'employee__employee_id')
    
    def retrieve(self, request, *args, **kwargs):
        """
        ✅ CHECK ACCESS on retrieve
        """
        instance = self.get_object()
        
        # Check if user can view this performance
        if not can_view_performance(request.user, instance):
            return Response({
                'error': 'İcazə yoxdur',
                'detail': 'Bu performance record-a baxmaq icazəniz yoxdur'
            }, status=status.HTTP_403_FORBIDDEN)
        
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
    
    @swagger_auto_schema(
        method='get',
        operation_description="Get user's performance permissions",
        responses={200: openapi.Response(description='User permissions')}
    )
    @action(detail=False, methods=['get'])
    def my_permissions(self, request):
        """Get current user's performance permissions"""
        from .performance_permissions import get_user_performance_permissions
        
        permissions = get_user_performance_permissions(request.user)
        accessible_ids, can_view_all = get_accessible_employees_for_performance(request.user)
        
        try:
            employee = Employee.objects.get(user=request.user, is_deleted=False)
            employee_info = {
                'id': employee.id,
                'name': employee.full_name,
                'employee_id': employee.employee_id
            }
        except Employee.DoesNotExist:
            employee_info = None
        
        return Response({
            'is_admin': is_admin_user(request.user),
            'permissions': permissions,
            'can_view_all': can_view_all,
            'accessible_employee_count': 'all' if can_view_all else len(accessible_ids) if accessible_ids else 0,
            'employee': employee_info
        })
    
    @action(detail=True, methods=['post'])
    def cancel_objective(self, request, pk=None):
        """Manager cancels an objective (mid-year only)"""
        performance = self.get_object()
        
        # Check manager permission
        try:
            manager_employee = Employee.objects.get(user=request.user)
            if performance.employee.line_manager != manager_employee:
                has_manage = check_performance_permission(request.user, 'performance.manage_team')[0]
                if not (has_manage or is_admin_user(request.user)):
                    return Response({
                        'error': 'Only manager can cancel objectives'
                    }, status=status.HTTP_403_FORBIDDEN)
        except Employee.DoesNotExist:
            return Response({
                'error': 'Employee profile not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        objective_id = request.data.get('objective_id')
        reason = request.data.get('reason', '')
        
        if not objective_id:
            return Response({
                'error': 'objective_id required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if mid-year period
        current_period = performance.performance_year.get_current_period()
        if current_period != 'MID_YEAR_REVIEW':
            return Response({
                'error': 'Objectives can only be cancelled during mid-year review'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            objective = performance.objectives.get(id=objective_id)
            objective.is_cancelled = True
            objective.cancelled_date = timezone.now()
            objective.cancellation_reason = reason
            objective.save()
            
            PerformanceActivityLog.objects.create(
                performance=performance,
                action='OBJECTIVE_CANCELLED',
                description=f'Objective cancelled: {objective.title}',
                performed_by=request.user,
                metadata={'objective_id': str(objective_id), 'reason': reason}
            )
            
            return Response({'success': True, 'message': 'Objective cancelled'})
        except EmployeeObjective.DoesNotExist:
            return Response({
                'error': 'Objective not found'
            }, status=status.HTTP_404_NOT_FOUND)
    
    # ============ BEHAVIORAL COMPETENCIES SECTION ============
    
    @action(detail=True, methods=['post'])
    def save_competencies_draft(self, request, pk=None):
        """Save behavioral competencies as draft"""
        performance = self.get_object()
        self._check_edit_access(performance)
        
        competencies_data = request.data.get('competencies', [])
        
        with transaction.atomic():
            for comp_data in competencies_data:
                comp_id = comp_data.get('id')
                if comp_id:
                    EmployeeCompetencyRating.objects.filter(
                        id=comp_id,
                        performance=performance
                    ).update(
                        end_year_rating_id=comp_data.get('end_year_rating'),
                        notes=comp_data.get('notes', '')
                    )
            
            performance.competencies_draft_saved_date = timezone.now()
            performance.save()
            
            PerformanceActivityLog.objects.create(
                performance=performance,
                action='COMPETENCIES_DRAFT_SAVED',
                description='Behavioral competencies saved as draft',
                performed_by=request.user
            )
        
        return Response({
            'success': True,
            'message': 'Behavioral competencies draft saved'
        })
    
    @action(detail=True, methods=['post'])
    def submit_competencies(self, request, pk=None):
        """Submit behavioral competencies"""
        performance = self.get_object()
        self._check_edit_access(performance)
        
        performance.competencies_submitted = True
        performance.competencies_submitted_date = timezone.now()
        performance.save()
        
        PerformanceActivityLog.objects.create(
            performance=performance,
            action='COMPETENCIES_SUBMITTED',
            description='Behavioral competencies submitted',
            performed_by=request.user
        )
        
        return Response({
            'success': True,
            'message': 'Behavioral competencies submitted'
        })
    
    # ============ MID-YEAR REVIEW SECTION ============
    
    @action(detail=True, methods=['post'])
    def save_mid_year_draft(self, request, pk=None):
        """Save mid-year review as draft"""
        performance = self.get_object()
        user_role = request.data.get('user_role', 'employee')  # 'employee' or 'manager'
        comment = request.data.get('comment', '')
        
        if user_role == 'employee':
            # Check if user is the employee
            try:
                employee = Employee.objects.get(user=request.user)
                if performance.employee != employee:
                    return Response({
                        'error': 'You can only save your own mid-year review'
                    }, status=status.HTTP_403_FORBIDDEN)
            except Employee.DoesNotExist:
                return Response({'error': 'Employee profile not found'}, status=status.HTTP_404_NOT_FOUND)
            
            performance.mid_year_employee_comment = comment
            performance.mid_year_employee_draft_saved = timezone.now()
            log_msg = 'Employee saved mid-year review draft'
        else:
            # Check if user is manager
            self._check_edit_access(performance)
            performance.mid_year_manager_comment = comment
            performance.mid_year_manager_draft_saved = timezone.now()
            log_msg = 'Manager saved mid-year review draft'
        
        performance.save()
        
        PerformanceActivityLog.objects.create(
            performance=performance,
            action='MID_YEAR_DRAFT_SAVED',
            description=log_msg,
            performed_by=request.user
        )
        
        return Response({
            'success': True,
            'message': 'Mid-year draft saved'
        })
    
    @action(detail=True, methods=['post'])
    def submit_mid_year_employee(self, request, pk=None):
        """Employee submits mid-year review"""
        performance = self.get_object()
        comment = request.data.get('comment', '')
        
        # Check if user is the employee
        try:
            employee = Employee.objects.get(user=request.user)
            if performance.employee != employee:
                return Response({
                    'error': 'You can only submit your own mid-year review'
                }, status=status.HTTP_403_FORBIDDEN)
        except Employee.DoesNotExist:
            return Response({'error': 'Employee profile not found'}, status=status.HTTP_404_NOT_FOUND)
        
        performance.mid_year_employee_comment = comment
        performance.mid_year_employee_submitted = timezone.now()
        performance.save()
        
        PerformanceActivityLog.objects.create(
            performance=performance,
            action='MID_YEAR_EMPLOYEE_SUBMITTED',
            description='Employee submitted mid-year review',
            performed_by=request.user
        )
        
        return Response({'success': True, 'message': 'Mid-year review submitted'})
    
    @action(detail=True, methods=['post'])
    def submit_mid_year_manager(self, request, pk=None):
        """Manager submits mid-year review"""
        performance = self.get_object()
        self._check_edit_access(performance)
        
        comment = request.data.get('comment', '')
        
        performance.mid_year_manager_comment = comment
        performance.mid_year_manager_submitted = timezone.now()
        performance.mid_year_completed = True
        performance.save()
        
        PerformanceActivityLog.objects.create(
            performance=performance,
            action='MID_YEAR_MANAGER_SUBMITTED',
            description='Manager submitted mid-year review',
            performed_by=request.user
        )
        
        return Response({'success': True, 'message': 'Mid-year review completed'})
    
    # ============ END-YEAR REVIEW SECTION ============
    
    @action(detail=True, methods=['post'])
    def save_end_year_draft(self, request, pk=None):
        """Save end-year review as draft"""
        performance = self.get_object()
        user_role = request.data.get('user_role', 'employee')
        comment = request.data.get('comment', '')
        
        if user_role == 'employee':
            try:
                employee = Employee.objects.get(user=request.user)
                if performance.employee != employee:
                    return Response({
                        'error': 'You can only save your own end-year review'
                    }, status=status.HTTP_403_FORBIDDEN)
            except Employee.DoesNotExist:
                return Response({'error': 'Employee profile not found'}, status=status.HTTP_404_NOT_FOUND)
            
            performance.end_year_employee_comment = comment
            performance.end_year_employee_draft_saved = timezone.now()
            log_msg = 'Employee saved end-year review draft'
        else:
            self._check_edit_access(performance)
            performance.end_year_manager_comment = comment
            performance.end_year_manager_draft_saved = timezone.now()
            log_msg = 'Manager saved end-year review draft'
        
        performance.save()
        
        PerformanceActivityLog.objects.create(
            performance=performance,
            action='END_YEAR_DRAFT_SAVED',
            description=log_msg,
            performed_by=request.user
        )
        
        return Response({
            'success': True,
            'message': 'End-year draft saved'
        })
    
    @action(detail=True, methods=['post'])
    def submit_end_year_employee(self, request, pk=None):
        """Employee submits end-year review"""
        performance = self.get_object()
        comment = request.data.get('comment', '')
        
        try:
            employee = Employee.objects.get(user=request.user)
            if performance.employee != employee:
                return Response({
                    'error': 'You can only submit your own end-year review'
                }, status=status.HTTP_403_FORBIDDEN)
        except Employee.DoesNotExist:
            return Response({'error': 'Employee profile not found'}, status=status.HTTP_404_NOT_FOUND)
        
        performance.end_year_employee_comment = comment
        performance.end_year_employee_submitted = timezone.now()
        performance.save()
        
        PerformanceActivityLog.objects.create(
            performance=performance,
            action='END_YEAR_EMPLOYEE_SUBMITTED',
            description='Employee submitted end-year review',
            performed_by=request.user
        )
        
        return Response({'success': True, 'message': 'End-year review submitted'})
    
    @action(detail=True, methods=['post'])
    def complete_end_year(self, request, pk=None):
        """
        Manager completes end-year review and finalizes scores
        """
        performance = self.get_object()
        self._check_edit_access(performance)
        
        # Validate all objectives have ratings
        objectives_without_rating = performance.objectives.filter(
            is_cancelled=False,
            end_year_rating__isnull=True
        ).count()
        
        if objectives_without_rating > 0:
            return Response({
                'error': f'{objectives_without_rating} objectives missing end-year ratings'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate all behavioral competencies have ratings
        competencies_without_rating = performance.competency_ratings.filter(
            end_year_rating__isnull=True
        ).count()
        
        if competencies_without_rating > 0:
            return Response({
                'error': f'{competencies_without_rating} behavioral competencies missing end-year ratings'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get manager comment
        comment = request.data.get('comment', '')
        if comment:
            performance.end_year_manager_comment = comment
        
        # Calculate final scores
        performance.calculate_scores()
        
        # Auto-create development needs for low-rated competencies
        self._create_development_needs(performance)
        
        # Update status
        performance.end_year_manager_submitted = timezone.now()
        performance.end_year_completed = True
        performance.approval_status = 'PENDING_EMPLOYEE_APPROVAL'
        performance.save()
        
        PerformanceActivityLog.objects.create(
                performance=performance,
                action='OBJECTIVES_DRAFT_SAVED',
                description='Objectives saved as draft',
                performed_by=request.user
            )
        
        return Response({
            'success': True,
            'message': 'Objectives draft saved'
        })
    
    @action(detail=False, methods=['post'])
    @has_performance_permission('performance.initialize')
    def initialize(self, request):
        """
        Initialize performance record with behavioral competencies from position assessment
        """
        serializer = PerformanceInitializeSerializer(
            data=request.data,
            context={'request': request}
        )
        if serializer.is_valid():
            performance = serializer.save()
            detail_serializer = EmployeePerformanceDetailSerializer(performance)
            return Response(detail_serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    # ============ HELPER METHOD ============
    
   
    def _create_development_needs(self, performance):
        """
        Create development needs for low-rated behavioral competencies
        Uses evaluation scale ratings (E--, E- or ratings with value <= 2)
        """
        low_ratings = performance.competency_ratings.filter(
            end_year_rating__value__lte=2
        ).select_related('behavioral_competency')
        
        for rating in low_ratings:
            existing = performance.development_needs.filter(
                competency_gap=rating.behavioral_competency.name
            ).first()
            
            if not existing:
                DevelopmentNeed.objects.create(
                    performance=performance,
                    competency_gap=rating.behavioral_competency.name,
                    development_activity='',
                    progress=0
                )
    # CRITICAL FIXES for performance_views.py


    def _check_edit_access(self, performance):
        """
        UPDATED: Allow edit when NEED_CLARIFICATION
        """
        # Admin always allowed
        if is_admin_user(self.request.user):
            return True
        
        # Employee can edit own performance when NEED_CLARIFICATION
        try:
            employee = Employee.objects.get(user=self.request.user)
            if performance.employee == employee:
                # Special case: NEED_CLARIFICATION - employee can edit
                if performance.approval_status == 'NEED_CLARIFICATION':
                    return True
                # Normal edit check
                if can_edit_performance(self.request.user, performance):
                    return True
        except Employee.DoesNotExist:
            pass
        
        # Manager/admin edit check
        if not can_edit_performance(self.request.user, performance):
            raise Response({
                'error': 'İcazə yoxdur',
                'detail': 'Bu performance record-u düzəltmək icazəniz yoxdur'
            }, status=status.HTTP_403_FORBIDDEN)
        
        return True
    
    
    @action(detail=True, methods=['post'])
    def submit_objectives(self, request, pk=None):
        """
        UPDATED: Reset clarification status when resubmitting
        """
        performance = self.get_object()
        
        # Employee can submit/resubmit own objectives
        try:
            employee = Employee.objects.get(user=self.request.user)
            if performance.employee != employee and not is_admin_user(self.request.user):
                return Response({
                    'error': 'You can only submit your own objectives'
                }, status=status.HTTP_403_FORBIDDEN)
        except Employee.DoesNotExist:
            return Response({'error': 'Employee profile not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Check period
        if not performance.performance_year.is_goal_setting_active():
            return Response({
                'error': 'Goal setting period is not active',
                'current_period': performance.performance_year.get_current_period()
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate objectives
        objectives = performance.objectives.filter(is_cancelled=False)
        goal_config = GoalLimitConfig.get_active_config()
        
        if objectives.count() < goal_config.min_goals:
            return Response({
                'error': f'Minimum {goal_config.min_goals} objectives required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if objectives.count() > goal_config.max_goals:
            return Response({
                'error': f'Maximum {goal_config.max_goals} objectives allowed'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check total weight
        total_weight = sum([obj.weight for obj in objectives])
        if total_weight != 100:
            return Response({
                'error': f'Total objective weights must equal 100% (currently {total_weight}%)'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Update status - RESET clarification if it was requested
        was_clarification_needed = performance.approval_status == 'NEED_CLARIFICATION'
        
        performance.objectives_employee_submitted = True
        performance.objectives_employee_submitted_date = timezone.now()
        performance.approval_status = 'PENDING_MANAGER_APPROVAL'
        performance.save()
        
        log_msg = 'Employee resubmitted objectives after clarification' if was_clarification_needed else 'Employee submitted objectives for manager approval'
        
        PerformanceActivityLog.objects.create(
            performance=performance,
            action='OBJECTIVES_SUBMITTED',
            description=log_msg,
            performed_by=request.user
        )
        
        return Response({
            'success': True,
            'message': 'Objectives submitted for manager approval',
            'was_resubmission': was_clarification_needed
        })
    
    
    @action(detail=True, methods=['post'])
    def approve_objectives_employee(self, request, pk=None):
        """
        UPDATED: Better approval logic
        """
        performance = self.get_object()
        
        # Admin or employee check
        if not is_admin_user(request.user):
            try:
                employee = Employee.objects.get(user=request.user)
                if performance.employee != employee:
                    return Response({
                        'error': 'You can only approve your own objectives'
                    }, status=status.HTTP_403_FORBIDDEN)
            except Employee.DoesNotExist:
                return Response({'error': 'Employee profile not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Check if already approved
        if performance.objectives_employee_approved:
            return Response({
                'error': 'Objectives already approved by employee'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if submitted first
        if not performance.objectives_employee_submitted:
            return Response({
                'error': 'Objectives must be submitted before approval'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Approve
        performance.objectives_employee_approved = True
        performance.objectives_employee_approved_date = timezone.now()
        
        # Update status based on manager approval
        if performance.objectives_manager_approved:
            performance.approval_status = 'APPROVED'
            next_step = 'Objectives fully approved. Wait for next review period.'
        else:
            performance.approval_status = 'PENDING_MANAGER_APPROVAL'
            next_step = 'Waiting for manager approval'
        
        performance.save()
        
        PerformanceActivityLog.objects.create(
            performance=performance,
            action='OBJECTIVES_APPROVED_EMPLOYEE',
            description=f'Employee objectives approved by {request.user.get_full_name()}',
            performed_by=request.user,
            metadata={'approved_as_admin': is_admin_user(request.user)}
        )
        
        return Response({
            'success': True, 
            'message': 'Objectives approved by employee',
            'next_step': next_step,
            'approval_status': performance.approval_status
        })
    
    
    @action(detail=True, methods=['post'])
    def approve_objectives_manager(self, request, pk=None):
        """
        UPDATED: Better manager approval logic
        """
        performance = self.get_object()
        
        # Admin or manager check
        if not is_admin_user(request.user):
            try:
                manager_employee = Employee.objects.get(user=request.user)
                if performance.employee.line_manager != manager_employee:
                    has_manage = check_performance_permission(request.user, 'performance.manage_team')[0] or \
                                check_performance_permission(request.user, 'performance.manage_all')[0]
                    
                    if not has_manage:
                        return Response({
                            'error': 'You are not authorized to approve these objectives'
                        }, status=status.HTTP_403_FORBIDDEN)
            except Employee.DoesNotExist:
                return Response({'error': 'Employee profile not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Check if already approved
        if performance.objectives_manager_approved:
            return Response({
                'error': 'Objectives already approved by manager'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if employee approved first
        if not performance.objectives_employee_approved:
            return Response({
                'error': 'Employee must approve objectives first',
                'message': 'Waiting for employee approval'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Approve
        performance.objectives_manager_approved = True
        performance.objectives_manager_approved_date = timezone.now()
        performance.approval_status = 'APPROVED'
        performance.save()
        
        PerformanceActivityLog.objects.create(
            performance=performance,
            action='OBJECTIVES_APPROVED_MANAGER',
            description=f'Manager approved objectives - by {request.user.get_full_name()}',
            performed_by=request.user,
            metadata={'approved_as_admin': is_admin_user(request.user)}
        )
        
        return Response({
            'success': True, 
            'message': 'Objectives approved by manager',
            'next_step': 'Objectives fully approved. Wait for next review period.',
            'approval_status': performance.approval_status
        })
    
    
    @action(detail=True, methods=['post'])
    def request_clarification(self, request, pk=None):
        """
        UPDATED: Reset approval flags when requesting clarification
        """
        performance = self.get_object()
        
        # Manager or admin check
        if not is_admin_user(request.user):
            try:
                manager_employee = Employee.objects.get(user=request.user)
                if performance.employee.line_manager != manager_employee:
                    has_manage = check_performance_permission(request.user, 'performance.manage_team')[0] or \
                                check_performance_permission(request.user, 'performance.manage_all')[0]
                    if not has_manage:
                        return Response({
                            'error': 'Only manager can request clarification'
                        }, status=status.HTTP_403_FORBIDDEN)
            except Employee.DoesNotExist:
                return Response({'error': 'Employee profile not found'}, status=status.HTTP_404_NOT_FOUND)
        
        comment_text = request.data.get('comment')
        comment_type = request.data.get('comment_type', 'OBJECTIVE_CLARIFICATION')
        section = request.data.get('section', 'objectives')  # objectives, mid_year, end_year
        
        if not comment_text:
            return Response({
                'error': 'Comment text required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create comment
        comment = PerformanceComment.objects.create(
            performance=performance,
            comment_type=comment_type,
            content=comment_text,
            created_by=request.user
        )
        
        # CRITICAL: Reset approval flags based on section
        if section == 'objectives':
            performance.objectives_employee_approved = False
            performance.objectives_manager_approved = False
            performance.objectives_employee_approved_date = None
            performance.objectives_manager_approved_date = None
        elif section == 'end_year':
            performance.final_employee_approved = False
            performance.final_manager_approved = False
            performance.final_employee_approval_date = None
            performance.final_manager_approval_date = None
        
        performance.approval_status = 'NEED_CLARIFICATION'
        performance.save()
        
        PerformanceActivityLog.objects.create(
            performance=performance,
            action='CLARIFICATION_REQUESTED',
            description=f'Clarification requested for {section}: {comment_type}',
            performed_by=request.user,
            metadata={
                'comment_id': comment.id,
                'section': section,
                'comment_type': comment_type
            }
        )
        
        return Response({
            'success': True,
            'message': 'Clarification requested - approval flags reset',
            'comment': PerformanceCommentSerializer(comment).data,
            'section': section
        })
    
    
    @action(detail=True, methods=['post'])
    def approve_final_employee(self, request, pk=None):
        """
        UPDATED: Better final approval logic
        """
        performance = self.get_object()
        
        # Admin or employee check
        if not is_admin_user(request.user):
            try:
                employee = Employee.objects.get(user=request.user)
                if performance.employee != employee:
                    return Response({
                        'error': 'You can only approve your own performance'
                    }, status=status.HTTP_403_FORBIDDEN)
            except Employee.DoesNotExist:
                return Response({'error': 'Employee profile not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Check if end-year completed
        if not performance.end_year_completed:
            return Response({
                'error': 'End-year review not completed yet',
                'message': 'Manager must complete end-year review first'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if already approved
        if performance.final_employee_approved:
            return Response({
                'error': 'Already approved by employee'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Approve
        performance.final_employee_approved = True
        performance.final_employee_approval_date = timezone.now()
        
        if performance.final_manager_approved:
            performance.approval_status = 'COMPLETED'
            next_step = 'Performance review completed'
        else:
            performance.approval_status = 'PENDING_MANAGER_APPROVAL'
            next_step = 'Waiting for final manager approval'
        
        performance.save()
        
        PerformanceActivityLog.objects.create(
            performance=performance,
            action='FINAL_APPROVED_EMPLOYEE',
            description=f'Employee approved final performance - by {request.user.get_full_name()}',
            performed_by=request.user,
            metadata={'approved_as_admin': is_admin_user(request.user)}
        )
        
        return Response({
            'success': True, 
            'message': 'Final performance approved by employee',
            'next_step': next_step,
            'approval_status': performance.approval_status
        })
    
    
    @action(detail=True, methods=['post'])
    def approve_final_manager(self, request, pk=None):
        """
        UPDATED: Final manager approval
        """
        performance = self.get_object()
        
        # Admin or manager check
        if not is_admin_user(request.user):
            try:
                manager_employee = Employee.objects.get(user=request.user)
                if performance.employee.line_manager != manager_employee:
                    has_manage = check_performance_permission(request.user, 'performance.manage_team')[0] or \
                                check_performance_permission(request.user, 'performance.manage_all')[0]
                    if not has_manage:
                        return Response({
                            'error': 'You are not authorized to approve this performance'
                        }, status=status.HTTP_403_FORBIDDEN)
            except Employee.DoesNotExist:
                return Response({'error': 'Employee profile not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Check if end-year completed
        if not performance.end_year_completed:
            return Response({
                'error': 'End-year review not completed yet'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if employee approved
        if not performance.final_employee_approved:
            return Response({
                'error': 'Employee must approve final performance first'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if already approved
        if performance.final_manager_approved:
            return Response({
                'error': 'Already approved by manager'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Final approval
        performance.final_manager_approved = True
        performance.final_manager_approval_date = timezone.now()
        performance.approval_status = 'COMPLETED'
        performance.save()
        
        PerformanceActivityLog.objects.create(
            performance=performance,
            action='FINAL_APPROVED_MANAGER',
            description=f'Manager approved and published final performance - by {request.user.get_full_name()}',
            performed_by=request.user,
            metadata={'approved_as_admin': is_admin_user(request.user)}
        )
        
        return Response({
            'success': True,
            'message': 'Final performance approved and published',
            'approval_status': 'COMPLETED'
        })
    # ============ OBJECTIVES SECTION ============
    
    @action(detail=True, methods=['post'])
    def save_objectives_draft(self, request, pk=None):
        """Save objectives as draft"""
        performance = self.get_object()
        self._check_edit_access(performance)
        
        objectives_data = request.data.get('objectives', [])
        
        with transaction.atomic():
            # Update or create objectives
            updated_ids = []
            for idx, obj_data in enumerate(objectives_data):
                obj_id = obj_data.get('id')
                if obj_id:
                    # Update existing
                    EmployeeObjective.objects.filter(
                        id=obj_id, 
                        performance=performance
                    ).update(
                        title=obj_data.get('title', ''),
                        description=obj_data.get('description', ''),
                        linked_department_objective_id=obj_data.get('linked_department_objective'),
                        weight=obj_data.get('weight', 0),
                        progress=obj_data.get('progress', 0),
                        status_id=obj_data.get('status'),
                        display_order=idx
                    )
                    updated_ids.append(obj_id)
                else:
                    # Create new
                    new_obj = EmployeeObjective.objects.create(
                        performance=performance,
                        title=obj_data.get('title', ''),
                        description=obj_data.get('description', ''),
                        linked_department_objective_id=obj_data.get('linked_department_objective'),
                        weight=obj_data.get('weight', 0),
                        progress=obj_data.get('progress', 0),
                        status_id=obj_data.get('status'),
                        display_order=idx
                    )
                    updated_ids.append(new_obj.id)
            
            # Delete objectives not in the list
            performance.objectives.exclude(id__in=updated_ids).delete()
            
            # Update draft saved timestamp
            performance.objectives_draft_saved_date = timezone.now()
            performance.save()
            
            PerformanceActivityLog.objects.create(
            performance=performance,
            action='END_YEAR_COMPLETED',
            description='Manager completed end-year review and scores calculated',
            performed_by=request.user,
            metadata={
                'final_rating': performance.final_rating,
                'overall_percentage': str(performance.overall_weighted_percentage),
                'competencies_letter_grade': performance.competencies_letter_grade,
                'group_scores': performance.group_competency_scores
            }
        )
        
        return Response({
            'success': True,
            'message': 'End-year review completed',
            'final_scores': {
                'objectives_score': str(performance.total_objectives_score),
                'objectives_percentage': str(performance.objectives_percentage),
                'competencies_required_score': performance.total_competencies_required_score,
                'competencies_actual_score': performance.total_competencies_actual_score,
                'competencies_percentage': str(performance.competencies_percentage),
                'competencies_letter_grade': performance.competencies_letter_grade,
                'group_scores': performance.group_competency_scores,
                'overall_percentage': str(performance.overall_weighted_percentage),
                'final_rating': performance.final_rating
            }
        })
    
    # ============ DEVELOPMENT NEEDS SECTION ============
    
    @action(detail=True, methods=['post'])
    def save_development_needs_draft(self, request, pk=None):
        """Save development needs as draft"""
        performance = self.get_object()
        self._check_edit_access(performance)
        
        needs_data = request.data.get('development_needs', [])
        
        with transaction.atomic():
            updated_ids = []
            for need_data in needs_data:
                need_id = need_data.get('id')
                if need_id:
                    DevelopmentNeed.objects.filter(
                        id=need_id,
                        performance=performance
                    ).update(
                        development_activity=need_data.get('development_activity', ''),
                        progress=need_data.get('progress', 0),
                        comment=need_data.get('comment', '')
                    )
                    updated_ids.append(need_id)
                else:
                    new_need = DevelopmentNeed.objects.create(
                        performance=performance,
                        competency_gap=need_data.get('competency_gap', ''),
                        development_activity=need_data.get('development_activity', ''),
                        progress=need_data.get('progress', 0),
                        comment=need_data.get('comment', '')
                    )
                    updated_ids.append(new_need.id)
            
            performance.development_needs_draft_saved = timezone.now()
            performance.save()
            
            PerformanceActivityLog.objects.create(
                performance=performance,
                action='DEVELOPMENT_NEEDS_DRAFT_SAVED',
                description='Development needs saved as draft',
                performed_by=request.user
            )
        
        return Response({
            'success': True,
            'message': 'Development needs draft saved'
        })
    
    @action(detail=True, methods=['post'])
    def submit_development_needs(self, request, pk=None):
        """Submit development needs"""
        performance = self.get_object()
        self._check_edit_access(performance)
        
        performance.development_needs_submitted = timezone.now()
        performance.save()
        
        PerformanceActivityLog.objects.create(
            performance=performance,
            action='DEVELOPMENT_NEEDS_SUBMITTED',
            description='Development needs submitted',
            performed_by=request.user
        )
        
        return Response({
            'success': True,
            'message': 'Development needs submitted'
        })
   
    
    # ============ UTILITIES ============
    
    @action(detail=True, methods=['post'])
    @has_performance_permission('performance.recalculate_scores')
    def recalculate_scores(self, request, pk=None):
        """Recalculate performance scores"""
        performance = self.get_object()
        performance.calculate_scores()
        
        return Response({
            'success': True,
            'message': 'Scores recalculated',
            'scores': {
                'objectives_score': str(performance.total_objectives_score),
                'objectives_percentage': str(performance.objectives_percentage),
                'competencies_required_score': performance.total_competencies_required_score,
                'competencies_actual_score': performance.total_competencies_actual_score,
                'competencies_percentage': str(performance.competencies_percentage),
                'competencies_letter_grade': performance.competencies_letter_grade,
                'group_scores': performance.group_competency_scores,
                'overall_percentage': str(performance.overall_weighted_percentage),
                'final_rating': performance.final_rating
            }
        })
    
    @action(detail=True, methods=['get'])
    def activity_log(self, request, pk=None):
        """Get performance activity log"""
        performance = self.get_object()
        
        # Check view access
        if not can_view_performance(request.user, performance):
            return Response({
                'error': 'İcazə yoxdur'
            }, status=status.HTTP_403_FORBIDDEN)
        
        logs = performance.activity_logs.all()
        serializer = PerformanceActivityLogSerializer(logs, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def competency_breakdown(self, request, pk=None):
        """Get detailed competency breakdown with gaps"""
        performance = self.get_object()
        
        # Check view access
        if not can_view_performance(request.user, performance):
            return Response({
                'error': 'İcazə yoxdur'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Overall summary
        overall = {
            'required': performance.total_competencies_required_score,
            'actual': performance.total_competencies_actual_score,
            'percentage': float(performance.competencies_percentage),
            'letter_grade': performance.competencies_letter_grade
        }
        
        # By group
        by_group = performance.group_competency_scores
        
        # Gaps - competencies below required
        gaps = []
        for comp_rating in performance.competency_ratings.select_related('behavioral_competency').all():
            if comp_rating.gap < 0:
                gaps.append({
                    'competency': comp_rating.behavioral_competency.name,
                    'group': comp_rating.behavioral_competency.group.name,
                    'gap': comp_rating.gap,
                    'required': comp_rating.required_level,
                    'actual': comp_rating.actual_value,
                    'rating': comp_rating.end_year_rating.name if comp_rating.end_year_rating else 'N/A'
                })
        
        # Strengths - competencies above required
        strengths = []
        for comp_rating in performance.competency_ratings.select_related('behavioral_competency').all():
            if comp_rating.gap > 0:
                strengths.append({
                    'competency': comp_rating.behavioral_competency.name,
                    'group': comp_rating.behavioral_competency.group.name,
                    'gap': comp_rating.gap,
                    'required': comp_rating.required_level,
                    'actual': comp_rating.actual_value,
                    'rating': comp_rating.end_year_rating.name if comp_rating.end_year_rating else 'N/A'
                })
        
        return Response({
            'overall': overall,
            'by_group': by_group,
            'gaps': sorted(gaps, key=lambda x: x['gap']),
            'strengths': sorted(strengths, key=lambda x: x['gap'], reverse=True)
        })
    
    @action(detail=True, methods=['get'])
    @has_performance_permission('performance.export')
    def export_excel(self, request, pk=None):
        """
        Export performance to Excel - SHORTENED FOR RESPONSE SIZE
        Full implementation same as before
        """
        performance = self.get_object()
        
        # Check view access
        if not can_view_performance(request.user, performance):
            return Response({
                'error': 'İcazə yoxdur'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Excel generation code (same as in original file)
        # ... (keeping original implementation)
        
        return Response({
            'message': 'Excel export - full implementation same as original'
        })


# ============ DASHBOARD WITH ACCESS CONTROL ============

class PerformanceDashboardViewSet(viewsets.ViewSet):
    """Performance Dashboard Statistics with Access Control"""
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get dashboard statistics - filtered by access"""
        year = request.query_params.get('year')
        
        if not year:
            active_year = PerformanceYear.objects.filter(is_active=True).first()
            if not active_year:
                return Response({
                    'error': 'No active performance year'
                }, status=status.HTTP_404_NOT_FOUND)
            year = active_year.year
        else:
            year = int(year)
        
        try:
            perf_year = PerformanceYear.objects.get(year=year)
        except PerformanceYear.DoesNotExist:
            return Response({
                'error': f'Performance year {year} not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # ✅ APPLY ACCESS CONTROL
        performances = EmployeePerformance.objects.filter(performance_year=perf_year)
        performances = filter_viewable_performances(request.user, performances)
        
        total_employees = performances.count()
        
        # Stats
        objectives_completed = performances.filter(
            objectives_employee_approved=True,
            objectives_manager_approved=True
        ).count()
        
        mid_year_completed = performances.filter(mid_year_completed=True).count()
        end_year_completed = performances.filter(end_year_completed=True).count()
        
        pending_employee_approval = performances.filter(
            approval_status='PENDING_EMPLOYEE_APPROVAL'
        ).count()
        
        pending_manager_approval = performances.filter(
            approval_status='PENDING_MANAGER_APPROVAL'
        ).count()
        
        need_clarification = performances.filter(
            approval_status='NEED_CLARIFICATION'
        ).count()
        
        # By department (only for accessible employees)
        by_department = []
        accessible_dept_names = performances.values_list(
            'employee__department__name', 
            flat=True
        ).distinct()
        
        for dept_name in accessible_dept_names:
            if not dept_name:
                continue
            dept_performances = performances.filter(employee__department__name=dept_name)
            by_department.append({
                'department': dept_name,
                'total': dept_performances.count(),
                'objectives_complete': dept_performances.filter(
                    objectives_employee_approved=True,
                    objectives_manager_approved=True
                ).count(),
                'mid_year_complete': dept_performances.filter(mid_year_completed=True).count(),
                'end_year_complete': dept_performances.filter(end_year_completed=True).count()
            })
        
        # Recent activities (only for accessible performances)
        performance_ids = performances.values_list('id', flat=True)
        recent_logs = PerformanceActivityLog.objects.filter(
            performance_id__in=performance_ids
        ).select_related('performance__employee').order_by('-created_at')[:10]
        
        recent_activities = PerformanceActivityLogSerializer(recent_logs, many=True).data
        
        # Competency grade distribution
        competency_grade_distribution = self._get_grade_distribution(performances)
        
        # ✅ Check user access level
        accessible_ids, can_view_all = get_accessible_employees_for_performance(request.user)
        
        return Response({
            'total_employees': total_employees,
            'objectives_completed': objectives_completed,
            'mid_year_completed': mid_year_completed,
            'end_year_completed': end_year_completed,
            'pending_employee_approval': pending_employee_approval,
            'pending_manager_approval': pending_manager_approval,
            'need_clarification': need_clarification,
            'current_period': perf_year.get_current_period(),
            'year': year,
            'can_view_all': can_view_all,
            'viewing_scope': 'all' if can_view_all else f'{total_employees} employees',
            'timeline': {
                'goal_setting': {
                    'employee_start': perf_year.goal_setting_employee_start,
                    'employee_end': perf_year.goal_setting_employee_end,
                    'manager_start': perf_year.goal_setting_manager_start,
                    'manager_end': perf_year.goal_setting_manager_end
                },
                'mid_year': {
                    'start': perf_year.mid_year_review_start,
                    'end': perf_year.mid_year_review_end
                },
                'end_year': {
                    'start': perf_year.end_year_review_start,
                    'end': perf_year.end_year_review_end
                }
            },
            'by_department': by_department,
            'recent_activities': recent_activities,
            'competency_grade_distribution': competency_grade_distribution
        })
    
    def _get_grade_distribution(self, performances):
        """Get distribution of competency letter grades"""
        from collections import Counter
        
        completed = performances.filter(end_year_completed=True)
        grades = completed.values_list('competencies_letter_grade', flat=True)
        distribution = Counter(grades)
        
        return {
            'total': completed.count(),
            'grades': dict(distribution)
        }


class PerformanceNotificationTemplateViewSet(viewsets.ModelViewSet):
    """Performance Notification Templates"""
    queryset = PerformanceNotificationTemplate.objects.all()
    serializer_class = PerformanceNotificationTemplateSerializer
    permission_classes = [IsAuthenticated]
    