# api/notification_views.py
import logging
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status, viewsets
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .notification_models import NotificationSettings, EmailTemplate, NotificationLog
from .notification_serializers import (
    NotificationSettingsSerializer,
    EmailTemplateSerializer,
    NotificationLogSerializer
)
from .notification_service import notification_service
from .business_trip_permissions import is_admin_user

logger = logging.getLogger(__name__)


def get_user_access_token(request):
    """Extract access token from request"""
    # Get token from Authorization header
    auth_header = request.META.get('HTTP_AUTHORIZATION', '')
    if auth_header.startswith('Bearer '):
        return auth_header.split(' ')[1]
    return None


# ==================== NOTIFICATION SETTINGS ====================

@swagger_auto_schema(
    method='get',
    operation_description="Get notification settings",
    operation_summary="Get Notification Settings",
    tags=['Notifications'],
    responses={200: NotificationSettingsSerializer()}
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_notification_settings(request):
    """Get notification settings"""
    try:
        settings = NotificationSettings.get_active()
        serializer = NotificationSettingsSerializer(settings)
        return Response(serializer.data)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@swagger_auto_schema(
    method='put',
    operation_description="Update notification settings (Admin only)",
    operation_summary="Update Notification Settings",
    tags=['Notifications'],
    request_body=NotificationSettingsSerializer,
    responses={200: NotificationSettingsSerializer()}
)
@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_notification_settings(request):
    """Update notification settings (Admin only)"""
    try:
        if not is_admin_user(request.user):
            return Response(
                {'error': 'Admin permission required'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        settings = NotificationSettings.get_active()
        serializer = NotificationSettingsSerializer(settings, data=request.data, partial=True)
        
        if serializer.is_valid():
            serializer.save(updated_by=request.user)
            return Response(serializer.data)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


# ==================== EMAIL TEMPLATES ====================

class EmailTemplateViewSet(viewsets.ModelViewSet):
    """Email Template CRUD ViewSet"""
    
    queryset = EmailTemplate.objects.all()
    serializer_class = EmailTemplateSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return EmailTemplate.objects.filter(is_active=True).order_by('template_type')
    
    def perform_create(self, serializer):
        if not is_admin_user(self.request.user):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Admin permission required")
        serializer.save(created_by=self.request.user)
    
    def perform_update(self, serializer):
        if not is_admin_user(self.request.user):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Admin permission required")
        serializer.save()
    
    def destroy(self, request, *args, **kwargs):
        if not is_admin_user(request.user):
            return Response(
                {'error': 'Admin permission required'},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().destroy(request, *args, **kwargs)


# ==================== NOTIFICATION LOGS ====================

@swagger_auto_schema(
    method='get',
    operation_description="Get notification history",
    operation_summary="Get Notification History",
    tags=['Notifications'],
    manual_parameters=[
        openapi.Parameter('status', openapi.IN_QUERY, type=openapi.TYPE_STRING),
        openapi.Parameter('recipient_email', openapi.IN_QUERY, type=openapi.TYPE_STRING),
        openapi.Parameter('related_model', openapi.IN_QUERY, type=openapi.TYPE_STRING),
        openapi.Parameter('days', openapi.IN_QUERY, type=openapi.TYPE_INTEGER, description='Last N days'),
    ],
    responses={200: NotificationLogSerializer(many=True)}
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_notification_history(request):
    """Get notification history with filters"""
    try:
        # Base queryset
        logs = NotificationLog.objects.all()
        
        # Apply filters
        status_filter = request.GET.get('status')
        if status_filter:
            logs = logs.filter(status=status_filter)
        
        recipient_email = request.GET.get('recipient_email')
        if recipient_email:
            logs = logs.filter(recipient_email__icontains=recipient_email)
        
        related_model = request.GET.get('related_model')
        if related_model:
            logs = logs.filter(related_model=related_model)
        
        # Time filter
        days = request.GET.get('days', 30)
        try:
            days = int(days)
            date_from = timezone.now() - timedelta(days=days)
            logs = logs.filter(created_at__gte=date_from)
        except ValueError:
            pass
        
        # Order and limit
        logs = logs.order_by('-created_at')[:100]
        
        serializer = NotificationLogSerializer(logs, many=True)
        return Response({
            'count': logs.count(),
            'notifications': serializer.data
        })
        
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@swagger_auto_schema(
    method='get',
    operation_description="Get Business Trip notification history",
    operation_summary="Get Business Trip Notifications",
    tags=['Notifications'],
    responses={200: NotificationLogSerializer(many=True)}
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_business_trip_notifications(request):
    """Get all Business Trip related notifications"""
    try:
        logs = NotificationLog.objects.filter(
            related_model='BusinessTripRequest'
        ).order_by('-created_at')[:50]
        
        serializer = NotificationLogSerializer(logs, many=True)
        return Response({
            'count': logs.count(),
            'notifications': serializer.data
        })
        
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

# ==================== OUTLOOK INTEGRATION ====================

@swagger_auto_schema(
    method='get',
    operation_description="Get Business Trip emails from Outlook",
    operation_summary="Get Outlook Business Trip Emails",
    tags=['Notifications'],
    responses={200: openapi.Response(description='Outlook emails')}
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_outlook_business_trip_emails(request):
    """Get Business Trip emails from user's Outlook mailbox"""
    try:
        from .models import UserGraphToken
        
        # Get Graph token from database
        graph_token = UserGraphToken.get_valid_token(request.user)
        
        if not graph_token:
            return Response({
                'error': 'Microsoft Graph token not available. Please login again.',
                'count': 0,
                'emails': []
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        # Get Business Trip emails
        settings = NotificationSettings.get_active()
        subject_filter = settings.business_trip_subject_prefix
        
        logger.info(f"Searching emails with filter: {subject_filter}")
        
        emails = notification_service.get_emails_by_subject(
            access_token=graph_token,
            subject_filter=subject_filter,
            top=50
        )
        
        # Format response
        formatted_emails = []
        for email in emails:
            formatted_emails.append({
                'id': email.get('id'),
                'subject': email.get('subject'),
                'from': email.get('from', {}).get('emailAddress', {}).get('address'),
                'received_at': email.get('receivedDateTime'),
                'is_read': email.get('isRead'),
                'preview': email.get('bodyPreview', '')[:200]
            })
        
        logger.info(f"Found {len(formatted_emails)} emails")
        
        return Response({
            'count': len(formatted_emails),
            'emails': formatted_emails
        })
        
    except Exception as e:
        logger.error(f"Error getting Outlook emails: {e}")
        return Response({
            'error': str(e),
            'count': 0,
            'emails': []
        }, status=status.HTTP_400_BAD_REQUEST)