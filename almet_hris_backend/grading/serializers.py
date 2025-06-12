# grading/serializers.py - FIXED: Removed competitiveness/riskLevel, Enhanced data display

from rest_framework import serializers
from .models import GradingSystem, SalaryGrade, SalaryScenario, ScenarioHistory
from api.models import PositionGroup
import logging

logger = logging.getLogger(__name__)

# --- HELPER SERIALIZERS (Updated for 4 intervals) ---

class _GradeValueSerializer(serializers.Serializer):
    """
    Helper serializer for a single grade's details.
    UPDATED: Now includes horizontal_intervals structure
    """
    LD = serializers.CharField(allow_blank=True, required=False)
    LQ = serializers.CharField(allow_blank=True, required=False)
    M = serializers.CharField(allow_blank=True, required=False)
    UQ = serializers.CharField(allow_blank=True, required=False)
    UD = serializers.CharField(allow_blank=True, required=False)
    
    # The following are sometimes present in the structure
    vertical = serializers.FloatField(required=False, allow_null=True)
    
    # UPDATED: 4 horizontal intervals instead of single horizontal
    horizontal_intervals = serializers.DictField(
        child=serializers.FloatField(min_value=0, max_value=100),
        required=False,
        allow_empty=True
    )

class _HorizontalIntervalsSerializer(serializers.Serializer):
    """NEW: Helper serializer for 4 horizontal interval inputs."""
    LD_to_LQ = serializers.FloatField(min_value=0, max_value=100, required=False, allow_null=True)
    LQ_to_M = serializers.FloatField(min_value=0, max_value=100, required=False, allow_null=True)
    M_to_UQ = serializers.FloatField(min_value=0, max_value=100, required=False, allow_null=True)
    UQ_to_UD = serializers.FloatField(min_value=0, max_value=100, required=False, allow_null=True)

class _RateInputSerializer(serializers.Serializer):
    """UPDATED: Helper serializer for vertical + 4 horizontal interval inputs."""
    vertical = serializers.FloatField(min_value=0, max_value=100, required=False, allow_null=True)
    horizontal_intervals = _HorizontalIntervalsSerializer(required=False)

# --- EXISTING SERIALIZERS (Updated where needed) ---

class CurrentStructureSerializer(serializers.Serializer):
    """Serializer for the current grade structure, matching frontend 'currentData'."""
    id = serializers.CharField()
    name = serializers.CharField()
    grades = serializers.DictField(child=_GradeValueSerializer(), required=False)
    gradeOrder = serializers.ListField(child=serializers.CharField())
    verticalAvg = serializers.FloatField()
    horizontalAvg = serializers.FloatField()
    baseValue1 = serializers.FloatField()
    status = serializers.CharField()
    grading_system_id = serializers.IntegerField(required=False, allow_null=True)
    grading_system_name = serializers.CharField(required=False, allow_blank=True, allow_null=True)

class DynamicCalculationRequestSerializer(serializers.Serializer):
    """UPDATED: Serializer for validating the dynamic calculation request with 4 intervals."""
    baseValue1 = serializers.DecimalField(max_digits=15, decimal_places=2, min_value=1)
    grades = serializers.DictField(child=_RateInputSerializer())

class DynamicCalculationResponseSerializer(serializers.Serializer):
    """Serializer for the dynamic calculation response."""
    calculatedOutputs = serializers.DictField(child=_GradeValueSerializer())
    success = serializers.BooleanField(default=True)

class ScenarioSaveRequestSerializer(serializers.Serializer):
    """UPDATED: Serializer for validating the 'save draft' request with 4 intervals."""
    name = serializers.CharField(max_length=100)
    description = serializers.CharField(allow_blank=True, required=False)
    baseValue1 = serializers.DecimalField(max_digits=15, decimal_places=2, min_value=1)
    gradeOrder = serializers.ListField(child=serializers.CharField())
    grades = serializers.DictField(child=_RateInputSerializer())
    calculatedOutputs = serializers.DictField(child=_GradeValueSerializer())

# --- EXISTING SERIALIZERS (Unchanged) ---

