# grading/serializers.py - UPDATED for 4 horizontal intervals

from rest_framework import serializers
from .models import GradingSystem, SalaryGrade, SalaryScenario, ScenarioHistory
from api.models import PositionGroup

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
    """List serializer for draft scenarios matching frontend format"""
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    is_calculated = serializers.SerializerMethodField()
    balance_score = serializers.SerializerMethodField()
    grading_system_name = serializers.CharField(source='grading_system.name', read_only=True)
    
    # Format data to match frontend structure
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
        vertical_avg = float(obj.vertical_avg)
        horizontal_avg = float(obj.horizontal_avg)
        deviation = abs(vertical_avg - horizontal_avg)
        return (vertical_avg + horizontal_avg) / (1 + deviation) if (vertical_avg + horizontal_avg) > 0 else 0
    
    def get_data(self, obj):
        """Format data to match frontend structure"""
        return {
            'baseValue1': float(obj.base_value),
            'gradeOrder': obj.grade_order,
            'grades': obj.calculated_grades,
            'verticalAvg': float(obj.vertical_avg),
            'horizontalAvg': float(obj.horizontal_avg)
        }

class SalaryScenarioDetailSerializer(serializers.ModelSerializer):
    """Detail serializer for scenario display"""
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    applied_by_name = serializers.CharField(source='applied_by.get_full_name', read_only=True)
    is_calculated = serializers.SerializerMethodField()
    grading_system_name = serializers.CharField(source='grading_system.name', read_only=True)
    
    # Format data to match frontend structure
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
        """Format data to match frontend structure"""
        return {
            'baseValue1': float(obj.base_value),
            'gradeOrder': obj.grade_order,
            'grades': obj.calculated_grades,
            'verticalAvg': float(obj.vertical_avg),
            'horizontalAvg': float(obj.horizontal_avg)
        }

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