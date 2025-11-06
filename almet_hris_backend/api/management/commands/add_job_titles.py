# management/commands/add_job_titles.py
"""
Django management command to add job titles to the system.
Usage: python manage.py add_job_titles
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from api.models import JobTitle

class Command(BaseCommand):
    help = 'Add job titles to the system (skips existing ones)'

    def handle(self, *args, **kwargs):
        job_titles_list = [
            "DEPUTY CHAIRMAN ON FINANCE",
            "DEPUTY CHAIRMAN ON COMMERCIAL",
            "DEPUTY CHAIRMAN ON BUSINESS TRASNFORMATION & CULTURE",
            "DEPUTY CHAIRMAN ON OPERAITON & SUPPLY CHAIN",
            "GROUP FINANCE DIRECTOR",
            "HEAD OF GROUP LEGAL & COMPLIANCE",
            "HEAD OF PROJECTS",
            "PROJECTS MANAGER",
            "CEO",
            "HEAD OF OPERATIONS",
            "HEAD OF PRODUCTION",
            "PROCESS PERFORMANCE ENGINEER",
            "MAINTENANCE MANAGER",
            "QUALITY CONTROL MANAGER",
            "HEAD OF FINANCE",
            "HEAD OF BUDGETING & COTROLLING",
            "HEAD OF TREASURY & RISKS",
            "SENIOR BUSINESS ANALYST",
            "SENIOR BUDGETING & CONTROLLING SPECIALIST",
            "SENIOR REPORTING SPECIALIST",
            "GROUP CHIEF ACCOUNTANT",
            "CHIEF ACCOUNTANT",
            "SENIOR ACCOUNTANT",
            "ACCOUNTANT",
            "CASHIER",
            "JUNIOR ACCOUNTANT",
            "LEGAL DEPARTMENT MANAGER",
            "LAWYER",
            "HSE MANAGER",
            "HSE SPECIALIST",
            "HEAD OF PEOPLE & CULTURE",
            "HR MANAGER",
            "HR BUSINESS PARTNER",
            "HR OPERATIONS SPECIALIST",
            "MARKETING MANAGER",
            "COMMUNICATION SPECIALIST",
            "DATA & DIGITAL TRANSFORMATION MANAGER",
            "EXECUTIVE ASSISTANT TO CHAIRMAN",
            "ADMINISTRATION SPECIALIST",
            "FACILITIES ASSISTANT",
            "DRIVER",
            "HEAD OF SALES",
            "MANAGER OF TRADING",
            "SENIOR TRADER",
            "TRADER",
            "TRADING TRAINEE",
            "SALES MANAGER",
            "SENIOR SALES EXECUTIVE",
            "SALES EXECUTIVE",
            "OPERATIONS MANAGER",
            "OPERATIONS SUPERVISOR",
            "OPERATIONS SPECIALIST",
            "JUNIOR OPERATIONS SPECIALIST",
            "LOGISTICS MANAGER",
            "LOGISTICS SPECIALIST",
            "CUSTOMS SPECIALIST",
            "WAREHOUSE AND LOGISTICS SPECIALIST",
            "WAREHOUSE FOREMAN",
            "WAREHOUSEMAN",
        ]

        added_count = 0
        skipped_count = 0
        errors = []

        self.stdout.write(self.style.NOTICE(f'Starting to add {len(job_titles_list)} job titles...'))

        with transaction.atomic():
            for job_title_name in job_titles_list:
                try:
                    job_title, created = JobTitle.objects.get_or_create(
                        name=job_title_name,
                        defaults={
                            'description': f'Job title: {job_title_name}',
                            'is_active': True
                        }
                    )
                    
                    if created:
                        added_count += 1
                        self.stdout.write(
                            self.style.SUCCESS(f'✓ Added: {job_title_name}')
                        )
                    else:
                        skipped_count += 1
                        self.stdout.write(
                            self.style.WARNING(f'⊘ Skipped (already exists): {job_title_name}')
                        )
                
                except Exception as e:
                    errors.append(f'{job_title_name}: {str(e)}')
                    self.stdout.write(
                        self.style.ERROR(f'✗ Error adding {job_title_name}: {str(e)}')
                    )

        # Print summary
        self.stdout.write('\n' + '='*70)
        self.stdout.write(self.style.NOTICE('SUMMARY:'))
        self.stdout.write(self.style.SUCCESS(f'✓ Successfully added: {added_count}'))
        self.stdout.write(self.style.WARNING(f'⊘ Skipped (existing): {skipped_count}'))
        
        if errors:
            self.stdout.write(self.style.ERROR(f'✗ Errors: {len(errors)}'))
            for error in errors:
                self.stdout.write(self.style.ERROR(f'  - {error}'))
        else:
            self.stdout.write(self.style.SUCCESS('✓ No errors'))
        
        self.stdout.write('='*70)
        
        total_job_titles = JobTitle.objects.filter(is_active=True).count()
        self.stdout.write(
            self.style.NOTICE(f'\nTotal active job titles in database: {total_job_titles}')
        )