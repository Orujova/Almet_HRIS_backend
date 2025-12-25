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
    # ==================== EMPLOYEE STATUS UPDATES ====================
    'update-employee-statuses-daily': {
        'task': 'api.tasks.update_all_employee_statuses',
        'schedule': crontab(hour=1, minute=0),
    },
    'update-employee-statuses-hourly': {
        'task': 'api.tasks.update_all_employee_statuses',
        'schedule': crontab(minute=0),
    },
    
    # ==================== CELEBRATION NOTIFICATIONS ====================
    'send-daily-celebrations': {
    'task': 'api.tasks.send_daily_celebration_notifications',
    # 'schedule': crontab(minute='*/2'),# # 🧪 TEST: Every 2 minutes
    # 'schedule': crontab(hour=9, minute=0),
    'schedule': crontab(hour=10, minute=30)

},
}

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')