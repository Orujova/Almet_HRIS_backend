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
            
            # JOB DESCRIPTIONS
            ('job_description.template.view', 'View JD Templates', 'Job Descriptions'),
            ('job_description.template.create', 'Create JD Template', 'Job Descriptions'),
            ('job_description.template.update', 'Update JD Template', 'Job Descriptions'),
            ('job_description.template.delete', 'Delete JD Template', 'Job Descriptions'),
            
            ('job_description.employee_jd.view', 'View Employee Job Descriptions', 'Job Descriptions'),
            ('job_description.employee_jd.create', 'Create Employee JD', 'Job Descriptions'),
            ('job_description.employee_jd.update', 'Update Employee JD', 'Job Descriptions'),
            ('job_description.employee_jd.delete', 'Delete Employee JD', 'Job Descriptions'),
            ('job_description.employee_jd.submit', 'Submit for Approval', 'Job Descriptions'),
            ('job_description.employee_jd.approve', 'Approve Job Description', 'Job Descriptions'),
            ('job_description.employee_jd.reject', 'Reject Job Description', 'Job Descriptions'),
            ('job_description.employee_jd.request_revision', 'Request Revision', 'Job Descriptions'),
            ('job_description.employee_jd.export', 'Export/Download JD', 'Job Descriptions'),
          
            # Performance Dashboard & Reports
            ('performance.dashboard.view', 'View Performance Dashboard', 'Performance'),
            ('performance.dashboard.view_statistics', 'View Performance Statistics', 'Performance'),
            
            # Performance Records - View Permissions
            ('performance.view_own', 'View Own Performance', 'Performance'),
            ('performance.view_team', 'View Team Performance (Direct Reports)', 'Performance'),
            ('performance.view_all', 'View All Performance Records', 'Performance'),
            
            # Performance Records - Edit Permissions  
            ('performance.edit_own', 'Edit Own Performance', 'Performance'),
            ('performance.manage_team', 'Manage Team Performance (Direct Reports)', 'Performance'),
            ('performance.manage_all', 'Manage All Performance Records', 'Performance'),
            
            # Performance Records - Actions
            ('performance.initialize', 'Initialize Performance Record', 'Performance'),
            
            # Objectives
            ('performance.objectives.submit', 'Submit Objectives', 'Performance'),
            ('performance.objectives.approve', 'Approve Objectives', 'Performance'),
            
            # Mid-Year Review - NEW PERMISSIONS
            ('performance.midyear.submit_employee', 'Submit Mid-Year Self-Review (Employee)', 'Performance'),
            ('performance.midyear.submit_manager', 'Complete Mid-Year Assessment (Manager)', 'Performance'),
            ('performance.midyear.request_clarification', 'Request Mid-Year Clarification', 'Performance'),
            
            # End-Year Review
            ('performance.endyear.submit_employee', 'Submit End-Year Self-Review (Employee)', 'Performance'),
            ('performance.endyear.complete', 'Complete End-Year Review (Manager)', 'Performance'),
            ('performance.endyear.approve_employee', 'Approve Final Performance (Employee)', 'Performance'),
            ('performance.endyear.approve_manager', 'Approve Final Performance (Manager)', 'Performance'),
            ('performance.endyear.request_clarification', 'Request End-Year Clarification', 'Performance'),
             ('performance.submit', 'Submit Performance for Approval', 'Performance'),
            ('performance.approve_as_manager', 'Approve Performance as Manager', 'Performance'),
            ('performance.approve_as_employee', 'Approve Performance as Employee', 'Performance'),
             ('performance.complete_end_year', 'Complete End-Year Review', 'Performance'),
            # General Actions
            ('performance.request_clarification', 'Request Clarification', 'Performance'),
            ('performance.recalculate_scores', 'Recalculate Performance Scores', 'Performance'),
            ('performance.export', 'Export Performance Data', 'Performance'),
            
            # Performance Settings
            ('performance.settings.view', 'View Performance Settings', 'Performance'),
            ('performance.settings.manage_years', 'Manage Performance Years', 'Performance'),
            ('performance.settings.manage_weights', 'Manage Weight Configs', 'Performance'),
            ('performance.settings.manage_scales', 'Manage Evaluation Scales', 'Performance'),
            ('performance.settings.manage_objectives', 'Manage Department Objectives', 'Performance'),
            # BULK UPLOAD
            ('bulk_upload.upload', 'Upload Bulk Data', 'Bulk Operations'),
            ('bulk_upload.download_template', 'Download Templates', 'Bulk Operations'),
    
            # ==================== COMPANY NEWS ====================
            # News Management
            ('news.news.view', 'View Company News', 'Company News'),
            ('news.news.view_all', 'View All News (including unpublished)', 'Company News'),
            ('news.news.create', 'Create Company News', 'Company News'),
            ('news.news.update', 'Update Company News', 'Company News'),
            ('news.news.delete', 'Delete Company News', 'Company News'),
            ('news.news.publish', 'Publish/Unpublish Company News', 'Company News'),
            ('news.news.pin', 'Pin/Unpin Company News', 'Company News'),
            ('news.news.view_statistics', 'View News Statistics', 'Company News'),

            # Target Groups
            ('news.target_group.view', 'View Target Groups', 'Company News'),
            ('news.target_group.create', 'Create Target Group', 'Company News'),
            ('news.target_group.update', 'Update Target Group', 'Company News'),
            ('news.target_group.delete', 'Delete Target Group', 'Company News'),
            ('news.target_group.add_members', 'Add Members to Target Group', 'Company News'),
            ('news.target_group.remove_members', 'Remove Members from Target Group', 'Company News'),
            ('news.target_group.view_statistics', 'View Target Group Statistics', 'Company News'),
            
            
             ('timeoff.dashboard.view', 'View Time Off Dashboard', 'Time Off'),
    ('timeoff.dashboard.view_own', 'View Own Time Off Dashboard', 'Time Off'),
    ('timeoff.dashboard.view_team', 'View Team Time Off Dashboard', 'Time Off'),
    ('timeoff.dashboard.view_statistics', 'View Time Off Statistics', 'Time Off'),
    
    # Balance Management
    ('timeoff.balance.view_own', 'View Own Balance', 'Time Off'),
    ('timeoff.balance.view_all', 'View All Balances', 'Time Off'),
    ('timeoff.balance.update', 'Update Employee Balance', 'Time Off'),
    ('timeoff.balance.reset', 'Reset Monthly Balances', 'Time Off'),
   
    
    # Request Management - View
    ('timeoff.request.view_own', 'View Own Time Off Requests', 'Time Off'),
    ('timeoff.request.view_team', 'View Team Time Off Requests', 'Time Off'),
    ('timeoff.request.view_all', 'View All Time Off Requests', 'Time Off'),
    
    # Request Management - Create/Update
    ('timeoff.request.create_own', 'Create Own Time Off Request', 'Time Off'),
    ('timeoff.request.create_for_employee', 'Create Time Off Request for Employee', 'Time Off'),
    ('timeoff.request.update_own', 'Update Own Time Off Request', 'Time Off'),
    ('timeoff.request.delete_own', 'Delete Own Time Off Request', 'Time Off'),
    
    # Request Management - Actions
    ('timeoff.request.cancel_own', 'Cancel Own Time Off Request', 'Time Off'),
    ('timeoff.request.approve_as_manager', 'Approve as Line Manager', 'Time Off'),
    ('timeoff.request.approve_as_hr', 'Approve as HR', 'Time Off'),
    ('timeoff.request.reject_as_manager', 'Reject as Line Manager', 'Time Off'),
    

    
    # Settings Management
    ('timeoff.settings.view', 'View Time Off Settings', 'Time Off'),
    ('timeoff.settings.update', 'Update Time Off Settings', 'Time Off'),
    ('timeoff.settings.manage_hr_emails', 'Manage HR Notification Emails', 'Time Off'),
    
    # Activity & History
    ('timeoff.activity.view_own', 'View Own Activity History', 'Time Off'),
    ('timeoff.activity.view_all', 'View All Activity History', 'Time Off'),
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