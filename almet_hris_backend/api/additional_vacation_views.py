# api/additional_vacation_views.py - Additional Views for Vacation Dashboard and Approval

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
    VacationApprovalHistorySerializer
)
from .models import Employee

logger = logging.getLogger(__name__)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def vacation_dashboard_view(request):
    """Main vacation dashboard with all necessary data"""
    try:
        user_employee = Employee.objects.get(user=request.user)
    except Employee.DoesNotExist:
        return Response({
            'error': 'User does not have an employee profile'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    current_year = date.today().year
    
    # Get current balance (5 stat cards data)
    try:
        current_balance = EmployeeVacationBalance.objects.get(
            employee=user_employee,
            year=current_year
        )
        balance_data = {
            'total_balance': float(current_balance.total_balance),
            'yearly_balance': float(current_balance.yearly_balance),
            'used_days': float(current_balance.used_days),
            'remaining_balance': float(current_balance.remaining_balance),
            'scheduled_days': float(current_balance.scheduled_days),
            'should_be_planned': float(current_balance.should_be_planned)
        }
    except EmployeeVacationBalance.DoesNotExist:
        balance_data = {
            'total_balance': 0,
            'yearly_balance': 0,
            'used_days': 0,
            'remaining_balance': 0,
            'scheduled_days': 0,
            'should_be_planned': 0
        }
    
    # Get pending approvals count (if manager or HR)
    pending_approvals = VacationRequest.objects.filter(
        Q(line_manager=user_employee, status='PENDING_LINE_MANAGER') |
        Q(hr_representative=user_employee, status='PENDING_HR'),
        is_deleted=False
    )
    
    # Get upcoming schedules
    upcoming_schedules = VacationSchedule.objects.filter(
        employee=user_employee,
        start_date__gte=date.today(),
        status='SCHEDULED',
        is_deleted=False
    )[:5]
    
    # Get recent requests
    recent_requests = VacationRequest.objects.filter(
        employee=user_employee,
        is_deleted=False
    ).order_by('-created_at')[:5]
    
    return Response({
        'balance': balance_data,
        'pending_approvals': VacationRequestListSerializer(
            pending_approvals, 
            many=True, 
            context={'request': request}
        ).data,
        'pending_approvals_count': pending_approvals.count(),
        'upcoming_schedules': VacationScheduleSerializer(upcoming_schedules, many=True).data,
        'upcoming_schedules_count': upcoming_schedules.count(),
        'recent_requests': VacationRequestListSerializer(
            recent_requests, 
            many=True, 
            context={'request': request}
        ).data
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def request_submission_view(request):
    """View for request submission section"""
    try:
        user_employee = Employee.objects.get(user=request.user)
    except Employee.DoesNotExist:
        return Response({
            'error': 'User does not have an employee profile'
        }, status=status.HTTP_400_BAD_REQUEST)
    
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
        'vacation_types': [
            {
                'id': vt.id,
                'name': vt.name,
                'code': vt.code,
                'color': vt.color,
                'requires_approval': vt.requires_approval,
                'affects_balance': vt.affects_balance,
                'max_consecutive_days': vt.max_consecutive_days
            }
            for vt in vacation_types
        ],
        'direct_reports': [
            {
                'id': emp.id,
                'employee_id': emp.employee_id,
                'full_name': emp.full_name,
                'department': emp.department.name if emp.department else None,
                'business_function': emp.business_function.name if emp.business_function else None,
                'unit': emp.unit.name if emp.unit else None,
                'job_function': emp.job_function.name if emp.job_function else None,
               
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
def approval_pending_view(request):
    """View for pending approvals section"""
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
def approval_history_view(request):
    """View for approval history"""
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
    ).select_related('employee', 'vacation_type').order_by('-line_manager_approved_at')
    
    # Get requests approved by this user as HR
    hr_approved = VacationRequest.objects.filter(
        hr_approved_by=request.user,
        is_deleted=False
    ).select_related('employee', 'vacation_type').order_by('-hr_approved_at')
    
    # Get requests rejected by this user
    rejected_requests = VacationRequest.objects.filter(
        rejected_by=request.user,
        is_deleted=False
    ).select_related('employee', 'vacation_type').order_by('-rejected_at')
    
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
def schedule_conflicts_view(request, schedule_id):
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
        
        # Get conflicting requests if this is a schedule being converted to request
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
def my_schedules_lists_view(request):
    """Get different lists of schedules for the user"""
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
def bulk_schedule_register(request):
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
                balance = schedule.get_employee_balance()
                if balance:
                    balance.use_days(schedule.number_of_days)
                
                schedule.status = 'REGISTERED'
                schedule.save()
                
                # Log activity
                VacationActivity.objects.create(
                    vacation_schedule=schedule,
                    activity_type='REGISTERED',
                    description=f"Schedule registered as taken by {request.user.get_full_name()}",
                    performed_by=request.user
                )
                
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
def production_calendar_view(request):
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