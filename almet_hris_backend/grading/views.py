# grading/views.py - COMPLETE FILE WITH ALL ACTIONS

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
        """Get current grade structure from database"""
        grading_system_id = request.query_params.get('grading_system_id')
        
        try:
            # Get or use default grading system
            if grading_system_id:
                try:
                    grading_system = GradingSystem.objects.get(id=grading_system_id, is_active=True)
                except GradingSystem.DoesNotExist:
                    grading_system = None
            else:
                grading_system = GradingSystem.objects.filter(is_active=True).first()
            
            # Create current structure from database
            current_data = SalaryCalculationManager.create_current_structure_from_db()
            
            if current_data is None:
                return Response({
                    'error': 'No position groups found in database',
                    'message': 'Please configure position groups in the admin panel first'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Add grading system info if available
            if grading_system:
                current_data['grading_system_id'] = grading_system.id
                current_data['grading_system_name'] = grading_system.name
            
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

    @action(detail=False, methods=['get'])
    def by_system(self, request):
        """Get salary grades by grading system"""
        grading_system_id = request.query_params.get('grading_system')
        
        if not grading_system_id:
            return Response({
                'error': 'grading_system parameter is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            queryset = self.get_queryset().filter(grading_system_id=grading_system_id)
            serializer = self.get_serializer(queryset, many=True)
            return Response(serializer.data)
        except Exception as e:
            logger.error(f"Error getting salary grades by system: {str(e)}")
            return Response({
                'error': 'Failed to get salary grades',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class SalaryScenarioViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description']
    filterset_fields = ['status', 'grading_system']
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
        """Calculate scenario dynamically using database position groups - UPDATED FOR 4 INTERVALS"""
        try:
            logger.info("=== CALCULATE DYNAMIC START (4 INTERVALS) ===")
            logger.info(f"Request data: {request.data}")
            
            # Validate request data
            request_data = request.data
            base_value = request_data.get('baseValue1')
            input_rates = request_data.get('grades', {})
            
            logger.info(f"Parsed - base_value: {base_value}, input_rates: {input_rates}")
            
            if not base_value:
                logger.error("Base value is missing")
                return Response({
                    'errors': ['Base value is required'],
                    'success': False
                }, status=status.HTTP_400_BAD_REQUEST)
                
            try:
                base_value_float = float(base_value)
            except (ValueError, TypeError) as e:
                logger.error(f"Base value conversion error: {e}")
                return Response({
                    'errors': ['Base value must be a valid number'],
                    'success': False
                }, status=status.HTTP_400_BAD_REQUEST)
            
            if base_value_float <= 0:
                logger.error(f"Base value too low: {base_value_float}")
                return Response({
                    'errors': ['Base value must be greater than 0'],
                    'success': False
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get position groups from database - CORRECT ORDER
            logger.info("Getting position groups from database...")
            position_groups = SalaryCalculationManager.get_position_groups_from_db()
            logger.info(f"Found position groups: {list(position_groups.values_list('name', 'hierarchy_level'))}")
            
            if not position_groups.exists():
                logger.error("No position groups found")
                return Response({
                    'errors': ['No position groups found in database. Please configure position groups first.'],
                    'success': False
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Validate input rates - UPDATED FOR 4 INTERVALS
            logger.info("Validating input rates with 4 interval structure...")
            validation_errors = SalaryCalculationManager.validate_scenario_inputs(
                base_value_float, input_rates
            )
            
            if validation_errors:
                logger.error(f"Validation errors: {validation_errors}")
                return Response({
                    'errors': validation_errors,
                    'success': False
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Log the structure of input_rates for debugging
            for grade_name, grade_data in input_rates.items():
                logger.info(f"Grade {grade_name}:")
                logger.info(f"  Vertical: {grade_data.get('vertical', 'N/A')}")
                if 'horizontal_intervals' in grade_data:
                    intervals = grade_data['horizontal_intervals']
                    logger.info(f"  Horizontal intervals:")
                    logger.info(f"    LD→LQ: {intervals.get('LD_to_LQ', 'empty')}")
                    logger.info(f"    LQ→M: {intervals.get('LQ_to_M', 'empty')}")
                    logger.info(f"    M→UQ: {intervals.get('M_to_UQ', 'empty')}")
                    logger.info(f"    UQ→UD: {intervals.get('UQ_to_UD', 'empty')}")
                else:
                    logger.warning(f"  No horizontal_intervals found for {grade_name}")
            
            # Calculate grades using database position groups with 4 intervals
            logger.info("Starting grade calculation with 4 intervals...")
            calculated_grades = SalaryCalculationManager.calculate_scenario_grades(
                base_value_float, input_rates, position_groups
            )
            logger.info(f"Calculated grades: {calculated_grades}")
            
            # Format output to match frontend calculatedOutputs
            calculated_outputs = {}
            for position_name, grades in calculated_grades.items():
                calculated_outputs[position_name] = {
                    'LD': grades['LD'] if grades['LD'] > 0 else "",
                    'LQ': grades['LQ'] if grades['LQ'] > 0 else "",
                    'M': grades['M'] if grades['M'] > 0 else "",
                    'UQ': grades['UQ'] if grades['UQ'] > 0 else "",
                    'UD': grades['UD'] if grades['UD'] > 0 else ""
                }
            
            logger.info(f"Formatted outputs: {calculated_outputs}")
            logger.info("=== CALCULATE DYNAMIC SUCCESS (4 INTERVALS) ===")
            
            return Response({
                'calculatedOutputs': calculated_outputs,
                'success': True
            })
        
        except Exception as e:
            logger.error(f"=== CALCULATE DYNAMIC ERROR ===")
            logger.error(f"Error type: {type(e).__name__}")
            logger.error(f"Error message: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            
            return Response({
                'errors': [f'Calculation error: {str(e)}'],
                'success': False,
                'debug_info': traceback.format_exc() if settings.DEBUG else None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'], url_path='save_draft')
    def  save_draft(self, request):
        """Save scenario as draft using database position groups - UPDATED for global intervals"""
        try:
            # Extract and validate data
            name = request.data.get('name')
            description = request.data.get('description', '')
            base_value = request.data.get('baseValue1')
            input_rates = request.data.get('grades', {})
            calculated_outputs = request.data.get('calculatedOutputs', {})
            
            logger.info(f"=== SAVE DRAFT START (GLOBAL INTERVALS) ===")
            logger.info(f"Name: {name}")
            logger.info(f"Base value: {base_value}")
            logger.info(f"Input rates: {input_rates}")
            
            if not name:
                return Response({
                    'success': False,
                    'error': 'Scenario name is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            if not base_value or base_value <= 0:
                return Response({
                    'success': False,
                    'error': 'Base value must be greater than 0'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Check if name already exists
            if SalaryScenario.objects.filter(name=name).exists():
                return Response({
                    'success': False,
                    'error': 'Scenario name already exists'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get or create default grading system
            grading_system, created = GradingSystem.objects.get_or_create(
                name="Default Grading System",
                defaults={
                    'description': "Default grading system",
                    'is_active': True,
                    'created_by': request.user
                }
            )
            
            # Get position groups from database
            position_groups = SalaryCalculationManager.get_position_groups_from_db()
            
            if not position_groups.exists():
                return Response({
                    'success': False,
                    'error': 'No position groups found in database'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Build grade order from database
            grade_order = [pos.get_name_display() for pos in position_groups]
            
            # UPDATED: Handle global horizontal intervals
            # The input_rates should already contain global intervals applied to each position
            # But we need to verify and log the structure
            
            sample_position = grade_order[0] if grade_order else None
            global_intervals = None
            if sample_position and input_rates.get(sample_position, {}).get('horizontal_intervals'):
                global_intervals = input_rates[sample_position]['horizontal_intervals']
                logger.info(f"Detected global horizontal intervals: {global_intervals}")
                
                # Verify all positions have the same intervals (they should for global logic)
                for position_name in grade_order:
                    position_intervals = input_rates.get(position_name, {}).get('horizontal_intervals', {})
                    if position_intervals != global_intervals:
                        logger.warning(f"Position {position_name} has different intervals: {position_intervals}")
            
            # Calculate averages - UPDATED for global intervals
            vertical_sum = 0
            horizontal_sum = 0
            vertical_count = 0
            horizontal_count = 0
            
            for position_name in grade_order:
                grade_data = input_rates.get(position_name, {})
                
                # Vertical (per position)
                if grade_data.get('vertical') is not None:
                    vertical_sum += float(grade_data['vertical'])
                    vertical_count += 1
                
                # Horizontal (global - only count once)
                if global_intervals and horizontal_count == 0:
                    for interval_name, interval_value in global_intervals.items():
                        if interval_value is not None and interval_value != '':
                            horizontal_sum += float(interval_value)
                            horizontal_count += 1
            
            vertical_avg = (vertical_sum / vertical_count / 100) if vertical_count > 0 else 0
            horizontal_avg = (horizontal_sum / horizontal_count / 100) if horizontal_count > 0 else 0
            
            logger.info(f"Calculated averages:")
            logger.info(f"  Vertical: {vertical_sum}/{vertical_count} = {vertical_avg}")
            logger.info(f"  Horizontal: {horizontal_sum}/{horizontal_count} = {horizontal_avg}")
            
            # Get current structure for metrics calculation
            current_data = SalaryCalculationManager.create_current_structure_from_db()
            
            # Prepare scenario data for metrics
            scenario_data = {
                'grades': calculated_outputs,
                'gradeOrder': grade_order,
                'verticalAvg': vertical_avg,
                'horizontalAvg': horizontal_avg
            }
            
            # Calculate metrics
            metrics = SalaryCalculationManager.calculate_scenario_metrics(
                scenario_data, current_data
            ) if current_data else {}
            
            # Create scenario
            with transaction.atomic():
                scenario = SalaryScenario.objects.create(
                    grading_system=grading_system,
                    name=name,
                    description=description,
                    base_value=base_value,
                    grade_order=grade_order,
                    input_rates=input_rates,  # Contains global intervals applied to each position
                    calculated_grades=calculated_outputs,
                    calculation_timestamp=timezone.now(),
                    vertical_avg=Decimal(str(vertical_avg)),
                    horizontal_avg=Decimal(str(horizontal_avg)),
                    metrics=metrics,
                    created_by=request.user
                )
                
                # Create history record
                ScenarioHistory.objects.create(
                    scenario=scenario,
                    action='CREATED',
                    performed_by=request.user,
                    changes_made={
                        'created_scenario': scenario.name,
                        'global_intervals': global_intervals,
                        'has_global_intervals': global_intervals is not None
                    }
                )
            
            logger.info(f"Scenario '{name}' saved as draft with global intervals by user {request.user.username}")
            logger.info(f"=== SAVE DRAFT SUCCESS ===")
            
            return Response({
                'success': True,
                'message': 'Scenario saved as draft with global intervals!',
                'scenario_id': str(scenario.id),
                'scenario': SalaryScenarioDetailSerializer(scenario).data
            })
            
        except Exception as e:
            logger.error(f"Error saving draft scenario with global intervals: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    @action(detail=True, methods=['post'])
    def apply_as_current(self, request, pk=None):
        """Apply scenario as current (archive previous current scenario)"""
        try:
            scenario = self.get_object()
            
            if scenario.status != 'DRAFT':
                return Response({
                    'success': False,
                    'error': 'Only draft scenarios can be applied'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            if not scenario.calculated_grades:
                return Response({
                    'success': False,
                    'error': 'Scenario must be calculated before applying'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Apply scenario using manager (handles archiving current)
            with transaction.atomic():
                applied_scenario = SalaryCalculationManager.apply_scenario(scenario.id, request.user)
            
            logger.info(f"Scenario {scenario.name} applied as current by user {request.user.username}, previous scenario archived")
            
            return Response({
                'success': True,
                'message': 'Scenario has been set as current grade structure! Previous current scenario archived.',
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
        """Archive scenario (matches frontend handleArchiveDraft)"""
        try:
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
            
            logger.info(f"Scenario {scenario.name} archived by user {request.user.username}")
            
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
    def get_best_draft(self, request):
        """Get best draft scenario based on balance score"""
        try:
            grading_system_id = request.query_params.get('grading_system_id')
            
            queryset = self.get_queryset().filter(status='DRAFT')
            if grading_system_id:
                queryset = queryset.filter(grading_system_id=grading_system_id)
            
            if not queryset.exists():
                return Response({
                    'best_draft': None
                })
            
            # Calculate balance scores and find best
            best_scenario = None
            best_score = -1
            
            for scenario in queryset:
                scenario_data = {
                    'verticalAvg': float(scenario.vertical_avg),
                    'horizontalAvg': float(scenario.horizontal_avg)
                }
                score = SalaryCalculationManager.get_balance_score(scenario_data)
                
                if score > best_score:
                    best_score = score
                    best_scenario = scenario
            
            if best_scenario:
                serializer = SalaryScenarioDetailSerializer(best_scenario)
                return Response({
                    'best_draft': serializer.data,
                    'balance_score': best_score
                })
            
            return Response({
                'best_draft': None
            })
            
        except Exception as e:
            logger.error(f"Error getting best draft: {str(e)}")
            return Response({
                'error': 'Failed to get best draft scenario',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def compare_scenarios(self, request):
        """Compare multiple scenarios"""
        try:
            scenario_ids = request.data.get('scenario_ids', [])
            include_current = request.data.get('include_current', False)
            
            if len(scenario_ids) < 2:
                return Response({
                    'success': False,
                    'error': 'At least 2 scenarios required for comparison'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            scenarios = []
            
            # Add selected scenarios
            for scenario_id in scenario_ids:
                try:
                    scenario = SalaryScenario.objects.get(id=scenario_id)
                    scenarios.append(scenario)
                except SalaryScenario.DoesNotExist:
                    return Response({
                        'success': False,
                        'error': f'Scenario with id {scenario_id} not found'
                    }, status=status.HTTP_404_NOT_FOUND)
            
            # Add current structure if requested
            current_data = None
            if include_current:
                current_data = SalaryCalculationManager.create_current_structure_from_db()
            
            # Prepare comparison data
            comparison_data = {
                'scenarios': SalaryScenarioDetailSerializer(scenarios, many=True).data,
                'current_structure': current_data
            }
            
            return Response({
                'success': True,
                'comparison_data': comparison_data
            })
            
        except Exception as e:
            logger.error(f"Error comparing scenarios: {str(e)}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def current_scenario(self, request):
        """Get current active scenario"""
        try:
            grading_system_id = request.query_params.get('grading_system')
            
            if not grading_system_id:
                # Get default grading system
                grading_system = GradingSystem.objects.filter(is_active=True).first()
                if grading_system:
                    grading_system_id = grading_system.id
                else:
                    return Response({
                        'error': 'No grading system found'
                    }, status=status.HTTP_404_NOT_FOUND)
            
            try:
                current_scenario = SalaryScenario.objects.get(
                    grading_system_id=grading_system_id,
                    status='CURRENT'
                )
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

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get scenario statistics"""
        try:
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
                'recent_scenarios': list(queryset.order_by('-created_at')[:5].values(
                    'id', 'name', 'status', 'created_at'
                ))
            }
            
            return Response(stats)
            
        except Exception as e:
            logger.error(f"Error getting statistics: {str(e)}")
            return Response({
                'error': 'Failed to get statistics',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def duplicate(self, request, pk=None):
        """Duplicate scenario"""
        try:
            original_scenario = self.get_object()
            
            # Create new scenario with copied data
            new_name = f"{original_scenario.name} (Copy)"
            
            # Ensure unique name
            counter = 1
            while SalaryScenario.objects.filter(name=new_name).exists():
                counter += 1
                new_name = f"{original_scenario.name} (Copy {counter})"
            
            with transaction.atomic():
                new_scenario = SalaryScenario.objects.create(
                    grading_system=original_scenario.grading_system,
                    name=new_name,
                    description=f"Duplicated from: {original_scenario.description}",
                    base_value=original_scenario.base_value,
                    grade_order=original_scenario.grade_order,
                    input_rates=original_scenario.input_rates,
                    calculated_grades=original_scenario.calculated_grades,
                    calculation_timestamp=timezone.now() if original_scenario.calculated_grades else None,
                    vertical_avg=original_scenario.vertical_avg,
                    horizontal_avg=original_scenario.horizontal_avg,
                    metrics=original_scenario.metrics,
                    created_by=request.user
                )
                
                # Create history record
                ScenarioHistory.objects.create(
                    scenario=new_scenario,
                    action='CREATED',
                    performed_by=request.user,
                    changes_made={
                        'duplicated_from': original_scenario.name,
                        'original_scenario_id': str(original_scenario.id)
                    }
                )
            
            logger.info(f"Scenario {original_scenario.name} duplicated as {new_name} by user {request.user.username}")
            
            serializer = SalaryScenarioDetailSerializer(new_scenario)
            return Response({
                'success': True,
                'message': 'Scenario duplicated successfully',
                'scenario': serializer.data
            })
            
        except Exception as e:
            logger.error(f"Error duplicating scenario: {str(e)}")
            return Response({
                'success': False,
                'error': str(e)
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
    
    @action(detail=False, methods=['get'])
    def recent(self, request):
        """Get recent history entries"""
        try:
            limit = int(request.query_params.get('limit', 20))
            grading_system_id = request.query_params.get('grading_system')
            
            queryset = self.get_queryset()
            if grading_system_id:
                queryset = queryset.filter(scenario__grading_system_id=grading_system_id)
            
            recent_history = queryset[:limit]
            serializer = self.get_serializer(recent_history, many=True)
            return Response(serializer.data)
            
        except Exception as e:
            logger.error(f"Error getting recent history: {str(e)}")
            return Response({
                'error': 'Failed to get recent history',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)