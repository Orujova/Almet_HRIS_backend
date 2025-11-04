# api/timeoff_permissions.py
"""
Time Off System - Role-Based Permissions
"""

from functools import wraps
from rest_framework.response import Response
from rest_framework import status
from .role_models import Permission, EmployeeRole, Role
from .business_trip_permissions import is_admin_user
import logging

logger = logging.getLogger(__name__)


def has_timeoff_permission(permission_codename):
    """
    Decorator to check time off permissions
    Admin role bütün permission-lara sahib
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(self_or_request, *args, **kwargs):
            # ✅ FIX: Handle both function-based views and ViewSet methods
            if hasattr(self_or_request, 'user'):
                # Function-based view - request is first argument
                request = self_or_request
                user = request.user
            else:
                # ViewSet method - self is first argument, request is in args or from self.request
                viewset_self = self_or_request
                if args and hasattr(args[0], 'user'):
                    request = args[0]
                    user = request.user
                elif hasattr(viewset_self, 'request'):
                    request = viewset_self.request
                    user = request.user
                else:
                    from rest_framework.response import Response
                    from rest_framework import status as rest_status
                    return Response({
                        'error': 'Could not determine request object'
                    }, status=rest_status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            # Admin role yoxla
            if is_admin_user(user):
                return view_func(self_or_request, *args, **kwargs)
            
            # Employee tap
            try:
                from .models import Employee
                employee = Employee.objects.get(user=user, is_deleted=False)
            except Employee.DoesNotExist:
                return Response({
                    'error': 'Employee profili tapılmadı',
                    'detail': 'Time Off sisteminə daxil olmaq üçün employee profili lazımdır'
                }, status=status.HTTP_403_FORBIDDEN)
            
            # Employee-in rollarını tap
            employee_roles = EmployeeRole.objects.filter(
                employee=employee,
                is_active=True
            ).select_related('role')
            
            if not employee_roles.exists():
                return Response({
                    'error': 'Aktiv rol tapılmadı',
                    'detail': 'Bu əmələiyyat üçün sizə rol təyin edilməlidir'
                }, status=status.HTTP_403_FORBIDDEN)
            
            # Permission yoxla
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
                    'error': 'İcazə yoxdur',
                    'detail': f'Bu əmələiyyat üçün "{permission_codename}" icazəsi lazımdır',
                    'your_roles': [er.role.name for er in employee_roles]
                }, status=status.HTTP_403_FORBIDDEN)
            
            return view_func(self_or_request, *args, **kwargs)
        
        return wrapper
    return decorator


def has_any_timeoff_permission(permission_codenames):
    """
    Check if user has ANY of the specified permissions
    Admin role automatically passes
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(self_or_request, *args, **kwargs):
            # ✅ FIX: Handle both function-based views and ViewSet methods
            if hasattr(self_or_request, 'user'):
                # Function-based view
                request = self_or_request
                user = request.user
            else:
                # ViewSet method
                viewset_self = self_or_request
                if args and hasattr(args[0], 'user'):
                    request = args[0]
                    user = request.user
                elif hasattr(viewset_self, 'request'):
                    request = viewset_self.request
                    user = request.user
                else:
                    from rest_framework.response import Response
                    from rest_framework import status as rest_status
                    return Response({
                        'error': 'Could not determine request object'
                    }, status=rest_status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            # Admin role yoxla
            if is_admin_user(user):
                return view_func(self_or_request, *args, **kwargs)
            
            try:
                from .models import Employee
                employee = Employee.objects.get(user=user, is_deleted=False)
            except Employee.DoesNotExist:
                return Response({
                    'error': 'Employee profili tapılmadı'
                }, status=status.HTTP_403_FORBIDDEN)
            
            employee_roles = EmployeeRole.objects.filter(
                employee=employee,
                is_active=True
            ).select_related('role')
            
            if not employee_roles.exists():
                return Response({
                    'error': 'Aktiv rol tapılmadı'
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
                    'error': 'İcazə yoxdur',
                    'detail': f'Bu əmələiyyat üçün aşağıdakı icazələrdən biri lazımdır',
                    'required_permissions': permission_codenames,
                    'your_roles': [er.role.name for er in employee_roles]
                }, status=status.HTTP_403_FORBIDDEN)
            
            return view_func(self_or_request, *args, **kwargs)
        
        return wrapper
    return decorator


def check_timeoff_permission(user, permission_codename):
    """
    Utility function to check permission without decorator
    Returns: (has_permission: bool, employee: Employee or None)
    """
    # Admin role yoxla
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


def get_user_timeoff_permissions(user):
    """
    Get all time off permissions for user
    Returns: list of permission codenames
    """
    if is_admin_user(user):
        # Admin has all time off permissions
        return list(Permission.objects.filter(
            category='Time Off',
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
            permission__category='Time Off'
        ).values_list('permission__codename', flat=True)
        permission_codenames.update(role_perms)
    
    return list(permission_codenames)


def can_approve_timeoff(user, request_obj):
    """
    Check if user can approve a specific time off request
    Returns: (can_approve: bool, reason: str)
    """
    # Admin həmişə approve edə bilər
    if is_admin_user(user):
        return True, "Admin permission"
    
    # Employee-i tap
    try:
        from .models import Employee
        employee = Employee.objects.get(user=user, is_deleted=False)
    except Employee.DoesNotExist:
        return False, "No employee profile"
    
    # 1. Line Manager yoxla
    if request_obj.line_manager == employee:
        # Line manager permission yoxla
        has_perm, _ = check_timeoff_permission(user, 'timeoff.request.approve_as_manager')
        if has_perm:
            return True, "Line Manager with permission"
        else:
            return False, "Line Manager but no approve permission"
    
    # 2. HR permission yoxla
    has_hr_perm, _ = check_timeoff_permission(user, 'timeoff.request.approve_as_hr')
    if has_hr_perm:
        return True, "HR permission"
    
    return False, "Not authorized"


def can_view_timeoff_request(user, request_obj):
    """
    Check if user can view a specific time off request
    Returns: (can_view: bool, reason: str)
    """
    # Admin həmişə görə bilər
    if is_admin_user(user):
        return True, "Admin permission"
    
    try:
        from .models import Employee
        employee = Employee.objects.get(user=user, is_deleted=False)
    except Employee.DoesNotExist:
        return False, "No employee profile"
    
    # 1. Öz request-i
    if request_obj.employee == employee:
        has_perm, _ = check_timeoff_permission(user, 'timeoff.request.view_own')
        if has_perm:
            return True, "Own request"
    
    # 2. Line Manager
    if request_obj.line_manager == employee:
        has_perm, _ = check_timeoff_permission(user, 'timeoff.request.view_team')
        if has_perm:
            return True, "Team request (Line Manager)"
    
    # 3. View all permission
    has_all_perm, _ = check_timeoff_permission(user, 'timeoff.request.view_all')
    if has_all_perm:
        return True, "View all permission"
    
    return False, "Not authorized"