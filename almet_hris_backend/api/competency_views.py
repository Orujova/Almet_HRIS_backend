# api/competency_views.py

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q, Count
from django.db import transaction

from .competency_models import (
    SkillGroup, Skill, BehavioralCompetencyGroup, 
    BehavioralCompetency
)
from .competency_serializers import (
    SkillGroupSerializer, SkillGroupListSerializer, SkillSerializer, SkillCreateSerializer,
    BehavioralCompetencyGroupSerializer, BehavioralCompetencyGroupListSerializer,
    BehavioralCompetencySerializer, BehavioralCompetencyCreateSerializer,
    CompetencyStatsSerializer
)

class SkillGroupViewSet(viewsets.ModelViewSet):
    queryset = SkillGroup.objects.all()
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'list':
            return SkillGroupListSerializer
        return SkillGroupSerializer
    
    def get_queryset(self):
        queryset = SkillGroup.objects.all()
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) 
            )
        return queryset.order_by('name')
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    @action(detail=True, methods=['get'])
    def skills(self, request, pk=None):
        """Qrup üçün skills siyahısı"""
        group = self.get_object()
        skills = group.skills.all()
        
        search = request.query_params.get('search', None)
        if search:
            skills = skills.filter(name__icontains=search)
            
        serializer = SkillSerializer(skills, many=True)
        return Response(serializer.data)

class SkillViewSet(viewsets.ModelViewSet):
    queryset = Skill.objects.select_related('group').all()
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return SkillCreateSerializer
        return SkillSerializer
    
    def get_queryset(self):
        queryset = Skill.objects.select_related('group').all()
        
        # Filter by group
        group_id = self.request.query_params.get('group', None)
        if group_id:
            queryset = queryset.filter(group_id=group_id)
        
        # Search
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | 
                
                Q(group__name__icontains=search)
            )
        
        return queryset.order_by('group__name', 'name')
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
   
class BehavioralCompetencyGroupViewSet(viewsets.ModelViewSet):
    queryset = BehavioralCompetencyGroup.objects.all()
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'list':
            return BehavioralCompetencyGroupListSerializer
        return BehavioralCompetencyGroupSerializer
    
    def get_queryset(self):
        queryset = BehavioralCompetencyGroup.objects.all()
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) 
            )
        return queryset.order_by('name')
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    @action(detail=True, methods=['get'])
    def competencies(self, request, pk=None):
        """Qrup üçün competencies siyahısı"""
        group = self.get_object()
        competencies = group.competencies.all()
        
        search = request.query_params.get('search', None)
        if search:
            competencies = competencies.filter(name__icontains=search)
            
        serializer = BehavioralCompetencySerializer(competencies, many=True)
        return Response(serializer.data)

class BehavioralCompetencyViewSet(viewsets.ModelViewSet):
    queryset = BehavioralCompetency.objects.select_related('group').all()
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return BehavioralCompetencyCreateSerializer
        return BehavioralCompetencySerializer
    
    def get_queryset(self):
        queryset = BehavioralCompetency.objects.select_related('group').all()
        
        # Filter by group
        group_id = self.request.query_params.get('group', None)
        if group_id:
            queryset = queryset.filter(group_id=group_id)
        
        # Search
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | 
                
                Q(group__name__icontains=search)
            )
        
        return queryset.order_by('group__name', 'name')
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    
from rest_framework.views import APIView

class CompetencyStatsView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        stats = {
            'total_skill_groups': SkillGroup.objects.count(),
            'total_skills': Skill.objects.count(),
            'total_behavioral_groups': BehavioralCompetencyGroup.objects.count(),
            'total_behavioral_competencies': BehavioralCompetency.objects.count(),
   
        }
        
        serializer = CompetencyStatsSerializer(stats)
        return Response(serializer.data)