# api/additional_vacation_views.py - Additional API Views for Frontend Requirements

from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q, Count, Sum, Avg
from django.db import transaction
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from datetime import date, timedelta
import logging

from .vacation_models import (
    VacationSetting, VacationType, EmployeeVacationBalance,
    VacationRequest, VacationActivity, VacationSchedule
)
from .vacation_serializers import (
    VacationRequestListSerializer, VacationScheduleSerializer,
    VacationTypeSerializer, EmployeeInfoSerializer
)
from .models import Employee

logger = logging.getLogger(__name__)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def request_submission_data(request):
    """Get data needed for request submission form"""
    try:
        user_employee = Employee.objects.get(user=request.user)
    except Employee.DoesNotExist:
        return Response({
            'error': 'User does not have an employee profile'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Get employee information for form
    employee_info = {
        'id': user_employee.id,
        'employee_id': user_employee.employee_id,
        'full_name': user_employee.full_name,
        'phone': user_employee.phone,
        'business_function': user_employee.business_function.name if user_employee.business_function else '',
        'department': user_employee.department.name if user_employee.department else '',
        'unit': user_employee.unit.name if user_employee.unit else '',
        'job_function': user_employee.job_function.name if user_employee.job_function else '',
        'line_manager': user_employee.line_manager.full_name if user_employee.line_manager else ''
    }
    
    # Get active vacation types
    vacation_types = VacationType.objects.filter(is_active=True, is_deleted=False)
    
    # Get user's direct reports for "for my employee" option
    direct_reports = Employee.objects.filter(
        line_manager=user_employee,
        status__affects_headcount=True,
        is_deleted=False
    )
    
    # Get active settings
    settings = VacationSetting.get_active_settings()
    
    # Get HR representatives
    hr_representatives = Employee.objects.filter(
        department__name__icontains='HR',
        status__affects_headcount=True,
        is_deleted=False
    )
    
    return Response({
        'employee_info': employee_info,
        'vacation_types': VacationTypeSerializer(vacation_types, many=True).data,
        'direct_reports': [
            {
                'id': emp.id,
                'employee_id': emp.employee_id,
                'full_name': emp.full_name,
                'department': emp.department.name if emp.department else None,
                'business_function': emp.business_function.name if emp.business_function else None,
                'unit': emp.unit.name if emp.unit else None,
                'job_function': emp.job_function.name if emp.job_function else None,
                'phone': emp.phone
            }
            for emp in direct_reports
        ],
        'hr_representatives': [
            {
                'id': hr.id,
                'employee_id': hr.employee_id,
                'full_name': hr.full_name,
                'department': hr.department.name if hr.department else None
            }
            for hr in hr_representatives
        ],
        'settings': {
            'allow_negative_balance': settings.allow_negative_balance if settings else False,
            'non_working_days': settings.non_working_days if settings else [],
            'default_hr_representative': settings.default_hr_representative.id if settings and settings.default_hr_representative else None
        }
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def approval_pending_requests(request):
    """Get pending approval requests for current user"""
    try:
        user_employee = Employee.objects.get(user=request.user)
    except Employee.DoesNotExist:
        return Response({
            'error': 'User does not have an employee profile'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Get requests pending approval by this user
    line_manager_requests = VacationRequest.objects.filter(
        line_manager=user_employee,
        status='PENDING_LINE_MANAGER',
        is_deleted=False
    ).order_by('-created_at')
    
    hr_requests = VacationRequest.objects.filter(
        hr_representative=user_employee,
        status='PENDING_HR',
        is_deleted=False
    ).order_by('-created_at')
    
    return Response({
        'line_manager_requests': VacationRequestListSerializer(
            line_manager_requests, 
            many=True, 
            context={'request': request}
        ).data,
        'hr_requests': VacationRequestListSerializer(
            hr_requests, 
            many=True, 
            context={'request': request}
        ).data,
        'total_pending': line_manager_requests.count() + hr_requests.count()
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def approval_history(request):
    """Get approval history for current user"""
    try:
        user_employee = Employee.objects.get(user=request.user)
    except Employee.DoesNotExist:
        return Response({
            'error': 'User does not have an employee profile'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Get requests approved by this user as line manager
    line_manager_approved = VacationRequest.objects.filter(
        line_manager_approved_by=request.user,
        is_deleted=False
    ).select_related('employee', 'vacation_type').order_by('-line_manager_approved_at')[:20]
    
    # Get requests approved by this user as HR
    hr_approved = VacationRequest.objects.filter(
        hr_approved_by=request.user,
        is_deleted=False
    ).select_related('employee', 'vacation_type').order_by('-hr_approved_at')[:20]
    
    # Get requests rejected by this user
    rejected_requests = VacationRequest.objects.filter(
        rejected_by=request.user,
        is_deleted=False
    ).select_related('employee', 'vacation_type').order_by('-rejected_at')[:20]
    
    # Combine and format history
    history = []
    
    for req in line_manager_approved:
        history.append({
            'request_id': req.request_id,
            'employee_name': req.employee.full_name,
            'vacation_type': req.vacation_type.name,
            'start_date': req.start_date,
            'end_date': req.end_date,
            'status': 'Approved as Line Manager',
            'approved_by': request.user.get_full_name(),
            'approved_at': req.line_manager_approved_at,
            'comments': req.line_manager_comment
        })
    
    for req in hr_approved:
        history.append({
            'request_id': req.request_id,
            'employee_name': req.employee.full_name,
            'vacation_type': req.vacation_type.name,
            'start_date': req.start_date,
            'end_date': req.end_date,
            'status': 'Approved as HR',
            'approved_by': request.user.get_full_name(),
            'approved_at': req.hr_approved_at,
            'comments': req.hr_comment
        })
    
    for req in rejected_requests:
        history.append({
            'request_id': req.request_id,
            'employee_name': req.employee.full_name,
            'vacation_type': req.vacation_type.name,
            'start_date': req.start_date,
            'end_date': req.end_date,
            'status': req.get_status_display(),
            'approved_by': request.user.get_full_name(),
            'approved_at': req.rejected_at,
            'comments': req.rejection_reason
        })
    
    # Sort by date descending
    history.sort(key=lambda x: x['approved_at'] if x['approved_at'] else timezone.now(), reverse=True)
    
    return Response({
        'approval_history': history[:20]  # Last 20 approvals
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_schedule_tabs(request):
    """Get different schedule tabs data for user"""
    try:
        user_employee = Employee.objects.get(user=request.user)
    except Employee.DoesNotExist:
        return Response({
            'error': 'User does not have an employee profile'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # My Upcoming schedules
    upcoming_schedules = VacationSchedule.objects.filter(
        employee=user_employee,
        start_date__gte=date.today(),
        status='SCHEDULED',
        is_deleted=False
    ).order_by('start_date')
    
    # My Peers and Team schedules
    peers_and_team = Employee.objects.filter(
        Q(department=user_employee.department) | 
        Q(line_manager=user_employee.line_manager),
        status__affects_headcount=True,
        is_deleted=False
    ).exclude(id=user_employee.id) if user_employee.department or user_employee.line_manager else Employee.objects.none()
    
    peers_schedules = VacationSchedule.objects.filter(
        employee__in=peers_and_team,
        start_date__gte=date.today(),
        status='SCHEDULED',
        is_deleted=False
    ).select_related('employee', 'vacation_type').order_by('start_date')
    
    # My All schedules
    all_schedules = VacationSchedule.objects.filter(
        employee=user_employee,
        is_deleted=False
    ).order_by('-start_date')
    
    return Response({
        'upcoming_schedules': VacationScheduleSerializer(upcoming_schedules, many=True).data,
        'peers_schedules': VacationScheduleSerializer(peers_schedules, many=True).data,
        'all_schedules': VacationScheduleSerializer(all_schedules, many=True).data
    })

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def bulk_register_schedules(request):
    """Bulk register multiple schedules as taken"""
    schedule_ids = request.data.get('schedule_ids', [])
    
    if not schedule_ids:
        return Response({
            'error': 'No schedule IDs provided'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        user_employee = Employee.objects.get(user=request.user)
    except Employee.DoesNotExist:
        return Response({
            'error': 'User does not have an employee profile'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    results = {
        'successful': 0,
        'failed': 0,
        'errors': []
    }
    
    with transaction.atomic():
        for schedule_id in schedule_ids:
            try:
                schedule = VacationSchedule.objects.get(id=schedule_id, is_deleted=False)
                
                # Check permissions
                if schedule.employee != user_employee:
                    # Check if user is manager or HR
                    if (schedule.employee.line_manager != user_employee and 
                        (not user_employee.department or 'HR' not in user_employee.department.name.upper())):
                        results['errors'].append(f"Schedule {schedule_id}: No permission")
                        results['failed'] += 1
                        continue
                
                if schedule.status != 'SCHEDULED':
                    results['errors'].append(f"Schedule {schedule_id}: Not in scheduled status")
                    results['failed'] += 1
                    continue
                
                # Register the schedule
                schedule.register_as_taken(request.user)
                
                results['successful'] += 1
                
            except VacationSchedule.DoesNotExist:
                results['errors'].append(f"Schedule {schedule_id}: Not found")
                results['failed'] += 1
            except Exception as e:
                results['errors'].append(f"Schedule {schedule_id}: {str(e)}")
                results['failed'] += 1
    
    return Response({
        'message': f'Bulk registration completed: {results["successful"]} successful, {results["failed"]} failed',
        'results': results
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def schedule_conflicts(request, schedule_id):
    """Get conflicts for a specific schedule"""
    try:
        user_employee = Employee.objects.get(user=request.user)
        schedule = get_object_or_404(VacationSchedule, id=schedule_id)
        
        # Check if user can view this schedule
        if schedule.employee != user_employee and schedule.employee.line_manager != user_employee:
            # Check if user is HR
            if not user_employee.department or 'HR' not in user_employee.department.name.upper():
                return Response({
                    'error': 'You do not have permission to view this schedule'
                }, status=status.HTTP_403_FORBIDDEN)
        
        # Get conflicting schedules
        conflicting_schedules = schedule.get_conflicting_schedules()
        
        # Get conflicting requests
        team_members = Employee.objects.filter(
            Q(department=schedule.employee.department) | 
            Q(line_manager=schedule.employee.line_manager),
            status__affects_headcount=True,
            is_deleted=False
        ).exclude(id=schedule.employee.id) if schedule.employee.department or schedule.employee.line_manager else Employee.objects.none()
        
        conflicting_requests = VacationRequest.objects.filter(
            employee__in=team_members,
            status__in=['APPROVED', 'PENDING_LINE_MANAGER', 'PENDING_HR'],
            start_date__lte=schedule.end_date,
            end_date__gte=schedule.start_date,
            is_deleted=False
        )
        
        return Response({
            'schedule': VacationScheduleSerializer(schedule).data,
            'conflicting_schedules': VacationScheduleSerializer(conflicting_schedules, many=True).data,
            'conflicting_requests': VacationRequestListSerializer(
                conflicting_requests, 
                many=True, 
                context={'request': request}
            ).data,
            'total_conflicts': conflicting_schedules.count() + conflicting_requests.count(),
            'conflict_message': f"There are {conflicting_schedules.count()} conflicting schedules and {conflicting_requests.count()} conflicting requests during this period."
        })
        
    except Employee.DoesNotExist:
        return Response({
            'error': 'User does not have an employee profile'
        }, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def all_requests_schedules(request):
    """Get all requests and schedules for current user"""
    try:
        user_employee = Employee.objects.get(user=request.user)
    except Employee.DoesNotExist:
        return Response({
            'error': 'User does not have an employee profile'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Get all requests
    requests = VacationRequest.objects.filter(
        employee=user_employee,
        is_deleted=False
    ).order_by('-created_at')
    
    # Get all schedules
    schedules = VacationSchedule.objects.filter(
        employee=user_employee,
        is_deleted=False
    ).order_by('-start_date')
    
    # Combine and format for unified display
    combined_records = []
    
    for req in requests:
        combined_records.append({
            'id': req.id,
            'type': 'request',
            'request_id': req.request_id,
            'vacation_type': req.vacation_type.name,
            'start_date': req.start_date,
            'end_date': req.end_date,
            'days': float(req.number_of_days),
            'status': req.status,
            'status_display': req.get_status_display(),
            'can_edit': req.can_be_edited(),
            'created_at': req.created_at
        })
    
    for schedule in schedules:
        combined_records.append({
            'id': schedule.id,
            'type': 'schedule',
            'request_id': f'SCH{schedule.id}',
            'vacation_type': schedule.vacation_type.name,
            'start_date': schedule.start_date,
            'end_date': schedule.end_date,
            'days': float(schedule.number_of_days),
            'status': schedule.status,
            'status_display': schedule.get_status_display(),
            'can_edit': schedule.can_edit(),
            'created_at': schedule.created_at
        })
    
    # Sort by created_at descending
    combined_records.sort(key=lambda x: x['created_at'], reverse=True)
    
    return Response({
        'records': combined_records,
        'total_count': len(combined_records)
    })

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def calculate_working_days(request):
    """Calculate working days between two dates"""
    start_date = request.data.get('start_date')
    end_date = request.data.get('end_date')
    
    if not start_date or not end_date:
        return Response({
            'error': 'Both start_date and end_date are required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        from datetime import datetime
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    except ValueError:
        return Response({
            'error': 'Invalid date format. Use YYYY-MM-DD'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    if start_date > end_date:
        return Response({
            'error': 'Start date cannot be after end date'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    settings = VacationSetting.get_active_settings()
    if settings:
        working_days = settings.calculate_working_days(start_date, end_date)
        return_date = settings.calculate_return_date(end_date)
    else:
        # Fallback calculation
        working_days = (end_date - start_date).days + 1
        return_date = end_date + timedelta(days=1)
    
    return Response({
        'working_days': working_days,
        'return_date': return_date.strftime('%Y-%m-%d')
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def production_calendar(request):
    """Get production calendar information"""
    settings = VacationSetting.get_active_settings()
    
    if not settings:
        return Response({
            'error': 'No active vacation settings found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Get year from query params
    year = request.query_params.get('year', date.today().year)
    try:
        year = int(year)
    except (ValueError, TypeError):
        year = date.today().year
    
    # Filter non-working days for the requested year
    year_non_working_days = [
        day for day in settings.non_working_days 
        if day.startswith(str(year))
    ]
    
    return Response({
        'year': year,
        'non_working_days': year_non_working_days,
        'total_non_working_days': len(year_non_working_days),
        'settings': {
            'allow_negative_balance': settings.allow_negative_balance,
            'max_schedule_edits': settings.max_schedule_edits,
            'notification_days_before': settings.notification_days_before
        }
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_balance_stats(request):
    """Get user's vacation balance statistics"""
    try:
        user_employee = Employee.objects.get(user=request.user)
    except Employee.DoesNotExist:
        return Response({
            'error': 'User does not have an employee profile'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    current_year = date.today().year
    year = request.query_params.get('year', current_year)
    
    try:
        year = int(year)
    except (ValueError, TypeError):
        year = current_year
    
    try:
        balance = EmployeeVacationBalance.objects.get(
            employee=user_employee,
            year=year
        )
        
        balance_data = {
            'total_balance': float(balance.total_balance),
            'yearly_balance': float(balance.yearly_balance),
            'used_days': float(balance.used_days),
            'remaining_balance': float(balance.remaining_balance),
            'scheduled_days': float(balance.scheduled_days),
            'should_be_planned': float(balance.should_be_planned),
            'balance_status': 'negative' if balance.remaining_balance < 0 else 
                             'low' if balance.remaining_balance < 5 else 
                             'high' if balance.remaining_balance > balance.yearly_balance * 0.8 else 'normal'
        }
        
        return Response({
            'year': year,
            'balance': balance_data,
            'employee_info': {
                'name': user_employee.full_name,
                'employee_id': user_employee.employee_id,
                'department': user_employee.department.name if user_employee.department else None
            }
        })
        
    except EmployeeVacationBalance.DoesNotExist:
        return Response({
            'error': f'No vacation balance found for year {year}'
        }, status=status.HTTP_404_NOT_FOUND)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def vacation_types_active(request):
    """Get active vacation types for form selection"""
    vacation_types = VacationType.objects.filter(is_active=True, is_deleted=False).order_by('name')
    
    return Response({
        'vacation_types': [
            {
                'id': vt.id,
                'name': vt.name,
                'code': vt.code,
                'description': vt.description,
                'color': vt.color,
                'requires_approval': vt.requires_approval,
                'affects_balance': vt.affects_balance,
                'max_consecutive_days': vt.max_consecutive_days
            }
            for vt in vacation_types
        ]
    })