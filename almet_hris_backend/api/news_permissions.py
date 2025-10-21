# api/news_permissions.py - COMPLETE FIX
"""
Company News System Permissions
Complete role-based permission system matching vacation module pattern
"""

from functools import wraps
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import BasePermission
from .role_models import Permission, EmployeeRole, Role


def is_admin_user(user):
    """Check if user has Admin role"""
    try:
        from .models import Employee
        employee = Employee.objects.get(user=user, is_deleted=False)
        
        # Admin role check (case-insensitive)
        has_admin_role = EmployeeRole.objects.filter(
            employee=employee,
            role__name__icontains='Admin',
            role__is_active=True,
            is_active=True
        ).exists()
        
        return has_admin_role
    except Employee.DoesNotExist:
        return False


def has_news_permission(permission_codename):
    """
    Decorator to check news permissions
    Admin role has all permissions
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            user = request.user
            
            # Admin role check
            if is_admin_user(user):
                return view_func(request, *args, **kwargs)
            
            # Get employee
            try:
                from .models import Employee
                employee = Employee.objects.get(user=user, is_deleted=False)
            except Employee.DoesNotExist:
                return Response({
                    'error': 'Employee profile not found',
                    'detail': 'You need an employee profile to access the news system'
                }, status=status.HTTP_403_FORBIDDEN)
            
            # Get employee roles
            employee_roles = EmployeeRole.objects.filter(
                employee=employee,
                is_active=True
            ).select_related('role')
            
            if not employee_roles.exists():
                return Response({
                    'error': 'No active role found',
                    'detail': 'You need to be assigned a role for this operation'
                }, status=status.HTTP_403_FORBIDDEN)
            
            # Check permission
            has_permission = False
            for emp_role in employee_roles:
                role = emp_role.role
                if role.role_permissions.filter(
                    permission__codename=permission_codename,
                    permission__is_active=True
                ).exists():
                    has_permission = True
                    break
            
            if not has_permission:
                return Response({
                    'error': 'Permission denied',
                    'detail': f'This operation requires "{permission_codename}" permission',
                    'your_roles': [er.role.name for er in employee_roles]
                }, status=status.HTTP_403_FORBIDDEN)
            
            return view_func(request, *args, **kwargs)
        
        return wrapper
    return decorator


def has_any_news_permission(permission_codenames):
    """
    Check if user has ANY of the specified permissions
    Admin role automatically passes
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            user = request.user
            
            # Admin role check
            if is_admin_user(user):
                return view_func(request, *args, **kwargs)
            
            try:
                from .models import Employee
                employee = Employee.objects.get(user=user, is_deleted=False)
            except Employee.DoesNotExist:
                return Response({
                    'error': 'Employee profile not found'
                }, status=status.HTTP_403_FORBIDDEN)
            
            employee_roles = EmployeeRole.objects.filter(
                employee=employee,
                is_active=True
            ).select_related('role')
            
            if not employee_roles.exists():
                return Response({
                    'error': 'No active role found'
                }, status=status.HTTP_403_FORBIDDEN)
            
            has_permission = False
            for emp_role in employee_roles:
                role = emp_role.role
                if role.role_permissions.filter(
                    permission__codename__in=permission_codenames,
                    permission__is_active=True
                ).exists():
                    has_permission = True
                    break
            
            if not has_permission:
                return Response({
                    'error': 'Permission denied',
                    'detail': 'This operation requires one of the following permissions',
                    'required_permissions': permission_codenames,
                    'your_roles': [er.role.name for er in employee_roles]
                }, status=status.HTTP_403_FORBIDDEN)
            
            return view_func(request, *args, **kwargs)
        
        return wrapper
    return decorator


def check_news_permission(user, permission_codename):
    """
    Utility function to check permission without decorator
    Returns: (has_permission: bool, employee: Employee or None)
    """
    # Admin role check
    if is_admin_user(user):
        return True, None
    
    try:
        from .models import Employee
        employee = Employee.objects.get(user=user, is_deleted=False)
    except Employee.DoesNotExist:
        return False, None
    
    employee_roles = EmployeeRole.objects.filter(
        employee=employee,
        is_active=True
    ).select_related('role')
    
    for emp_role in employee_roles:
        role = emp_role.role
        if role.role_permissions.filter(
            permission__codename=permission_codename,
            permission__is_active=True
        ).exists():
            return True, employee
    
    return False, employee


def get_user_news_permissions(user):
    """
    Get all news permissions for user
    Returns: list of permission codenames
    """
    if is_admin_user(user):
        # Admin has all news permissions
        return list(Permission.objects.filter(
            category='Company News',
            is_active=True
        ).values_list('codename', flat=True))
    
    try:
        from .models import Employee
        employee = Employee.objects.get(user=user, is_deleted=False)
    except Employee.DoesNotExist:
        return []
    
    employee_roles = EmployeeRole.objects.filter(
        employee=employee,
        is_active=True
    ).select_related('role')
    
    permission_codenames = set()
    for emp_role in employee_roles:
        role_perms = emp_role.role.role_permissions.filter(
            permission__is_active=True,
            permission__category='Company News'
        ).values_list('permission__codename', flat=True)
        permission_codenames.update(role_perms)
    
    return list(permission_codenames)


