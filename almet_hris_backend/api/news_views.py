# api/news_views.py - COMPLETE WITH CATEGORY CRUD & NOTIFICATION INTEGRATION
"""
Company News System Views
- NewsCategoryViewSet: Dynamic category CRUD
- CompanyNewsViewSet: Full news management
- TargetGroupViewSet: Target group management
- Notification integration: Get company news from Outlook
"""

import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Q, Count, Sum
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .news_models import NewsCategory, CompanyNews, TargetGroup
from .news_serializers import (
    NewsCategorySerializer,
    NewsListSerializer,
    NewsDetailSerializer,
    NewsCreateUpdateSerializer,
    TargetGroupListSerializer,
    TargetGroupDetailSerializer,
    TargetGroupCreateUpdateSerializer,
  
)
from .news_permissions import (
    IsAdminOrNewsManager,
    IsAdminOrTargetGroupManager,
    CanViewNews,
    is_admin_user
)
from .news_notifications import news_notification_manager
from .token_helpers import extract_graph_token_from_request
from .notification_service import notification_service
from .notification_models import NotificationSettings

logger = logging.getLogger(__name__)


# ==================== NEWS CATEGORY VIEWSET ====================

class NewsCategoryViewSet(viewsets.ModelViewSet):

    
    queryset = NewsCategory.objects.filter(is_deleted=False)
    serializer_class = NewsCategorySerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = NewsCategory.objects.filter(is_deleted=False)
        
        # Filter by active status
        is_active = self.request.query_params.get('is_active', None)
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        # Search
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
             
                Q(description__icontains=search)
            )
        
        return queryset.order_by( 'name')
    
    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [IsAuthenticated()]
        return [IsAdminOrNewsManager()]
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
   


# ==================== COMPANY NEWS VIEWSET ====================

