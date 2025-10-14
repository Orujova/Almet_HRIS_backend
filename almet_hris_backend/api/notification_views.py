# api/notification_views.py - FIXED with proper token extraction
import logging
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status, viewsets
from django.utils import timezone
from datetime import timedelta
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .notification_models import NotificationSettings, EmailTemplate, NotificationLog
from .notification_serializers import (
    EmailTemplateSerializer,
    NotificationLogSerializer
)
from .notification_service import notification_service
from .business_trip_permissions import is_admin_user
from .models import UserGraphToken  # ✅ ADD THIS


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

# ==================== OUTLOOK INTEGRATION ====================

@swagger_auto_schema(
    method='get',
    operation_description="Get emails from Outlook filtered by module",
    operation_summary="Get Outlook Emails",
    tags=['Notifications'],
    manual_parameters=[
        openapi.Parameter(
            'module',
            openapi.IN_QUERY,
            type=openapi.TYPE_STRING,
            enum=['business_trip', 'vacation', 'all'],
            required=False,
            default='all',
            description='Filter by module: business_trip, vacation, or all'
        ),
        openapi.Parameter(
            'top',
            openapi.IN_QUERY,
            type=openapi.TYPE_INTEGER,
            required=False,
            default=50,
            description='Number of emails to retrieve (max 50)'
        )
    ],
    responses={200: openapi.Response(description='Outlook emails')}
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_outlook_emails(request):
    """
    Get emails from user's Outlook mailbox
    Filter by module: business_trip, vacation, or all
    """
    try:
        # Get parameters
        module = request.GET.get('module', 'all')
        top = int(request.GET.get('top', 50))
        
        # Get Graph token
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
        logger.info(f"📧 Fetching emails for module: {module}")
        
        # Get settings
        settings = NotificationSettings.get_active()
        
        # Determine which filters to use
        emails = []
        
        if module == 'business_trip':
            # Only Business Trip emails
            subject_filter = settings.business_trip_subject_prefix
            emails = notification_service.get_emails_by_subject(
                access_token=graph_token,
                subject_filter=subject_filter,
                top=top
            )
            
        elif module == 'vacation':
            # Only Vacation emails
            subject_filter = settings.vacation_subject_prefix
            emails = notification_service.get_emails_by_subject(
                access_token=graph_token,
                subject_filter=subject_filter,
                top=top
            )
            
        else:  # module == 'all'
            # Get both Business Trip and Vacation emails
            business_trip_emails = notification_service.get_emails_by_subject(
                access_token=graph_token,
                subject_filter=settings.business_trip_subject_prefix,
                top=top
            )
            
            vacation_emails = notification_service.get_emails_by_subject(
                access_token=graph_token,
                subject_filter=settings.vacation_subject_prefix,
                top=top
            )
            
            # Combine and sort by receivedDateTime
            emails = business_trip_emails + vacation_emails
            emails.sort(key=lambda x: x.get('receivedDateTime', ''), reverse=True)
            
            # Limit to top count
            emails = emails[:top]
        
        # Format response
        formatted_emails = []
        for email in emails:
            # Determine module from subject
            subject = email.get('subject', '')
            email_module = 'unknown'
            
            if settings.business_trip_subject_prefix in subject:
                email_module = 'business_trip'
            elif settings.vacation_subject_prefix in subject:
                email_module = 'vacation'
            
            formatted_emails.append({
                'id': email.get('id'),
                'subject': subject,
                'module': email_module,  # ✅ Module tag
                'from': email.get('from', {}).get('emailAddress', {}).get('address'),
                'from_name': email.get('from', {}).get('emailAddress', {}).get('name'),
                'received_at': email.get('receivedDateTime'),
                'is_read': email.get('isRead'),
                'has_attachments': email.get('hasAttachments', False),
                'importance': email.get('importance'),
                'preview': email.get('bodyPreview', '')[:200]
            })
        
        logger.info(f"✅ Found {len(formatted_emails)} emails for module: {module}")
        
        return Response({
            'success': True,
            'count': len(formatted_emails),
            'emails': formatted_emails,
            'module_filter': module,
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
    operation_description="Mark all emails as read by module",
    operation_summary="Mark All Emails as Read",
    tags=['Notifications'],
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=['module'],
        properties={
            'module': openapi.Schema(
                type=openapi.TYPE_STRING,
                enum=['business_trip', 'vacation', 'all'],
                description='Module filter'
            )
        }
    ),
    responses={200: openapi.Response(description='Batch result')}
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_all_emails_read(request):
    """Mark all emails as read filtered by module"""
    try:
        module = request.data.get('module', 'all')
        
        graph_token = get_graph_token_from_request(request)
        
        if not graph_token:
            return Response({
                'error': 'Microsoft Graph token not available'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        settings = NotificationSettings.get_active()
        
        # Collect unread email IDs based on module
        unread_ids = []
        
        if module in ['business_trip', 'all']:
            # Get Business Trip emails
            bt_emails = notification_service.get_emails_by_subject(
                access_token=graph_token,
                subject_filter=settings.business_trip_subject_prefix,
                top=50
            )
            unread_ids.extend([
                email['id'] for email in bt_emails 
                if not email.get('isRead', False)
            ])
        
        if module in ['vacation', 'all']:
            # Get Vacation emails
            vac_emails = notification_service.get_emails_by_subject(
                access_token=graph_token,
                subject_filter=settings.vacation_subject_prefix,
                top=50
            )
            unread_ids.extend([
                email['id'] for email in vac_emails 
                if not email.get('isRead', False)
            ])
        
        if not unread_ids:
            return Response({
                'success': True,
                'message': f'No unread emails for module: {module}',
                'marked_count': 0,
                'module': module
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
            'total_unread': len(unread_ids),
            'module': module
        })
        
    except Exception as e:
        logger.error(f"Error marking emails as read: {e}")
        return Response({
            'error': str(e)
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