# ==================== DRF PERMISSION CLASSES ====================

class IsAdminOrNewsManager(BasePermission):
    """
    Permission class for News management
    Maps CRUD actions to specific permissions
    """
    
    def has_permission(self, request, view):
        """Check permission at view level"""
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Admin bypass
        if is_admin_user(request.user):
            return True
        
        # Map actions to permissions
        permission_map = {
            'list': 'news.news.view',
            'retrieve': 'news.news.view',
            'create': 'news.news.create',
            'update': 'news.news.update',
            'partial_update': 'news.news.update',
            'destroy': 'news.news.delete',
            'toggle_pin': 'news.news.pin',
            'toggle_publish': 'news.news.publish',
            'statistics': 'news.news.view_statistics',
        }
        
        required_permission = permission_map.get(view.action)
        
        if not required_permission:
            # Default deny for unknown actions
            return False
        
        has_perm, _ = check_news_permission(request.user, required_permission)
        return has_perm
    
    def has_object_permission(self, request, view, obj):
        """Check permission at object level"""
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Admin bypass
        if is_admin_user(request.user):
            return True
        
        # Check action-specific permissions
        permission_map = {
            'retrieve': 'news.news.view',
            'update': 'news.news.update',
            'partial_update': 'news.news.update',
            'destroy': 'news.news.delete',
            'toggle_pin': 'news.news.pin',
            'toggle_publish': 'news.news.publish',
        }
        
        required_permission = permission_map.get(view.action)
        
        if not required_permission:
            return False
        
        has_perm, _ = check_news_permission(request.user, required_permission)
        return has_perm


class IsAdminOrTargetGroupManager(BasePermission):
    """
    Permission class for Target Group management
    Maps CRUD actions to specific permissions
    """
    
    def has_permission(self, request, view):
        """Check permission at view level"""
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Admin bypass
        if is_admin_user(request.user):
            return True
        
        # Map actions to permissions
        permission_map = {
            'list': 'news.target_group.view',
            'retrieve': 'news.target_group.view',
            'create': 'news.target_group.create',
            'update': 'news.target_group.update',
            'partial_update': 'news.target_group.update',
            'destroy': 'news.target_group.delete',
            'add_members': 'news.target_group.add_members',
            'remove_members': 'news.target_group.remove_members',
            'statistics': 'news.target_group.view_statistics',
        }
        
        required_permission = permission_map.get(view.action)
        
        if not required_permission:
            return False
        
        has_perm, _ = check_news_permission(request.user, required_permission)
        return has_perm
    
    def has_object_permission(self, request, view, obj):
        """Check permission at object level"""
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Admin bypass
        if is_admin_user(request.user):
            return True
        
        # Check action-specific permissions
        permission_map = {
            'retrieve': 'news.target_group.view',
            'update': 'news.target_group.update',
            'partial_update': 'news.target_group.update',
            'destroy': 'news.target_group.delete',
            'add_members': 'news.target_group.add_members',
            'remove_members': 'news.target_group.remove_members',
        }
        
        required_permission = permission_map.get(view.action)
        
        if not required_permission:
            return False
        
        has_perm, _ = check_news_permission(request.user, required_permission)
        return has_perm


class CanViewNews(BasePermission):
    """
    Permission class for viewing news
    Regular users can only view published news
    News managers can view all news
    """
    
    def has_permission(self, request, view):
        """Check permission at view level"""
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Check if user can view news
        has_view_perm, _ = check_news_permission(request.user, 'news.news.view')
        return has_view_perm
    
    def has_object_permission(self, request, view, obj):
        """Check permission at object level"""
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Admin can view all
        if is_admin_user(request.user):
            return True
        
        # News managers can view all news (including drafts)
        has_manage_perm, _ = check_news_permission(request.user, 'news.news.view_all')
        if has_manage_perm:
            return True
        
        # Regular users can only view published news
        has_view_perm, _ = check_news_permission(request.user, 'news.news.view')
        if has_view_perm:
            return obj.is_published and not obj.is_deleted
        
        return False


class IsAdminOrNewsCategoryManager(BasePermission):
    """
    Permission class for News Category management
    Only authenticated users can list/view
    Only admins can create/update/delete
    """
    
    def has_permission(self, request, view):
        """Check permission at view level"""
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Anyone authenticated can view categories
        if view.action in ['list', 'retrieve']:
            return True
        
        # Only admin can manage categories
        return is_admin_user(request.user)
    
    def has_object_permission(self, request, view, obj):
        """Check permission at object level"""
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Anyone authenticated can view
        if view.action == 'retrieve':
            return True
        
        # Only admin can modify
        return is_admin_user(request.user)