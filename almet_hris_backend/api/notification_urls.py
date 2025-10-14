# api/notification_urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import notification_views

router = DefaultRouter()
router.register(r'templates', notification_views.EmailTemplateViewSet, basename='notification-template')

urlpatterns = [
    # Settings
    path('settings/', notification_views.get_notification_settings, name='notification-settings'),
    path('settings/update/', notification_views.update_notification_settings, name='notification-settings-update'),
    
    # History
    path('history/', notification_views.get_notification_history, name='notification-history'),
    path('history/business-trip/', notification_views.get_business_trip_notifications, name='notification-business-trip'),
    
 
    
 path('outlook/mark-read/', notification_views.mark_email_read, name='notification-mark-read'),
    path('outlook/mark-unread/', notification_views.mark_email_unread, name='notification-mark-unread'),
    path('outlook/mark-all-business-trips-read/', notification_views.mark_all_business_trip_emails_read, name='notification-mark-all-read'),
    
    # Outlook Integration
    path('outlook/business-trips/', notification_views.get_outlook_business_trip_emails, name='notification-outlook-business-trips'),
    
    # Templates
    path('', include(router.urls)),
]