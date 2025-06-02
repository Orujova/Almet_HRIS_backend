# api/status_management.py

from django.utils import timezone
from datetime import timedelta
from .models import Employee, EmployeeStatus, EmployeeActivity
import logging

logger = logging.getLogger(__name__)

class EmployeeStatusManager:
    """
    Employee status-larını avtomatik idarə etmək üçün class
    """
    
    @staticmethod
    def get_or_create_default_statuses():
        """Default status-ları yarat və ya gətir"""
        statuses = {}
        
        status_configs = [
            ('ONBOARDING', '#FFA500', 'İlk 7 gün ərzində'),
            ('PROBATION', '#FFD700', 'Probation müddəti ərzində'),
            ('ACTIVE', '#28A745', 'Normal işçi statusu'),
            ('ON LEAVE', '#DC3545', 'İş müddəti bitib')
        ]
        
        for name, color, description in status_configs:
            status, created = EmployeeStatus.objects.get_or_create(
                name=name,
                defaults={'color': color, 'is_active': True}
            )
            statuses[name] = status
            if created:
                logger.info(f"Status yaradıldı: {name}")
        
        return statuses
    
    @staticmethod
    def calculate_required_status(employee):
        """
        Employee üçün olması lazım olan status-u hesabla
        """
        current_date = timezone.now().date()
        
        # End date yoxla
        if employee.end_date and employee.end_date <= current_date:
            return 'ON LEAVE'
        
        # Start date-dən neçə gün keçib
        days_since_start = (current_date - employee.start_date).days
        
        # İlk 7 gün - ONBOARDING
        if days_since_start <= 7:
            return 'ONBOARDING'
        
        # Contract duration əsasında probation
        if employee.contract_duration != 'PERMANENT':
            probation_days = EmployeeStatusManager.get_probation_days(employee.contract_duration)
            
            if days_since_start <= probation_days:
                return 'PROBATION'
        
        # Normal halda ACTIVE
        return 'ACTIVE'
    
    @staticmethod
    def get_probation_days(contract_duration):
        """Contract duration əsasında probation müddətini qaytar"""
        probation_mapping = {
            '3_MONTHS': 7,      # 7 gün probation
            '6_MONTHS': 14,     # 14 gün probation  
            '1_YEAR': 90,       # 90 gün probation
            'PERMANENT': 0,     # Probation yoxdur
        }
        return probation_mapping.get(contract_duration, 0)
    
    @staticmethod
    def update_employee_status(employee, force_update=False):
        """
        Tək employee üçün status-u yenilə
        """
        required_status_name = EmployeeStatusManager.calculate_required_status(employee)
        current_status_name = employee.status.name if employee.status else None
        
        # Əgər status dəyişməlidirsə
        if current_status_name != required_status_name or force_update:
            statuses = EmployeeStatusManager.get_or_create_default_statuses()
            new_status = statuses.get(required_status_name)
            
            if new_status:
                old_status = employee.status
                employee.status = new_status
                employee.save()
                
                # Activity log
                EmployeeActivity.objects.create(
                    employee=employee,
                    activity_type='STATUS_CHANGED',
                    description=f"Status avtomatik olaraq dəyişdirildi: {current_status_name} → {required_status_name}",
                    performed_by=None,  # System tərəfindən
                    metadata={
                        'old_status': current_status_name,
                        'new_status': required_status_name,
                        'automatic': True,
                        'reason': EmployeeStatusManager.get_status_change_reason(employee, required_status_name)
                    }
                )
                
                logger.info(f"Employee {employee.employee_id} status dəyişdi: {current_status_name} → {required_status_name}")
                return True
        
        return False
    
    @staticmethod
    def get_status_change_reason(employee, new_status):
        """Status dəyişməsinin səbəbini qaytar"""
        current_date = timezone.now().date()
        days_since_start = (current_date - employee.start_date).days
        
        if new_status == 'ONBOARDING':
            return f"İlk 7 gün ərzində ({days_since_start} gün)"
        elif new_status == 'PROBATION':
            probation_days = EmployeeStatusManager.get_probation_days(employee.contract_duration)
            return f"Probation müddəti ({employee.get_contract_duration_display()}, {days_since_start}/{probation_days} gün)"
        elif new_status == 'ACTIVE':
            return "Onboarding və probation tamamlandı"
        elif new_status == 'ON LEAVE':
            return f"İş müddəti bitib (end_date: {employee.end_date})"
        else:
            return "Naməlum səbəb"
    
    @staticmethod
    def bulk_update_statuses():
        """
        Bütün employee-lər üçün status-ları yenilə
        """
        employees = Employee.objects.select_related('status').all()
        updated_count = 0
        
        for employee in employees:
            if EmployeeStatusManager.update_employee_status(employee):
                updated_count += 1
        
        logger.info(f"Bulk status update: {updated_count} employee yeniləndi")
        return updated_count
    
    @staticmethod
    def get_status_preview(employee):
        """
        Employee üçün status preview-ını qaytar (actual update etmədən)
        """
        required_status = EmployeeStatusManager.calculate_required_status(employee)
        current_status = employee.status.name if employee.status else None
        
        return {
            'current_status': current_status,
            'required_status': required_status,
            'needs_update': current_status != required_status,
            'reason': EmployeeStatusManager.get_status_change_reason(employee, required_status)
        }


