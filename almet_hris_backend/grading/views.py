# grading/views.py - SIMPLIFIED: Removed unnecessary complexity, fixed API issues

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from django.db import transaction
from django.utils import timezone
from django.conf import settings
from decimal import Decimal
import logging
import traceback
import json

from .models import GradingSystem, SalaryGrade, SalaryScenario, ScenarioHistory
from .serializers import (
    GradingSystemSerializer, SalaryGradeSerializer, CurrentStructureSerializer,
    SalaryScenarioListSerializer, SalaryScenarioDetailSerializer,
    SalaryScenarioCreateSerializer, DynamicCalculationRequestSerializer,
    DynamicCalculationResponseSerializer, ScenarioSaveRequestSerializer,
    ScenarioHistorySerializer
)
from .managers import SalaryCalculationManager
from api.views import StandardResultsSetPagination
from api.models import PositionGroup

logger = logging.getLogger(__name__)

class GradingSystemViewSet(viewsets.ModelViewSet):
    queryset = GradingSystem.objects.all()
    serializer_class = GradingSystemSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description']
    filterset_fields = ['is_active']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']

    @action(detail=False, methods=['get'])
    def current_structure(self, request):
        """Get current grade structure from database - SIMPLIFIED"""
        try:
            # Create current structure from database
            current_data = SalaryCalculationManager.create_current_structure_from_db()
            
            if current_data is None:
                return Response({
                    'error': 'No position groups found in database',
                    'message': 'Please configure position groups in the admin panel first'
                }, status=status.HTTP_404_NOT_FOUND)
            
            serializer = CurrentStructureSerializer(current_data)
            return Response(serializer.data)
            
        except Exception as e:
            logger.error(f"Error getting current structure: {str(e)}")
            return Response({
                'error': 'Failed to get current structure',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def position_groups(self, request):
        """Get position groups from database for frontend"""
        try:
            position_groups = SalaryCalculationManager.get_position_groups_from_db()
            
            if not position_groups.exists():
                return Response({
                    'error': 'No position groups found in database',
                    'position_groups': []
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Format for frontend
            formatted_positions = []
            for pos in position_groups:
                formatted_positions.append({
                    'id': pos.id,
                    'name': pos.name,
                    'display_name': pos.get_name_display(),
                    'hierarchy_level': pos.hierarchy_level,
                    'is_active': pos.is_active
                })
            
            return Response({
                'position_groups': formatted_positions,
                'count': len(formatted_positions)
            })
            
        except Exception as e:
            logger.error(f"Error getting position groups: {str(e)}")
            return Response({
                'error': 'Failed to get position groups',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class SalaryGradeViewSet(viewsets.ModelViewSet):
    serializer_class = SalaryGradeSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['grading_system']
    ordering = ['position_group__hierarchy_level']
    
    def get_queryset(self):
        return SalaryGrade.objects.select_related('grading_system', 'position_group')

class SalaryScenarioViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description']
    filterset_fields = ['status']  # FIXED: Removed grading_system filter that was causing 400 errors
    ordering_fields = ['name', 'created_at']
    ordering = ['-created_at']
    
    def get_queryset(self):
        return SalaryScenario.objects.select_related(
            'grading_system', 'created_by', 'applied_by'
        )
    
    def get_serializer_class(self):
        if self.action == 'list':
            return SalaryScenarioListSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return SalaryScenarioCreateSerializer
        else:
            return SalaryScenarioDetailSerializer

    @action(detail=False, methods=['post'], url_path='calculate_dynamic')
    def calculate_dynamic(self, request):
        """SIMPLIFIED: Calculate scenario dynamically"""
        try:
            logger.info("=== CALCULATE DYNAMIC START ===")
            
            # Extract and validate request data
            base_value = request.data.get('baseValue1')
            input_rates = request.data.get('grades', {})
            
            # Enhanced validation
            if not base_value or float(base_value) <= 0:
                return Response({
                    'errors': ['Base value must be greater than 0'],
                    'success': False
                }, status=status.HTTP_400_BAD_REQUEST)
            
            if not input_rates:
                return Response({
                    'errors': ['Grade input rates are required'],
                    'success': False
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get position groups from database
            position_groups = SalaryCalculationManager.get_position_groups_from_db()
            
            if not position_groups.exists():
                return Response({
                    'errors': ['No position groups found in database'],
                    'success': False
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Validate inputs
            validation_errors = SalaryCalculationManager.validate_scenario_inputs(float(base_value), input_rates)
            if validation_errors:
                return Response({
                    'errors': validation_errors,
                    'success': False
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Calculate grades
            calculated_grades = SalaryCalculationManager.calculate_scenario_grades(
                float(base_value), input_rates, position_groups
            )
            
            # Format output for frontend
            calculated_outputs = {}
            for position_name, grades in calculated_grades.items():
                if isinstance(grades, dict):
                    calculated_outputs[position_name] = {
                        'LD': grades.get('LD', 0) if grades.get('LD', 0) > 0 else "",
                        'LQ': grades.get('LQ', 0) if grades.get('LQ', 0) > 0 else "",
                        'M': grades.get('M', 0) if grades.get('M', 0) > 0 else "",
                        'UQ': grades.get('UQ', 0) if grades.get('UQ', 0) > 0 else "",
                        'UD': grades.get('UD', 0) if grades.get('UD', 0) > 0 else ""
                    }
            
            return Response({
                'calculatedOutputs': calculated_outputs,
                'success': True
            })
            
        except Exception as e:
            logger.error(f"Calculate dynamic error: {str(e)}")
            return Response({
                'errors': [f'Calculation error: {str(e)}'],
                'success': False
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'], url_path='save_draft')
    def save_draft(self, request):
        """SIMPLIFIED: Save scenario with clean data handling"""
        try:
            logger.info("=== SAVE DRAFT START ===")
            
            # Extract data
            name = request.data.get('name')
            description = request.data.get('description', '')
            base_value = request.data.get('baseValue1')
            grade_order = request.data.get('gradeOrder', [])
            input_rates = request.data.get('grades', {})
            global_horizontal_intervals = request.data.get('globalHorizontalIntervals', {})
            calculated_outputs = request.data.get('calculatedOutputs', {})
            
            # Simple validation
            if not name or not base_value or float(base_value) <= 0:
                return Response({
                    'success': False,
                    'error': 'Name and valid base value are required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get or create grading system
            grading_system, created = GradingSystem.objects.get_or_create(
                name="Default Grading System",
                defaults={
                    'description': "Default grading system",
                    'is_active': True,
                    'created_by': request.user
                }
            )
            
            # Format input rates with global intervals
            formatted_input_rates = {}
            for position_name in grade_order:
                position_input = input_rates.get(position_name, {})
                
                # Handle vertical
                vertical_value = position_input.get('vertical')
                if vertical_value in ['', None]:
                    vertical_value = None
                else:
                    try:
                        vertical_value = float(vertical_value)
                    except (ValueError, TypeError):
                        vertical_value = None
                
                # Apply global intervals
                clean_intervals = {}
                if global_horizontal_intervals:
                    for interval_key, interval_value in global_horizontal_intervals.items():
                        try:
                            clean_value = float(interval_value) if interval_value not in ['', None] else 0
                            clean_intervals[interval_key] = clean_value
                        except (ValueError, TypeError):
                            clean_intervals[interval_key] = 0
                
                formatted_input_rates[position_name] = {
                    'vertical': vertical_value,
                    'horizontal_intervals': clean_intervals
                }
            
            # Calculate averages
            vertical_sum = 0
            vertical_count = 0
            horizontal_sum = 0
            horizontal_count = 0
            
            # Vertical averages (exclude base position)
            for i, position_name in enumerate(grade_order):
                is_base_position = (i == len(grade_order) - 1)
                if is_base_position:
                    continue
                    
                position_data = formatted_input_rates.get(position_name, {})
                vertical_value = position_data.get('vertical')
                if vertical_value is not None and vertical_value != 0:
                    vertical_sum += vertical_value
                    vertical_count += 1
            
            # Horizontal averages from global intervals
            if global_horizontal_intervals:
                for interval_value in global_horizontal_intervals.values():
                    if interval_value not in ['', None, 0]:
                        try:
                            horizontal_sum += float(interval_value)
                            horizontal_count += 1
                        except (ValueError, TypeError):
                            pass
            
            vertical_avg = (vertical_sum / vertical_count / 100) if vertical_count > 0 else 0
            horizontal_avg = (horizontal_sum / horizontal_count / 100) if horizontal_count > 0 else 0
            
            # Create scenario
            with transaction.atomic():
                scenario = SalaryScenario.objects.create(
                    grading_system=grading_system,
                    name=name.strip(),
                    description=description,
                    base_value=Decimal(str(float(base_value))),
                    grade_order=grade_order,
                    input_rates=formatted_input_rates,
                    calculated_grades=calculated_outputs,
                    calculation_timestamp=timezone.now(),
                    vertical_avg=Decimal(str(vertical_avg)),
                    horizontal_avg=Decimal(str(horizontal_avg)),
                    created_by=request.user
                )
            
            # Format response
            scenario_serializer = SalaryScenarioDetailSerializer(scenario)
            
            return Response({
                'success': True,
                'message': 'Scenario saved successfully!',
                'scenario_id': str(scenario.id),
                'scenario': scenario_serializer.data
            })
            
        except Exception as e:
            logger.error(f"Save draft error: {str(e)}")
            return Response({
                'success': False,
                'error': f'Failed to save scenario: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def apply_as_current(self, request, pk=None):
        """Apply scenario as current"""
        try:
            scenario = self.get_object()
            
            if scenario.status != 'DRAFT':
                return Response({
                    'success': False,
                    'error': 'Only draft scenarios can be applied'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Apply scenario using manager
            with transaction.atomic():
                applied_scenario = SalaryCalculationManager.apply_scenario(scenario.id, request.user)
            
            return Response({
                'success': True,
                'message': 'Scenario applied successfully!',
                'scenario': SalaryScenarioDetailSerializer(applied_scenario).data
            })
            
        except Exception as e:
            logger.error(f"Error applying scenario: {str(e)}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def archive(self, request, pk=None):
        """Archive scenario"""
        try:
            scenario = self.get_object()
            
            if scenario.status == 'CURRENT':
                return Response({
                    'success': False,
                    'error': 'Cannot archive current scenario'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Archive scenario
            with transaction.atomic():
                scenario.status = 'ARCHIVED'
                scenario.save()
                
                # Create history record
                ScenarioHistory.objects.create(
                    scenario=scenario,
                    action='ARCHIVED',
                    performed_by=request.user,
                    changes_made={'archived_by': request.user.get_full_name()}
                )
            
            return Response({
                'success': True,
                'message': 'Scenario archived successfully'
            })
            
        except Exception as e:
            logger.error(f"Error archiving scenario: {str(e)}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def current_scenario(self, request):
        """Get current active scenario"""
        try:
            try:
                current_scenario = SalaryScenario.objects.get(status='CURRENT')
                serializer = SalaryScenarioDetailSerializer(current_scenario)
                return Response(serializer.data)
            except SalaryScenario.DoesNotExist:
                return Response({
                    'message': 'No current scenario found',
                    'current_scenario': None
                }, status=status.HTTP_404_NOT_FOUND)
                
        except Exception as e:
            logger.error(f"Error getting current scenario: {str(e)}")
            return Response({
                'error': 'Failed to get current scenario',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ScenarioHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ScenarioHistorySerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['scenario', 'action', 'performed_by']
    ordering = ['-timestamp']
    
    def get_queryset(self):
        return ScenarioHistory.objects.select_related(
            'scenario', 'performed_by', 'previous_current_scenario'
        )