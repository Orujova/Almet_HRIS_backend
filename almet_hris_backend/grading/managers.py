# grading/managers.py - CORRECTED HORIZONTAL LOGIC WITH 4 INTERVALS

from django.db import models
from django.utils import timezone
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

class SalaryCalculationManager:
    """Manager for salary calculations with CORRECT horizontal logic - 4 intervals"""
    
    @staticmethod
    def get_position_groups_from_db():
        """Get position groups from database in hierarchy order"""
        from api.models import PositionGroup
        try:
            positions = PositionGroup.objects.filter(is_active=True).order_by('hierarchy_level')
            position_list = list(positions.values_list('name', 'hierarchy_level'))
            logger.info(f"Position groups order (ASC): {position_list}")
            logger.info(f"Total position groups found: {positions.count()}")
            return positions
        except Exception as e:
            logger.error(f"Error getting position groups: {e}")
            return PositionGroup.objects.none()
    
    @staticmethod
    def create_current_structure_from_db():
        """Create current structure data from database"""
        from .models import SalaryGrade, SalaryScenario
        from api.models import PositionGroup
        
        logger.info("Creating current structure from DB...")
        
        # Get position groups from database
        position_groups = SalaryCalculationManager.get_position_groups_from_db()
        
        if not position_groups.exists():
            logger.error("No position groups found for current structure")
            return None
        
        # Log the order for debugging
        for pos in position_groups:
            logger.info(f"Position: {pos.get_name_display()} (level {pos.hierarchy_level})")
        
        # Try to get current scenario first
        try:
            current_scenario = SalaryScenario.objects.get(status='CURRENT')
            logger.info(f"Found current scenario: {current_scenario.name}")
            
            # Build grade order from database position groups
            grade_order = []
            grades_data = {}
            
            for pos_group in position_groups:
                grade_name = pos_group.get_name_display()
                grade_order.append(grade_name)
                
                if grade_name in current_scenario.calculated_grades:
                    grade_data = current_scenario.calculated_grades[grade_name]
                    grades_data[grade_name] = {
                        'LD': grade_data.get('LD', 0),
                        'LQ': grade_data.get('LQ', 0), 
                        'M': grade_data.get('M', 0),
                        'UQ': grade_data.get('UQ', 0),
                        'UD': grade_data.get('UD', 0),
                        'vertical': 0,
                        'horizontal_intervals': {
                            'LD_to_LQ': 0,
                            'LQ_to_M': 0,
                            'M_to_UQ': 0,
                            'UQ_to_UD': 0
                        }
                    }
            
            logger.info(f"Current structure grade order: {grade_order}")
            logger.info(f"Base value position: {grade_order[-1]} (last = lowest hierarchy)")
            
            return {
                'id': 'current',
                'name': 'Current Structure',
                'grades': grades_data,
                'gradeOrder': grade_order,
                'verticalAvg': float(current_scenario.vertical_avg),
                'horizontalAvg': float(current_scenario.horizontal_avg),
                'baseValue1': float(current_scenario.base_value),
                'status': 'current'
            }
            
        except SalaryScenario.DoesNotExist:
            logger.info("No current scenario, creating empty structure")
            # No current scenario, return empty structure with position groups
            grade_order = []
            grades_data = {}
            
            for pos_group in position_groups:
                grade_name = pos_group.get_name_display()
                grade_order.append(grade_name)
                grades_data[grade_name] = {
                    'LD': 0, 'LQ': 0, 'M': 0, 'UQ': 0, 'UD': 0,
                    'vertical': 0,
                    'horizontal_intervals': {
                        'LD_to_LQ': 0,
                        'LQ_to_M': 0,
                        'M_to_UQ': 0,
                        'UQ_to_UD': 0
                    }
                }
            
            return {
                'id': 'current',
                'name': 'Current Structure',
                'grades': grades_data,
                'gradeOrder': grade_order,
                'verticalAvg': 0.0,
                'horizontalAvg': 0.0,
                'baseValue1': 0,
                'status': 'current'
            }
    
    @staticmethod
    def calculate_scenario_grades(base_value, input_rates, position_groups=None):
        """
        Calculate grades with CORRECTED horizontal logic - 4 intervals
        
        HORIZONTAL LOGIC CORRECTION:
        - Each position has 4 horizontal intervals: LD→LQ→M→UQ→UD
        - Each interval is controlled separately
        - input_rates now contains horizontal_intervals dict for each position
        
        Args:
            base_value: Base salary value (Last position LD)
            input_rates: Dict with position_name -> {
                vertical: %, 
                horizontal_intervals: {
                    'LD_to_LQ': %,
                    'LQ_to_M': %,
                    'M_to_UQ': %,
                    'UQ_to_UD': %
                }
            }
            position_groups: QuerySet of PositionGroup objects (optional)
        """
        logger.info(f"=== GRADE CALCULATION START (4 INTERVALS) ===")
        logger.info(f"Base value: {base_value}")
        logger.info(f"Input rates: {input_rates}")
        
        if position_groups is None:
            position_groups = SalaryCalculationManager.get_position_groups_from_db()
        
        calculated_grades = {}
        
        # Convert queryset to list
        positions_list = list(position_groups)
        logger.info(f"Positions order: {[(p.get_name_display(), p.hierarchy_level) for p in positions_list]}")
        
        if not positions_list:
            logger.error("No positions to calculate")
            return calculated_grades
        
        # Start from LAST position (base position)
        base_position = positions_list[-1]
        current_ld = Decimal(str(base_value))
        
        logger.info(f"Base position: {base_position.get_name_display()} with LD={current_ld}")
        
        # Calculate from base position upwards
        for i in range(len(positions_list) - 1, -1, -1):
            position = positions_list[i]
            position_name = position.get_name_display()
            grade_inputs = input_rates.get(position_name, {})
            
            # Get horizontal intervals - NEW LOGIC
            horizontal_intervals = grade_inputs.get('horizontal_intervals', {})
            
            logger.info(f"Processing {position_name} (level {position.hierarchy_level}): LD={current_ld}")
            logger.info(f"Horizontal intervals: {horizontal_intervals}")
            
            # Calculate horizontal grades for current position with 4 intervals
            grades = SalaryCalculationManager._calculate_horizontal_grades_with_intervals(
                current_ld, horizontal_intervals
            )
            calculated_grades[position_name] = grades
            
            # Calculate LD for next higher position (if exists)
            if i > 0:  # Not the first position
                vertical_input = grade_inputs.get('vertical', 0)
                if vertical_input == '' or vertical_input is None:
                    vertical_rate = Decimal('0')
                else:
                    vertical_rate = Decimal(str(vertical_input))
                
                # Next position LD = Current LD * (1 + vertical_rate/100)
                current_ld = current_ld * (Decimal('1') + vertical_rate / Decimal('100'))
                logger.info(f"Next position LD calculated: {current_ld} (using {position_name} vertical {vertical_rate}%)")
        
        logger.info(f"=== CALCULATION COMPLETE ===")
        logger.info(f"Final result: {calculated_grades}")
        return calculated_grades
    
    @staticmethod
    def _calculate_horizontal_grades_with_intervals(lower_decile, horizontal_intervals):
        """
        NEW: Calculate horizontal grades with 4 separate interval inputs
        
        horizontal_intervals = {
            'LD_to_LQ': 5.0,  # LD→LQ artım faizi
            'LQ_to_M': 5.0,   # LQ→M artım faizi  
            'M_to_UQ': 5.0,   # M→UQ artım faizi
            'UQ_to_UD': 5.0   # UQ→UD artım faizi
        }
        
        Returns:
            dict: {'LD': value, 'LQ': value, 'M': value, 'UQ': value, 'UD': value}
        """
        ld = float(lower_decile)
        
        # Get interval percentages (default to 0 if not provided)
        ld_to_lq = float(horizontal_intervals.get('LD_to_LQ', 0)) / 100
        lq_to_m = float(horizontal_intervals.get('LQ_to_M', 0)) / 100
        m_to_uq = float(horizontal_intervals.get('M_to_UQ', 0)) / 100
        uq_to_ud = float(horizontal_intervals.get('UQ_to_UD', 0)) / 100
        
        # Calculate step by step
        lq = ld * (1 + ld_to_lq)
        m = lq * (1 + lq_to_m)
        uq = m * (1 + m_to_uq)
        ud = uq * (1 + uq_to_ud)
        
        grades = {
            'LD': round(ld),
            'LQ': round(lq),
            'M': round(m),
            'UQ': round(uq),
            'UD': round(ud)
        }
        
        logger.info(f"Horizontal calculation with 4 intervals:")
        logger.info(f"  LD→LQ: {ld_to_lq*100:.1f}% → {ld:.0f} → {lq:.0f}")
        logger.info(f"  LQ→M: {lq_to_m*100:.1f}% → {lq:.0f} → {m:.0f}")
        logger.info(f"  M→UQ: {m_to_uq*100:.1f}% → {m:.0f} → {uq:.0f}")
        logger.info(f"  UQ→UD: {uq_to_ud*100:.1f}% → {uq:.0f} → {ud:.0f}")
        logger.info(f"  Final grades: {grades}")
        
        return grades
    
    @staticmethod
    def calculate_scenario_metrics(scenario_data, current_data):
        """Calculate scenario metrics for comparison"""
        if not scenario_data.get('grades') or not current_data.get('grades'):
            return {}
        
        total_budget_impact = 0
        salary_increases = []
        
        for grade_name in scenario_data.get('gradeOrder', []):
            scenario_grade = scenario_data['grades'].get(grade_name, {})
            current_grade = current_data['grades'].get(grade_name, {})
            
            scenario_median = scenario_grade.get('M', 0)
            current_median = current_grade.get('M', 0)
            
            total_budget_impact += scenario_median
            
            if current_median > 0:
                increase = ((scenario_median - current_median) / current_median) * 100
                salary_increases.append(increase)
        
        avg_salary_increase = sum(salary_increases) / len(salary_increases) if salary_increases else 0
        
        # Calculate competitiveness
        competitiveness = min((scenario_data.get('verticalAvg', 0) + scenario_data.get('horizontalAvg', 0)) * 200, 100)
        
        # Calculate risk level
        max_increase = max(salary_increases) if salary_increases else 0
        if max_increase > 30:
            risk_level = "High"
        elif max_increase > 15:
            risk_level = "Medium"
        else:
            risk_level = "Low"
        
        return {
            'totalBudgetImpact': total_budget_impact,
            'avgSalaryIncrease': avg_salary_increase,
            'competitiveness': competitiveness,
            'riskLevel': risk_level
        }
    
    @staticmethod
    def apply_scenario(scenario_id, user=None):
        """Apply a scenario to current grading system"""
        from .models import SalaryScenario, SalaryGrade, ScenarioHistory
        
        scenario = SalaryScenario.objects.get(id=scenario_id)
        
        if scenario.status != 'DRAFT':
            raise ValueError("Only draft scenarios can be applied")
        
        if not scenario.calculated_grades:
            raise ValueError("Scenario must be calculated before applying")
        
        # Archive current scenario if exists
        try:
            current_scenario = SalaryScenario.objects.get(
                grading_system=scenario.grading_system,
                status='CURRENT'
            )
            current_scenario.status = 'ARCHIVED'
            current_scenario.save()
            
            ScenarioHistory.objects.create(
                scenario=scenario,
                action='APPLIED',
                previous_current_scenario=current_scenario,
                performed_by=user,
                changes_made={
                    'replaced_scenario': current_scenario.name,
                    'archived_previous': True
                }
            )
            
        except SalaryScenario.DoesNotExist:
            ScenarioHistory.objects.create(
                scenario=scenario,
                action='APPLIED',
                performed_by=user,
                changes_made={'first_application': True}
            )
        
        # Apply new scenario
        scenario.status = 'CURRENT'
        scenario.applied_at = timezone.now()
        scenario.applied_by = user
        scenario.save()
        
        # Update actual salary grades
        SalaryGrade.objects.filter(grading_system=scenario.grading_system).delete()
        
        position_groups = SalaryCalculationManager.get_position_groups_from_db()
        position_map = {pos.get_name_display(): pos for pos in position_groups}
        
        salary_grades_created = 0
        for position_name, grades in scenario.calculated_grades.items():
            if position_name in position_map:
                SalaryGrade.objects.create(
                    grading_system=scenario.grading_system,
                    position_group=position_map[position_name],
                    lower_decile=Decimal(str(grades['LD'])),
                    lower_quartile=Decimal(str(grades['LQ'])),
                    median=Decimal(str(grades['M'])),
                    upper_quartile=Decimal(str(grades['UQ'])),
                    upper_decile=Decimal(str(grades['UD']))
                )
                salary_grades_created += 1
        
        logger.info(f"Applied scenario {scenario.name}: created {salary_grades_created} salary grades")
        return scenario
    
    @staticmethod
    def get_balance_score(scenario_data):
        """Calculate balance score matching frontend logic"""
        vertical_avg = scenario_data.get('verticalAvg', 0)
        horizontal_avg = scenario_data.get('horizontalAvg', 0)
        deviation = abs(vertical_avg - horizontal_avg)
        return (vertical_avg + horizontal_avg) / (1 + deviation)
    
    @staticmethod
    def validate_scenario_inputs(base_value, input_rates):
        """Validate scenario inputs with proper type checking - UPDATED for 4 intervals"""
        errors = []
        
        logger.info(f"=== VALIDATION START (4 INTERVALS) ===")
        logger.info(f"Base value: {base_value} (type: {type(base_value)})")
        logger.info(f"Input rates: {input_rates}")
        
        if not base_value or base_value <= 0:
            errors.append("Base value must be greater than 0")
        
        for grade_name, rates in input_rates.items():
            logger.info(f"Validating {grade_name}: {rates}")
            
            if isinstance(rates, dict):
                # Validate vertical rate
                if rates.get('vertical') is not None:
                    vertical = rates['vertical']
                    logger.info(f"Vertical value: {vertical} (type: {type(vertical)})")
                    
                    if vertical == '' or vertical is None:
                        continue
                    
                    try:
                        vertical_float = float(vertical)
                        if vertical_float < 0 or vertical_float > 100:
                            errors.append(f"Vertical rate for {grade_name} must be between 0-100")
                    except (ValueError, TypeError):
                        errors.append(f"Vertical rate for {grade_name} must be a valid number")
                
                # Validate horizontal intervals - NEW
                horizontal_intervals = rates.get('horizontal_intervals', {})
                if horizontal_intervals:
                    interval_names = ['LD_to_LQ', 'LQ_to_M', 'M_to_UQ', 'UQ_to_UD']
                    for interval_name in interval_names:
                        interval_value = horizontal_intervals.get(interval_name)
                        if interval_value is not None and interval_value != '':
                            try:
                                interval_float = float(interval_value)
                                if interval_float < 0 or interval_float > 100:
                                    errors.append(f"Horizontal interval {interval_name} for {grade_name} must be between 0-100")
                            except (ValueError, TypeError):
                                errors.append(f"Horizontal interval {interval_name} for {grade_name} must be a valid number")
        
        logger.info(f"Validation errors: {errors}")
        logger.info(f"=== VALIDATION END ===")
        return errors