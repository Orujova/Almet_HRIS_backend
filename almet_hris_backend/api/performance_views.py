# api/performance_views.py

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

from .performance_models import *
from .performance_serializers import *
from .models import Employee
from .competency_models import Skill

logger = logging.getLogger(__name__)


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
    
    @action(detail=False, methods=['get'])
    def by_percentage(self, request):
        """Get rating by percentage"""
        percentage = request.query_params.get('percentage')
        if not percentage:
            return Response({
                'error': 'percentage parameter required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            pct = float(percentage)
            rating = EvaluationScale.get_rating_by_percentage(pct)
            if rating:
                return Response(EvaluationScaleSerializer(rating).data)
            return Response({
                'error': 'No rating found for this percentage'
            }, status=status.HTTP_404_NOT_FOUND)
        except ValueError:
            return Response({
                'error': 'Invalid percentage value'
            }, status=status.HTTP_400_BAD_REQUEST)


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


class EmployeePerformanceViewSet(viewsets.ModelViewSet):
    """Employee Performance Management"""
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'list':
            return EmployeePerformanceListSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return EmployeePerformanceCreateUpdateSerializer
        return EmployeePerformanceDetailSerializer
    
    def get_queryset(self):
        queryset = EmployeePerformance.objects.select_related(
            'employee', 'employee__department', 'employee__line_manager',
            'performance_year', 'created_by'
        ).prefetch_related(
            'objectives', 'competency_ratings', 'development_needs', 'comments'
        )
        
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
    
    @action(detail=False, methods=['post'])
    def initialize(self, request):
        """Initialize performance record with competencies"""
        serializer = PerformanceInitializeSerializer(
            data=request.data,
            context={'request': request}
        )
        if serializer.is_valid():
            performance = serializer.save()
            detail_serializer = EmployeePerformanceDetailSerializer(performance)
            return Response(detail_serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    # ============ OBJECTIVES SECTION ============
    
    @action(detail=True, methods=['post'])
    def save_objectives_draft(self, request, pk=None):
        """Save objectives as draft"""
        performance = self.get_object()
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
                action='OBJECTIVES_DRAFT_SAVED',
                description='Objectives saved as draft',
                performed_by=request.user
            )
        
        return Response({
            'success': True,
            'message': 'Objectives draft saved'
        })
    
    @action(detail=True, methods=['post'])
    def submit_objectives(self, request, pk=None):
        """Submit objectives for approval"""
        performance = self.get_object()
        
        # Check period
        current_period = performance.performance_year.get_current_period()
        if current_period not in ['GOAL_SETTING', 'MID_YEAR_REVIEW']:
            return Response({
                'error': 'Goal setting period is not active'
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
        
        # Update status
        performance.objectives_employee_submitted = True
        performance.objectives_employee_submitted_date = timezone.now()
        performance.approval_status = 'PENDING_MANAGER_APPROVAL'
        performance.save()
        
        PerformanceActivityLog.objects.create(
            performance=performance,
            action='OBJECTIVES_SUBMITTED',
            description='Employee submitted objectives for manager approval',
            performed_by=request.user
        )
        
        return Response({
            'success': True,
            'message': 'Objectives submitted for manager approval'
        })
    
    @action(detail=True, methods=['post'])
    def approve_objectives_employee(self, request, pk=None):
        """Employee approves objectives"""
        performance = self.get_object()
        
        performance.objectives_employee_approved = True
        performance.objectives_employee_approved_date = timezone.now()
        
        if performance.objectives_manager_approved:
            performance.approval_status = 'APPROVED'
        
        performance.save()
        
        PerformanceActivityLog.objects.create(
            performance=performance,
            action='OBJECTIVES_APPROVED_EMPLOYEE',
            description='Employee approved objectives',
            performed_by=request.user
        )
        
        return Response({'success': True, 'message': 'Objectives approved by employee'})
    
    @action(detail=True, methods=['post'])
    def approve_objectives_manager(self, request, pk=None):
        """Manager approves objectives"""
        performance = self.get_object()
        
        performance.objectives_manager_approved = True
        performance.objectives_manager_approved_date = timezone.now()
        
        if performance.objectives_employee_approved:
            performance.approval_status = 'APPROVED'
        else:
            performance.approval_status = 'PENDING_EMPLOYEE_APPROVAL'
        
        performance.save()
        
        PerformanceActivityLog.objects.create(
            performance=performance,
            action='OBJECTIVES_APPROVED_MANAGER',
            description='Manager approved objectives',
            performed_by=request.user
        )
        
        return Response({'success': True, 'message': 'Objectives approved by manager'})
    
    @action(detail=True, methods=['post'])
    def cancel_objective(self, request, pk=None):
        """Manager cancels an objective (mid-year only)"""
        performance = self.get_object()
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
    
    # ============ COMPETENCIES SECTION ============
    
    @action(detail=True, methods=['post'])
    def save_competencies_draft(self, request, pk=None):
        """Save competencies as draft"""
        performance = self.get_object()
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
                description='Competencies saved as draft',
                performed_by=request.user
            )
        
        return Response({
            'success': True,
            'message': 'Competencies draft saved'
        })
    
    @action(detail=True, methods=['post'])
    def submit_competencies(self, request, pk=None):
        """Submit competencies"""
        performance = self.get_object()
        
        performance.competencies_submitted = True
        performance.competencies_submitted_date = timezone.now()
        performance.save()
        
        PerformanceActivityLog.objects.create(
            performance=performance,
            action='COMPETENCIES_SUBMITTED',
            description='Competencies submitted',
            performed_by=request.user
        )
        
        return Response({
            'success': True,
            'message': 'Competencies submitted'
        })
    
    # ============ MID-YEAR REVIEW SECTION ============
    
    @action(detail=True, methods=['post'])
    def save_mid_year_draft(self, request, pk=None):
        """Save mid-year review as draft"""
        performance = self.get_object()
        user_role = request.data.get('user_role', 'employee')  # 'employee' or 'manager'
        comment = request.data.get('comment', '')
        
        if user_role == 'employee':
            performance.mid_year_employee_comment = comment
            performance.mid_year_employee_draft_saved = timezone.now()
            log_msg = 'Employee saved mid-year review draft'
        else:
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
            performance.end_year_employee_comment = comment
            performance.end_year_employee_draft_saved = timezone.now()
            log_msg = 'Employee saved end-year review draft'
        else:
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
        """Manager completes end-year review and finalizes scores"""
        performance = self.get_object()
        
        # Validate all objectives have ratings
        objectives_without_rating = performance.objectives.filter(
            is_cancelled=False,
            end_year_rating__isnull=True
        ).count()
        
        if objectives_without_rating > 0:
            return Response({
                'error': f'{objectives_without_rating} objectives missing end-year ratings'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate all competencies have ratings
        competencies_without_rating = performance.competency_ratings.filter(
            end_year_rating__isnull=True
        ).count()
        
        if competencies_without_rating > 0:
            return Response({
                'error': f'{competencies_without_rating} competencies missing end-year ratings'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get manager comment
        comment = request.data.get('comment', '')
        if comment:
            performance.end_year_manager_comment = comment
        
        # Calculate final scores
        performance.calculate_scores()
        
        # Auto-create development needs
        self._create_development_needs(performance)
        
        # Update status
        performance.end_year_manager_submitted = timezone.now()
        performance.end_year_completed = True
        performance.approval_status = 'PENDING_EMPLOYEE_APPROVAL'
        performance.save()
        
        PerformanceActivityLog.objects.create(
            performance=performance,
            action='END_YEAR_COMPLETED',
            description='Manager completed end-year review and scores calculated',
            performed_by=request.user,
            metadata={
                'final_rating': performance.final_rating,
                'overall_percentage': str(performance.overall_weighted_percentage)
            }
        )
        
        return Response({
            'success': True,
            'message': 'End-year review completed',
            'final_scores': {
                'objectives_score': str(performance.total_objectives_score),
                'objectives_percentage': str(performance.objectives_percentage),
                'competencies_score': str(performance.total_competencies_score),
                'competencies_percentage': str(performance.competencies_percentage),
                'overall_percentage': str(performance.overall_weighted_percentage),
                'final_rating': performance.final_rating
            }
        })
    
    def _create_development_needs(self, performance):
        """Create development needs for E-- and E- rated competencies"""
        low_ratings = performance.competency_ratings.filter(
            end_year_rating__name__in=['E--', 'E-']
        )
        
        for rating in low_ratings:
            existing = performance.development_needs.filter(
                competency_gap=rating.competency.name
            ).first()
            
            if not existing:
                DevelopmentNeed.objects.create(
                    performance=performance,
                    competency_gap=rating.competency.name,
                    development_activity='',
                    progress=0
                )
    
    # ============ DEVELOPMENT NEEDS SECTION ============
    
    @action(detail=True, methods=['post'])
    def save_development_needs_draft(self, request, pk=None):
        """Save development needs as draft"""
        performance = self.get_object()
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
    
    # ============ CLARIFICATION & APPROVAL ============
    
    @action(detail=True, methods=['post'])
    def request_clarification(self, request, pk=None):
        """Request clarification"""
        performance = self.get_object()
        comment_text = request.data.get('comment')
        comment_type = request.data.get('comment_type', 'OBJECTIVE_CLARIFICATION')
        
        if not comment_text:
            return Response({
                'error': 'Comment text required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        comment = PerformanceComment.objects.create(
            performance=performance,
            comment_type=comment_type,
            content=comment_text,
            created_by=request.user
        )
        
        performance.approval_status = 'NEED_CLARIFICATION'
        performance.save()
        
        PerformanceActivityLog.objects.create(
            performance=performance,
            action='CLARIFICATION_REQUESTED',
            description=f'Clarification requested: {comment_type}',
            performed_by=request.user,
            metadata={'comment_id': comment.id}
        )
        
        return Response({
            'success': True,
            'message': 'Clarification requested',
            'comment': PerformanceCommentSerializer(comment).data
        })
    
    @action(detail=True, methods=['post'])
    def approve_final_employee(self, request, pk=None):
        """Employee approves final performance results"""
        performance = self.get_object()
        
        if not performance.end_year_completed:
            return Response({
                'error': 'End-year review not completed yet'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        performance.final_employee_approved = True
        performance.final_employee_approval_date = timezone.now()
        
        if performance.final_manager_approved:
            performance.approval_status = 'COMPLETED'
        else:
            performance.approval_status = 'PENDING_MANAGER_APPROVAL'
        
        performance.save()
        
        PerformanceActivityLog.objects.create(
            performance=performance,
            action='FINAL_APPROVED_EMPLOYEE',
            description='Employee approved final performance results',
            performed_by=request.user
        )
        
        return Response({'success': True, 'message': 'Final performance approved by employee'})
    
    @action(detail=True, methods=['post'])
    def approve_final_manager(self, request, pk=None):
        """Manager final approval"""
        performance = self.get_object()
        
        if not performance.end_year_completed:
            return Response({
                'error': 'End-year review not completed yet'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        performance.final_manager_approved = True
        performance.final_manager_approval_date = timezone.now()
        performance.approval_status = 'COMPLETED'
        performance.save()
        
        PerformanceActivityLog.objects.create(
            performance=performance,
            action='FINAL_APPROVED_MANAGER',
            description='Manager approved and published final performance results',
            performed_by=request.user
        )
        
        return Response({
            'success': True,
            'message': 'Final performance approved and published'
        })
    
    # ============ UTILITIES ============
    
    @action(detail=True, methods=['post'])
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
                'competencies_score': str(performance.total_competencies_score),
                'competencies_percentage': str(performance.competencies_percentage),
                'overall_percentage': str(performance.overall_weighted_percentage),
                'final_rating': performance.final_rating
            }
        })
    
    @action(detail=True, methods=['get'])
    def activity_log(self, request, pk=None):
        """Get performance activity log"""
        performance = self.get_object()
        logs = performance.activity_logs.all()
        serializer = PerformanceActivityLogSerializer(logs, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def export_excel(self, request, pk=None):
        """Export performance to Excel"""
        performance = self.get_object()
        
        try:
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Performance Report"
            
            # Styles
            header_font = Font(bold=True, size=14, color="FFFFFF")
            header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
            section_font = Font(bold=True, size=12)
            border = Border(
                left=Side(style='thin'), right=Side(style='thin'),
                top=Side(style='thin'), bottom=Side(style='thin')
            )
            
            # Header
            ws['A1'] = f"PERFORMANCE REVIEW - {performance.performance_year.year}"
            ws['A1'].font = header_font
            ws['A1'].fill = header_fill
            ws.merge_cells('A1:F1')
            ws['A1'].alignment = Alignment(horizontal='center')
            
            # Employee Info
            row = 3
            info_data = [
                ("Employee ID:", performance.employee.employee_id),
                ("Name:", performance.employee.full_name),
                ("Job Title:", performance.employee.job_title),
                ("Department:", performance.employee.department.name),
                ("Manager:", performance.employee.line_manager.full_name if performance.employee.line_manager else "N/A"),
                ("Status:", performance.get_approval_status_display()),
            ]
            
            for label, value in info_data:
                ws[f'A{row}'] = label
                ws[f'A{row}'].font = Font(bold=True)
                ws[f'B{row}'] = value
                row += 1
            
            # Objectives
            row += 2
            ws[f'A{row}'] = "OBJECTIVES"
            ws[f'A{row}'].font = section_font
            ws.merge_cells(f'A{row}:F{row}')
            row += 1
            
            obj_headers = ['Title', 'Weight %', 'Progress %', 'Status', 'Rating', 'Score']
            for col, header in enumerate(obj_headers, start=1):
                cell = ws.cell(row=row, column=col, value=header)
                cell.font = Font(bold=True)
                cell.border = border
            row += 1
            
            for obj in performance.objectives.filter(is_cancelled=False):
                ws.cell(row=row, column=1, value=obj.title).border = border
                ws.cell(row=row, column=2, value=obj.weight).border = border
                ws.cell(row=row, column=3, value=obj.progress).border = border
                ws.cell(row=row, column=4, value=obj.status.label).border = border
                ws.cell(row=row, column=5, value=obj.end_year_rating.name if obj.end_year_rating else 'N/A').border = border
                ws.cell(row=row, column=6, value=str(obj.calculated_score)).border = border
                row += 1
            
            row += 1
            ws[f'A{row}'] = "Objectives Total Score:"
            ws[f'A{row}'].font = Font(bold=True)
            ws[f'B{row}'] = f"{performance.total_objectives_score} / {EvaluationTargetConfig.get_active_config().objective_score_target}"
            ws[f'C{row}'] = f"{performance.objectives_percentage}%"
            
            # Competencies
            row += 3
            ws[f'A{row}'] = "CORE COMPETENCIES"
            ws[f'A{row}'].font = section_font
            ws.merge_cells(f'A{row}:E{row}')
            row += 1
            
            comp_headers = ['Group', 'Competency', 'Rating', 'Score', 'Notes']
            for col, header in enumerate(comp_headers, start=1):
                cell = ws.cell(row=row, column=col, value=header)
                cell.font = Font(bold=True)
                cell.border = border
            row += 1
            
            for comp in performance.competency_ratings.all():
                ws.cell(row=row, column=1, value=comp.competency.group.name).border = border
                ws.cell(row=row, column=2, value=comp.competency.name).border = border
                ws.cell(row=row, column=3, value=comp.end_year_rating.name if comp.end_year_rating else 'N/A').border = border
                ws.cell(row=row, column=4, value=comp.end_year_rating.value if comp.end_year_rating else 0).border = border
                ws.cell(row=row, column=5, value=comp.notes).border = border
                row += 1
            
            row += 1
            ws[f'A{row}'] = "Competencies Total Score:"
            ws[f'A{row}'].font = Font(bold=True)
            ws[f'B{row}'] = f"{performance.total_competencies_score} / {EvaluationTargetConfig.get_active_config().competency_score_target}"
            ws[f'C{row}'] = f"{performance.competencies_percentage}%"
            
            # Final Scores
            row += 3
            ws[f'A{row}'] = "FINAL PERFORMANCE SUMMARY"
            ws[f'A{row}'].font = section_font
            ws.merge_cells(f'A{row}:D{row}')
            row += 1
            
            weight_config = PerformanceWeightConfig.objects.filter(
                position_group=performance.employee.position_group
            ).first()
            
            final_data = [
                ("Objectives Score:", f"{performance.objectives_percentage}%", f"Weight: {weight_config.objectives_weight if weight_config else 70}%"),
                ("Competencies Score:", f"{performance.competencies_percentage}%", f"Weight: {weight_config.competencies_weight if weight_config else 30}%"),
                ("Overall Weighted Score:", f"{performance.overall_weighted_percentage}%", ""),
                ("Final Rating:", performance.final_rating, ""),
            ]
            
            for label, value, extra in final_data:
                ws[f'A{row}'] = label
                ws[f'A{row}'].font = Font(bold=True)
                ws[f'B{row}'] = value
                ws[f'C{row}'] = extra
                row += 1
            
            # Auto-adjust column widths
            for column in ws.columns:
                max_length = 0
                column = [cell for cell in column]
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(cell.value)
                    except:
                        pass
                adjusted_width = min(max_length + 2, 50)
                ws.column_dimensions[column[0].column_letter].width = adjusted_width
            
            # Save to BytesIO
            output = io.BytesIO()
            wb.save(output)
            output.seek(0)
            
            response = HttpResponse(
                output.getvalue(),
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            filename = f"performance_{performance.employee.employee_id}_{performance.performance_year.year}.xlsx"
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            
            return response
            
        except Exception as e:
            logger.error(f"Error exporting performance: {str(e)}")
            return Response({
                'error': f'Failed to export: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PerformanceDashboardViewSet(viewsets.ViewSet):
    """Performance Dashboard Statistics"""
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get dashboard statistics"""
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
        
        performances = EmployeePerformance.objects.filter(performance_year=perf_year)
        
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
        
        # By department
        by_department = []
        departments = Employee.objects.values_list('department__name', flat=True).distinct()
        for dept_name in departments:
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
        
        # Recent activities
        recent_logs = PerformanceActivityLog.objects.filter(
            performance__performance_year=perf_year
        ).select_related('performance__employee').order_by('-created_at')[:10]
        
        recent_activities = PerformanceActivityLogSerializer(recent_logs, many=True).data
        
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
            'recent_activities': recent_activities
        })


class PerformanceNotificationTemplateViewSet(viewsets.ModelViewSet):
    """Performance Notification Templates"""
    queryset = PerformanceNotificationTemplate.objects.all()
    serializer_class = PerformanceNotificationTemplateSerializer
    permission_classes = [IsAuthenticated]