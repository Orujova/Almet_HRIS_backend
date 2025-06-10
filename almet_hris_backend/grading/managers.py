# grading/managers.py

from django.db import models
from django.utils import timezone
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

class SalaryCalculationManager:
    """Manager for salary calculations"""
    
    @staticmethod
    def calculate_scenario(scenario):
        """Calculate all salary grades for a scenario"""
        from .models import SalaryGrade, GrowthRate, HorizontalRate
        from api.models import PositionGroup
        
        grading_system = scenario.grading_system
        base_position = scenario.base_position
        base_value = Decimal(str(scenario.base_value))
        
        logger.info(f"Starting calculation for scenario: {scenario.name}")
        logger.info(f"Base position: {base_position.get_name_display()}, Base value: {base_value}")
        
        # Get all position groups ordered by hierarchy level (1=highest level, higher numbers=lower levels)
        positions = PositionGroup.objects.filter(is_active=True).order_by('hierarchy_level')
        
        # Get growth rates and create maps
        vertical_rates = GrowthRate.objects.filter(grading_system=grading_system)
        horizontal_rates = HorizontalRate.objects.filter(grading_system=grading_system)
        
        # Create rate maps for vertical growth (from lower level to higher level)
        vertical_rate_map = {}
        for vr in vertical_rates:
            # Key is the "from" position (lower level), value is rate to get to "to" position (higher level)
            vertical_rate_map[vr.from_position_id] = vr.vertical_rate
        
        # Apply custom vertical rates from scenario
        for pos_id_str, rate in scenario.custom_vertical_rates.items():
            if rate is not None and rate != '':
                vertical_rate_map[int(pos_id_str)] = Decimal(str(rate))
        
        # Create horizontal rate maps
        horizontal_rate_map = {}
        for hr in horizontal_rates:
            if hr.position_group_id not in horizontal_rate_map:
                horizontal_rate_map[hr.position_group_id] = {}
            horizontal_rate_map[hr.position_group_id][hr.transition_type] = hr.horizontal_rate
        
        # Apply custom horizontal rates
        for pos_id_str, rates in scenario.custom_horizontal_rates.items():
            pos_id = int(pos_id_str)
            if pos_id not in horizontal_rate_map:
                horizontal_rate_map[pos_id] = {}
            for transition, rate in rates.items():
                if rate is not None and rate != '':
                    horizontal_rate_map[pos_id][transition] = Decimal(str(rate))
        
        # Calculate grades
        calculated_grades = {}
        
        # Find base position index
        base_pos_idx = None
        for i, pos in enumerate(positions):
            if pos.id == base_position.id:
                base_pos_idx = i
                break
        
        if base_pos_idx is None:
            raise ValueError(f"Base position {base_position.get_name_display()} not found in active positions")
        
        # STEP 1: Calculate base position first (this is typically the lowest grade)
        base_pos = positions[base_pos_idx]
        calculated_grades[base_pos.id] = SalaryCalculationManager._calculate_horizontal_grades(
            base_value, base_pos.id, horizontal_rate_map
        )
        
        logger.info(f"Calculated base position {base_pos.get_name_display()}: {calculated_grades[base_pos.id]}")
        
        # STEP 2: Calculate positions ABOVE base (lower hierarchy numbers = higher organizational levels)
        # This is moving UP the organizational hierarchy (from Blue Collar to VC)
        for i in range(base_pos_idx - 1, -1, -1):
            current_pos = positions[i]
            lower_pos = positions[i + 1]  # The position one level below current
            
            # Get vertical growth rate FROM the lower position TO current position
            vertical_rate = vertical_rate_map.get(lower_pos.id, Decimal('0.0'))
            
            if vertical_rate == Decimal('0.0'):
                raise ValueError(f"No vertical rate defined from {lower_pos.get_name_display()} to {current_pos.get_name_display()}")
            
            # Calculate new Lower Decile for current position
            # Formula: Current_LD = Lower_Position_LD * (1 + vertical_rate/100)
            lower_pos_ld = calculated_grades[lower_pos.id]['lower_decile']
            current_ld = Decimal(str(lower_pos_ld)) * (Decimal('1') + vertical_rate / Decimal('100'))
            
            # Calculate all horizontal grades for this position
            calculated_grades[current_pos.id] = SalaryCalculationManager._calculate_horizontal_grades(
                current_ld, current_pos.id, horizontal_rate_map
            )
            
            logger.info(f"Calculated {current_pos.get_name_display()}: LD={current_ld}, Vertical rate from {lower_pos.get_name_display()}: {vertical_rate}%")
        
        # STEP 3: Calculate positions BELOW base (higher hierarchy numbers = lower organizational levels)
        # This is moving DOWN the organizational hierarchy (from base position to lower levels)
        for i in range(base_pos_idx + 1, len(positions)):
            current_pos = positions[i]
            higher_pos = positions[i - 1]  # The position one level above current
            
            # Get vertical growth rate FROM current position TO higher position
            vertical_rate = vertical_rate_map.get(current_pos.id, Decimal('0.0'))
            
            if vertical_rate == Decimal('0.0'):
                raise ValueError(f"No vertical rate defined from {current_pos.get_name_display()} to {higher_pos.get_name_display()}")
            
            # Calculate new Lower Decile for current position
            # Formula: Current_LD = Higher_Position_LD / (1 + vertical_rate/100)
            higher_pos_ld = calculated_grades[higher_pos.id]['lower_decile']
            current_ld = Decimal(str(higher_pos_ld)) / (Decimal('1') + vertical_rate / Decimal('100'))
            
            # Calculate all horizontal grades for this position
            calculated_grades[current_pos.id] = SalaryCalculationManager._calculate_horizontal_grades(
                current_ld, current_pos.id, horizontal_rate_map
            )
            
            logger.info(f"Calculated {current_pos.get_name_display()}: LD={current_ld}, Vertical rate to {higher_pos.get_name_display()}: {vertical_rate}%")
        
        # Update scenario with calculated results
        scenario.calculated_grades = calculated_grades
        scenario.calculation_timestamp = timezone.now()
        scenario.save()
        
        logger.info(f"Calculation completed for scenario: {scenario.name}")
        return calculated_grades
    
    @staticmethod
    def _calculate_horizontal_grades(lower_decile_value, position_id, horizontal_rate_map):
        """Calculate horizontal grades (LD, LQ, M, UQ, UD) for a position"""
        grades = {'lower_decile': float(lower_decile_value)}
        
        # Get horizontal rates for this position
        pos_rates = horizontal_rate_map.get(position_id, {})
        
        if not pos_rates:
            raise ValueError(f"No horizontal rates defined for position ID {position_id}")
        
        # Calculate each grade step by step: LD → LQ → M → UQ → UD
        current_value = lower_decile_value
        
        # Step 1: Lower Decile to Lower Quartile
        ld_to_lq_rate = pos_rates.get('LD_TO_LQ')
        if ld_to_lq_rate is None:
            raise ValueError(f"Missing LD_TO_LQ rate for position ID {position_id}")
        
        ld_to_lq_rate = Decimal(str(ld_to_lq_rate))
        current_value = current_value * (Decimal('1') + ld_to_lq_rate / Decimal('100'))
        grades['lower_quartile'] = float(current_value)
        
        # Step 2: Lower Quartile to Median
        lq_to_m_rate = pos_rates.get('LQ_TO_M')
        if lq_to_m_rate is None:
            raise ValueError(f"Missing LQ_TO_M rate for position ID {position_id}")
        
        lq_to_m_rate = Decimal(str(lq_to_m_rate))
        current_value = current_value * (Decimal('1') + lq_to_m_rate / Decimal('100'))
        grades['median'] = float(current_value)
        
        # Step 3: Median to Upper Quartile
        m_to_uq_rate = pos_rates.get('M_TO_UQ')
        if m_to_uq_rate is None:
            raise ValueError(f"Missing M_TO_UQ rate for position ID {position_id}")
        
        m_to_uq_rate = Decimal(str(m_to_uq_rate))
        current_value = current_value * (Decimal('1') + m_to_uq_rate / Decimal('100'))
        grades['upper_quartile'] = float(current_value)
        
        # Step 4: Upper Quartile to Upper Decile
        uq_to_ud_rate = pos_rates.get('UQ_TO_UD')
        if uq_to_ud_rate is None:
            raise ValueError(f"Missing UQ_TO_UD rate for position ID {position_id}")
        
        uq_to_ud_rate = Decimal(str(uq_to_ud_rate))
        current_value = current_value * (Decimal('1') + uq_to_ud_rate / Decimal('100'))
        grades['upper_decile'] = float(current_value)
        
        return grades
    
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
            
            # Create history record
            ScenarioHistory.objects.create(
                scenario=scenario,
                action='APPLIED',
                previous_current_scenario=current_scenario,
                performed_by=user,
                changes_made={'replaced_scenario': current_scenario.name}
            )
            
            logger.info(f"Archived previous current scenario: {current_scenario.name}")
        except SalaryScenario.DoesNotExist:
            # No current scenario exists
            ScenarioHistory.objects.create(
                scenario=scenario,
                action='APPLIED',
                performed_by=user,
                changes_made={'first_application': True}
            )
            logger.info("No previous current scenario to archive")
        
        # Apply new scenario
        scenario.status = 'CURRENT'
        scenario.applied_at = timezone.now()
        scenario.applied_by = user
        scenario.save()
        
        # Update actual salary grades - delete existing and create new
        SalaryGrade.objects.filter(grading_system=scenario.grading_system).delete()
        
        salary_grades_created = 0
        for pos_id_str, grades in scenario.calculated_grades.items():
            pos_id = int(pos_id_str)
            SalaryGrade.objects.create(
                grading_system=scenario.grading_system,
                position_group_id=pos_id,
                lower_decile=Decimal(str(grades['lower_decile'])),
                lower_quartile=Decimal(str(grades['lower_quartile'])),
                median=Decimal(str(grades['median'])),
                upper_quartile=Decimal(str(grades['upper_quartile'])),
                upper_decile=Decimal(str(grades['upper_decile']))
            )
            salary_grades_created += 1
        
        logger.info(f"Applied scenario {scenario.name}: created {salary_grades_created} salary grades")
        
        return scenario
    
    @staticmethod
    def get_current_scenario(grading_system_id):
        """Get current active scenario for a grading system"""
        from .models import SalaryScenario
        
        try:
            return SalaryScenario.objects.get(
                grading_system_id=grading_system_id,
                status='CURRENT'
            )
        except SalaryScenario.DoesNotExist:
            return None
    
    @staticmethod
    def validate_scenario_data(scenario_data):
        """Validate scenario data before calculation"""
        errors = []
        
        if not scenario_data.get('base_value') or scenario_data['base_value'] <= 0:
            errors.append("Base value must be greater than 0")
        
        if not scenario_data.get('base_position'):
            errors.append("Base position is required")
        
        # Validate custom vertical rates
        custom_vertical_rates = scenario_data.get('custom_vertical_rates', {})
        for pos_id_str, rate in custom_vertical_rates.items():
            try:
                pos_id = int(pos_id_str)
                if rate is not None and rate != '':
                    rate_decimal = Decimal(str(rate))
                    if rate_decimal < 0:
                        errors.append(f"Vertical rate for position {pos_id} cannot be negative")
            except (ValueError, TypeError):
                errors.append(f"Invalid vertical rate for position {pos_id_str}")
        
        # Validate custom horizontal rates
        custom_horizontal_rates = scenario_data.get('custom_horizontal_rates', {})
        for pos_id_str, rates in custom_horizontal_rates.items():
            try:
                pos_id = int(pos_id_str)
                for transition, rate in rates.items():
                    if rate is not None and rate != '':
                        rate_decimal = Decimal(str(rate))
                        if rate_decimal < 0:
                            errors.append(f"Horizontal rate for position {pos_id}, transition {transition} cannot be negative")
            except (ValueError, TypeError):
                errors.append(f"Invalid horizontal rates for position {pos_id_str}")
        
        return errors

    @staticmethod
    def calculate_average_rates(scenario):
        """Calculate average vertical and horizontal rates for display"""
        vertical_rates = []
        horizontal_rates = []
        
        # Calculate vertical rate averages
        for pos_id_str, rate in scenario.custom_vertical_rates.items():
            if rate is not None and rate != '':
                vertical_rates.append(float(rate))
        
        # Calculate horizontal rate averages
        for pos_id_str, rates in scenario.custom_horizontal_rates.items():
            if isinstance(rates, dict):
                for transition, rate in rates.items():
                    if rate is not None and rate != '':
                        horizontal_rates.append(float(rate))
        
        vertical_avg = sum(vertical_rates) / len(vertical_rates) if vertical_rates else 0
        horizontal_avg = sum(horizontal_rates) / len(horizontal_rates) if horizontal_rates else 0
        
        return {
            'vertical_average': round(vertical_avg, 1),
            'horizontal_average': round(horizontal_avg, 1),
            'vertical_rates_count': len(vertical_rates),
            'horizontal_rates_count': len(horizontal_rates)
        }

    @staticmethod
    def calculate_dynamic_grades(positions, base_position, base_value, 
                               vertical_rates, horizontal_rates):
        """Calculate grades dynamically with partial data for real-time updates"""
        calculated_grades = {}
        
        # Find base position index
        base_pos_idx = None
        for i, pos in enumerate(positions):
            if pos.id == base_position.id:
                base_pos_idx = i
                break
        
        if base_pos_idx is None:
            raise ValueError("Base position not found")
        
        # Calculate base position if horizontal rates are available
        base_pos = positions[base_pos_idx]
        if base_pos.id in horizontal_rates and len(horizontal_rates[base_pos.id]) == 4:
            # Check if all required horizontal rates are present and not None/empty
            required_transitions = ['LD_TO_LQ', 'LQ_TO_M', 'M_TO_UQ', 'UQ_TO_UD']
            all_rates_present = all(
                transition in horizontal_rates[base_pos.id] and 
                horizontal_rates[base_pos.id][transition] is not None and
                horizontal_rates[base_pos.id][transition] != ''
                for transition in required_transitions
            )
            
            if all_rates_present:
                calculated_grades[base_pos.id] = SalaryCalculationManager._calculate_horizontal_grades_dynamic(
                    base_value, base_pos.id, horizontal_rates
                )
            else:
                # Only show Lower Decile if horizontal rates not complete
                calculated_grades[base_pos.id] = {
                    'lower_decile': float(base_value),
                    'lower_quartile': None,
                    'median': None,
                    'upper_quartile': None,
                    'upper_decile': None
                }
        else:
            # Only show Lower Decile if horizontal rates not complete
            calculated_grades[base_pos.id] = {
                'lower_decile': float(base_value),
                'lower_quartile': None,
                'median': None,
                'upper_quartile': None,
                'upper_decile': None
            }
        
        # Calculate positions above base (going up the hierarchy)
        for i in range(base_pos_idx - 1, -1, -1):
            current_pos = positions[i]
            lower_pos = positions[i + 1]
            
            # Check if we have vertical rate and previous position is calculated
            if (lower_pos.id in vertical_rates and 
                vertical_rates[lower_pos.id] is not None and
                vertical_rates[lower_pos.id] != '' and
                lower_pos.id in calculated_grades and
                calculated_grades[lower_pos.id]['lower_decile'] is not None):
                
                vertical_rate = Decimal(str(vertical_rates[lower_pos.id]))
                lower_pos_ld = Decimal(str(calculated_grades[lower_pos.id]['lower_decile']))
                current_ld = lower_pos_ld * (Decimal('1') + vertical_rate / Decimal('100'))
                
                # Calculate horizontal grades if rates available
                if (current_pos.id in horizontal_rates and 
                    len(horizontal_rates[current_pos.id]) == 4):
                    
                    # Check if all horizontal rates are present and not None/empty
                    required_transitions = ['LD_TO_LQ', 'LQ_TO_M', 'M_TO_UQ', 'UQ_TO_UD']
                    all_rates_present = all(
                        transition in horizontal_rates[current_pos.id] and 
                        horizontal_rates[current_pos.id][transition] is not None and
                        horizontal_rates[current_pos.id][transition] != ''
                        for transition in required_transitions
                    )
                    
                    if all_rates_present:
                        calculated_grades[current_pos.id] = SalaryCalculationManager._calculate_horizontal_grades_dynamic(
                            current_ld, current_pos.id, horizontal_rates
                        )
                    else:
                        calculated_grades[current_pos.id] = {
                            'lower_decile': float(current_ld),
                            'lower_quartile': None,
                            'median': None,
                            'upper_quartile': None,
                            'upper_decile': None
                        }
                else:
                    calculated_grades[current_pos.id] = {
                        'lower_decile': float(current_ld),
                        'lower_quartile': None,
                        'median': None,
                        'upper_quartile': None,
                        'upper_decile': None
                    }
            else:
                # Can't calculate this position yet
                calculated_grades[current_pos.id] = {
                    'lower_decile': None,
                    'lower_quartile': None,
                    'median': None,
                    'upper_quartile': None,
                    'upper_decile': None
                }
        
        # Calculate positions below base (going down the hierarchy)
        for i in range(base_pos_idx + 1, len(positions)):
            current_pos = positions[i]
            higher_pos = positions[i - 1]
            
            # Check if we have vertical rate and higher position is calculated
            if (current_pos.id in vertical_rates and 
                vertical_rates[current_pos.id] is not None and
                vertical_rates[current_pos.id] != '' and
                higher_pos.id in calculated_grades and
                calculated_grades[higher_pos.id]['lower_decile'] is not None):
                
                vertical_rate = Decimal(str(vertical_rates[current_pos.id]))
                higher_pos_ld = Decimal(str(calculated_grades[higher_pos.id]['lower_decile']))
                current_ld = higher_pos_ld / (Decimal('1') + vertical_rate / Decimal('100'))
                
                # Calculate horizontal grades if rates available
                if (current_pos.id in horizontal_rates and 
                    len(horizontal_rates[current_pos.id]) == 4):
                    
                    # Check if all horizontal rates are present and not None/empty
                    required_transitions = ['LD_TO_LQ', 'LQ_TO_M', 'M_TO_UQ', 'UQ_TO_UD']
                    all_rates_present = all(
                        transition in horizontal_rates[current_pos.id] and 
                        horizontal_rates[current_pos.id][transition] is not None and
                        horizontal_rates[current_pos.id][transition] != ''
                        for transition in required_transitions
                    )
                    
                    if all_rates_present:
                        calculated_grades[current_pos.id] = SalaryCalculationManager._calculate_horizontal_grades_dynamic(
                            current_ld, current_pos.id, horizontal_rates
                        )
                    else:
                        calculated_grades[current_pos.id] = {
                            'lower_decile': float(current_ld),
                            'lower_quartile': None,
                            'median': None,
                            'upper_quartile': None,
                            'upper_decile': None
                        }
                else:
                    calculated_grades[current_pos.id] = {
                        'lower_decile': float(current_ld),
                        'lower_quartile': None,
                        'median': None,
                        'upper_quartile': None,
                        'upper_decile': None
                    }
            else:
                # Can't calculate this position yet
                calculated_grades[current_pos.id] = {
                    'lower_decile': None,
                    'lower_quartile': None,
                    'median': None,
                    'upper_quartile': None,
                    'upper_decile': None
                }
        
        return calculated_grades

    @staticmethod
    def _calculate_horizontal_grades_dynamic(lower_decile_value, position_id, horizontal_rates):
        """Calculate horizontal grades for dynamic scenarios"""
        grades = {'lower_decile': float(lower_decile_value)}
        
        pos_rates = horizontal_rates.get(position_id, {})
        
        # Check if all horizontal rates are available and not None/empty
        required_transitions = ['LD_TO_LQ', 'LQ_TO_M', 'M_TO_UQ', 'UQ_TO_UD']
        if not all(transition in pos_rates and 
                  pos_rates[transition] is not None and 
                  pos_rates[transition] != '' 
                  for transition in required_transitions):
            # Return partial data
            grades.update({
                'lower_quartile': None,
                'median': None,
                'upper_quartile': None,
                'upper_decile': None
            })
            return grades
        
        # Calculate step by step
        current_value = lower_decile_value
        
        # LD to LQ
        ld_to_lq_rate = Decimal(str(pos_rates['LD_TO_LQ']))
        current_value = current_value * (Decimal('1') + ld_to_lq_rate / Decimal('100'))
        grades['lower_quartile'] = float(current_value)
        
        # LQ to M
        lq_to_m_rate = Decimal(str(pos_rates['LQ_TO_M']))
        current_value = current_value * (Decimal('1') + lq_to_m_rate / Decimal('100'))
        grades['median'] = float(current_value)
        
        # M to UQ
        m_to_uq_rate = Decimal(str(pos_rates['M_TO_UQ']))
        current_value = current_value * (Decimal('1') + m_to_uq_rate / Decimal('100'))
        grades['upper_quartile'] = float(current_value)
        
        # UQ to UD
        uq_to_ud_rate = Decimal(str(pos_rates['UQ_TO_UD']))
        current_value = current_value * (Decimal('1') + uq_to_ud_rate / Decimal('100'))
        grades['upper_decile'] = float(current_value)
        
        return grades