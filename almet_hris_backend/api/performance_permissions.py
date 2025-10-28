# api/performance_permissions.py - UPDATED with better access control

from functools import wraps
from rest_framework.response import Response
from rest_framework import status
from .role_models import Permission, EmployeeRole

def is_admin_user(user):
    """Check if user has Admin role"""
    try:
        from .models import Employee
        employee = Employee.objects.get(user=user, is_deleted=False)
        
        has_admin_role = EmployeeRole.objects.filter(
            employee=employee,
            role__name__icontains='Admin',
            role__is_active=True,
            is_active=True
        ).exists()
        
        return has_admin_role
    except Employee.DoesNotExist:
        return False


def has_performance_permission(permission_codename):
    """
    Decorator to check performance permissions
    Admin role bütün permission-lara sahib
    
    FIXED: Works with both function views and ViewSet methods
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(self_or_request, *args, **kwargs):
            # Determine if this is a ViewSet method or a function view
            # ViewSet methods: first arg is 'self', second is 'request'
            # Function views: first arg is 'request'
            if hasattr(self_or_request, 'request'):
                # This is a ViewSet instance (self)
                request = self_or_request.request
                view_func_args = (self_or_request,) + args
            else:
                # This is a request object (function view)
                request = self_or_request
                view_func_args = args
            
            user = request.user
            
            # Admin role yoxla
            if is_admin_user(user):
                return view_func(*((self_or_request,) + args), **kwargs)
            
            # Employee tap
            try:
                from .models import Employee
                employee = Employee.objects.get(user=user, is_deleted=False)
            except Employee.DoesNotExist:
                return Response({
                    'error': 'Employee profili tapılmadı',
                    'detail': 'Performance sisteminə daxil olmaq üçün employee profili lazımdır'
                }, status=status.HTTP_403_FORBIDDEN)
            
            # Employee-in rollarını tap
            employee_roles = EmployeeRole.objects.filter(
                employee=employee,
                is_active=True
            ).select_related('role')
            
            if not employee_roles.exists():
                return Response({
                    'error': 'Aktiv rol tapılmadı',
                    'detail': 'Bu əməliyyat üçün sizə rol təyin edilməlidir'
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
                    'detail': f'Bu əməliyyat üçün "{permission_codename}" icazəsi lazımdır',
                    'your_roles': [er.role.name for er in employee_roles]
                }, status=status.HTTP_403_FORBIDDEN)
            
            return view_func(*((self_or_request,) + args), **kwargs)
        
        return wrapper
    return decorator

def check_performance_permission(user, permission_codename):
    """
    Utility function to check permission without decorator
    Returns: (has_permission: bool, employee: Employee or None)
    """
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


def get_user_performance_permissions(user):
    """
    Get all performance permissions for user
    Returns: list of permission codenames
    """
    if is_admin_user(user):
        return list(Permission.objects.filter(
            category='Performance',
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
            permission__category='Performance'
        ).values_list('permission__codename', flat=True)
        permission_codenames.update(role_perms)
    
    return list(permission_codenames)


def can_view_performance(user, performance):
    """
    Check if user can view specific performance record
    - Admin: can view all
    - With performance.view_all permission: can view all  
    - With performance.view_team permission: can view direct reports
    - Everyone: can view own performance
    """
    # Admin check
    if is_admin_user(user):
        return True
    
    try:
        from .models import Employee
        employee = Employee.objects.get(user=user, is_deleted=False)
    except Employee.DoesNotExist:
        return False
    
    # Own performance
    if performance.employee == employee:
        return True
    
    # Check view_all permission
    has_view_all, _ = check_performance_permission(user, 'performance.view_all')
    if has_view_all:
        return True
    
    # Check view_team permission + is direct report
    has_view_team, _ = check_performance_permission(user, 'performance.view_team')
    if has_view_team and performance.employee.line_manager == employee:
        return True
    
    return False


def can_edit_performance(user, performance):
   
    if is_admin_user(user):
        return True
    
    try:
        from .models import Employee
        employee = Employee.objects.get(user=user, is_deleted=False)
    except Employee.DoesNotExist:
        return False
    
    # Check manage_all permission
    has_manage_all, _ = check_performance_permission(user, 'performance.manage_all')
    if has_manage_all:
        return True
    
    # Check manage_team permission + is direct report
    has_manage_team, _ = check_performance_permission(user, 'performance.manage_team')
    if has_manage_team and performance.employee.line_manager == employee:
        return True
    
    # Own performance - limited edit rights
    if performance.employee == employee:
        has_own_edit, _ = check_performance_permission(user, 'performance.edit_own')
        return has_own_edit
    
    return False


def get_accessible_employees_for_performance(user):
    """
    Get list of employee IDs that user can view performance for
    Returns: QuerySet of Employee IDs or None (if all accessible)
    
    NEW: Returns a tuple (employee_ids, can_view_all)
    """
    from .models import Employee
    
    # Admin sees all
    if is_admin_user(user):
        return None, True  # None means "all employees", True means "can_view_all"
    
    try:
        employee = Employee.objects.get(user=user, is_deleted=False)
    except Employee.DoesNotExist:
        return Employee.objects.none(), False
    
    # Check view_all permission
    has_view_all, _ = check_performance_permission(user, 'performance.view_all')
    if has_view_all:
        return None, True  # All employees
    
    # Check view_team permission
    has_view_team, _ = check_performance_permission(user, 'performance.view_team')
    
    accessible_ids = [employee.id]  # Always include self
    
    if has_view_team:
        # Add direct reports
        direct_reports = Employee.objects.filter(
            line_manager=employee,
            is_deleted=False
        ).values_list('id', flat=True)
        accessible_ids.extend(list(direct_reports))
    
    return accessible_ids, False


# NEW: Helper to check if user can view a list of performances
def filter_viewable_performances(user, queryset):
    """
    Filter performance queryset based on user permissions
    Returns filtered queryset
    """
    accessible_ids, can_view_all = get_accessible_employees_for_performance(user)
    
    if can_view_all:
        # User can see all performances
        return queryset
    
    # Filter by accessible employee IDs
    return queryset.filter(employee_id__in=accessible_ids)