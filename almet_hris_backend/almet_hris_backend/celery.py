import os
from celery import Celery
from celery.schedules import crontab

# Set default Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'almet_hris_backend.settings')

app = Celery('almet_hris_backend')

# Load config from Django settings with CELERY namespace
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks from all installed apps
app.autodiscover_tasks()

# Configure periodic tasks
app.conf.beat_schedule = {
    'update-employee-statuses-every-day': {
        'task': 'api.tasks.update_all_employee_statuses',
        'schedule': crontab(hour=1, minute=0),  # Run daily at 1 AM
    },
    'update-employee-statuses-every-hour': {
        'task': 'api.tasks.update_all_employee_statuses',
        'schedule': crontab(minute=0),  # Run every hour
    },
}

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')