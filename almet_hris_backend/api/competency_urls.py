# api/competency_urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .competency_views import (
    SkillGroupViewSet, SkillViewSet,
    BehavioralCompetencyGroupViewSet, BehavioralCompetencyViewSet,
    CompetencyStatsView
)

router = DefaultRouter()
router.register(r'skill-groups', SkillGroupViewSet)
router.register(r'skills', SkillViewSet)
router.register(r'behavioral-groups', BehavioralCompetencyGroupViewSet)
router.register(r'behavioral-competencies', BehavioralCompetencyViewSet)


urlpatterns = [
    path('', include(router.urls)),
    path('stats/', CompetencyStatsView.as_view(), name='competency-stats'),
]