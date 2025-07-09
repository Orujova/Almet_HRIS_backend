# api/management/commands/update_employee_statuses.py - FIXED
# Management command to automatically update employee statuses based on contract configurations

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import date, timedelta
from api.models import Employee, EmployeeActivity
from api.status_management import EmployeeStatusManager, StatusAutomationRules
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Update employee statuses based on contract configurations and duration'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            dest='dry_run',
            help='Show what would be updated without making changes',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            dest='force_update',
            help='Force update even if status appears correct',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            dest='verbose',
            help='Show detailed output',
        )
        parser.add_argument(
            '--employee-ids',
            type=str,
            dest='employee_ids',
            help='Comma-separated list of employee IDs to update (optional)',
        )
        parser.add_argument(
            '--contract-type',
            type=str,
            dest='contract_type',
            choices=['3_MONTHS', '6_MONTHS', '1_YEAR', '2_YEARS', '3_YEARS', 'PERMANENT'],
            help='Only update employees with specific contract type',
        )
        parser.add_argument(
            '--days-since-start',
            type=int,
            dest='days_since_start',
            help='Only update employees who started X days ago or more',
        )
        parser.add_argument(
            '--run-automation-rules',
            action='store_true',
            dest='run_automation',
            help='Run status automation rules after updating',
        )
    
    def handle(self, *args, **options):
        dry_run = options['dry_run']
        force_update = options['force_update']
        verbose = options['verbose']
        employee_ids = options['employee_ids']
        contract_type = options['contract_type']
        days_since_start = options['days_since_start']
        run_automation = options['run_automation']
        
        self.stdout.write('=' * 60)
        self.stdout.write(f'Employee Status Update - {timezone.now().strftime("%Y-%m-%d %H:%M:%S")}')
        self.stdout.write('=' * 60)
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))
        
        # Build queryset based on filters
        queryset = Employee.objects.filter(is_deleted=False)
        
        if employee_ids:
            ids = [id.strip() for id in employee_ids.split(',')]
            queryset = queryset.filter(employee_id__in=ids)
            self.stdout.write(f'Filtering by employee IDs: {ids}')
        
        if contract_type:
            queryset = queryset.filter(contract_duration=contract_type)
            self.stdout.write(f'Filtering by contract type: {contract_type}')
        
        if days_since_start:
            cutoff_date = date.today() - timedelta(days=days_since_start)
            queryset = queryset.filter(start_date__lte=cutoff_date)
            self.stdout.write(f'Filtering by start date: {cutoff_date} or earlier')
        
        total_employees = queryset.count()
        self.stdout.write(f'Total employees to check: {total_employees}')
        self.stdout.write('')
        
        if dry_run:
            self._dry_run_analysis(queryset, verbose)
        else:
            self._update_statuses(queryset, force_update, verbose)
            
            # Run automation rules if requested
            if run_automation:
                self._run_automation_rules()
        
        # Always show contract expiry warnings
        self._show_contract_expiry_warning()
    
    def _dry_run_analysis(self, queryset, verbose):
        """Analyze what would be updated without making changes"""
        updates_needed = []
        current_status = []
        errors = []
        
        for employee in queryset:
            try:
                preview = EmployeeStatusManager.get_status_preview(employee)
                
                employee_info = {
                    'employee_id': employee.employee_id,
                    'name': employee.full_name,
                    'current_status': preview['current_status'],
                    'required_status': preview['required_status'],
                    'needs_update': preview['needs_update'],
                    'reason': preview['reason'],
                    'contract_type': preview['contract_type'],
                    'days_since_start': preview['days_since_start']
                }
                
                if preview['needs_update']:
                    updates_needed.append(employee_info)
                else:
                    current_status.append(employee_info)
                    
            except Exception as e:
                errors.append(f"{employee.employee_id}: {str(e)}")
        
        # Display results
        self.stdout.write(self.style.SUCCESS(f'Analysis Results:'))
        self.stdout.write(f'  - Employees needing status update: {len(updates_needed)}')
        self.stdout.write(f'  - Employees with current status: {len(current_status)}')
        self.stdout.write(f'  - Errors encountered: {len(errors)}')
        self.stdout.write('')
        
        if updates_needed:
            self.stdout.write(self.style.WARNING('Employees needing status updates:'))
            for emp in updates_needed:
                self.stdout.write(
                    f"  {emp['employee_id']} - {emp['name']}: "
                    f"{emp['current_status']} → {emp['required_status']} "
                    f"({emp['reason']})"
                )
            self.stdout.write('')
        
        if verbose and current_status:
            self.stdout.write(self.style.SUCCESS('Employees with current status:'))
            for emp in current_status[:10]:  # Show first 10
                self.stdout.write(
                    f"  {emp['employee_id']} - {emp['name']}: "
                    f"{emp['current_status']} (current) - {emp['reason']}"
                )
            if len(current_status) > 10:
                self.stdout.write(f"  ... and {len(current_status) - 10} more")
            self.stdout.write('')
        
        if errors:
            self.stdout.write(self.style.ERROR('Errors encountered:'))
            for error in errors:
                self.stdout.write(f"  {error}")
            self.stdout.write('')
        
        # Summary by contract type
        contract_analysis = {}
        for emp in updates_needed + current_status:
            contract = emp['contract_type']
            if contract not in contract_analysis:
                contract_analysis[contract] = {'needs_update': 0, 'current': 0}
            
            if emp['needs_update']:
                contract_analysis[contract]['needs_update'] += 1
            else:
                contract_analysis[contract]['current'] += 1
        
        if contract_analysis:
            self.stdout.write(self.style.SUCCESS('Analysis by contract type:'))
            for contract, stats in contract_analysis.items():
                total = stats['needs_update'] + stats['current']
                self.stdout.write(
                    f"  {contract}: {stats['needs_update']} need update, "
                    f"{stats['current']} current (total: {total})"
                )
            self.stdout.write('')
    
    def _update_statuses(self, queryset, force_update, verbose):
        """Actually update employee statuses"""
        updated_count = 0
        skipped_count = 0
        error_count = 0
        
        self.stdout.write(f'Starting status updates...')
        self.stdout.write('')
        
        for employee in queryset:
            try:
                preview = EmployeeStatusManager.get_status_preview(employee)
                
                if preview['needs_update'] or force_update:
                    # Use EmployeeStatusManager to update status
                    if EmployeeStatusManager.update_employee_status(employee, force_update=force_update):
                        updated_count += 1
                        if verbose:
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f"✓ {employee.employee_id} - {employee.full_name}: "
                                    f"{preview['current_status']} → {preview['required_status']}"
                                )
                            )
                    else:
                        skipped_count += 1
                        if verbose:
                            self.stdout.write(
                                self.style.WARNING(
                                    f"- {employee.employee_id} - {employee.full_name}: "
                                    f"No update made"
                                )
                            )
                else:
                    skipped_count += 1
                    if verbose:
                        self.stdout.write(
                            f"✓ {employee.employee_id} - {employee.full_name}: "
                            f"{preview['current_status']} (already current)"
                        )
                        
            except Exception as e:
                error_count += 1
                self.stdout.write(
                    self.style.ERROR(
                        f"✗ {employee.employee_id} - {employee.full_name}: "
                        f"Error - {str(e)}"
                    )
                )
                logger.error(f"Error updating {employee.employee_id}: {e}")
        
        # Summary
        self.stdout.write('')
        self.stdout.write('=' * 60)
        self.stdout.write(self.style.SUCCESS('Update Summary:'))
        self.stdout.write(f'  - Total employees processed: {queryset.count()}')
        self.stdout.write(f'  - Statuses updated: {updated_count}')
        self.stdout.write(f'  - Employees skipped (no update needed): {skipped_count}')
        self.stdout.write(f'  - Errors encountered: {error_count}')
        self.stdout.write('=' * 60)
        
        if updated_count > 0:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully updated {updated_count} employee statuses!'
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING('No employee statuses were updated.')
            )
    
    def _run_automation_rules(self):
        """Run status automation rules"""
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('Running status automation rules...'))
        
        try:
            results = StatusAutomationRules.check_and_apply_rules()
            
            total_updated = (
                results['onboarding_to_probation'] + 
                results['probation_to_active'] + 
                results['contract_expired_to_inactive']
            )
            
            self.stdout.write(f'  - Onboarding → Probation: {results["onboarding_to_probation"]}')
            self.stdout.write(f'  - Probation → Active: {results["probation_to_active"]}')
            self.stdout.write(f'  - Contract Expired → Inactive: {results["contract_expired_to_inactive"]}')
            self.stdout.write(f'  - Total automated updates: {total_updated}')
            
            if results['errors']:
                self.stdout.write(self.style.ERROR('Automation errors:'))
                for error in results['errors']:
                    self.stdout.write(f'  - {error}')
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error running automation rules: {e}'))
            logger.error(f"Automation rules error: {e}")
    
    def _show_contract_expiry_warning(self):
        """Show warning about contracts expiring soon"""
        try:
            expiring_soon = EmployeeStatusManager.get_contract_expiry_analysis(30)
            
            if expiring_soon['total_expiring'] > 0:
                self.stdout.write('')
                self.stdout.write(
                    self.style.WARNING(
                        f'⚠ Warning: {expiring_soon["total_expiring"]} contracts expire within 30 days'
                    )
                )
                
                # Show by urgency
                for urgency, count in expiring_soon['by_urgency'].items():
                    if count > 0:
                        color = self.style.ERROR if urgency == 'critical' else self.style.WARNING
                        self.stdout.write(color(f'  - {urgency.title()}: {count} contracts'))
                
                # Show first 5 employees
                for emp in expiring_soon['employees'][:5]:
                    days_left = emp['days_remaining']
                    urgency_color = self.style.ERROR if emp['urgency'] == 'critical' else self.style.WARNING
                    self.stdout.write(
                        urgency_color(
                            f"  - {emp['employee_id']} ({emp['name']}): "
                            f"{days_left} days remaining ({emp['urgency']})"
                        )
                    )
                
                if len(expiring_soon['employees']) > 5:
                    self.stdout.write(f"  ... and {len(expiring_soon['employees']) - 5} more")
                
                self.stdout.write('')
        except Exception as e:
            logger.error(f"Error checking contract expiry: {e}")
    
    def _show_specific_scenarios(self):
        """Show specific scenarios for testing"""
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=== Specific Scenarios Analysis ==='))
        
        # Scenario 1: New employees (started within last 7 days)
        new_employees = Employee.objects.filter(
            start_date__gte=date.today() - timedelta(days=7),
            is_deleted=False
        )
        
        if new_employees.exists():
            self.stdout.write(self.style.SUCCESS(f'New employees (last 7 days): {new_employees.count()}'))
            for emp in new_employees:
                preview = EmployeeStatusManager.get_status_preview(emp)
                status_indicator = '⚠' if preview['needs_update'] else '✓'
                self.stdout.write(
                    f"  {status_indicator} {emp.employee_id} - {emp.full_name}: {preview['current_status']} "
                    f"({'needs update' if preview['needs_update'] else 'current'})"
                )
            self.stdout.write('')
        
        # Scenario 2: Employees in onboarding
        onboarding_employees = Employee.objects.filter(
            status__status_type='ONBOARDING',
            is_deleted=False
        )
        
        if onboarding_employees.exists():
            self.stdout.write(self.style.SUCCESS(f'Employees in onboarding: {onboarding_employees.count()}'))
            for emp in onboarding_employees:
                preview = EmployeeStatusManager.get_status_preview(emp)
                status_indicator = '⚠' if preview['needs_update'] else '✓'
                self.stdout.write(
                    f"  {status_indicator} {emp.employee_id} - {emp.full_name}: Should be {preview['required_status']} "
                    f"({'needs update' if preview['needs_update'] else 'current'})"
                )
            self.stdout.write('')
        
        # Scenario 3: Employees in probation period
        probation_employees = Employee.objects.filter(
            status__status_type='PROBATION',
            is_deleted=False
        )
        
        if probation_employees.exists():
            self.stdout.write(self.style.SUCCESS(f'Employees in probation: {probation_employees.count()}'))
            for emp in probation_employees:
                preview = EmployeeStatusManager.get_status_preview(emp)
                status_indicator = '⚠' if preview['needs_update'] else '✓'
                self.stdout.write(
                    f"  {status_indicator} {emp.employee_id} - {emp.full_name}: Should be {preview['required_status']} "
                    f"({'needs update' if preview['needs_update'] else 'current'})"
                )
            self.stdout.write('')
        
        # Scenario 4: Employees without line managers
        no_manager_employees = Employee.objects.filter(
            line_manager__isnull=True,
            status__affects_headcount=True,
            is_deleted=False
        )
        
        if no_manager_employees.exists():
            self.stdout.write(self.style.WARNING(f'Employees without line managers: {no_manager_employees.count()}'))
            for emp in no_manager_employees[:5]:  # Show first 5
                self.stdout.write(
                    f"  - {emp.employee_id} - {emp.full_name} ({emp.position_group.get_name_display()})"
                )
            if no_manager_employees.count() > 5:
                self.stdout.write(f"  ... and {no_manager_employees.count() - 5} more")
            self.stdout.write('')


# Enhanced usage examples with new options:
# 
# Basic commands:
# python manage.py update_employee_statuses --dry-run
# python manage.py update_employee_statuses --dry-run --verbose
# python manage.py update_employee_statuses --force
# 
# Filtered commands:
# python manage.py update_employee_statuses --employee-ids="HC001,HC002,HC003"
# python manage.py update_employee_statuses --contract-type="1_YEAR" --dry-run
# python manage.py update_employee_statuses --days-since-start=90 --verbose
# 
# With automation rules:
# python manage.py update_employee_statuses --run-automation-rules
# python manage.py update_employee_statuses --force --run-automation-rules --verbose
# 
# Comprehensive analysis:
# python manage.py update_employee_statuses --dry-run --verbose --contract-type="3_MONTHS"