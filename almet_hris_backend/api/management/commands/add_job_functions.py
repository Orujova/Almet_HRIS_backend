# management/commands/add_job_functions.py
"""
Django management command to add job functions to the system.
Usage: python manage.py add_job_functions
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from api.models import JobFunction

class Command(BaseCommand):
    help = 'Add job functions to the system (skips existing ones)'

    def handle(self, *args, **kwargs):
        job_functions_list = [
            "STRATEGY DESIGN & EXECUTION",
            "STRATEGY EXECUTION",
            "CONSTRUCTION",
            "PRODUCTION",
            "PROCESS PERFORMANCE",
            "MAINTENANCE",
            "QUALITY CONTROL",
            "FINANCE BUSINESS",
            "FINANCE OPERATIONS",
            "LEGAL",
            "HSE",
            "HR BUSINESS & CULTURE",
            "HR OPERATIONS",
            "MARKETING BUSINESS",
            "EXTERNAL COMMUNICATION",
            "SOFTWARE DEVELOPMENT",
            "BUSINESS PLANNING",
            "ADMINISTRATION",
            "TRADE",
            "SALES",
            "OPERATIONS",
            "OPERATIONS SUPPORT",
            "LOGISTICS",
            "WAREHOUSE & INVENTORY",
        ]

        added_count = 0
        skipped_count = 0
        errors = []

        self.stdout.write(self.style.NOTICE(f'Starting to add {len(job_functions_list)} job functions...'))

        with transaction.atomic():
            for job_function_name in job_functions_list:
                try:
                    job_function, created = JobFunction.objects.get_or_create(
                        name=job_function_name,
                        defaults={
                            'is_active': True
                        }
                    )
                    
                    if created:
                        added_count += 1
                        self.stdout.write(
                            self.style.SUCCESS(f'✓ Added: {job_function_name}')
                        )
                    else:
                        skipped_count += 1
                        self.stdout.write(
                            self.style.WARNING(f'⊘ Skipped (already exists): {job_function_name}')
                        )
                
                except Exception as e:
                    errors.append(f'{job_function_name}: {str(e)}')
                    self.stdout.write(
                        self.style.ERROR(f'✗ Error adding {job_function_name}: {str(e)}')
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
        
        total_job_functions = JobFunction.objects.filter(is_active=True).count()
        self.stdout.write(
            self.style.NOTICE(f'\nTotal active job functions in database: {total_job_functions}')
        )