# api/notification_views.py - FIXED with proper token extraction
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
from .models import UserGraphToken  # ✅ ADD THIS
from .token_helpers import extract_graph_token_from_request  # ✅ ADD THIS

logger = logging.getLogger(__name__)


def get_graph_token_from_request(request):
    """
    ✅ FIXED: Extract Microsoft Graph token from request
    Tries multiple sources in priority order
    """
    # 1. Try custom header
    graph_token = request.META.get('HTTP_X_GRAPH_TOKEN')
    if graph_token:
        logger.info("✅ Graph token found in X-Graph-Token header")
        return graph_token
    
    # 2. Try database (stored during login)
    if request.user and request.user.is_authenticated:
        try:
            graph_token = UserGraphToken.get_valid_token(request.user)
            if graph_token:
                logger.info(f"✅ Graph token found in database for {request.user.username}")
                return graph_token
            else:
                logger.warning(f"⚠️ Graph token in database is expired for {request.user.username}")
        except Exception as e:
            logger.error(f"❌ Error retrieving Graph token from database: {e}")
    
    logger.warning("❌ No valid Graph token found")
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


# ==================== GRAPH TOKEN STATUS ====================

@swagger_auto_schema(
    method='get',
    operation_description="Check Microsoft Graph token status",
    operation_summary="Graph Token Status",
    tags=['Notifications'],
    responses={
        200: openapi.Response(
            description='Token status',
            examples={
                'application/json': {
                    'has_graph_token': True,
                    'token_valid': True,
                    'expires_at': '2025-01-15T10:30:00Z',
                    'can_send_emails': True
                }
            }
        )
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_graph_token_status(request):
    """Check if user has valid Graph token for sending emails"""
    try:
        graph_token = get_graph_token_from_request(request)
        
        if graph_token:
            # Check expiry
            try:
                token_obj = UserGraphToken.objects.get(user=request.user)
                
                return Response({
                    'has_graph_token': True,
                    'token_valid': token_obj.is_valid(),
                    'token_expired': token_obj.is_expired(),
                    'expires_at': token_obj.expires_at.isoformat(),
                    'can_send_emails': token_obj.is_valid(),
                    'message': 'Graph token is valid' if token_obj.is_valid() else 'Token expired'
                })
            except UserGraphToken.DoesNotExist:
                return Response({
                    'has_graph_token': True,
                    'token_valid': True,
                    'can_send_emails': True,
                    'message': 'Graph token available (no expiry info)'
                })
        else:
            return Response({
                'has_graph_token': False,
                'token_valid': False,
                'can_send_emails': False,
                'message': 'No Graph token. Please login again.'
            })
            
    except Exception as e:
        logger.error(f"Error checking Graph token status: {e}")
        return Response({
            'has_graph_token': False,
            'token_valid': False,
            'can_send_emails': False,
            'message': f'Error: {str(e)}'
        }, status=status.HTTP_400_BAD_REQUEST)


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
    """
    ✅ FIXED: Get Business Trip emails from user's Outlook mailbox
    Properly extracts Graph token from request
    """
    try:
        # ✅ Get Graph token using helper function
        graph_token = get_graph_token_from_request(request)
        
        if not graph_token:
            logger.warning(f"No Graph token for user {request.user.username}")
            
            return Response({
                'error': 'Microsoft Graph token not available',
                'message': 'Please login again to refresh your Graph token',
                'count': 0,
                'emails': [],
                'graph_token_status': 'missing'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        logger.info(f"✅ Graph token retrieved for {request.user.username}")
        
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
                'from_name': email.get('from', {}).get('emailAddress', {}).get('name'),
                'received_at': email.get('receivedDateTime'),
                'is_read': email.get('isRead'),
                'has_attachments': email.get('hasAttachments', False),
                'importance': email.get('importance'),
                'preview': email.get('bodyPreview', '')[:200]
            })
        
        logger.info(f"✅ Found {len(formatted_emails)} emails for {request.user.username}")
        
        return Response({
            'success': True,
            'count': len(formatted_emails),
            'emails': formatted_emails,
            'subject_filter': subject_filter,
            'graph_token_status': 'valid'
        })
        
    except Exception as e:
        logger.error(f"Error getting Outlook emails: {e}")
        import traceback
        logger.error(traceback.format_exc())
        
        return Response({
            'error': str(e),
            'count': 0,
            'emails': [],
            'graph_token_status': 'error'
        }, status=status.HTTP_400_BAD_REQUEST)

@swagger_auto_schema(
    method='post',
    operation_description="Mark email as read",
    operation_summary="Mark Email as Read",
    tags=['Notifications'],
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=['message_id'],
        properties={
            'message_id': openapi.Schema(type=openapi.TYPE_STRING, description='Email message ID')
        }
    ),
    responses={
        200: openapi.Response(description='Success'),
        400: openapi.Response(description='Error')
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_email_read(request):
    """Mark an email as read"""
    try:
        message_id = request.data.get('message_id')
        
        if not message_id:
            return Response(
                {'error': 'message_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get Graph token
        graph_token = get_graph_token_from_request(request)
        
        if not graph_token:
            return Response({
                'error': 'Microsoft Graph token not available',
                'message': 'Please login again'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        # Mark as read
        success = notification_service.mark_email_as_read(
            access_token=graph_token,
            message_id=message_id
        )
        
        if success:
            return Response({
                'success': True,
                'message': 'Email marked as read',
                'message_id': message_id
            })
        else:
            return Response({
                'error': 'Failed to mark email as read'
            }, status=status.HTTP_400_BAD_REQUEST)
            
    except Exception as e:
        logger.error(f"Error in mark_email_read: {e}")
        return Response({
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)


@swagger_auto_schema(
    method='post',
    operation_description="Mark email as unread",
    operation_summary="Mark Email as Unread",
    tags=['Notifications'],
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=['message_id'],
        properties={
            'message_id': openapi.Schema(type=openapi.TYPE_STRING, description='Email message ID')
        }
    ),
    responses={200: openapi.Response(description='Success')}
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_email_unread(request):
    """Mark an email as unread"""
    try:
        message_id = request.data.get('message_id')
        
        if not message_id:
            return Response(
                {'error': 'message_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        graph_token = get_graph_token_from_request(request)
        
        if not graph_token:
            return Response({
                'error': 'Microsoft Graph token not available'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        success = notification_service.mark_email_as_unread(
            access_token=graph_token,
            message_id=message_id
        )
        
        if success:
            return Response({
                'success': True,
                'message': 'Email marked as unread',
                'message_id': message_id
            })
        else:
            return Response({
                'error': 'Failed to mark email as unread'
            }, status=status.HTTP_400_BAD_REQUEST)
            
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)


@swagger_auto_schema(
    method='post',
    operation_description="Mark multiple Business Trip emails as read",
    operation_summary="Mark All Business Trip Emails as Read",
    tags=['Notifications'],
    responses={200: openapi.Response(description='Batch result')}
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_all_business_trip_emails_read(request):
    """Mark all Business Trip emails as read"""
    try:
        graph_token = get_graph_token_from_request(request)
        
        if not graph_token:
            return Response({
                'error': 'Microsoft Graph token not available'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        # Get all Business Trip emails
        settings = NotificationSettings.get_active()
        emails = notification_service.get_emails_by_subject(
            access_token=graph_token,
            subject_filter=settings.business_trip_subject_prefix,
            top=50
        )
        
        # Get unread email IDs
        unread_ids = [
            email['id'] for email in emails 
            if not email.get('isRead', False)
        ]
        
        if not unread_ids:
            return Response({
                'success': True,
                'message': 'No unread Business Trip emails',
                'marked_count': 0
            })
        
        # Mark all as read
        results = notification_service.mark_multiple_emails_as_read(
            access_token=graph_token,
            message_ids=unread_ids
        )
        
        return Response({
            'success': True,
            'marked_count': results['success'],
            'failed_count': results['failed'],
            'total_unread': len(unread_ids)
        })
        
    except Exception as e:
        logger.error(f"Error marking emails as read: {e}")
        return Response({
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)