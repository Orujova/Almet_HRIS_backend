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


from .models import GradingSystem, SalaryGrade, SalaryScenario, ScenarioHistory
from .serializers import (
    GradingSystemSerializer, SalaryGradeSerializer, CurrentStructureSerializer,
    SalaryScenarioListSerializer, SalaryScenarioDetailSerializer,
    SalaryScenarioCreateSerializer,
    ScenarioHistorySerializer
)
from .managers import SalaryCalculationManager
from api.views import ModernPagination
from api.models import PositionGroup

logger = logging.getLogger(__name__)

class GradingSystemViewSet(viewsets.ModelViewSet):
    queryset = GradingSystem.objects.all()
    serializer_class = GradingSystemSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = ModernPagination
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
    pagination_class = ModernPagination
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
    
    
    @action(detail=False, methods=['post'], url_path='compare_scenarios')
    def compare_scenarios(self, request):
        """
        Scenario-ları müqayisə et
        Request: {
            "scenario_ids": ["uuid1", "uuid2", "uuid3"]  // Compare ediləcək scenario ID-ləri
        }
        """
        try:
            from api.models import Employee
            from collections import defaultdict
            
            scenario_ids = request.data.get('scenario_ids', [])
            
            if not scenario_ids:
                return Response({
                    'success': False,
                    'error': 'At least one scenario ID is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get scenarios
            scenarios = SalaryScenario.objects.filter(id__in=scenario_ids)
            
            if not scenarios.exists():
                return Response({
                    'success': False,
                    'error': 'No scenarios found'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Get CURRENT scenario (cari struktur)
            try:
                current_scenario = SalaryScenario.objects.get(status='CURRENT')
            except SalaryScenario.DoesNotExist:
                return Response({
                    'success': False,
                    'error': 'No current scenario found. Please apply a scenario first.'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get all active employees
            employees = Employee.objects.filter(
                is_deleted=False,
                status__affects_headcount=True
            ).select_related(
                'position_group', 'business_function', 'department'
            ).values(
                'id', 'employee_id', 'full_name', 
                'position_group__name', 'position_group__hierarchy_level',
                'grading_level', 'start_date',
                'business_function__name', 'department__name',
                'job_title'
            )
            
            # Build comparison
            comparison_result = {
                'total_cost_comparison': self._build_total_cost_comparison(
                    current_scenario, scenarios, employees
                ),
                'employee_analysis': self._build_employee_analysis(
                    current_scenario, scenarios, employees
                ),
                'underpaid_overpaid_lists': self._build_underpaid_overpaid_lists(
                    current_scenario, scenarios, employees
                ),
                'scenarios_comparison': self._build_scenarios_percentage_comparison(
                    current_scenario, scenarios
                )
            }
            
            return Response({
                'success': True,
                'comparison': comparison_result,
                'scenarios': [
                    {
                        'id': str(s.id),
                        'name': s.name,
                        'is_current': s.status == 'CURRENT'
                    } 
                    for s in [current_scenario] + list(scenarios)
                ]
            })
            
        except Exception as e:
            logger.error(f"Comparison error: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _get_salary_for_employee(self, employee, scenario):
        """
        Employee-nin salary-sini scenario-dan götür
        Employee grading_level-inə görə scenario-dan uyğun dəyəri tap
        """
        grading_level = employee['grading_level']  # e.g., "MGR_UQ"
        position_name = employee['position_group__name']  # e.g., "MANAGER"
        
        if not grading_level or not scenario.calculated_grades:
            return 0
        
        # Parse grading: "MGR_UQ" -> level = "UQ"
        parts = grading_level.split('_')
        if len(parts) != 2:
            return 0
        
        position_short, level = parts  # position_short = "MGR", level = "UQ"
        
        # Scenario-da bu position-u tap
        for pos_name, grades in scenario.calculated_grades.items():
            # "MANAGER" və "MGR" uyğunluğunu yoxla
            if (pos_name == position_name or 
                position_name in pos_name or 
                pos_name.startswith(position_short)):
                
                if isinstance(grades, dict):
                    salary = grades.get(level, 0)
                    return float(salary) if salary else 0
        
        return 0
    
    def _build_total_cost_comparison(self, current_scenario, scenarios, employees):
        """
        Şəkil 1: Total Cost Comparison Table
        Hər position üçün total cost hesabla
        """
        from collections import defaultdict
        
        # Position-lara görə qruplaşdır
        position_costs = defaultdict(lambda: {
            'current': 0,
            'scenarios': {}
        })
        
        # Hər employee üçün
        for emp in employees:
            position = emp['position_group__name']
            
            # Current scenario-dan salary
            current_salary = self._get_salary_for_employee(emp, current_scenario)
            position_costs[position]['current'] += current_salary
            
            # Hər scenario-dan salary
            for scenario in scenarios:
                scenario_name = scenario.name
                if scenario_name not in position_costs[position]['scenarios']:
                    position_costs[position]['scenarios'][scenario_name] = 0
                
                scenario_salary = self._get_salary_for_employee(emp, scenario)
                position_costs[position]['scenarios'][scenario_name] += scenario_salary
        
        # Format output
        result = {
            'positions': {},
            'totals': {
                'current': 0,
                'scenarios': {}
            }
        }
        
        for position, costs in position_costs.items():
            result['positions'][position] = {
                'current': round(costs['current']),
                'scenarios': {
                    name: round(value) 
                    for name, value in costs['scenarios'].items()
                }
            }
            
            # Total-a əlavə et
            result['totals']['current'] += costs['current']
            for scenario_name, value in costs['scenarios'].items():
                if scenario_name not in result['totals']['scenarios']:
                    result['totals']['scenarios'][scenario_name] = 0
                result['totals']['scenarios'][scenario_name] += value
        
        # Round totals
        result['totals']['current'] = round(result['totals']['current'])
        result['totals']['scenarios'] = {
            name: round(value)
            for name, value in result['totals']['scenarios'].items()
        }
        
        return result
    
    def _build_employee_analysis(self, current_scenario, scenarios, employees):
        """
        Şəkil 2: Employee Analysis - Headcount Table
        Hər position və grade üçün neçə employee over/under/at grade-dir
        """
        from collections import defaultdict
        
        analysis = {}
        
        # Position-lara görə qruplaşdır
        positions = set(emp['position_group__name'] for emp in employees)
        
        for position in positions:
            position_employees = [
                emp for emp in employees 
                if emp['position_group__name'] == position
            ]
            
            analysis[position] = {
                'total_employees': len(position_employees),
                'current_grading': defaultdict(lambda: {
                    'count': 0,
                    'over': 0,
                    'at': 0,
                    'under': 0
                }),
                'scenarios': {}
            }
            
            # Current scenario üçün
            for emp in position_employees:
                grade = emp['grading_level']
                current_salary = self._get_salary_for_employee(emp, current_scenario)
                current_grade_salary = self._get_grade_salary(current_scenario, grade)
                
                analysis[position]['current_grading'][grade]['count'] += 1
                
                # Over/Under/At hesabla
                if current_salary > current_grade_salary * 1.02:  # 2% tolerans
                    analysis[position]['current_grading'][grade]['over'] += 1
                elif current_salary < current_grade_salary * 0.98:
                    analysis[position]['current_grading'][grade]['under'] += 1
                else:
                    analysis[position]['current_grading'][grade]['at'] += 1
            
            # Hər scenario üçün
            for scenario in scenarios:
                scenario_name = scenario.name
                scenario_data = defaultdict(lambda: {
                    'count': 0,
                    'over': 0,
                    'at': 0,
                    'under': 0
                })
                
                for emp in position_employees:
                    grade = emp['grading_level']
                    current_salary = self._get_salary_for_employee(emp, current_scenario)
                    scenario_salary = self._get_grade_salary(scenario, grade)
                    
                    scenario_data[grade]['count'] += 1
                    
                    if current_salary > scenario_salary * 1.02:
                        scenario_data[grade]['over'] += 1
                    elif current_salary < scenario_salary * 0.98:
                        scenario_data[grade]['under'] += 1
                    else:
                        scenario_data[grade]['at'] += 1
                
                analysis[position]['scenarios'][scenario_name] = dict(scenario_data)
            
            # Convert defaultdict to dict
            analysis[position]['current_grading'] = dict(analysis[position]['current_grading'])
        
        return analysis
    
    def _get_grade_salary(self, scenario, grading_level):
        """Grading level üçün scenario-dan median (M) dəyərini götür"""
        if not grading_level or not scenario.calculated_grades:
            return 0
        
        parts = grading_level.split('_')
        if len(parts) != 2:
            return 0
        
        position_short, level = parts
        
        for pos_name, grades in scenario.calculated_grades.items():
            if isinstance(grades, dict):
                # Position uyğunluğunu yoxla
                if any(x in pos_name.upper() for x in [position_short, position_short.replace('_', ' ')]):
                    return float(grades.get(level, 0) or 0)
        
        return 0
    
    def _build_underpaid_overpaid_lists(self, current_scenario, scenarios, employees):
        """
        Şəkil 1-in alt hissəsi: Underpaid və Overpaid employee list-ləri
        """
        result = {}
        
        for scenario in scenarios:
            scenario_name = scenario.name
            underpaid = []
            overpaid = []
            
            for emp in employees:
                current_salary = self._get_salary_for_employee(emp, current_scenario)
                scenario_salary = self._get_salary_for_employee(emp, scenario)
                
                diff_percent = 0
                if current_salary > 0:
                    diff_percent = ((scenario_salary - current_salary) / current_salary) * 100
                
                employee_info = {
                    'employee_id': emp['employee_id'],
                    'employee_name': emp['full_name'],
                    'position': emp['position_group__name'],
                    'department': emp['department__name'],
                    'start_date': emp['start_date'],
                    'current_salary': round(current_salary),
                    'scenario_salary': round(scenario_salary),
                    'difference': round(scenario_salary - current_salary),
                    'difference_percent': round(diff_percent, 1),
                    'grading_level': emp['grading_level']
                }
                
                if scenario_salary < current_salary * 0.98:  # 2% tolerans
                    overpaid.append(employee_info)
                elif scenario_salary > current_salary * 1.02:
                    underpaid.append(employee_info)
            
            # Sort
            underpaid.sort(key=lambda x: x['difference'], reverse=True)
            overpaid.sort(key=lambda x: abs(x['difference']), reverse=True)
            
            result[scenario_name] = {
                'underpaid': underpaid,
                'overpaid': overpaid
            }
        
        return result
    
    def _build_scenarios_percentage_comparison(self, current_scenario, scenarios):
        """
        Şəkil 3: Scenarios Comparison - Percentage Table
        Hər scenario-nun current-dən faiz fərqi
        """
        result = {}
        
        if not current_scenario.calculated_grades:
            return result
        
        # Hər position üçün
        for position_name in current_scenario.grade_order:
            current_grades = current_scenario.calculated_grades.get(position_name, {})
            
            if not isinstance(current_grades, dict):
                continue
            
            result[position_name] = {
                'current': {
                    'LD': float(current_grades.get('LD', 0) or 0),
                    'LQ': float(current_grades.get('LQ', 0) or 0),
                    'M': float(current_grades.get('M', 0) or 0),
                    'UQ': float(current_grades.get('UQ', 0) or 0),
                    'UD': float(current_grades.get('UD', 0) or 0)
                },
                'scenarios': {}
            }
            
            # Hər scenario ilə müqayisə
            for scenario in scenarios:
                scenario_name = scenario.name
                scenario_grades = scenario.calculated_grades.get(position_name, {})
                
                if not isinstance(scenario_grades, dict):
                    continue
                
                scenario_comparison = {}
                
                for level in ['LD', 'LQ', 'M', 'UQ', 'UD']:
                    current_value = float(current_grades.get(level, 0) or 0)
                    scenario_value = float(scenario_grades.get(level, 0) or 0)
                    
                    diff_percent = 0
                    if current_value > 0:
                        diff_percent = ((scenario_value - current_value) / current_value) * 100
                    
                    scenario_comparison[level] = {
                        'value': round(scenario_value),
                        'diff_percent': round(diff_percent, 1),
                        'diff_amount': round(scenario_value - current_value)
                    }
                
                result[position_name]['scenarios'][scenario_name] = scenario_comparison
        
        return result
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
    pagination_class = ModernPagination
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['scenario', 'action', 'performed_by']
    ordering = ['-timestamp']
    
    def get_queryset(self):
        return ScenarioHistory.objects.select_related(
            'scenario', 'performed_by', 'previous_current_scenario'
        )