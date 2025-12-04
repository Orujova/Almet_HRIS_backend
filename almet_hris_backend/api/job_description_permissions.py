# api/job_description_permissions.py - YENİ FİL
from functools import wraps
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Q

def is_admin_user(user):
    """Check if user has Admin role"""
    try:
        from .models import Employee
        from .role_models import EmployeeRole
        
        employee = Employee.objects.get(user=user, is_deleted=False)
        
        has_admin_role = EmployeeRole.objects.filter(
            employee=employee,
            role__name__icontains='Admin',
            role__is_active=True,
            is_active=True
        ).exists()
        
        return has_admin_role
    except:
        return False

def get_job_description_access(user):
    """
    ✅ Get job description access level for user
    Returns: {
        'can_view_all': bool,
        'is_manager': bool,
        'employee': Employee or None,
        'accessible_employee_ids': list or None
    }
    """
    from .models import Employee
    
    # Admin - Full Access
    if is_admin_user(user):
        return {
            'can_view_all': True,
            'is_manager': True,
            'employee': None,
            'accessible_employee_ids': None  # None means ALL
        }
    
    try:
        employee = Employee.objects.get(user=user, is_deleted=False)
    except Employee.DoesNotExist:
        return {
            'can_view_all': False,
            'is_manager': False,
            'employee': None,
            'accessible_employee_ids': []
        }
    
    # Check if manager (has direct reports)
    direct_reports = Employee.objects.filter(
        line_manager=employee,
        is_deleted=False
    )
    
    is_manager = direct_reports.exists()
    
    if is_manager:
        # Manager can see: self + direct reports' job descriptions
        accessible_ids = [employee.id]
        accessible_ids.extend(list(direct_reports.values_list('id', flat=True)))
        
        return {
            'can_view_all': False,
            'is_manager': True,
            'employee': employee,
            'accessible_employee_ids': accessible_ids
        }
    else:
        # Regular employee - only their own job description
        return {
            'can_view_all': False,
            'is_manager': False,
            'employee': employee,
            'accessible_employee_ids': [employee.id]
        }

def filter_job_description_queryset(user, queryset):
    """
    ✅ Filter job description queryset based on user access
    Manager sees: their own + direct reports' JDs
    Admin sees: all JDs
    Employee sees: only their own JD
    """
    access = get_job_description_access(user)
    
    # Admin - see all
    if access['can_view_all']:
        return queryset
    
    # Manager or Employee - filter by assignments
    if access['accessible_employee_ids']:
        return queryset.filter(
            assignments__employee_id__in=access['accessible_employee_ids'],
            assignments__is_active=True
        ).distinct()
    
    # No access
    return queryset.none()