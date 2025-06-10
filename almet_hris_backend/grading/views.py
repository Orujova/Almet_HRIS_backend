# grading/views.py

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from django.db import transaction
from django.utils import timezone
from decimal import Decimal

from .models import (
    GradingSystem, SalaryGrade, GrowthRate, HorizontalRate, 
    SalaryScenario, ScenarioHistory
)
from .serializers import (
    GradingSystemSerializer, GradingSystemCreateSerializer, SalaryGradeSerializer, 
    GrowthRateSerializer, HorizontalRateSerializer, SalaryScenarioListSerializer, 
    SalaryScenarioDetailSerializer, SalaryScenarioCreateUpdateSerializer,
    ScenarioHistorySerializer, GradingDropdownsSerializer, PositionGroupSimpleSerializer
)
from .managers import SalaryCalculationManager
from api.views import StandardResultsSetPagination
from api.models import PositionGroup

import logging

logger = logging.getLogger(__name__)

class GradingSystemViewSet(viewsets.ModelViewSet):
    queryset = GradingSystem.objects.all()
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description']
    filterset_fields = ['is_active']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']
    
    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return GradingSystemCreateSerializer
        return GradingSystemSerializer
    
    @action(detail=False, methods=['get'])
    def dropdowns(self, request):
        """Get dropdown data for grading system creation"""
        data = {
            'grading_systems': GradingSystem.objects.filter(is_active=True),
            'position_groups': PositionGroup.objects.filter(is_active=True).order_by('hierarchy_level'),
            'transition_types': [
                {'value': 'LD_TO_LQ', 'label': 'LD to LQ'},
                {'value': 'LQ_TO_M', 'label': 'LQ to Median'},
                {'value': 'M_TO_UQ', 'label': 'Median to UQ'},
                {'value': 'UQ_TO_UD', 'label': 'UQ to UD'},
            ]
        }
        serializer = GradingDropdownsSerializer(data)
        return Response(serializer.data)

