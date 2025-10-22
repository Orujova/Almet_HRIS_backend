# api/news_views.py - WITH TARGET GROUP FILTERING

import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Q, Sum
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
    IsAdminOrNewsCategoryManager,
    CanViewNews,
    is_admin_user,
    check_news_permission,
)
from .news_notifications import news_notification_manager
from .token_helpers import extract_graph_token_from_request

logger = logging.getLogger(__name__)


# ==================== NEWS CATEGORY VIEWSET ====================

class NewsCategoryViewSet(viewsets.ModelViewSet):
    """News Category CRUD - Admin Only for Create/Update/Delete"""
    
    queryset = NewsCategory.objects.filter(is_deleted=False)
    serializer_class = NewsCategorySerializer
    permission_classes = [IsAdminOrNewsCategoryManager]
    
    def get_queryset(self):
        queryset = NewsCategory.objects.filter(is_deleted=False)
        
        is_active = self.request.query_params.get('is_active', None)
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(description__icontains=search)
            )
        
        return queryset.order_by('name')
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


# ==================== COMPANY NEWS VIEWSET ====================

class CompanyNewsViewSet(viewsets.ModelViewSet):
    """Company News CRUD with Target Group Filtering"""
    
    queryset = CompanyNews.objects.filter(is_deleted=False)
    
    def get_serializer_class(self):
        if self.action in ['toggle_pin', 'toggle_publish']:
            return None
        
        if self.action == 'list':
            return NewsListSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return NewsCreateUpdateSerializer
        return NewsDetailSerializer
    
    def get_permissions(self):
        """Dynamic permission classes based on action"""
        if self.action in ['list', 'retrieve']:
            return [CanViewNews()]
        elif self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminOrNewsManager()]
        elif self.action in ['toggle_pin', 'toggle_publish']:
            return [IsAdminOrNewsManager()]
        elif self.action == 'statistics':
            return [IsAdminOrNewsManager()]
        
        return [IsAuthenticated()]
    
    def get_queryset(self):
        queryset = CompanyNews.objects.filter(is_deleted=False)
        user = self.request.user
        
        # Check if user is admin or has view_all permission
        is_admin = is_admin_user(user)
        has_view_all, _ = check_news_permission(user, 'news.news.view_all')
        
        # CRITICAL: Target Group Filtering
        if not is_admin and not has_view_all:
            # Get current employee
            try:
                from .models import Employee
                employee = Employee.objects.get(user=user, is_deleted=False)
                
                # Get target groups where this employee is a member
                employee_target_groups = TargetGroup.objects.filter(
                    members=employee,
                    is_active=True,
                    is_deleted=False
                )
                
                # Filter news: show only published news that belong to user's target groups
                queryset = queryset.filter(
                    Q(is_published=True) &
                    (
                        Q(target_groups__in=employee_target_groups) |
                        Q(target_groups__isnull=True)  # News without target groups are visible to all
                    )
                ).distinct()
                
            except Employee.DoesNotExist:
                # If no employee profile, show only published news without target groups
                queryset = queryset.filter(
                    is_published=True,
                    target_groups__isnull=True
                )
        else:
            # Admin or users with view_all permission can see everything
            pass
        
        # Filter by category
        category_id = self.request.query_params.get('category', None)
        if category_id:
            queryset = queryset.filter(category_id=category_id)
        
        # Filter by publish status (only for admin/view_all users)
        if is_admin or has_view_all:
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
        
        return queryset.select_related('author', 'category').prefetch_related('target_groups')

    def retrieve(self, request, *args, **kwargs):
        """Get news detail and increment view count"""
        instance = self.get_object()
        
        # Check if user has access to this news
        user = request.user
        is_admin = is_admin_user(user)
        has_view_all, _ = check_news_permission(user, 'news.news.view_all')
        
        if not is_admin and not has_view_all:
            # Regular users can only view published news in their target groups
            try:
                from .models import Employee
                employee = Employee.objects.get(user=user, is_deleted=False)
                
                # Check if news is published
                if not instance.is_published:
                    return Response(
                        {'error': 'News not found or you do not have access'},
                        status=status.HTTP_404_NOT_FOUND
                    )
                
                # Check if user is in any of the news target groups
                news_target_groups = instance.target_groups.filter(is_active=True, is_deleted=False)
                
                # If news has target groups, user must be in at least one of them
                if news_target_groups.exists():
                    user_in_target_group = news_target_groups.filter(members=employee).exists()
                    
                    if not user_in_target_group:
                        return Response(
                            {'error': 'You do not have access to this news'},
                            status=status.HTTP_403_FORBIDDEN
                        )
                
            except Employee.DoesNotExist:
                return Response(
                    {'error': 'Employee profile not found'},
                    status=status.HTTP_403_FORBIDDEN
                )
        
        # Increment view count
        instance.increment_view_count()
        
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
    
    def perform_create(self, serializer):
        """Create news and send notifications if published"""
        news = serializer.save(
            created_by=self.request.user,
            author=self.request.user
        )
        
        # Auto-send notifications if published
        if news.is_published and news.notify_members and not news.notification_sent:
            self._send_notifications_async(news)
        
        return news
    
    def perform_update(self, serializer):
        """Update news and send notifications if newly published"""
        instance = self.get_object()
        was_published = instance.is_published
        
        news = serializer.save(updated_by=self.request.user)
        
        # Send notifications if newly published
        if not was_published and news.is_published and news.notify_members and not news.notification_sent:
            self._send_notifications_async(news)
        
        return news
    
    # ==================== TOGGLE PIN ACTION ====================
    @swagger_auto_schema(
        method='post',
        operation_description='Toggle pin status (requires news.news.pin permission)',
        request_body=openapi.Schema(type=openapi.TYPE_OBJECT, properties={}),
        responses={
            200: openapi.Response(
                description='Pin status toggled',
                examples={'application/json': {
                    'message': 'News pinned successfully',
                    'news_id': 'uuid',
                    'is_pinned': True
                }}
            ),
            403: 'Permission denied - requires news.news.pin'
        }
    )
    @action(detail=True, methods=['post'], serializer_class=None)
    def toggle_pin(self, request, pk=None):
        """Toggle pin status - requires news.news.pin permission"""
        news = self.get_object()
        
        news.is_pinned = not news.is_pinned
        news.save(update_fields=['is_pinned'])
        
        action_taken = 'pinned' if news.is_pinned else 'unpinned'
        
        return Response({
            'message': f'News {action_taken} successfully',
            'news_id': str(news.id),
            'is_pinned': news.is_pinned
        })
    
    # ==================== TOGGLE PUBLISH ACTION ====================
    @swagger_auto_schema(
        method='post',
        operation_description='Toggle publish status with auto-notifications (requires news.news.publish permission)',
        request_body=openapi.Schema(type=openapi.TYPE_OBJECT, properties={}),
        responses={
            200: openapi.Response(
                description='Publish status toggled',
                examples={'application/json': {
                    'message': 'News published successfully',
                    'news_id': 'uuid',
                    'is_published': True,
                    'notification_status': {
                        'sent': True,
                        'total_recipients': 50,
                        'success_count': 48,
                        'failed_count': 2
                    }
                }}
            ),
            403: 'Permission denied - requires news.news.publish'
        }
    )
    @action(detail=True, methods=['post'], serializer_class=None)
    def toggle_publish(self, request, pk=None):
        """Toggle publish status - requires news.news.publish permission"""
        news = self.get_object()
        
        news.is_published = not news.is_published
        news.save(update_fields=['is_published'])
        
        action_taken = 'published' if news.is_published else 'unpublished'
        
        response_data = {
            'message': f'News {action_taken} successfully',
            'news_id': str(news.id),
            'is_published': news.is_published
        }
        
        # Auto-send notifications when publishing
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
        """Helper to send notifications"""
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
    
    @swagger_auto_schema(
        method='get',
        operation_description='Get news statistics (requires news.news.view_statistics permission)',
        responses={
            200: openapi.Response(description='Statistics retrieved successfully'),
            403: 'Permission denied - requires news.news.view_statistics'
        }
    )
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get news statistics - requires news.news.view_statistics permission"""
        user = request.user
        is_admin = is_admin_user(user)
        has_view_all, _ = check_news_permission(user, 'news.news.view_all')
        
        # Base queryset
        base_queryset = CompanyNews.objects.filter(is_deleted=False)
        
        # Filter by user's target groups if not admin
        if not is_admin and not has_view_all:
            try:
                from .models import Employee
                employee = Employee.objects.get(user=user, is_deleted=False)
                
                employee_target_groups = TargetGroup.objects.filter(
                    members=employee,
                    is_active=True,
                    is_deleted=False
                )
                
                base_queryset = base_queryset.filter(
                    Q(is_published=True) &
                    (
                        Q(target_groups__in=employee_target_groups) |
                        Q(target_groups__isnull=True)
                    )
                ).distinct()
            except Employee.DoesNotExist:
                base_queryset = base_queryset.filter(
                    is_published=True,
                    target_groups__isnull=True
                )
        
        total_news = base_queryset.count()
        published_news = base_queryset.filter(is_published=True).count()
        pinned_news = base_queryset.filter(is_pinned=True).count()
        
        total_views = base_queryset.aggregate(
            total=Sum('view_count')
        )['total'] or 0
        
        news_by_category = []
        for category in NewsCategory.objects.filter(is_active=True, is_deleted=False):
            count = base_queryset.filter(category=category).count()
            if count > 0:  # Only show categories with news
                news_by_category.append({
                    'id': str(category.id),
                    'name': category.name,
                    'count': count
                })
        
        return Response({
            'total_news': total_news,
            'published_news': published_news,
            'pinned_news': pinned_news,
            'draft_news': total_news - published_news if (is_admin or has_view_all) else 0,
            'total_views': total_views,
            'news_by_category': news_by_category
        })


# ==================== TARGET GROUP VIEWSET ====================

class TargetGroupViewSet(viewsets.ModelViewSet):
    """Target Group CRUD with Permission Checks"""
    
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
        operation_description='Add members to target group (requires news.target_group.add_members permission)',
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['employee_ids'],
            properties={
                'employee_ids': openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(type=openapi.TYPE_INTEGER),
                    example=[1, 2, 3, 5]
                )
            }
        ),
        responses={
            200: 'Members added successfully',
            400: 'Bad Request',
            403: 'Permission denied',
            404: 'Not Found'
        }
    )
    @action(detail=True, methods=['post'])
    def add_members(self, request, pk=None):
        """Add members - requires news.target_group.add_members permission"""
        group = self.get_object()
        
        employee_ids = request.data.get('employee_ids', [])
        
        if not employee_ids:
            return Response(
                {'error': 'employee_ids is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
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
        operation_description='Remove members from target group (requires news.target_group.remove_members permission)',
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['employee_ids'],
            properties={
                'employee_ids': openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(type=openapi.TYPE_INTEGER),
                    example=[1, 2, 3]
                )
            }
        ),
        responses={
            200: 'Members removed successfully',
            400: 'Bad Request',
            403: 'Permission denied',
            404: 'Not Found'
        }
    )
    @action(detail=True, methods=['post'])
    def remove_members(self, request, pk=None):
        """Remove members - requires news.target_group.remove_members permission"""
        group = self.get_object()
        
        employee_ids = request.data.get('employee_ids', [])
        
        if not employee_ids:
            return Response(
                {'error': 'employee_ids is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
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
    
    @swagger_auto_schema(
        method='get',
        operation_description='Get target group statistics (requires news.target_group.view_statistics permission)',
        responses={
            200: 'Statistics retrieved successfully',
            403: 'Permission denied'
        }
    )
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get statistics - requires news.target_group.view_statistics permission"""
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


