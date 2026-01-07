# management/commands/load_permissions.py
# Run: python manage.py load_permissions

from django.core.management.base import BaseCommand
from api.role_models import Permission

class Command(BaseCommand):
    help = 'Load all permissions into database'

    def handle(self, *args, **kwargs):
        permissions_data = [


        
            
            # BUSINESS TRIPS
            ('business_trips.request.view', 'View Business Trip Requests', 'Business Trips'),
            ('business_trips.request.create', 'Create Business Trip Request', 'Business Trips'),
            ('business_trips.request.update', 'Update Business Trip Request', 'Business Trips'),
            ('business_trips.request.delete', 'Delete Business Trip Request', 'Business Trips'),
            ('business_trips.request.submit', 'Submit Business Trip Request', 'Business Trips'),
            ('business_trips.request.approve', 'Approve Business Trip Request', 'Business Trips'),
            ('business_trips.request.cancel', 'Cancel Business Trip', 'Business Trips'),
            ('business_trips.request.view_pending', 'View Pending Approvals', 'Business Trips'),
            ('business_trips.request.view_statistics', 'View Trip Statistics', 'Business Trips'),
            ('business_trips.export_all', 'Export All Business Trip Records', 'Business Trips'),
            ('business_trips.settings.view', 'View Trip Settings', 'Business Trips'),
            ('business_trips.settings.update', 'Update Trip Settings', 'Business Trips'),
            
            # VACATION
            ('vacation.dashboard.view', 'View Vacation Dashboard', 'Vacation'),
            ('vacation.dashboard.view_own', 'View Own Vacation Dashboard', 'Vacation'),
            ('vacation.dashboard.view_team', 'View Team Dashboard', 'Vacation'),

            # Vacation Requests
            ('vacation.request.view_own', 'View Own Vacation Requests', 'Vacation'),
            ('vacation.request.view_team', 'View Team Vacation Requests', 'Vacation'),
            ('vacation.request.view_all', 'View All Vacation Requests', 'Vacation'),
            ('vacation.request.create_own', 'Create Own Vacation Request', 'Vacation'),
            ('vacation.request.create_for_employee', 'Create Vacation Request for Employee', 'Vacation'),
            ('vacation.request.update_own', 'Update Own Vacation Request', 'Vacation'),
            ('vacation.request.delete_own', 'Delete Own Vacation Request', 'Vacation'),
            ('vacation.request.approve_as_line_manager', 'Approve as Line Manager', 'Vacation'),
            ('vacation.request.approve_as_hr', 'Approve as HR', 'Vacation'),
            ('vacation.request.export_own', 'Export Own Vacation Records', 'Vacation'),
            ('vacation.request.export_all', 'Export All Vacation Records', 'Vacation'),
            ('vacation.request.export_team', 'Export Team Vacations', 'Vacation'),

            # Vacation Schedules
            ('vacation.schedule.view_own', 'View Own Schedules', 'Vacation'),
            ('vacation.schedule.view_team', 'View Team Schedules', 'Vacation'),
            ('vacation.schedule.view_all', 'View All Schedules', 'Vacation'),
            ('vacation.schedule.create_own', 'Create Own Schedule', 'Vacation'),
            ('vacation.schedule.create_for_employee', 'Create Schedule for Employee', 'Vacation'),
            ('vacation.schedule.update_own', 'Update Own Schedule', 'Vacation'),
            ('vacation.schedule.delete_own', 'Delete Own Schedule', 'Vacation'),
            ('vacation.schedule.register', 'Register Schedule as Taken', 'Vacation'),

            # Vacation Balances
            ('vacation.balance.view_own', 'View Own Balance', 'Vacation'),
            ('vacation.balance.view_all', 'View All Balances', 'Vacation'),
            ('vacation.balance.update', 'Update Any Employee Balance', 'Vacation'),
            ('vacation.balance.bulk_upload', 'Bulk Upload Balances', 'Vacation'),
            ('vacation.balance.reset', 'Reset Employee Balance', 'Vacation'),
            ('vacation.balance.export', 'Export Balances', 'Vacation'),

            # Vacation Settings
            ('vacation.settings.view', 'View Vacation Settings', 'Vacation'),
            ('vacation.settings.update_production_calendar', 'Update Production Calendar', 'Vacation'),
            ('vacation.settings.update_general', 'Update General Settings', 'Vacation'),
            ('vacation.settings.update_hr_representative', 'Update HR Representative', 'Vacation'),

            # Vacation Types
            ('vacation.type.view', 'View Vacation Types', 'Vacation'),
            ('vacation.type.create', 'Create Vacation Type', 'Vacation'),
            ('vacation.type.update', 'Update Vacation Type', 'Vacation'),
            ('vacation.type.delete', 'Delete Vacation Type', 'Vacation'),
            
      
            
       
           
        ]
        
        created_count = 0
        updated_count = 0
        
        for codename, name, category in permissions_data:
            permission, created = Permission.objects.update_or_create(
                codename=codename,
                defaults={
                    'name': name,
                    'category': category,
                    'is_active': True
                }
            )
            
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'✓ Created: {codename}'))
            else:
                updated_count += 1
                self.stdout.write(self.style.WARNING(f'↻ Updated: {codename}'))
        
        # Summary by category
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS('SUMMARY BY CATEGORY:'))
        self.stdout.write('='*60)
        
        categories = {}
        for codename, name, category in permissions_data:
            if category not in categories:
                categories[category] = 0
            categories[category] += 1
        
        for category, count in sorted(categories.items()):
            self.stdout.write(f'  {category}: {count} permissions')
        
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS(f'✓ Created: {created_count} permissions'))
        self.stdout.write(self.style.SUCCESS(f'↻ Updated: {updated_count} permissions'))
        self.stdout.write(self.style.SUCCESS(f'Total: {created_count + updated_count} permissions'))
        self.stdout.write('='*60)