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
    # ==================== CONTRACT & PROBATION TASKS ====================
    'check-expiring-contracts': {
        'task': 'api.tasks.check_expiring_contracts',  # ✅ FIXED: Correct task name
        # 'schedule': crontab(hour=10, minute=0),  # ✅ Daily at 10 AM (production)
        'schedule': crontab(minute='*/2'), 
    },
    
    'check-probation-reviews': {
        'task': 'api.tasks.check_probation_reviews',  # ✅ FIXED: Correct task name
        # 'schedule': crontab(hour=10, minute=30),  # ✅ Daily at 10:30 AM (production)
        'schedule': crontab(minute='*/2'),  # 🧪 TEST: Every 2 minutes
    },
    
    'send-resignation-reminders': {
        'task': 'api.tasks.send_resignation_reminders',  # ✅ FIXED: Correct task name
        'schedule': crontab(hour=9, minute=0),  # Daily at 9 AM
    },
    
    'send-exit-interview-reminders': {
        'task': 'api.tasks.send_exit_interview_reminders',  # ✅ FIXED: Correct task name
        'schedule': crontab(hour=9, minute=30),  # Daily at 9:30 AM
    },
    
    # ==================== CELEBRATION NOTIFICATIONS ====================
    'send-daily-celebrations': {
        'task': 'api.tasks.send_daily_celebration_notifications',
        'schedule': crontab(hour=9, minute=0),  # Daily at 9 AM
    },
}

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')