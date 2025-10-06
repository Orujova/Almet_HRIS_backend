# management/commands/setup_vacation_roles.py

from django.core.management.base import BaseCommand
from api.role_models import Role, Permission, RolePermission
from django.contrib.auth.models import User

class Command(BaseCommand):
    help = 'Setup default vacation roles'

    def handle(self, *args, **kwargs):
        # İstənilən aktiv user tap (superuser olmasına baxmırıq)
        admin_user = User.objects.filter(is_active=True).first()
        
        if not admin_user:
            self.stdout.write(self.style.ERROR('❌ Heç bir aktiv user tapılmadı'))
            return
        
        self.stdout.write(self.style.WARNING(f'⚙ User: {admin_user.username} ({admin_user.email})'))
        
        # 1. EMPLOYEE ROLE
        employee_role, created = Role.objects.get_or_create(
            name='Employee - Vacation',
            defaults={'created_by': admin_user}
        )
        
        employee_perms = [
            'vacation.dashboard.view_own',
            'vacation.request.view_own',
            'vacation.request.create_own',
            'vacation.request.update_own',
            'vacation.request.export_own',
            'vacation.schedule.view_own',
            'vacation.schedule.create_own',
            'vacation.schedule.update_own',
            'vacation.schedule.delete_own',
            'vacation.balance.view_own',
            'vacation.type.view',
        ]
        
        self._assign_permissions(employee_role, employee_perms, admin_user)
        status = '✓ Created' if created else '↻ Updated'
        self.stdout.write(self.style.SUCCESS(f'{status} Employee Role: {len(employee_perms)} permissions'))
        
        # 2. LINE MANAGER ROLE
        manager_role, created = Role.objects.get_or_create(
            name='Line Manager - Vacation',
            defaults={'created_by': admin_user}
        )
        
        manager_perms = employee_perms + [
            'vacation.dashboard.view_team',
            'vacation.request.view_team',
            'vacation.request.create_for_employee',
            'vacation.request.approve_as_line_manager',
            'vacation.schedule.view_team',
            'vacation.schedule.create_for_employee',
        ]
        
        self._assign_permissions(manager_role, manager_perms, admin_user)
        status = '✓ Created' if created else '↻ Updated'
        self.stdout.write(self.style.SUCCESS(f'{status} Manager Role: {len(manager_perms)} permissions'))
        
        # 3. HR ROLE
        hr_role, created = Role.objects.get_or_create(
            name='HR - Vacation',
            defaults={'created_by': admin_user}
        )
        
        hr_perms = [
            'vacation.dashboard.view',
            'vacation.request.view_all',
            'vacation.request.approve_as_hr',
            'vacation.request.export_all',
            'vacation.schedule.view_all',
            'vacation.schedule.register',
            'vacation.balance.view_all',
            'vacation.balance.update',
            'vacation.balance.bulk_upload',
            'vacation.balance.reset',
            'vacation.balance.export',
            'vacation.settings.view',
            'vacation.settings.update_production_calendar',
            'vacation.settings.update_general',
            'vacation.settings.update_hr_representative',
            'vacation.type.view',
            'vacation.type.create',
            'vacation.type.update',
            'vacation.notification.view',
            'vacation.notification.update',
        ]
        
        self._assign_permissions(hr_role, hr_perms, admin_user)
        status = '✓ Created' if created else '↻ Updated'
        self.stdout.write(self.style.SUCCESS(f'{status} HR Role: {len(hr_perms)} permissions'))
        
        # 4. ADMIN ROLE
        admin_role, created = Role.objects.get_or_create(
            name='Admin - Vacation',
            defaults={'created_by': admin_user}
        )
        
        # Admin bütün vacation permissionslarına sahib
        admin_perms = Permission.objects.filter(
            category='Vacation',
            is_active=True
        )
        
        # Əvvəlki permissionsları sil
        admin_role.role_permissions.all().delete()
        
        count = 0
        for perm in admin_perms:
            RolePermission.objects.get_or_create(
                role=admin_role,
                permission=perm,
                defaults={'granted_by': admin_user}
            )
            count += 1
        
        status = '✓ Created' if created else '↻ Updated'
        self.stdout.write(self.style.SUCCESS(f'{status} Admin Role: {count} permissions'))
        
        self.stdout.write(self.style.SUCCESS(f'\n✅ Vacation roles uğurla yaradıldı!'))
    
    def _assign_permissions(self, role, permission_codenames, admin_user):
        """Assign permissions to role"""
        # Əvvəlki permissionsları sil
        role.role_permissions.all().delete()
        
        assigned = 0
        missing = []
        
        for codename in permission_codenames:
            try:
                perm = Permission.objects.get(codename=codename, is_active=True)
                RolePermission.objects.get_or_create(
                    role=role,
                    permission=perm,
                    defaults={'granted_by': admin_user}
                )
                assigned += 1
            except Permission.DoesNotExist:
                missing.append(codename)
        
        if missing:
            self.stdout.write(self.style.WARNING(f'  ⚠ Missing permissions: {", ".join(missing)}'))