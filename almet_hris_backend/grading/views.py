# grading/views.py - FIXED: Removed competitiveness/riskLevel, Enhanced data validation

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
        """ENHANCED: Get current grade structure from database with better validation"""
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
            
            # Create current structure from database with enhanced validation
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
            
            # ENHANCED: Log current structure for debugging
            logger.info(f"Current structure data: verticalAvg={current_data.get('verticalAvg')}, horizontalAvg={current_data.get('horizontalAvg')}")
            
            serializer = CurrentStructureSerializer(current_data)
            return Response(serializer.data)
            
        except Exception as e:
            logger.error(f"Error getting current structure: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
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
        """ENHANCED: Calculate scenario dynamically with better validation and debugging"""
        try:
            logger.info("=== CALCULATE DYNAMIC START (ENHANCED) ===")
            logger.info(f"Request data type: {type(request.data)}")
            logger.info(f"Request data: {json.dumps(request.data, indent=2, default=str)}")
            
            # Extract and validate request data
            request_data = request.data
            base_value = request_data.get('baseValue1')
            input_rates = request_data.get('grades', {})
            
            logger.info(f"Parsed - base_value: {base_value} (type: {type(base_value)})")
            logger.info(f"Parsed - input_rates: {json.dumps(input_rates, indent=2, default=str)}")
            
            # Enhanced base value validation
            if not base_value:
                logger.error("Base value is missing")
                return Response({
                    'errors': ['Base value is required'],
                    'success': False
                }, status=status.HTTP_400_BAD_REQUEST)
                
            try:
                base_value_float = float(base_value)
                if base_value_float <= 0:
                    raise ValueError("Base value must be positive")
            except (ValueError, TypeError) as e:
                logger.error(f"Base value validation error: {e}")
                return Response({
                    'errors': [f'Base value must be a valid positive number: {str(e)}'],
                    'success': False
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Enhanced input rates validation
            if not input_rates or not isinstance(input_rates, dict):
                logger.error("Input rates missing or invalid")
                return Response({
                    'errors': ['Grade input rates are required'],
                    'success': False
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get position groups from database
            logger.info("Getting position groups from database...")
            position_groups = SalaryCalculationManager.get_position_groups_from_db()
            position_list = list(position_groups.values_list('name', 'hierarchy_level'))
            logger.info(f"Found position groups: {position_list}")
            
            if not position_groups.exists():
                logger.error("No position groups found")
                return Response({
                    'errors': ['No position groups found in database. Please configure position groups first.'],
                    'success': False
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Enhanced validation using manager
            validation_errors = SalaryCalculationManager.validate_scenario_inputs(base_value_float, input_rates)
            if validation_errors:
                logger.error(f"Validation errors found: {validation_errors}")
                return Response({
                    'errors': validation_errors,
                    'success': False
                }, status=status.HTTP_400_BAD_REQUEST)
            
            logger.info("=== VALIDATION PASSED ===")
            
            # Calculate grades using enhanced manager
            logger.info("Starting grade calculation...")
            calculated_grades = SalaryCalculationManager.calculate_scenario_grades(
                base_value_float, input_rates, position_groups
            )
            logger.info(f"Calculation complete. Results: {json.dumps(calculated_grades, indent=2, default=str)}")
            
            # ENHANCED: Format output for frontend with validation
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
                else:
                    logger.warning(f"Invalid grade data for {position_name}: {grades}")
                    calculated_outputs[position_name] = {
                        'LD': "", 'LQ': "", 'M': "", 'UQ': "", 'UD': ""
                    }
            
            logger.info(f"Formatted outputs: {json.dumps(calculated_outputs, indent=2, default=str)}")
            logger.info("=== CALCULATE DYNAMIC SUCCESS ===")
            
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
                'debug_info': {
                    'error_type': type(e).__name__,
                    'traceback': traceback.format_exc()
                } if settings.DEBUG else None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'], url_path='save_draft')
    def save_draft(self, request):
        """COMPLETELY FIXED: Save scenario with proper global horizontal intervals"""
        try:
            logger.info("=== SAVE DRAFT START (COMPLETE FIX) ===")
            
            # Extract data
            name = request.data.get('name')
            description = request.data.get('description', '')
            base_value = request.data.get('baseValue1')
            grade_order = request.data.get('gradeOrder', [])
            input_rates = request.data.get('grades', {})
            global_horizontal_intervals = request.data.get('globalHorizontalIntervals', {})
            calculated_outputs = request.data.get('calculatedOutputs', {})
            
            logger.info(f"📊 RECEIVED DATA:")
            logger.info(f"  Global intervals: {global_horizontal_intervals}")
            logger.info(f"  Has intervals: {bool(global_horizontal_intervals)}")
            
            # Validation
            validation_errors = []
            
            if not name or len(name.strip()) == 0:
                validation_errors.append('Scenario name is required')
            
            try:
                base_value_float = float(base_value) if base_value else 0
                if base_value_float <= 0:
                    validation_errors.append('Base value must be greater than 0')
            except (ValueError, TypeError):
                validation_errors.append('Base value must be a valid number')
                base_value_float = 0
            
            if not grade_order:
                validation_errors.append('Grade order is required')
            
            if validation_errors:
                return Response({
                    'success': False,
                    'errors': validation_errors
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get grading system
            grading_system, created = GradingSystem.objects.get_or_create(
                name="Default Grading System",
                defaults={
                    'description': "Default grading system",
                    'is_active': True,
                    'created_by': request.user
                }
            )
            
            # COMPLETELY FIXED: Format input rates with global intervals
            formatted_input_rates = {}
            
            logger.info(f"🔧 FORMATTING INPUT RATES:")
            for position_name in grade_order:
                position_input = input_rates.get(position_name, {})
                
                # Handle vertical
                vertical_value = position_input.get('vertical')
                if vertical_value == '' or vertical_value is None:
                    vertical_value = None
                else:
                    try:
                        vertical_value = float(vertical_value)
                    except (ValueError, TypeError):
                        vertical_value = None
                
                # FIXED: Apply global intervals to EVERY position
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
                
                logger.info(f"  {position_name}: vertical={vertical_value}, intervals={clean_intervals}")
            
            # FIXED: Calculate averages manually to ensure they're correct
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
            
            # FIXED: Horizontal averages from global intervals
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
            
            logger.info(f"🎯 CALCULATED AVERAGES:")
            logger.info(f"  Vertical: {vertical_sum} ÷ {vertical_count} ÷ 100 = {vertical_avg} ({vertical_avg * 100:.1f}%)")
            logger.info(f"  Horizontal: {horizontal_sum} ÷ {horizontal_count} ÷ 100 = {horizontal_avg} ({horizontal_avg * 100:.1f}%)")
            
            # Create scenario
            with transaction.atomic():
                scenario = SalaryScenario.objects.create(
                    grading_system=grading_system,
                    name=name.strip(),
                    description=description,
                    base_value=Decimal(str(base_value_float)),
                    grade_order=grade_order,
                    input_rates=formatted_input_rates,
                    calculated_grades=calculated_outputs,
                    calculation_timestamp=timezone.now(),
                    vertical_avg=Decimal(str(vertical_avg)),
                    horizontal_avg=Decimal(str(horizontal_avg)),
                    created_by=request.user
                )
                
                logger.info(f"✅ SCENARIO CREATED:")
                logger.info(f"  ID: {scenario.id}")
                logger.info(f"  Vertical avg: {scenario.vertical_avg}")
                logger.info(f"  Horizontal avg: {scenario.horizontal_avg}")
            
            # Format response
            scenario_serializer = SalaryScenarioDetailSerializer(scenario)
            
            return Response({
                'success': True,
                'message': 'Scenario saved successfully!',
                'scenario_id': str(scenario.id),
                'scenario': scenario_serializer.data
            })
            
        except Exception as e:
            logger.error(f"❌ SAVE DRAFT ERROR: {str(e)}")
            return Response({
                'success': False,
                'error': f'Failed to save scenario: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
        """FIXED: Save scenario as draft with proper global horizontal interval handling"""
        try:
            logger.info("=== SAVE DRAFT START (FIXED) ===")
            logger.info(f"Request data: {json.dumps(request.data, indent=2, default=str)}")
            
            # Extract and validate data
            name = request.data.get('name')
            description = request.data.get('description', '')
            base_value = request.data.get('baseValue1')
            grade_order = request.data.get('gradeOrder', [])
            input_rates = request.data.get('grades', {})
            global_horizontal_intervals = request.data.get('globalHorizontalIntervals', {})
            calculated_outputs = request.data.get('calculatedOutputs', {})
            
            logger.info(f"Extracted data:")
            logger.info(f"  Name: {name}")
            logger.info(f"  Base value: {base_value}")
            logger.info(f"  Grade order: {grade_order}")
            logger.info(f"  Global intervals: {global_horizontal_intervals}")
            
            # Enhanced validation
            validation_errors = []
            
            if not name or len(name.strip()) == 0:
                validation_errors.append('Scenario name is required')
            
            if not base_value:
                validation_errors.append('Base value is required')
            else:
                try:
                    base_value_float = float(base_value)
                    if base_value_float <= 0:
                        validation_errors.append('Base value must be greater than 0')
                except (ValueError, TypeError):
                    validation_errors.append('Base value must be a valid number')
            
            if not grade_order or len(grade_order) == 0:
                validation_errors.append('Grade order is required')
            
            # ENHANCED: Validate calculated outputs structure
            if calculated_outputs:
                for grade_name, grade_data in calculated_outputs.items():
                    if not isinstance(grade_data, dict):
                        validation_errors.append(f'Invalid calculated output structure for {grade_name}')
                    else:
                        # Ensure all required fields exist
                        for field in ['LD', 'LQ', 'M', 'UQ', 'UD']:
                            if field not in grade_data:
                                logger.warning(f"Missing field {field} in calculated output for {grade_name}")
            
            if validation_errors:
                logger.error(f"Validation errors: {validation_errors}")
                return Response({
                    'success': False,
                    'errors': validation_errors
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Check if name already exists
            if SalaryScenario.objects.filter(name=name.strip()).exists():
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
            
            # FIXED: Build formatted input rates with global intervals applied to ALL positions
            formatted_input_rates = {}
            
            # Ensure global_horizontal_intervals has all required keys with default values
            default_intervals = {
                'LD_to_LQ': 0,
                'LQ_to_M': 0,
                'M_to_UQ': 0,
                'UQ_to_UD': 0
            }
            
            # Merge with provided intervals, cleaning values
            final_global_intervals = {}
            for key in default_intervals.keys():
                value = global_horizontal_intervals.get(key, 0)
                if value == '' or value is None:
                    final_global_intervals[key] = 0
                else:
                    try:
                        final_global_intervals[key] = float(value)
                    except (ValueError, TypeError):
                        final_global_intervals[key] = 0
            
            logger.info(f"Final global intervals: {final_global_intervals}")
            
            # Apply global horizontal intervals to each position
            for position_name in grade_order:
                position_input = input_rates.get(position_name, {})
                
                # Handle vertical input
                vertical_value = position_input.get('vertical')
                if vertical_value == '' or vertical_value is None:
                    vertical_value = None
                else:
                    try:
                        vertical_value = float(vertical_value)
                    except (ValueError, TypeError):
                        vertical_value = None
                
                # Apply global horizontal intervals to this position (FIXED)
                formatted_input_rates[position_name] = {
                    'vertical': vertical_value,
                    'horizontal_intervals': final_global_intervals.copy()  # Copy to each position
                }
            
            logger.info(f"Formatted input rates: {json.dumps(formatted_input_rates, indent=2, default=str)}")
            
            # ENHANCED: Calculate averages with proper validation
            vertical_sum = 0
            vertical_count = 0
            horizontal_sum = 0
            horizontal_count = 0
            
            # Vertical averages (per position)
            for position_name in grade_order:
                position_data = formatted_input_rates.get(position_name, {})
                vertical_value = position_data.get('vertical')
                if vertical_value is not None and vertical_value != 0:
                    try:
                        vertical_sum += float(vertical_value)
                        vertical_count += 1
                    except (ValueError, TypeError):
                        pass
            
            # Horizontal averages (global - from final_global_intervals)
            for interval_value in final_global_intervals.values():
                if interval_value is not None and interval_value != 0:
                    try:
                        horizontal_sum += float(interval_value)
                        horizontal_count += 1
                    except (ValueError, TypeError):
                        pass
            
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
            
            # SIMPLIFIED: Calculate basic metrics (removed competitiveness/riskLevel)
            metrics = SalaryCalculationManager.calculate_scenario_metrics(
                scenario_data, current_data
            ) if current_data else {}
            
            # Create scenario
            with transaction.atomic():
                scenario = SalaryScenario.objects.create(
                    grading_system=grading_system,
                    name=name.strip(),
                    description=description,
                    base_value=Decimal(str(base_value_float)),
                    grade_order=grade_order,
                    input_rates=formatted_input_rates,
                    calculated_grades=calculated_outputs,
                    calculation_timestamp=timezone.now(),
                    vertical_avg=Decimal(str(vertical_avg)),  # FIXED: Set calculated average
                    horizontal_avg=Decimal(str(horizontal_avg)),  # FIXED: Set calculated average
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
                        'global_intervals': final_global_intervals,
                        'has_global_intervals': bool(any(v != 0 for v in final_global_intervals.values())),
                        'calculated_averages': {
                            'vertical_avg': vertical_avg,
                            'horizontal_avg': horizontal_avg
                        }
                    }
                )
            
            logger.info(f"Scenario '{name}' saved successfully with ID: {scenario.id}")
            logger.info(f"Final averages - Vertical: {vertical_avg}, Horizontal: {horizontal_avg}")
            logger.info(f"=== SAVE DRAFT SUCCESS ===")
            
            # Format response
            scenario_serializer = SalaryScenarioDetailSerializer(scenario)
            
            return Response({
                'success': True,
                'message': 'Scenario saved as draft successfully!',
                'scenario_id': str(scenario.id),
                'scenario': scenario_serializer.data
            })
            
        except Exception as e:
            logger.error(f"=== SAVE DRAFT ERROR ===")
            logger.error(f"Error type: {type(e).__name__}")
            logger.error(f"Error message: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            
            return Response({
                'success': False,
                'error': f'Failed to save scenario: {str(e)}',
                'debug_info': {
                    'error_type': type(e).__name__,
                    'traceback': traceback.format_exc()
                } if settings.DEBUG else None
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
            
            logger.info(f"Scenario {scenario.name} applied as current by user {request.user.username}")
            
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
                    'verticalAvg': float(scenario.vertical_avg) if scenario.vertical_avg else 0,
                    'horizontalAvg': float(scenario.horizontal_avg) if scenario.horizontal_avg else 0
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
        """SIMPLIFIED: Get scenario statistics (removed competitiveness/riskLevel)"""
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