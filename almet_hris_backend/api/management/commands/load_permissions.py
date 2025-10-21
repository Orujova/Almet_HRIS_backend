# management/commands/load_permissions.py
# Run: python manage.py load_permissions

from django.core.management.base import BaseCommand
from api.role_models import Permission

class Command(BaseCommand):
    help = 'Load all permissions into database'

    def handle(self, *args, **kwargs):
        permissions_data = [
            # EMPLOYEES
            ('employees.employee.view', 'View Employees', 'Employees'),
            ('employees.employee.create', 'Create Employee', 'Employees'),
            ('employees.employee.update', 'Update Employee', 'Employees'),
            ('employees.employee.delete', 'Delete Employee', 'Employees'),
            ('employees.employee.export', 'Export Employees', 'Employees'),
            ('employees.employee.manage_line_manager', 'Manage Line Manager', 'Employees'),
            ('employees.employee.manage_tags', 'Manage Employee Tags', 'Employees'),
            ('employees.employee.manage_contract', 'Manage Employee Contract', 'Employees'),
            ('employees.employee.manage_system_access', 'Manage System Access', 'Employees'),
            ('employees.employee.view_archived', 'View Archived Employees', 'Employees'),
            ('employees.employee.restore', 'Restore Deleted Employees', 'Employees'),
            
            # ASSESSMENTS - Core Scales
            ('assessments.core_scale.view', 'View Core Scales', 'Assessments'),
            ('assessments.core_scale.create', 'Create Core Scale', 'Assessments'),
            ('assessments.core_scale.update', 'Update Core Scale', 'Assessments'),
            ('assessments.core_scale.delete', 'Delete Core Scale', 'Assessments'),
            
            # ASSESSMENTS - Behavioral Scales
            ('assessments.behavioral_scale.view', 'View Behavioral Scales', 'Assessments'),
            ('assessments.behavioral_scale.create', 'Create Behavioral Scale', 'Assessments'),
            ('assessments.behavioral_scale.update', 'Update Behavioral Scale', 'Assessments'),
            ('assessments.behavioral_scale.delete', 'Delete Behavioral Scale', 'Assessments'),
            
            # ASSESSMENTS - Employee Assessments
            ('assessments.employee_assessment.view', 'View Employee Assessments', 'Assessments'),
            ('assessments.employee_assessment.create', 'Create Employee Assessment', 'Assessments'),
            ('assessments.employee_assessment.update', 'Update Employee Assessment', 'Assessments'),
            ('assessments.employee_assessment.delete', 'Delete Employee Assessment', 'Assessments'),
            ('assessments.employee_assessment.submit', 'Submit Assessment', 'Assessments'),
            ('assessments.employee_assessment.reopen', 'Reopen Assessment', 'Assessments'),
            ('assessments.employee_assessment.export', 'Export Assessment', 'Assessments'),
            
            # ASSESSMENTS - Dashboard
            ('assessments.dashboard.view', 'View Assessment Dashboard', 'Assessments'),
            
            # ASSETS
            ('assets.asset.view', 'View Assets', 'Assets'),
            ('assets.asset.create', 'Create Asset', 'Assets'),
            ('assets.asset.update', 'Update Asset', 'Assets'),
            ('assets.asset.delete', 'Delete Asset', 'Assets'),
            ('assets.asset.assign', 'Assign Asset to Employee', 'Assets'),
            ('assets.asset.checkin', 'Check-in Asset', 'Assets'),
            ('assets.asset.change_status', 'Change Asset Status', 'Assets'),
            ('assets.asset.export', 'Export Assets', 'Assets'),
            ('assets.asset.view_history', 'View Asset History', 'Assets'),
            
            ('assets.category.view', 'View Asset Categories', 'Assets'),
            ('assets.category.create', 'Create Asset Category', 'Assets'),
            ('assets.category.update', 'Update Asset Category', 'Assets'),
            ('assets.category.delete', 'Delete Asset Category', 'Assets'),
            
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
            
            # COMPETENCY
            ('competency.skill.view', 'View Skills', 'Competency'),
            ('competency.skill.create', 'Create Skill', 'Competency'),
            ('competency.skill.update', 'Update Skill', 'Competency'),
            ('competency.skill.delete', 'Delete Skill', 'Competency'),
            ('competency.skill.bulk_create', 'Bulk Create Skills', 'Competency'),
            
            ('competency.behavioral.view', 'View Behavioral Competencies', 'Competency'),
            ('competency.behavioral.create', 'Create Behavioral Competency', 'Competency'),
            ('competency.behavioral.update', 'Update Behavioral Competency', 'Competency'),
            ('competency.behavioral.delete', 'Delete Behavioral Competency', 'Competency'),
            ('competency.behavioral.bulk_create', 'Bulk Create Competencies', 'Competency'),
            
            ('competency.group.view', 'View Competency Groups', 'Competency'),
            ('competency.group.create', 'Create Competency Group', 'Competency'),
            ('competency.group.update', 'Update Competency Group', 'Competency'),
            ('competency.group.delete', 'Delete Competency Group', 'Competency'),
            
            # GRADING
            ('grading.salary_grade.view', 'View Salary Grades', 'Grading'),
            ('grading.salary_grade.create', 'Create Salary Grade', 'Grading'),
            ('grading.salary_grade.update', 'Update Salary Grade', 'Grading'),
            ('grading.salary_grade.delete', 'Delete Salary Grade', 'Grading'),
            
            ('grading.scenario.view', 'View Grading Scenarios', 'Grading'),
            ('grading.scenario.create', 'Create Grading Scenario', 'Grading'),
            ('grading.scenario.update', 'Update Grading Scenario', 'Grading'),
            ('grading.scenario.delete', 'Delete Grading Scenario', 'Grading'),
            ('grading.scenario.apply', 'Apply Scenario as Current', 'Grading'),
            ('grading.scenario.calculate', 'Calculate Dynamic Grading', 'Grading'),
            
            ('grading.employee.view', 'View Employee Grades', 'Grading'),
            ('grading.employee.update', 'Update Employee Grades', 'Grading'),
            ('grading.employee.bulk_update', 'Bulk Update Grades', 'Grading'),
            
            # ORG CHART
            ('org_chart.view', 'View Organization Chart', 'Org Chart'),
            ('org_chart.view_full', 'View Full Org Chart with Vacancies', 'Org Chart'),
            ('org_chart.manage_visibility', 'Manage Org Chart Visibility', 'Org Chart'),
            ('org_chart.view_statistics', 'View Org Chart Statistics', 'Org Chart'),
            
            # DEPARTMENTS & UNITS
            ('organization.department.view', 'View Departments', 'Organization'),
            ('organization.department.create', 'Create Department', 'Organization'),
            ('organization.department.update', 'Update Department', 'Organization'),
            ('organization.department.delete', 'Delete Department', 'Organization'),
            
            ('organization.unit.view', 'View Units', 'Organization'),
            ('organization.unit.create', 'Create Unit', 'Organization'),
            ('organization.unit.update', 'Update Unit', 'Organization'),
            ('organization.unit.delete', 'Delete Unit', 'Organization'),
            
            ('organization.business_function.view', 'View Business Functions', 'Organization'),
            ('organization.business_function.create', 'Create Business Function', 'Organization'),
            ('organization.business_function.update', 'Update Business Function', 'Organization'),
            ('organization.business_function.delete', 'Delete Business Function', 'Organization'),
            
            ('organization.job_function.view', 'View Job Functions', 'Organization'),
            ('organization.job_function.create', 'Create Job Function', 'Organization'),
            ('organization.job_function.update', 'Update Job Function', 'Organization'),
            ('organization.job_function.delete', 'Delete Job Function', 'Organization'),
            
            # VACANT POSITIONS
            ('vacant_position.view', 'View Vacant Positions', 'Vacant Positions'),
            ('vacant_position.create', 'Create Vacant Position', 'Vacant Positions'),
            ('vacant_position.update', 'Update Vacant Position', 'Vacant Positions'),
            ('vacant_position.delete', 'Delete Vacant Position', 'Vacant Positions'),
            ('vacant_position.convert', 'Convert to Employee', 'Vacant Positions'),
            
            # RBAC - Roles & Permissions
            ('rbac.role.view', 'View Roles', 'RBAC'),
            ('rbac.role.create', 'Create Role', 'RBAC'),
            ('rbac.role.update', 'Update Role', 'RBAC'),
            ('rbac.role.delete', 'Delete Role', 'RBAC'),
            ('rbac.role.assign_permissions', 'Assign Permissions to Roles', 'RBAC'),
            ('rbac.role.assign_to_employees', 'Assign Roles to Employees', 'RBAC'),
            ('rbac.role.view_statistics', 'View Role Statistics', 'RBAC'),
            
            ('rbac.permission.view', 'View Permissions', 'RBAC'),
            ('rbac.permission.create', 'Create Permission', 'RBAC'),
            ('rbac.permission.update', 'Update Permission', 'RBAC'),
            ('rbac.permission.delete', 'Delete Permission', 'RBAC'),
            
            # CONTRACT CONFIGS
            ('contract.config.view', 'View Contract Configs', 'Contracts'),
            ('contract.config.create', 'Create Contract Config', 'Contracts'),
            ('contract.config.update', 'Update Contract Config', 'Contracts'),
            ('contract.config.delete', 'Delete Contract Config', 'Contracts'),
            
            # BULK UPLOAD
            ('bulk_upload.upload', 'Upload Bulk Data', 'Bulk Operations'),
            ('bulk_upload.download_template', 'Download Templates', 'Bulk Operations'),
            
            # PROFILE IMAGES
            ('profile.image.upload', 'Upload Profile Image', 'Profile'),
            ('profile.image.delete', 'Delete Profile Image', 'Profile'),
            
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