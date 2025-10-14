# api/notification_urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import notification_views

router = DefaultRouter()
router.register(r'templates', notification_views.EmailTemplateViewSet, basename='notification-template')

urlpatterns = [

    path('history/', notification_views.get_notification_history, name='notification-history'),

    path('outlook/mark-read/', notification_views.mark_email_read, name='notification-mark-read'),
    path('outlook/mark-unread/', notification_views.mark_email_unread, name='notification-mark-unread'),
    path('outlook/mark-all-read/', notification_views.mark_all_emails_read, name='notification-mark-all-read'),
    path('outlook/emails/', notification_views.get_outlook_emails, name='notification-outlook-emails'),

    path('', include(router.urls)),
]