# grading/serializers.py

from rest_framework import serializers
from .models import (
    GradingSystem, SalaryGrade, GrowthRate, HorizontalRate, 
    SalaryScenario, ScenarioHistory
)
from api.models import PositionGroup

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
    grading_system_name = serializers.CharField(source='grading_system.name', read_only=True)
    
    class Meta:
        model = SalaryGrade
        fields = [
            'id', 'grading_system', 'grading_system_name', 'position_group', 
            'position_group_name', 'hierarchy_level', 'lower_decile', 
            'lower_quartile', 'median', 'upper_quartile', 'upper_decile',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

class GrowthRateSerializer(serializers.ModelSerializer):
    from_position_name = serializers.CharField(source='from_position.get_name_display', read_only=True)
    to_position_name = serializers.CharField(source='to_position.get_name_display', read_only=True)
    from_hierarchy_level = serializers.IntegerField(source='from_position.hierarchy_level', read_only=True)
    to_hierarchy_level = serializers.IntegerField(source='to_position.hierarchy_level', read_only=True)
    
    class Meta:
        model = GrowthRate
        fields = [
            'id', 'grading_system', 'from_position', 'from_position_name', 
            'from_hierarchy_level', 'to_position', 'to_position_name', 
            'to_hierarchy_level', 'vertical_rate', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']

class HorizontalRateSerializer(serializers.ModelSerializer):
    position_group_name = serializers.CharField(source='position_group.get_name_display', read_only=True)
    hierarchy_level = serializers.IntegerField(source='position_group.hierarchy_level', read_only=True)
    transition_display = serializers.CharField(source='get_transition_type_display', read_only=True)
    
    class Meta:
        model = HorizontalRate
        fields = [
            'id', 'grading_system', 'position_group', 'position_group_name', 
            'hierarchy_level', 'transition_type', 'transition_display', 
            'horizontal_rate', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']

class PositionGroupSimpleSerializer(serializers.ModelSerializer):
    """Simple serializer for position groups in dropdowns"""
    display_name = serializers.CharField(source='get_name_display', read_only=True)
    
    class Meta:
        model = PositionGroup
        fields = ['id', 'name', 'display_name', 'hierarchy_level']

class SalaryScenarioListSerializer(serializers.ModelSerializer):
    grading_system_name = serializers.CharField(source='grading_system.name', read_only=True)
    base_position_name = serializers.CharField(source='base_position.get_name_display', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    applied_by_name = serializers.CharField(source='applied_by.get_full_name', read_only=True)
    is_calculated = serializers.SerializerMethodField()
    completion_percentage = serializers.SerializerMethodField()
    
    class Meta:
        model = SalaryScenario
        fields = [
            'id', 'name', 'description', 'status', 'grading_system_name',
            'base_position_name', 'base_value', 'is_calculated', 'completion_percentage',
            'created_by_name', 'applied_by_name', 'created_at', 
            'calculation_timestamp', 'applied_at'
        ]
    
    def get_is_calculated(self, obj):
        return bool(obj.calculated_grades and obj.calculation_timestamp)
    
    def get_completion_percentage(self, obj):
        """Calculate how complete the scenario configuration is"""
        if not obj.custom_vertical_rates and not obj.custom_horizontal_rates:
            return 0
        
        # Count total positions
        total_positions = PositionGroup.objects.filter(is_active=True).count()
        total_vertical_needed = total_positions - 1  # All except top position
        total_horizontal_needed = total_positions * 4  # 4 transitions per position
        
        # Count completed rates
        completed_vertical = len([r for r in obj.custom_vertical_rates.values() if r is not None and r != ''])
        completed_horizontal = 0
        for rates in obj.custom_horizontal_rates.values():
            if isinstance(rates, dict):
                completed_horizontal += len([r for r in rates.values() if r is not None and r != ''])
        
        total_completed = completed_vertical + completed_horizontal
        total_needed = total_vertical_needed + total_horizontal_needed
        
        return round((total_completed / total_needed) * 100, 1) if total_needed > 0 else 0

class SalaryScenarioDetailSerializer(serializers.ModelSerializer):
    grading_system = GradingSystemSerializer(read_only=True)
    base_position = PositionGroupSimpleSerializer(read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    applied_by_name = serializers.CharField(source='applied_by.get_full_name', read_only=True)
    is_calculated = serializers.SerializerMethodField()
    available_positions = serializers.SerializerMethodField()
    completion_stats = serializers.SerializerMethodField()
    
    class Meta:
        model = SalaryScenario
        fields = [
            'id', 'name', 'description', 'status', 'grading_system', 
            'base_position', 'base_value', 'custom_vertical_rates', 
            'custom_horizontal_rates', 'calculated_grades', 'is_calculated',
            'available_positions', 'completion_stats', 'calculation_timestamp', 
            'created_by_name', 'applied_by_name', 'created_at', 'updated_at', 'applied_at'
        ]
    
    def get_is_calculated(self, obj):
        return bool(obj.calculated_grades and obj.calculation_timestamp)
    
    def get_available_positions(self, obj):
        """Get all position groups for this scenario"""
        positions = PositionGroup.objects.filter(is_active=True).order_by('hierarchy_level')
        return PositionGroupSimpleSerializer(positions, many=True).data
    
    def get_completion_stats(self, obj):
        """Get detailed completion statistics"""
        positions = PositionGroup.objects.filter(is_active=True)
        total_positions = positions.count()
        total_vertical_needed = total_positions - 1
        total_horizontal_needed = total_positions * 4
        
        # Count completed rates
        completed_vertical = len([r for r in obj.custom_vertical_rates.values() if r is not None and r != ''])
        completed_horizontal = 0
        for rates in obj.custom_horizontal_rates.values():
            if isinstance(rates, dict):
                completed_horizontal += len([r for r in rates.values() if r is not None and r != ''])
        
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

class SalaryScenarioCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SalaryScenario
        fields = [
            'name', 'description', 'grading_system', 'base_position', 'base_value',
            'custom_vertical_rates', 'custom_horizontal_rates'
        ]
    
    def validate_base_value(self, value):
        if value <= 0:
            raise serializers.ValidationError("Base value must be greater than 0")
        return value
    
    def validate_custom_vertical_rates(self, value):
        """Validate custom vertical rates format"""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Custom vertical rates must be a dictionary")
        
        for pos_id, rate in value.items():
            try:
                int(pos_id)  # Position ID should be convertible to int
                if rate is not None and rate != '':
                    float(rate)  # Rate should be convertible to float
                    if float(rate) < 0:
                        raise serializers.ValidationError(f"Vertical rate for position {pos_id} cannot be negative")
            except (ValueError, TypeError):
                raise serializers.ValidationError(f"Invalid vertical rate data for position {pos_id}")
        
        return value
    
    def validate_custom_horizontal_rates(self, value):
        """Validate custom horizontal rates format"""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Custom horizontal rates must be a dictionary")
        
        valid_transitions = ['LD_TO_LQ', 'LQ_TO_M', 'M_TO_UQ', 'UQ_TO_UD']
        
        for pos_id, rates in value.items():
            try:
                int(pos_id)  # Position ID should be convertible to int
                if not isinstance(rates, dict):
                    raise serializers.ValidationError(f"Rates for position {pos_id} must be a dictionary")
                
                for transition, rate in rates.items():
                    if transition not in valid_transitions:
                        raise serializers.ValidationError(f"Invalid transition type: {transition}")
                    
                    if rate is not None and rate != '':
                        float(rate)  # Rate should be convertible to float
                        if float(rate) < 0:
                            raise serializers.ValidationError(f"Horizontal rate for position {pos_id}, transition {transition} cannot be negative")
            except (ValueError, TypeError):
                raise serializers.ValidationError(f"Invalid horizontal rate data for position {pos_id}")
        
        return value
    
    def create(self, validated_data):
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)

class ScenarioHistorySerializer(serializers.ModelSerializer):
    performed_by_name = serializers.CharField(source='performed_by.get_full_name', read_only=True)
    previous_scenario_name = serializers.CharField(source='previous_current_scenario.name', read_only=True)
    scenario_name = serializers.CharField(source='scenario.name', read_only=True)
    
    class Meta:
        model = ScenarioHistory
        fields = [
            'id', 'scenario', 'scenario_name', 'action', 'previous_scenario_name', 
            'changes_made', 'performed_by', 'performed_by_name', 'timestamp'
        ]
        read_only_fields = ['id', 'timestamp']

class GradingSystemCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating grading systems with default data"""
    class Meta:
        model = GradingSystem
        fields = ['name', 'description', 'base_currency']
    
    def create(self, validated_data):
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)

# Dropdown serializers for frontend
class GradingDropdownsSerializer(serializers.Serializer):
    """Serializer for grading system dropdown data"""
    grading_systems = GradingSystemSerializer(many=True, read_only=True)
    position_groups = PositionGroupSimpleSerializer(many=True, read_only=True)
    transition_types = serializers.ListField(
        child=serializers.DictField(),
        read_only=True
    )

# Dynamic scenario serializers
class DynamicScenarioInitSerializer(serializers.Serializer):
    """Serializer for dynamic scenario initialization response"""
    base_info = serializers.DictField()
    positions = PositionGroupSimpleSerializer(many=True)
    vertical_rates = serializers.DictField()
    horizontal_rates = serializers.DictField()

class DynamicCalculationRequestSerializer(serializers.Serializer):
    """Serializer for dynamic calculation request"""
    base_position = serializers.IntegerField()
    base_value = serializers.DecimalField(max_digits=15, decimal_places=2)
    vertical_rates = serializers.DictField(required=False, default=dict)
    horizontal_rates = serializers.DictField(required=False, default=dict)

class CompletionStatsSerializer(serializers.Serializer):
    """Serializer for completion statistics"""
    vertical_completion = serializers.DictField()
    horizontal_completion = serializers.DictField()
    overall_completion = serializers.DictField()

class DynamicCalculationResponseSerializer(serializers.Serializer):
    """Serializer for dynamic calculation response"""
    success = serializers.BooleanField()
    calculated_grades = serializers.DictField()
    completion_stats = CompletionStatsSerializer()