class CompanyNewsViewSet(viewsets.ModelViewSet):
  
    
    queryset = CompanyNews.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'list':
            return NewsListSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return NewsCreateUpdateSerializer
        return NewsDetailSerializer
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminOrNewsManager()]
        return [CanViewNews()]
    
    def get_queryset(self):
        queryset = CompanyNews.objects.filter(is_deleted=False)
        
        # Filter by category
        category_id = self.request.query_params.get('category', None)
        if category_id:
            queryset = queryset.filter(category_id=category_id)
        
        # Filter by published status
        is_published = self.request.query_params.get('is_published', None)
        if is_published is not None:
            queryset = queryset.filter(is_published=is_published.lower() == 'true')
        
        # Filter by pinned status
        is_pinned = self.request.query_params.get('is_pinned', None)
        if is_pinned is not None:
            queryset = queryset.filter(is_pinned=is_pinned.lower() == 'true')
        
        # Search
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) |
                Q(excerpt__icontains=search) |
                Q(content__icontains=search) |
                Q(tags__icontains=search)
            )
        
        # If not news manager, only show published news
        try:
            from .models import Employee
            employee = Employee.objects.get(user=self.request.user, is_deleted=False)
            if not is_admin_user(self.request.user):
                queryset = queryset.filter(is_published=True)
        except:
            queryset = queryset.filter(is_published=True)
        
        return queryset.select_related('author', 'category').prefetch_related('target_groups')

    
    def retrieve(self, request, *args, **kwargs):
        """Get news detail and increment view count"""
        instance = self.get_object()
        instance.increment_view_count()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
    
    def perform_create(self, serializer):
        """Create news and send notifications if published"""
        news = serializer.save(
            created_by=self.request.user,
            author=self.request.user
        )
        
        # If news is published and notify_members is True, send notifications
        if news.is_published and news.notify_members and not news.notification_sent:
            self._send_notifications_async(news)
        
        return news
    
    def perform_update(self, serializer):
        """Update news and send notifications if newly published"""
        instance = self.get_object()
        was_published = instance.is_published
        
        news = serializer.save(updated_by=self.request.user)
        
        # If news was just published and notify_members is True, send notifications
        if not was_published and news.is_published and news.notify_members and not news.notification_sent:
            self._send_notifications_async(news)
        
        return news
    
    

    @swagger_auto_schema(
        method='post',
        operation_description='Toggle pin status of news (pin if unpinned, unpin if pinned). No request body required, only news ID in URL.',
        manual_parameters=[
            openapi.Parameter(
                'id',
                openapi.IN_PATH,
                description="News UUID",
                type=openapi.TYPE_STRING,
                format=openapi.FORMAT_UUID,
                required=True
            )
        ],
        request_body=None,  # ✅ Explicitly None
        responses={
            200: openapi.Response(
                description='Pin status toggled successfully',
                examples={
                    'application/json': {
                        'message': 'News pinned successfully',
                        'news_id': '3fa85f64-5717-4562-b3fc-2c963f66afa6',
                        'is_pinned': True
                    }
                }
            ),
            404: openapi.Response(description='News not found'),
            403: openapi.Response(description='Permission denied')
        }
    )
    @action(detail=True, methods=['post'], permission_classes=[IsAdminOrNewsManager])
    def toggle_pin(self, request, pk=None):
        """Toggle pin status - pin if unpinned, unpin if pinned"""
        news = self.get_object()
        
        # Toggle the status
        news.is_pinned = not news.is_pinned
        news.save(update_fields=['is_pinned'])
        
        action_taken = 'pinned' if news.is_pinned else 'unpinned'
        
        return Response({
            'message': f'News {action_taken} successfully',
            'news_id': str(news.id),
            'is_pinned': news.is_pinned
        })
    
    
    # ==================== ✅ TOGGLE PUBLISH ACTION ====================
    @swagger_auto_schema(
        method='post',
        operation_description='Toggle publish status of news (publish if unpublished, unpublish if published). Auto-sends notifications on publish if notify_members is True. No request body required, only news ID in URL.',
        manual_parameters=[
            openapi.Parameter(
                'id',
                openapi.IN_PATH,
                description="News UUID",
                type=openapi.TYPE_STRING,
                format=openapi.FORMAT_UUID,
                required=True
            )
        ],
        request_body=None,  # ✅ Explicitly None
        responses={
            200: openapi.Response(
                description='Publish status toggled successfully',
                examples={
                    'application/json': {
                        'message': 'News published successfully',
                        'news_id': '3fa85f64-5717-4562-b3fc-2c963f66afa6',
                        'is_published': True,
                        'notification_status': {
                            'sent': True,
                            'total_recipients': 50,
                            'success_count': 48,
                            'failed_count': 2
                        }
                    }
                }
            ),
            404: openapi.Response(description='News not found'),
            403: openapi.Response(description='Permission denied')
        }
    )
    @action(detail=True, methods=['post'], permission_classes=[IsAdminOrNewsManager])
    def toggle_publish(self, request, pk=None):
        """Toggle publish status - publish if unpublished, unpublish if published"""
        news = self.get_object()
        
        # Toggle the status
        news.is_published = not news.is_published
        news.save(update_fields=['is_published'])
        
        action_taken = 'published' if news.is_published else 'unpublished'
        
        response_data = {
            'message': f'News {action_taken} successfully',
            'news_id': str(news.id),
            'is_published': news.is_published
        }
        
        # Auto-send notifications if news was just published
        if news.is_published and news.notify_members and not news.notification_sent:
            graph_token = extract_graph_token_from_request(request)
            
            if graph_token:
                notification_result = news_notification_manager.send_news_notification(
                    news=news,
                    access_token=graph_token,
                    request=request
                )
                
                if notification_result:
                    response_data['notification_status'] = {
                        'sent': notification_result['success'],
                        'total_recipients': notification_result.get('total_recipients', 0),
                        'success_count': notification_result.get('success_count', 0),
                        'failed_count': notification_result.get('failed_count', 0)
                    }
        
        return Response(response_data)
    
    def _send_notifications_async(self, news):
        """Helper method to send notifications"""
        try:
            graph_token = extract_graph_token_from_request(self.request)
            
            if graph_token:
                news_notification_manager.send_news_notification(
                    news=news,
                    access_token=graph_token,
                    request=self.request
                )
        except Exception as e:
            logger.error(f"Failed to send auto-notifications for news {news.id}: {e}")
    
    @action(detail=False, methods=['get'], permission_classes=[IsAdminOrNewsManager])
    def statistics(self, request):
        """Get news statistics"""
        
        total_news = CompanyNews.objects.filter(is_deleted=False).count()
        published_news = CompanyNews.objects.filter(is_deleted=False, is_published=True).count()
        pinned_news = CompanyNews.objects.filter(is_deleted=False, is_pinned=True).count()
        
        total_views = CompanyNews.objects.filter(is_deleted=False).aggregate(
            total=Sum('view_count')
        )['total'] or 0
        
        # News by category
        news_by_category = []
        for category in NewsCategory.objects.filter(is_active=True, is_deleted=False):
            count = CompanyNews.objects.filter(
                is_deleted=False,
                category=category
            ).count()
            news_by_category.append({
                'id': str(category.id),
              
                'name': category.name,
              
                'count': count
            })
        
        return Response({
            'total_news': total_news,
            'published_news': published_news,
            'pinned_news': pinned_news,
            'draft_news': total_news - published_news,
            'total_views': total_views,
            'news_by_category': news_by_category
        })


# ==================== TARGET GROUP VIEWSET ====================