class GradingSystemSerializer(serializers.ModelSerializer):
    salary_grades_count = serializers.SerializerMethodField()
    scenarios_count = serializers.SerializerMethodField()
    current_scenario = serializers.SerializerMethodField()
    
    class Meta:
        model = GradingSystem
        fields = [
            'id', 'name', 'description', 'is_active', 'base_currency',
            'salary_grades_count', 'scenarios_count', 'current_scenario',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_salary_grades_count(self, obj):
        return obj.salary_grades.count()
    
    def get_scenarios_count(self, obj):
        return obj.scenarios.count()
    
    def get_current_scenario(self, obj):
        try:
            current = obj.scenarios.get(status='CURRENT')
            return {'id': str(current.id), 'name': current.name}
        except SalaryScenario.DoesNotExist:
            return None

class SalaryGradeSerializer(serializers.ModelSerializer):
    position_group_name = serializers.CharField(source='position_group.get_name_display', read_only=True)
    hierarchy_level = serializers.IntegerField(source='position_group.hierarchy_level', read_only=True)
    
    class Meta:
        model = SalaryGrade
        fields = [
            'id', 'grading_system', 'position_group', 'position_group_name', 
            'hierarchy_level', 'lower_decile', 'lower_quartile', 'median', 
            'upper_quartile', 'upper_decile', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

class SalaryScenarioListSerializer(serializers.ModelSerializer):
    """FIXED: List serializer for draft scenarios (removed competitiveness/riskLevel)"""
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    is_calculated = serializers.SerializerMethodField()
    balance_score = serializers.SerializerMethodField()
    grading_system_name = serializers.CharField(source='grading_system.name', read_only=True)
    
    # Format data to match frontend structure - ENHANCED
    data = serializers.SerializerMethodField()
    
    class Meta:
        model = SalaryScenario
        fields = [
            'id', 'name', 'status', 'grading_system_name', 'base_value', 
            'vertical_avg', 'horizontal_avg', 'metrics', 'data',
            'is_calculated', 'balance_score', 'created_by_name', 
            'created_at', 'calculation_timestamp'
        ]
    
    def get_is_calculated(self, obj):
        return bool(obj.calculated_grades and obj.calculation_timestamp)
    
    def get_balance_score(self, obj):
        """ENHANCED: Safe balance score calculation"""
        try:
            vertical_avg = float(obj.vertical_avg) if obj.vertical_avg else 0
            horizontal_avg = float(obj.horizontal_avg) if obj.horizontal_avg else 0
            
            if vertical_avg == 0 and horizontal_avg == 0:
                return 0
                
            deviation = abs(vertical_avg - horizontal_avg)
            return (vertical_avg + horizontal_avg) / (1 + deviation)
        except (ValueError, TypeError):
            return 0
    
    def get_data(self, obj):
        """ENHANCED: Format data with proper validation"""
        # Ensure calculated_grades exists and is properly formatted
        calculated_grades = {}
        if obj.calculated_grades and isinstance(obj.calculated_grades, dict):
            calculated_grades = obj.calculated_grades
        
        # Ensure grade_order exists
        grade_order = obj.grade_order if obj.grade_order else []
        
        # Fill missing grades with proper structure
        for grade_name in grade_order:
            if grade_name not in calculated_grades:
                calculated_grades[grade_name] = {
                    'LD': 0, 'LQ': 0, 'M': 0, 'UQ': 0, 'UD': 0
                }
            else:
                # Ensure all required fields exist
                grade_data = calculated_grades[grade_name]
                if isinstance(grade_data, dict):
                    for field in ['LD', 'LQ', 'M', 'UQ', 'UD']:
                        if field not in grade_data or grade_data[field] is None:
                            grade_data[field] = 0
                else:
                    # Invalid grade data structure
                    calculated_grades[grade_name] = {
                        'LD': 0, 'LQ': 0, 'M': 0, 'UQ': 0, 'UD': 0
                    }
        
        return {
            'baseValue1': float(obj.base_value) if obj.base_value else 0,
            'gradeOrder': grade_order,
            'grades': calculated_grades,
            'verticalAvg': float(obj.vertical_avg) if obj.vertical_avg else 0,
            'horizontalAvg': float(obj.horizontal_avg) if obj.horizontal_avg else 0
        }

class SalaryScenarioDetailSerializer(serializers.ModelSerializer):
    """ENHANCED: Detail serializer with better data validation"""
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    applied_by_name = serializers.CharField(source='applied_by.get_full_name', read_only=True)
    is_calculated = serializers.SerializerMethodField()
    grading_system_name = serializers.CharField(source='grading_system.name', read_only=True)
    
    # ENHANCED: Format data to match frontend structure with validation
    data = serializers.SerializerMethodField()
    
    class Meta:
        model = SalaryScenario
        fields = [
            'id', 'name', 'description', 'status', 'grading_system_name',
            'base_value', 'grade_order', 'input_rates', 'calculated_grades', 
            'vertical_avg', 'horizontal_avg', 'metrics', 'data',
            'is_calculated', 'created_by_name', 'applied_by_name',
            'created_at', 'calculation_timestamp', 'applied_at'
        ]
    
    def get_is_calculated(self, obj):
        return bool(obj.calculated_grades and obj.calculation_timestamp)
    
    def get_data(self, obj):
        """FIXED: Data formatting with comprehensive validation for detail modal"""
        logger.info(f"=== DETAIL SERIALIZER DATA FORMATTING for {obj.name} ===")
        
        # Validate calculated_grades
        calculated_grades = {}
        if obj.calculated_grades:
            if isinstance(obj.calculated_grades, dict):
                calculated_grades = obj.calculated_grades.copy()
                logger.info(f"Found calculated_grades: {calculated_grades}")
            else:
                logger.warning(f"Invalid calculated_grades type: {type(obj.calculated_grades)}")
        else:
            logger.info("No calculated_grades found")
        
        # Validate grade_order
        grade_order = []
        if obj.grade_order:
            if isinstance(obj.grade_order, list):
                grade_order = obj.grade_order.copy()
                logger.info(f"Found grade_order: {grade_order}")
            else:
                logger.warning(f"Invalid grade_order type: {type(obj.grade_order)}")
        else:
            logger.info("No grade_order found")
        
        # FIXED: Extract global horizontal intervals from input_rates
        global_horizontal_intervals = {
            'LD_to_LQ': 0,
            'LQ_to_M': 0,
            'M_to_UQ': 0,
            'UQ_to_UD': 0
        }
        
        if obj.input_rates and isinstance(obj.input_rates, dict):
            # Find first position with horizontal intervals
            for grade_name in grade_order:
                grade_input_data = obj.input_rates.get(grade_name, {})
                if isinstance(grade_input_data, dict):
                    intervals = grade_input_data.get('horizontal_intervals', {})
                    if intervals and isinstance(intervals, dict):
                        # Update global intervals with found values
                        for key in global_horizontal_intervals.keys():
                            if key in intervals and intervals[key] is not None:
                                try:
                                    global_horizontal_intervals[key] = float(intervals[key])
                                except (ValueError, TypeError):
                                    pass
                        logger.info(f"Found horizontal intervals in {grade_name}: {intervals}")
                        break
        
        logger.info(f"Global horizontal intervals: {global_horizontal_intervals}")
        
        # ENHANCED: Fill missing grades and validate existing ones
        for grade_name in grade_order:
            if grade_name not in calculated_grades:
                logger.info(f"Adding missing grade data for {grade_name}")
                calculated_grades[grade_name] = {
                    'LD': 0, 'LQ': 0, 'M': 0, 'UQ': 0, 'UD': 0
                }
            else:
                # Validate existing grade data
                grade_data = calculated_grades[grade_name]
                if isinstance(grade_data, dict):
                    # Ensure all required fields exist with valid values
                    for field in ['LD', 'LQ', 'M', 'UQ', 'UD']:
                        if field not in grade_data:
                            logger.info(f"Adding missing field {field} for {grade_name}")
                            grade_data[field] = 0
                        else:
                            # Validate field value
                            field_value = grade_data[field]
                            if field_value is None or field_value == '':
                                logger.info(f"Fixing null/empty field {field} for {grade_name}")
                                grade_data[field] = 0
                            else:
                                try:
                                    # Ensure it's a valid number
                                    grade_data[field] = float(field_value)
                                except (ValueError, TypeError):
                                    logger.warning(f"Invalid value for {field} in {grade_name}: {field_value}")
                                    grade_data[field] = 0
                else:
                    logger.warning(f"Invalid grade data structure for {grade_name}: {type(grade_data)}")
                    calculated_grades[grade_name] = {
                        'LD': 0, 'LQ': 0, 'M': 0, 'UQ': 0, 'UD': 0
                    }
        
        # FIXED: Validate averages using actual database values
        vertical_avg = 0
        horizontal_avg = 0
        
        try:
            if obj.vertical_avg is not None:
                vertical_avg = float(obj.vertical_avg)
                logger.info(f"Using stored vertical_avg: {vertical_avg}")
        except (ValueError, TypeError):
            logger.warning(f"Invalid vertical_avg: {obj.vertical_avg}")
            vertical_avg = 0
        
        try:
            if obj.horizontal_avg is not None:
                horizontal_avg = float(obj.horizontal_avg)
                logger.info(f"Using stored horizontal_avg: {horizontal_avg}")
        except (ValueError, TypeError):
            logger.warning(f"Invalid horizontal_avg: {obj.horizontal_avg}")
            horizontal_avg = 0
        
        # ENHANCED: Validate base_value
        base_value = 0
        try:
            if obj.base_value is not None:
                base_value = float(obj.base_value)
        except (ValueError, TypeError):
            logger.warning(f"Invalid base_value: {obj.base_value}")
            base_value = 0
        
        result = {
            'baseValue1': base_value,
            'gradeOrder': grade_order,
            'grades': calculated_grades,
            'globalHorizontalIntervals': global_horizontal_intervals,  # FIXED: Include global intervals
            'verticalAvg': vertical_avg,
            'horizontalAvg': horizontal_avg,
            'hasCalculation': bool(obj.calculated_grades and obj.calculation_timestamp),
            'isComplete': bool(calculated_grades and all(
                isinstance(grade, dict) and sum(float(v) for v in grade.values() if v is not None) > 0 
                for grade in calculated_grades.values()
            ))
        }
        
        logger.info(f"Final data result:")
        logger.info(f"  verticalAvg: {result['verticalAvg']}")
        logger.info(f"  horizontalAvg: {result['horizontalAvg']}")
        logger.info(f"  globalHorizontalIntervals: {result['globalHorizontalIntervals']}")
        logger.info(f"=== DETAIL SERIALIZER DATA FORMATTING END ===")
        
        return result


class SalaryScenarioCreateSerializer(serializers.ModelSerializer):
    """UPDATED: Create/Update serializer for scenarios with 4 interval validation"""
    
    class Meta:
        model = SalaryScenario
        fields = [
            'name', 'description', 'grading_system', 'base_value', 
            'grade_order', 'input_rates'
        ]
    
    def validate_base_value(self, value):
        if value <= 0:
            raise serializers.ValidationError("Base value must be greater than 0")
        return value
    
    def validate_input_rates(self, value):
        """UPDATED: Validate input rates format with 4 intervals"""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Input rates must be a dictionary")
        
        for grade_name, rates in value.items():
            if not isinstance(rates, dict):
                raise serializers.ValidationError(f"Rates for {grade_name} must be a dictionary")
            
            # Validate vertical rate
            if 'vertical' in rates and rates['vertical'] is not None:
                try:
                    vertical_value = float(rates['vertical'])
                    if vertical_value < 0 or vertical_value > 100:
                        raise serializers.ValidationError(
                            f"Vertical rate for {grade_name} must be between 0-100"
                        )
                except (ValueError, TypeError):
                    raise serializers.ValidationError(
                        f"Invalid vertical rate for {grade_name}"
                    )
            
            # UPDATED: Validate 4 horizontal intervals
            if 'horizontal_intervals' in rates and rates['horizontal_intervals']:
                intervals = rates['horizontal_intervals']
                if not isinstance(intervals, dict):
                    raise serializers.ValidationError(
                        f"Horizontal intervals for {grade_name} must be a dictionary"
                    )
                
                interval_names = ['LD_to_LQ', 'LQ_to_M', 'M_to_UQ', 'UQ_to_UD']
                for interval_name in interval_names:
                    if interval_name in intervals and intervals[interval_name] is not None:
                        try:
                            interval_value = float(intervals[interval_name])
                            if interval_value < 0 or interval_value > 100:
                                raise serializers.ValidationError(
                                    f"Horizontal interval {interval_name} for {grade_name} must be between 0-100"
                                )
                        except (ValueError, TypeError):
                            raise serializers.ValidationError(
                                f"Invalid horizontal interval {interval_name} for {grade_name}"
                            )
        
        return value
    
    def create(self, validated_data):
        validated_data['created_by'] = self.context['request'].user
        
        # Create scenario
        scenario = SalaryScenario.objects.create(**validated_data)
        
        # Calculate averages
        scenario.calculate_averages()
        scenario.save()
        
        return scenario

class ScenarioHistorySerializer(serializers.ModelSerializer):
    performed_by_name = serializers.CharField(source='performed_by.get_full_name', read_only=True)
    scenario_name = serializers.CharField(source='scenario.name', read_only=True)
    previous_scenario_name = serializers.CharField(source='previous_current_scenario.name', read_only=True)
    
    class Meta:
        model = ScenarioHistory
        fields = [
            'id', 'scenario', 'scenario_name', 'action', 'previous_scenario_name',
            'changes_made', 'performed_by', 'performed_by_name', 'timestamp'
        ]
        read_only_fields = ['id', 'timestamp']

# Position Group serializer for dropdowns
class PositionGroupDropdownSerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(source='get_name_display', read_only=True)
    
    class Meta:
        model = PositionGroup
        fields = ['id', 'name', 'display_name', 'hierarchy_level', 'is_active']