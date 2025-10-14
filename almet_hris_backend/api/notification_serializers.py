# api/notification_serializers.py
from rest_framework import serializers
from .notification_models import NotificationSettings, EmailTemplate, NotificationLog


class NotificationSettingsSerializer(serializers.ModelSerializer):
    """Notification Settings Serializer"""
    
    class Meta:
        model = NotificationSettings
        fields = [
            'id', 
           
            'enable_email_notifications', 'email_retry_attempts',
            'email_retry_delay_minutes', 'business_trip_subject_prefix',
            'is_active', 'created_at', 'updated_at','vacation_subject_prefix'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class EmailTemplateSerializer(serializers.ModelSerializer):
    """Email Template Serializer"""
    
    template_type_display = serializers.CharField(source='get_template_type_display', read_only=True)
    
    class Meta:
        model = EmailTemplate
        fields = [
            'id', 'template_type', 'template_type_display',
            'subject', 'body_html', 'body_text',
            'available_variables', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class NotificationLogSerializer(serializers.ModelSerializer):
    """Notification Log Serializer"""
    
    notification_type_display = serializers.CharField(source='get_notification_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    sent_by_name = serializers.CharField(source='sent_by.get_full_name', read_only=True)
    
    class Meta:
        model = NotificationLog
        fields = [
            'id', 'notification_type', 'notification_type_display',
            'recipient_email', 'recipient_name', 'subject', 'body',
            'related_model', 'related_object_id',
            'status', 'status_display', 'error_message', 'retry_count',
            'message_id', 'sent_at', 'created_at', 'updated_at',
            'sent_by', 'sent_by_name'
        ]
        read_only_fields = [
            'id', 'created_at', 'updated_at', 'sent_at',
            'message_id', 'sent_by'
        ]


