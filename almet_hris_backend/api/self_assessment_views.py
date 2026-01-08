# api/self_assessment_views.py - Core Skills Assessment Views

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from django.db.models import Q, Avg, Count
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from .self_assessment_models import (
    AssessmentPeriod, SelfAssessment, SkillRating, AssessmentActivity
)
from .self_assessment_serializers import (
    AssessmentPeriodSerializer, AssessmentPeriodCreateSerializer,
    SelfAssessmentDetailSerializer, SelfAssessmentListSerializer,
    SelfAssessmentCreateSerializer,
    SkillRatingSerializer, SkillRatingCreateUpdateSerializer,
    AssessmentActivitySerializer, AssessmentStatsSerializer
)
from .models import Employee


class AssessmentPeriodViewSet(viewsets.ModelViewSet):
    """Assessment Period Management"""
    queryset = AssessmentPeriod.objects.all()
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return AssessmentPeriodCreateSerializer
        return AssessmentPeriodSerializer
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    @action(detail=False, methods=['get'])
    def active(self, request):
        """Get active assessment period"""
        active_period = AssessmentPeriod.get_active_period()
        if active_period:
            serializer = self.get_serializer(active_period)
            return Response(serializer.data)
        return Response(
            {'detail': 'No active assessment period'}, 
            status=status.HTTP_404_NOT_FOUND
        )
    
    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Activate this period"""
        period = self.get_object()
        period.is_active = True
        period.status = 'ACTIVE'
        period.save()
        serializer = self.get_serializer(period)
        return Response(serializer.data)


class SelfAssessmentViewSet(viewsets.ModelViewSet):
    """Self Assessment CRUD"""
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return SelfAssessmentCreateSerializer
        elif self.action == 'list':
            return SelfAssessmentListSerializer
        return SelfAssessmentDetailSerializer
    
    def get_queryset(self):
        user = self.request.user
        
        try:
            employee = Employee.objects.get(user=user)
        except Employee.DoesNotExist:
            return SelfAssessment.objects.none()
        
        # Admin görür hamısını
        if user.is_staff or user.is_superuser:
            return SelfAssessment.objects.select_related(
                'employee', 'period'
            ).prefetch_related('skill_ratings__skill__group').all()
        
        # Manager görür özünkünü və team-in
        if employee.direct_reports.exists():
            team_ids = list(employee.direct_reports.values_list('id', flat=True))
            team_ids.append(employee.id)
            
            queryset = SelfAssessment.objects.filter(employee_id__in=team_ids)
        else:
            # Employee yalnız özünkünü görür
            queryset = SelfAssessment.objects.filter(employee=employee)
        
        return queryset.select_related('employee', 'period').prefetch_related(
            'skill_ratings__skill__group'
        )
    
    def perform_create(self, serializer):
        try:
            employee = Employee.objects.get(user=self.request.user)
        except Employee.DoesNotExist:
            raise serializers.ValidationError('Employee profile not found')
        
        assessment = serializer.save(employee=employee)
        
        # Log activity
        AssessmentActivity.objects.create(
            assessment=assessment,
            activity_type='CREATED',
            description=f'Assessment created for period {assessment.period.name}',
            performed_by=self.request.user
        )
    
    @action(detail=False, methods=['get'])
    def my_assessments(self, request):
        """Get current user's assessments"""
        try:
            employee = Employee.objects.get(user=request.user)
        except Employee.DoesNotExist:
            return Response(
                {'detail': 'Employee profile not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        assessments = SelfAssessment.objects.filter(
            employee=employee
        ).select_related('period').order_by('-created_at')
        
        serializer = SelfAssessmentListSerializer(assessments, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def team_assessments(self, request):
        """Get assessments of direct reports (Manager view)"""
        try:
            employee = Employee.objects.get(user=request.user)
        except Employee.DoesNotExist:
            return Response(
                {'detail': 'Employee profile not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check if user is manager
        if not employee.direct_reports.exists():
            return Response(
                {'detail': 'No direct reports found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        team_ids = list(employee.direct_reports.values_list('id', flat=True))
        
        assessments = SelfAssessment.objects.filter(
            employee_id__in=team_ids
        ).select_related('employee', 'period').order_by('-created_at')
        
        serializer = SelfAssessmentListSerializer(assessments, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def start_assessment(self, request):
        """Start new assessment for active period"""
        try:
            employee = Employee.objects.get(user=request.user)
        except Employee.DoesNotExist:
            return Response(
                {'detail': 'Employee profile not found'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get active period
        period = AssessmentPeriod.get_active_period()
        if not period:
            return Response(
                {'detail': 'No active assessment period'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if already exists
        existing = SelfAssessment.objects.filter(
            employee=employee,
            period=period
        ).first()
        
        if existing:
            serializer = SelfAssessmentDetailSerializer(
                existing, 
                context={'request': request}
            )
            return Response(serializer.data)
        
        # Create new assessment
        assessment = SelfAssessment.objects.create(
            employee=employee,
            period=period,
            status='DRAFT'
        )
        
        # Log activity
        AssessmentActivity.objects.create(
            assessment=assessment,
            activity_type='CREATED',
            description=f'Assessment started for period {period.name}',
            performed_by=request.user
        )
        
        serializer = SelfAssessmentDetailSerializer(
            assessment, 
            context={'request': request}
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """Submit assessment"""
        assessment = self.get_object()
        
        # Check permission
        if assessment.employee.user != request.user:
            return Response(
                {'detail': 'Permission denied'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        if assessment.status != 'DRAFT':
            return Response(
                {'detail': 'Assessment already submitted'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if has ratings
        if not assessment.skill_ratings.exists():
            return Response(
                {'detail': 'Please add skill ratings before submitting'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Submit
        assessment.submit()
        
        serializer = self.get_serializer(assessment)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def manager_review(self, request, pk=None):
        """Manager reviews assessment"""
        assessment = self.get_object()
        
        # Check if user is manager
        try:
            employee = Employee.objects.get(user=request.user)
        except Employee.DoesNotExist:
            return Response(
                {'detail': 'Employee profile not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        if assessment.employee.line_manager != employee and not request.user.is_staff:
            return Response(
                {'detail': 'Permission denied'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Update manager comments
        manager_comments = request.data.get('manager_comments', '')
        
        with transaction.atomic():
            assessment.status = 'REVIEWED'
            assessment.manager_comments = manager_comments
            assessment.manager_reviewed_by = request.user
            assessment.manager_reviewed_at = timezone.now()
            assessment.save()
            
            # Update individual rating comments if provided
            rating_comments = request.data.get('rating_comments', [])
            for comment_data in rating_comments:
                rating_id = comment_data.get('rating_id')
                manager_comment = comment_data.get('manager_comment', '')
                
                SkillRating.objects.filter(
                    id=rating_id, 
                    assessment=assessment
                ).update(manager_comment=manager_comment)
            
            # Log activity
            AssessmentActivity.objects.create(
                assessment=assessment,
                activity_type='REVIEWED',
                description='Assessment reviewed by manager',
                performed_by=request.user
            )
        
        serializer = self.get_serializer(assessment)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def activities(self, request, pk=None):
        """Get assessment activities"""
        assessment = self.get_object()
        activities = assessment.activities.all()
        serializer = AssessmentActivitySerializer(activities, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def add_rating(self, request, pk=None):
        """Add or update a skill rating"""
        assessment = self.get_object()
        
        # Check permission
        if assessment.employee.user != request.user:
            return Response(
                {'detail': 'Permission denied'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        if assessment.status != 'DRAFT':
            return Response(
                {'detail': 'Cannot modify submitted assessment'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = SkillRatingCreateUpdateSerializer(data=request.data)
        if serializer.is_valid():
            # Update or create rating
            skill_rating, created = SkillRating.objects.update_or_create(
                assessment=assessment,
                skill=serializer.validated_data['skill'],
                defaults={
                    'rating': serializer.validated_data['rating'],
                    'self_comment': serializer.validated_data.get('self_comment', '')
                }
            )
            
            # Recalculate overall score
            assessment.calculate_overall_score()
            
            # Log activity
            action_text = 'added' if created else 'updated'
            AssessmentActivity.objects.create(
                assessment=assessment,
                activity_type='RATING_CHANGED',
                description=f'Skill rating {action_text}: {skill_rating.skill.name}',
                performed_by=request.user,
                metadata={'skill_id': skill_rating.skill.id, 'rating': skill_rating.rating}
            )
            
            response_serializer = SkillRatingSerializer(skill_rating)
            return Response(response_serializer.data)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def bulk_add_ratings(self, request, pk=None):
        """Bulk add/update skill ratings"""
        assessment = self.get_object()
        
        # Check permission
        if assessment.employee.user != request.user:
            return Response(
                {'detail': 'Permission denied'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        if assessment.status != 'DRAFT':
            return Response(
                {'detail': 'Cannot modify submitted assessment'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        ratings_data = request.data.get('ratings', [])
        
        with transaction.atomic():
            for rating_data in ratings_data:
                SkillRating.objects.update_or_create(
                    assessment=assessment,
                    skill_id=rating_data['skill'],
                    defaults={
                        'rating': rating_data['rating'],
                        'self_comment': rating_data.get('self_comment', '')
                    }
                )
            
            # Recalculate overall score
            assessment.calculate_overall_score()
            
            # Log activity
            AssessmentActivity.objects.create(
                assessment=assessment,
                activity_type='UPDATED',
                description=f'Bulk updated {len(ratings_data)} skill ratings',
                performed_by=request.user
            )
        
        serializer = self.get_serializer(assessment)
        return Response(serializer.data)


# Statistics View
class AssessmentStatsView(APIView):
    """Assessment statistics for current user"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        try:
            employee = Employee.objects.get(user=request.user)
        except Employee.DoesNotExist:
            return Response(
                {'detail': 'Employee profile not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get active period
        active_period = AssessmentPeriod.get_active_period()
        
        # My assessments
        my_assessments = SelfAssessment.objects.filter(employee=employee)
        my_assessments_count = my_assessments.count()
        
        # My average score
        my_avg_data = my_assessments.filter(
            overall_score__isnull=False
        ).aggregate(avg_score=Avg('overall_score'))
        my_average = float(my_avg_data['avg_score'] or 0)
        
        # My last assessment
        my_last = my_assessments.first()
        
        # Team data (if manager)
        team_assessments_count = 0
        pending_reviews = 0
        team_average = 0
        
        if employee.direct_reports.exists():
            team_ids = list(employee.direct_reports.values_list('id', flat=True))
            
            team_assessments = SelfAssessment.objects.filter(employee_id__in=team_ids)
            team_assessments_count = team_assessments.count()
            
            pending_reviews = team_assessments.filter(status='SUBMITTED').count()
            
            # Team average score
            team_avg_data = team_assessments.filter(
                overall_score__isnull=False
            ).aggregate(avg_score=Avg('overall_score'))
            team_average = float(team_avg_data['avg_score'] or 0)
        
        stats = {
            'total_periods': AssessmentPeriod.objects.count(),
            'active_period': active_period,
            'my_assessments_count': my_assessments_count,
            'team_assessments_count': team_assessments_count,
            'pending_reviews': pending_reviews,
            'my_average_score': round(my_average, 2),
            'team_average_score': round(team_average, 2),
            'my_last_assessment': my_last
        }
        
        serializer = AssessmentStatsSerializer(stats)
        return Response(serializer.data)