# api/views.py-ə əlavə ediləcək ViewSet-lər

from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from .status_management import EmployeeStatusManager

# EmployeeViewSet-ə əlavə action-lar
class EmployeeStatusManagementMixin:
    """
    Employee ViewSet-ə status management əlavə etmək üçün mixin
    """
    
    @action(detail=True, methods=['post'], url_path='update-status')
    def update_status(self, request, pk=None):
        """
        Tək employee üçün status-u avtomatik yenilə
        """
        employee = self.get_object()
        
        # Preview göstər
        preview = EmployeeStatusManager.get_status_preview(employee)
        
        if not preview['needs_update']:
            return Response({
                'message': 'Status yeniləməyə ehtiyac yoxdur',
                'current_status': preview['current_status'],
                'preview': preview
            })
        
        # Force update parametri
        force_update = request.data.get('force_update', False)
        
        # Status-u yenilə
        updated = EmployeeStatusManager.update_employee_status(employee, force_update=force_update)
        
        if updated:
            employee.refresh_from_db()
            return Response({
                'message': 'Status uğurla yeniləndi',
                'old_status': preview['current_status'],
                'new_status': employee.status.name,
                'reason': preview['reason']
            })
        else:
            return Response({
                'message': 'Status yenilənmədi',
                'preview': preview
            })
    
    @action(detail=True, methods=['get'], url_path='status-preview')
    def status_preview(self, request, pk=None):
        """
        Employee üçün status preview-ını göstər
        """
        employee = self.get_object()
        preview = EmployeeStatusManager.get_status_preview(employee)
        
        # Əlavə məlumatlar
        current_date = timezone.now().date()
        days_since_start = (current_date - employee.start_date).days
        
        probation_days = EmployeeStatusManager.get_probation_days(employee.contract_duration)
        
        additional_info = {
            'days_since_start': days_since_start,
            'contract_duration': employee.get_contract_duration_display(),
            'probation_days': probation_days,
            'end_date': employee.end_date,
            'is_probation_completed': days_since_start > probation_days if probation_days > 0 else True,
            'is_onboarding_completed': days_since_start > 7
        }
        
        return Response({
            'employee_id': employee.employee_id,
            'employee_name': employee.full_name,
            'preview': preview,
            'details': additional_info
        })
    
    @action(detail=False, methods=['post'], url_path='bulk-update-statuses')
    def bulk_update_statuses(self, request):
        """
        Bütün employee-lər üçün status-ları yenilə
        """
        # Yalnız spesifik employee ID-lər
        employee_ids = request.data.get('employee_ids', [])
        
        if employee_ids:
            employees = Employee.objects.filter(id__in=employee_ids)
            updated_count = 0
            
            for employee in employees:
                if EmployeeStatusManager.update_employee_status(employee):
                    updated_count += 1
        else:
            # Bütün employee-lər
            updated_count = EmployeeStatusManager.bulk_update_statuses()
        
        return Response({
            'message': f'{updated_count} employee status yeniləndi',
            'updated_count': updated_count
        })
    
    @action(detail=False, methods=['get'], url_path='status-rules')
    def status_rules(self, request):
        """
        Status rules və contract mapping-ini qaytar
        """
        rules = {
            'onboarding': {
                'duration_days': 7,
                'description': 'İlk 7 gün ərzində bütün employee-lər üçün'
            },
            'probation_by_contract': {
                '3_MONTHS': {
                    'probation_days': 7,
                    'description': '3 aylıq contract - 7 gün probation'
                },
                '6_MONTHS': {
                    'probation_days': 14,
                    'description': '6 aylıq contract - 14 gün probation'
                },
                '1_YEAR': {
                    'probation_days': 90,
                    'description': '1 illik contract - 90 gün probation'
                },
                'PERMANENT': {
                    'probation_days': 0,
                    'description': 'Permanent contract - probation yoxdur'
                }
            },
            'leave_condition': {
                'description': 'end_date təyin edilib və keçib'
            }
        }
        
        return Response(rules)


# Management command üçün əlavə
# api/management/commands/update_employee_statuses.py faylına əlavə:

def handle_with_status_manager(self, *args, **options):
    """
    EmployeeStatusManager istifadə edərək status yeniləmə
    """
    from api.status_management import EmployeeStatusManager
    
    dry_run = options['dry_run']
    verbose = options['verbose']
    
    if dry_run:
        self.stdout.write('DRY RUN - Status preview-ları:')
        employees = Employee.objects.all()
        
        for employee in employees:
            preview = EmployeeStatusManager.get_status_preview(employee)
            if preview['needs_update']:
                self.stdout.write(
                    f"{employee.employee_id} - {employee.full_name}: "
                    f"{preview['current_status']} → {preview['required_status']} "
                    f"({preview['reason']})"
                )
    else:
        updated_count = EmployeeStatusManager.bulk_update_statuses()
        self.stdout.write(
            self.style.SUCCESS(f'{updated_count} employee status yeniləndi')
        )