# ==================== NEWS PERMISSIONS VIEW ====================

from rest_framework.views import APIView
from .news_permissions import get_user_news_permissions, is_admin_user

class NewsPermissionsView(APIView):
    """
    GET /api/news/permissions/
    Returns current user's news permissions
    """
    permission_classes = [IsAuthenticated]
    
    @swagger_auto_schema(
        operation_description='Get current user news permissions',
        responses={
            200: openapi.Response(
                description='User permissions',
                examples={
                    'application/json': {
                        'is_admin': True,
                        'permissions': ['news.news.view', 'news.news.create'],
                        'capabilities': {
                            'can_view_news': True,
                            'can_create_news': True
                        }
                    }
                }
            )
        }
    )
    def get(self, request):
        """Get user's news permissions"""
        user = request.user
        
        is_admin = is_admin_user(user)
        permissions = get_user_news_permissions(user)
        
        # Helper flags for frontend
        can_manage_news = (
            is_admin or 
            'news.news.update' in permissions or 
            'news.news.create' in permissions
        )
        
        can_manage_target_groups = (
            is_admin or 
            'news.target_group.update' in permissions or 
            'news.target_group.create' in permissions
        )
        
        can_view_statistics = (
            is_admin or 
            'news.news.view_statistics' in permissions
        )
        
        can_pin_news = is_admin or 'news.news.pin' in permissions
        can_publish_news = is_admin or 'news.news.publish' in permissions
        
        return Response({
            'is_admin': is_admin,
            'permissions': permissions,
            'capabilities': {
                'can_view_news': 'news.news.view' in permissions or is_admin,
                'can_view_all_news': 'news.news.view_all' in permissions or is_admin,
                'can_create_news': 'news.news.create' in permissions or is_admin,
                'can_update_news': 'news.news.update' in permissions or is_admin,
                'can_delete_news': 'news.news.delete' in permissions or is_admin,
                'can_pin_news': can_pin_news,
                'can_publish_news': can_publish_news,
                'can_manage_news': can_manage_news,
                'can_view_target_groups': 'news.target_group.view' in permissions or is_admin,
                'can_create_target_groups': 'news.target_group.create' in permissions or is_admin,
                'can_update_target_groups': 'news.target_group.update' in permissions or is_admin,
                'can_delete_target_groups': 'news.target_group.delete' in permissions or is_admin,
                'can_add_members': 'news.target_group.add_members' in permissions or is_admin,
                'can_remove_members': 'news.target_group.remove_members' in permissions or is_admin,
                'can_manage_target_groups': can_manage_target_groups,
                'can_view_statistics': can_view_statistics,
                'can_view_news_statistics': 'news.news.view_statistics' in permissions or is_admin,
                'can_view_group_statistics': 'news.target_group.view_statistics' in permissions or is_admin,
            }
        })