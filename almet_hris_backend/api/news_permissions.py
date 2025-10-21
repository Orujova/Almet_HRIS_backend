# api/news_permissions.py
"""
Company News System Permissions
Role-based permission system similar to vacation module
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


# ✅ UPDATED: Permission classes with both has_permission and has_object_permission
class IsAdminOrNewsManager(BasePermission):
    """
    Permission class for News management
    Inherits from BasePermission to get all required methods
    """
    
    def has_permission(self, request, view):
        """Check permission at view level"""
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Check specific permissions based on action
        if view.action in ['list', 'retrieve']:
            has_perm, _ = check_news_permission(request.user, 'news.news.view')
            return has_perm
        elif view.action == 'create':
            has_perm, _ = check_news_permission(request.user, 'news.news.create')
            return has_perm
        elif view.action in ['update', 'partial_update']:
            has_perm, _ = check_news_permission(request.user, 'news.news.update')
            return has_perm
        elif view.action == 'destroy':
            has_perm, _ = check_news_permission(request.user, 'news.news.delete')
            return has_perm
        
        # Default: admin only
        return is_admin_user(request.user)
    
    def has_object_permission(self, request, view, obj):
        """Check permission at object level"""
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Admin has full access
        if is_admin_user(request.user):
            return True
        
        # Check action-specific permissions
        if view.action == 'retrieve':
            has_perm, _ = check_news_permission(request.user, 'news.news.view')
            return has_perm
        elif view.action in ['update', 'partial_update']:
            has_perm, _ = check_news_permission(request.user, 'news.news.update')
            return has_perm
        elif view.action == 'destroy':
            has_perm, _ = check_news_permission(request.user, 'news.news.delete')
            return has_perm
        
        return False


class IsAdminOrTargetGroupManager(BasePermission):
    """
    Permission class for Target Group management
    Inherits from BasePermission to get all required methods
    """
    
    def has_permission(self, request, view):
        """Check permission at view level"""
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Check specific permissions based on action
        if view.action in ['list', 'retrieve']:
            has_perm, _ = check_news_permission(request.user, 'news.target_group.view')
            return has_perm
        elif view.action == 'create':
            has_perm, _ = check_news_permission(request.user, 'news.target_group.create')
            return has_perm
        elif view.action in ['update', 'partial_update', 'add_members', 'remove_members']:
            has_perm, _ = check_news_permission(request.user, 'news.target_group.update')
            return has_perm
        elif view.action == 'destroy':
            has_perm, _ = check_news_permission(request.user, 'news.target_group.delete')
            return has_perm
        
        # Default: admin only
        return is_admin_user(request.user)
    
    def has_object_permission(self, request, view, obj):
        """Check permission at object level"""
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Admin has full access
        if is_admin_user(request.user):
            return True
        
        # Check action-specific permissions
        if view.action == 'retrieve':
            has_perm, _ = check_news_permission(request.user, 'news.target_group.view')
            return has_perm
        elif view.action in ['update', 'partial_update', 'add_members', 'remove_members']:
            has_perm, _ = check_news_permission(request.user, 'news.target_group.update')
            return has_perm
        elif view.action == 'destroy':
            has_perm, _ = check_news_permission(request.user, 'news.target_group.delete')
            return has_perm
        
        return False


class CanViewNews(BasePermission):
    """
    Permission class for viewing news
    Inherits from BasePermission to get all required methods
    """
    
    def has_permission(self, request, view):
        """Check permission at view level"""
        if not request.user or not request.user.is_authenticated:
            return False
        
        has_perm, _ = check_news_permission(request.user, 'news.news.view')
        return has_perm
    
    def has_object_permission(self, request, view, obj):
        """Check permission at object level"""
        if not request.user or not request.user.is_authenticated:
            return False
        
        # News managers can view all news
        has_manage_perm, _ = check_news_permission(request.user, 'news.news.update')
        if has_manage_perm:
            return True
        
        # Regular users can only view published news
        has_view_perm, _ = check_news_permission(request.user, 'news.news.view')
        if has_view_perm:
            return obj.is_published and not obj.is_deleted
        
        return False