class TargetGroupViewSet(viewsets.ModelViewSet):
    """Target Group CRUD ViewSet"""
    
    queryset = TargetGroup.objects.filter(is_deleted=False)
    permission_classes = [IsAdminOrTargetGroupManager]
    
    def get_serializer_class(self):
        if self.action == 'list':
            return TargetGroupListSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return TargetGroupCreateUpdateSerializer
        return TargetGroupDetailSerializer
    
    def get_queryset(self):
        queryset = TargetGroup.objects.filter(is_deleted=False)
        
        is_active = self.request.query_params.get('is_active', None)
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(description__icontains=search)
            )
        
        return queryset.prefetch_related('members')
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    @swagger_auto_schema(
    method='post',
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=['employee_ids'],
        properties={
            'employee_ids': openapi.Schema(
                type=openapi.TYPE_ARRAY,
                items=openapi.Schema(type=openapi.TYPE_INTEGER),
                description='List of employee IDs to add to the target group',
                example=[1, 2, 3, 5]
            )
        }
    ),
    responses={
        200: openapi.Response(
            description='Members added successfully',
            examples={
                'application/json': {
                    'message': '3 member(s) added successfully',
                    'group_id': 'uuid-here',
                    'total_members': 10,
                    'already_existing': 0
                }
            }
        ),
        400: 'Bad Request - Invalid data',
        404: 'Not Found - No valid employees'
    }
)
    @action(detail=True, methods=['post'])
    def add_members(self, request, pk=None):
        """Add members to target group"""
        group = self.get_object()
        
        employee_ids = request.data.get('employee_ids', [])
        
        if not employee_ids:
            return Response(
                {'error': 'employee_ids is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate employee_ids format
        if not isinstance(employee_ids, list):
            return Response(
                {'error': 'employee_ids must be a list of integers'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        from .models import Employee
        employees = Employee.objects.filter(id__in=employee_ids, is_deleted=False)
        
        if not employees.exists():
            return Response(
                {'error': 'No valid employees found with provided IDs'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Add only non-existing members
        added_count = 0
        for employee in employees:
            if not group.members.filter(id=employee.id).exists():
                group.members.add(employee)
                added_count += 1
        
        return Response({
            'message': f'{added_count} member(s) added successfully',
            'group_id': str(group.id),
            'total_members': group.member_count,
            'already_existing': employees.count() - added_count
        })
    @swagger_auto_schema(
    method='post',
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=['employee_ids'],
        properties={
            'employee_ids': openapi.Schema(
                type=openapi.TYPE_ARRAY,
                items=openapi.Schema(type=openapi.TYPE_INTEGER),
                description='List of employee IDs to remove from the target group',
                example=[1, 2, 3]
            )
        }
    ),
    responses={
        200: openapi.Response(
            description='Members removed successfully',
            examples={
                'application/json': {
                    'message': '2 member(s) removed successfully',
                    'group_id': 'uuid-here',
                    'total_members': 8,
                    'not_found': 1
                }
            }
        ),
        400: 'Bad Request - Invalid data',
        404: 'Not Found - No valid employees'
    }
)
    @action(detail=True, methods=['post'])
    def remove_members(self, request, pk=None):
        """Remove members from target group"""
        group = self.get_object()
        
        employee_ids = request.data.get('employee_ids', [])
        
        if not employee_ids:
            return Response(
                {'error': 'employee_ids is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate employee_ids format
        if not isinstance(employee_ids, list):
            return Response(
                {'error': 'employee_ids must be a list of integers'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        from .models import Employee
        employees = Employee.objects.filter(id__in=employee_ids)
        
        if not employees.exists():
            return Response(
                {'error': 'No valid employees found with provided IDs'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Remove only existing members
        removed_count = 0
        for employee in employees:
            if group.members.filter(id=employee.id).exists():
                group.members.remove(employee)
                removed_count += 1
        
        return Response({
            'message': f'{removed_count} member(s) removed successfully',
            'group_id': str(group.id),
            'total_members': group.member_count,
            'not_found': employees.count() - removed_count
        })
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get target group statistics"""
        
        total_groups = TargetGroup.objects.filter(is_deleted=False).count()
        active_groups = TargetGroup.objects.filter(is_deleted=False, is_active=True).count()
        
        from .models import Employee
        all_member_ids = set()
        for group in TargetGroup.objects.filter(is_deleted=False):
            all_member_ids.update(group.members.values_list('id', flat=True))
        
        total_unique_members = len(all_member_ids)
        
        groups_with_members = TargetGroup.objects.filter(is_deleted=False)
        total_members_count = sum(group.member_count for group in groups_with_members)
        avg_members_per_group = total_members_count / total_groups if total_groups > 0 else 0
        
        largest_groups = []
        for group in TargetGroup.objects.filter(is_deleted=False).order_by('-id')[:5]:
            largest_groups.append({
                'id': str(group.id),
                'name': group.name,
                'member_count': group.member_count
            })
        
        return Response({
            'total_groups': total_groups,
            'active_groups': active_groups,
            'inactive_groups': total_groups - active_groups,
            'total_unique_members': total_unique_members,
            'average_members_per_group': round(avg_members_per_group, 1),
            'largest_groups': largest_groups
        })