class SalaryGradeViewSet(viewsets.ModelViewSet):
    serializer_class = SalaryGradeSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['grading_system', 'position_group']
    ordering_fields = ['position_group__hierarchy_level']
    ordering = ['position_group__hierarchy_level']
    
    def get_queryset(self):
        return SalaryGrade.objects.select_related('grading_system', 'position_group')
    
    @action(detail=False, methods=['get'])
    def by_system(self, request):
        """Get salary grades grouped by grading system"""
        grading_system_id = request.query_params.get('grading_system')
        if not grading_system_id:
            return Response({'error': 'grading_system parameter is required'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        queryset = self.get_queryset().filter(grading_system_id=grading_system_id)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

class GrowthRateViewSet(viewsets.ModelViewSet):
    serializer_class = GrowthRateSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['grading_system']
    ordering = ['from_position__hierarchy_level']
    
    def get_queryset(self):
        return GrowthRate.objects.select_related('grading_system', 'from_position', 'to_position')
    
    @action(detail=False, methods=['post'])
    def bulk_create(self, request):
        """Bulk create growth rates"""
        grading_system_id = request.data.get('grading_system')
        rates_data = request.data.get('rates', [])
        
        if not grading_system_id or not rates_data:
            return Response({'error': 'grading_system and rates are required'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        created_rates = []
        with transaction.atomic():
            for rate_data in rates_data:
                rate_data['grading_system'] = grading_system_id
                serializer = self.get_serializer(data=rate_data)
                if serializer.is_valid():
                    growth_rate = serializer.save()
                    created_rates.append(growth_rate)
                else:
                    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        response_serializer = self.get_serializer(created_rates, many=True)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

class HorizontalRateViewSet(viewsets.ModelViewSet):
    serializer_class = HorizontalRateSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['grading_system', 'position_group', 'transition_type']
    ordering = ['position_group__hierarchy_level', 'transition_type']
    
    def get_queryset(self):
        return HorizontalRate.objects.select_related('grading_system', 'position_group')
    
    @action(detail=False, methods=['post'])
    def bulk_create(self, request):
        """Bulk create horizontal rates"""
        grading_system_id = request.data.get('grading_system')
        rates_data = request.data.get('rates', [])
        
        if not grading_system_id or not rates_data:
            return Response({'error': 'grading_system and rates are required'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        created_rates = []
        with transaction.atomic():
            for rate_data in rates_data:
                rate_data['grading_system'] = grading_system_id
                serializer = self.get_serializer(data=rate_data)
                if serializer.is_valid():
                    horizontal_rate = serializer.save()
                    created_rates.append(horizontal_rate)
                else:
                    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        response_serializer = self.get_serializer(created_rates, many=True)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

class SalaryScenarioViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description']
    filterset_fields = ['status', 'grading_system']
    ordering_fields = ['name', 'created_at', 'applied_at']
    ordering = ['-created_at']
    
    def get_queryset(self):
        return SalaryScenario.objects.select_related(
            'grading_system', 'base_position', 'created_by', 'applied_by'
        )
    
    def get_serializer_class(self):
        if self.action == 'list':
            return SalaryScenarioListSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return SalaryScenarioCreateUpdateSerializer
        else:
            return SalaryScenarioDetailSerializer

    @action(detail=False, methods=['post'])
    def initialize_scenario(self, request):
        """Initialize scenario with base value and get empty rate structure"""
        base_value = request.data.get('base_value')
        
        # Default grading system - get the first active one or create if none exists
        try:
            grading_system = GradingSystem.objects.filter(is_active=True).first()
            if not grading_system:
                # Create default grading system if none exists
                grading_system = GradingSystem.objects.create(
                    name="Default Grading System",
                    description="Automatically created default grading system",
                    is_active=True,
                    created_by=request.user
                )
        except Exception as e:
            return Response({
                'success': False,
                'error': 'Could not find or create grading system'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        grading_system_id = grading_system.id
        
        if not base_value or float(base_value) <= 0:
            return Response({
                'success': False,
                'error': 'Valid base value is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            grading_system = GradingSystem.objects.get(id=grading_system_id)
        except GradingSystem.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Grading system not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Get all active positions ordered by hierarchy level (base position = highest number)
        positions = PositionGroup.objects.filter(is_active=True).order_by('hierarchy_level')
        base_position = positions.last()  # Highest hierarchy level (Blue Collar)
        
        # Create empty rate structure
        rate_structure = {
            'base_info': {
                'grading_system': grading_system_id,
                'base_position': base_position.id,
                'base_value': float(base_value)
            },
            'positions': [],
            'vertical_rates': {},
            'horizontal_rates': {}
        }
        
        # Build position structure with empty rates
        for position in positions:
            pos_data = {
                'id': position.id,
                'name': position.name,
                'display_name': position.get_name_display(),
                'hierarchy_level': position.hierarchy_level,
                'is_base': position.id == base_position.id
            }
            rate_structure['positions'].append(pos_data)
            
            # Initialize empty vertical rate (except for top position)
            if position.hierarchy_level > 1:
                rate_structure['vertical_rates'][str(position.id)] = None
            
            # Initialize empty horizontal rates for all positions
            rate_structure['horizontal_rates'][str(position.id)] = {
                'LD_TO_LQ': None,
                'LQ_TO_M': None,
                'M_TO_UQ': None,
                'UQ_TO_UD': None
            }
        
        return Response({
            'success': True,
            'data': rate_structure
        })

    @action(detail=False, methods=['post'])
    def calculate_dynamic(self, request):
        """Calculate scenario dynamically as rates are entered"""
        scenario_data = request.data
        
        try:
            # Extract data
            grading_system_id = scenario_data.get('grading_system')
            base_position_id = scenario_data.get('base_position')
            base_value = Decimal(str(scenario_data.get('base_value', 0)))
            vertical_rates = scenario_data.get('vertical_rates', {})
            horizontal_rates = scenario_data.get('horizontal_rates', {})
            
            # Validate basic data
            if not grading_system_id or not base_position_id or base_value <= 0:
                return Response({
                    'success': False,
                    'error': 'Invalid scenario data'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get positions
            positions = PositionGroup.objects.filter(is_active=True).order_by('hierarchy_level')
            base_position = PositionGroup.objects.get(id=base_position_id)
            
            # Filter out empty rates and convert to proper format
            clean_vertical_rates = {}
            for pos_id, rate in vertical_rates.items():
                if rate is not None and rate != '' and float(rate) >= 0:
                    clean_vertical_rates[int(pos_id)] = float(rate)
            
            clean_horizontal_rates = {}
            for pos_id, rates in horizontal_rates.items():
                pos_id_int = int(pos_id)
                clean_horizontal_rates[pos_id_int] = {}
                if isinstance(rates, dict):
                    for transition, rate in rates.items():
                        if rate is not None and rate != '' and float(rate) >= 0:
                            clean_horizontal_rates[pos_id_int][transition] = float(rate)
            
            # Calculate grades using the manager
            calculated_grades = SalaryCalculationManager.calculate_dynamic_grades(
                positions, base_position, base_value, 
                clean_vertical_rates, clean_horizontal_rates
            )
            
            # Calculate completion status
            completion_stats = self._get_completion_stats(
                positions, vertical_rates, horizontal_rates
            )
            
            return Response({
                'success': True,
                'calculated_grades': calculated_grades,
                'completion_stats': completion_stats
            })
            
        except Exception as e:
            logger.error(f"Error in dynamic calculation: {str(e)}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)

    def _get_completion_stats(self, positions, vertical_rates, horizontal_rates):
        """Get completion statistics for the scenario"""
        total_vertical_needed = len(positions) - 1  # All except top position
        total_horizontal_needed = len(positions) * 4  # 4 transitions per position
        
        completed_vertical = 0
        completed_horizontal = 0
        
        # Count completed vertical rates
        for pos in positions:
            if pos.hierarchy_level > 1:  # Not the top position
                if str(pos.id) in vertical_rates and vertical_rates[str(pos.id)] not in [None, '']:
                    completed_vertical += 1
        
        # Count completed horizontal rates
        for pos in positions:
            pos_rates = horizontal_rates.get(str(pos.id), {})
            if isinstance(pos_rates, dict):
                for transition in ['LD_TO_LQ', 'LQ_TO_M', 'M_TO_UQ', 'UQ_TO_UD']:
                    if transition in pos_rates and pos_rates[transition] not in [None, '']:
                        completed_horizontal += 1
        
        return {
            'vertical_completion': {
                'completed': completed_vertical,
                'total': total_vertical_needed,
                'percentage': round((completed_vertical / total_vertical_needed) * 100, 1) if total_vertical_needed > 0 else 0
            },
            'horizontal_completion': {
                'completed': completed_horizontal,
                'total': total_horizontal_needed,
                'percentage': round((completed_horizontal / total_horizontal_needed) * 100, 1) if total_horizontal_needed > 0 else 0
            },
            'overall_completion': {
                'completed': completed_vertical + completed_horizontal,
                'total': total_vertical_needed + total_horizontal_needed,
                'percentage': round(((completed_vertical + completed_horizontal) / (total_vertical_needed + total_horizontal_needed)) * 100, 1)
            }
        }

    @action(detail=False, methods=['post'])
    def save_scenario(self, request):
        """Save scenario with calculated grades"""
        scenario_data = request.data
        
        try:
            # Extract and validate data
            name = scenario_data.get('name')
            description = scenario_data.get('description', '')
            grading_system_id = scenario_data.get('grading_system')
            base_position_id = scenario_data.get('base_position')
            base_value = scenario_data.get('base_value')
            vertical_rates = scenario_data.get('vertical_rates', {})
            horizontal_rates = scenario_data.get('horizontal_rates', {})
            calculated_grades = scenario_data.get('calculated_grades', {})
            
            if not name:
                return Response({
                    'success': False,
                    'error': 'Scenario name is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Check if name already exists
            if SalaryScenario.objects.filter(name=name).exists():
                return Response({
                    'success': False,
                    'error': 'Scenario name already exists'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Clean up rate data - remove empty values
            clean_vertical_rates = {}
            for pos_id, rate in vertical_rates.items():
                if rate is not None and rate != '':
                    clean_vertical_rates[pos_id] = float(rate)
            
            clean_horizontal_rates = {}
            for pos_id, rates in horizontal_rates.items():
                if isinstance(rates, dict):
                    clean_horizontal_rates[pos_id] = {}
                    for transition, rate in rates.items():
                        if rate is not None and rate != '':
                            clean_horizontal_rates[pos_id][transition] = float(rate)
            
            # Create scenario
            scenario = SalaryScenario.objects.create(
                name=name,
                description=description,
                grading_system_id=grading_system_id,
                base_position_id=base_position_id,
                base_value=base_value,
                custom_vertical_rates=clean_vertical_rates,
                custom_horizontal_rates=clean_horizontal_rates,
                calculated_grades=calculated_grades,
                calculation_timestamp=timezone.now(),
                created_by=request.user
            )
            
            logger.info(f"Scenario '{name}' saved successfully by user {request.user.username}")
            
            return Response({
                'success': True,
                'message': 'Scenario saved successfully',
                'scenario_id': str(scenario.id),
                'scenario': SalaryScenarioDetailSerializer(scenario).data
            })
            
        except Exception as e:
            logger.error(f"Error saving scenario: {str(e)}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def calculate(self, request, pk=None):
        """Calculate salary grades for this scenario"""
        scenario = self.get_object()
        
        try:
            # Validate scenario data
            validation_errors = SalaryCalculationManager.validate_scenario_data({
                'base_value': scenario.base_value,
                'base_position': scenario.base_position,
                'custom_vertical_rates': scenario.custom_vertical_rates,
                'custom_horizontal_rates': scenario.custom_horizontal_rates
            })
            
            if validation_errors:
                return Response({
                    'success': False,
                    'errors': validation_errors
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Perform calculation
            calculated_grades = SalaryCalculationManager.calculate_scenario(scenario)
            
            # Calculate average rates for display
            rate_averages = SalaryCalculationManager.calculate_average_rates(scenario)
            
            logger.info(f"Scenario {scenario.name} calculated successfully by user {request.user.username}")
            
            return Response({
                'success': True,
                'message': 'Scenario calculated successfully',
                'calculated_grades': calculated_grades,
                'rate_averages': rate_averages,
                'calculation_timestamp': scenario.calculation_timestamp
            })
        except Exception as e:
            logger.error(f"Error calculating scenario {scenario.name}: {str(e)}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def apply(self, request, pk=None):
        """Apply this scenario as current"""
        scenario = self.get_object()
        
        try:
            applied_scenario = SalaryCalculationManager.apply_scenario(scenario.id, request.user)
            
            logger.info(f"Scenario {scenario.name} applied successfully by user {request.user.username}")
            
            return Response({
                'success': True,
                'message': 'Scenario applied successfully',
                'scenario': SalaryScenarioDetailSerializer(applied_scenario).data
            })
        except Exception as e:
            logger.error(f"Error applying scenario {scenario.name}: {str(e)}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def archive(self, request, pk=None):
        """Archive this scenario"""
        scenario = self.get_object()
        
        if scenario.status == 'CURRENT':
            return Response({
                'success': False,
                'error': 'Cannot archive current scenario. Apply another scenario first.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if scenario.status == 'ARCHIVED':
            return Response({
                'success': False,
                'error': 'Scenario is already archived'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        scenario.status = 'ARCHIVED'
        scenario.save()
        
        # Create history record
        ScenarioHistory.objects.create(
            scenario=scenario,
            action='ARCHIVED',
            performed_by=request.user,
            changes_made={'archived_by': request.user.get_full_name()}
        )
        
        logger.info(f"Scenario {scenario.name} archived by user {request.user.username}")
        
        return Response({
            'success': True,
            'message': 'Scenario archived successfully'
        })
    
    @action(detail=True, methods=['post'])
    def duplicate(self, request, pk=None):
        """Duplicate this scenario"""
        original_scenario = self.get_object()
        
        # Create new scenario with copied data
        new_name = f"{original_scenario.name} (Copy)"
        
        # Ensure unique name
        counter = 1
        while SalaryScenario.objects.filter(name=new_name).exists():
            counter += 1
            new_name = f"{original_scenario.name} (Copy {counter})"
        
        new_scenario = SalaryScenario.objects.create(
            grading_system=original_scenario.grading_system,
            name=new_name,
            description=f"Duplicated from: {original_scenario.description}",
            base_position=original_scenario.base_position,
            base_value=original_scenario.base_value,
            custom_vertical_rates=original_scenario.custom_vertical_rates,
            custom_horizontal_rates=original_scenario.custom_horizontal_rates,
            created_by=request.user
        )
        
        logger.info(f"Scenario {original_scenario.name} duplicated as {new_name} by user {request.user.username}")
        
        serializer = SalaryScenarioDetailSerializer(new_scenario)
        return Response({
            'success': True,
            'message': 'Scenario duplicated successfully',
            'scenario': serializer.data
        })
    
    @action(detail=False, methods=['get'])
    def current(self, request):
        """Get current active scenario"""
        grading_system_id = request.query_params.get('grading_system')
        
        if not grading_system_id:
            return Response({
                'error': 'grading_system parameter is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        current_scenario = SalaryCalculationManager.get_current_scenario(grading_system_id)
        
        if current_scenario:
            serializer = SalaryScenarioDetailSerializer(current_scenario)
            return Response(serializer.data)
        else:
            return Response({
                'message': 'No current scenario found',
                'current_scenario': None
            }, status=status.HTTP_404_NOT_FOUND)
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get scenario statistics"""
        grading_system_id = request.query_params.get('grading_system')
        queryset = self.get_queryset()
        
        if grading_system_id:
            queryset = queryset.filter(grading_system_id=grading_system_id)
        
        stats = {
            'total_scenarios': queryset.count(),
            'draft_scenarios': queryset.filter(status='DRAFT').count(),
            'current_scenarios': queryset.filter(status='CURRENT').count(),
            'archived_scenarios': queryset.filter(status='ARCHIVED').count(),
            'calculated_scenarios': queryset.exclude(calculated_grades={}).count(),
            'recent_scenarios': queryset.order_by('-created_at')[:5].values(
                'id', 'name', 'status', 'created_at'
            )
        }
        
        return Response(stats)

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
    
    @action(detail=False, methods=['get'])
    def recent(self, request):
        """Get recent history entries"""
        limit = int(request.query_params.get('limit', 20))
        grading_system_id = request.query_params.get('grading_system')
        
        queryset = self.get_queryset()
        if grading_system_id:
            queryset = queryset.filter(scenario__grading_system_id=grading_system_id)
        
        recent_history = queryset[:limit]
        serializer = self.get_serializer(recent_history, many=True)
        return Response(serializer.data)