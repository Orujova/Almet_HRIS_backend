# api/vacation_views.py - Separated Settings APIs

from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status, viewsets
from rest_framework.parsers import MultiPartParser, FormParser
from django.db import transaction
from django.db.models import Q, Count, Sum
from datetime import date, datetime, timedelta
from collections import defaultdict
from .vacation_models import *
from .vacation_serializers import *
from .models import Employee
import pandas as pd
from django.http import HttpResponse
from openpyxl import Workbook
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

# ==================== PRODUCTION CALENDAR SETTINGS ====================
@swagger_auto_schema(
    method='post',
    operation_description="Production Calendar - qeyri-iş günlərini təyin et",
    operation_summary="Set Non-Working Days",
    tags=['Vacation - Settings'],
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=['non_working_days'],
        properties={
            'non_working_days': openapi.Schema(
                type=openapi.TYPE_ARRAY,
                items=openapi.Schema(type=openapi.TYPE_STRING, format='date'),
                description='Qeyri-iş günləri massivi',
                example=['2025-01-01', '2025-01-20', '2025-03-08', '2025-03-20']
            ),
        }
    ),
    responses={
        200: openapi.Response(
            description='Production calendar yeniləndi',
            examples={
                'application/json': {
                    'message': 'Production calendar uğurla yeniləndi',
                    'non_working_days': ['2025-01-01', '2025-01-20', '2025-03-08']
                }
            }
        )
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def set_production_calendar(request):
    """Production Calendar - qeyri-iş günlərini təyin et"""
    try:
        serializer = ProductionCalendarSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        non_working_days = serializer.validated_data['non_working_days']
        
        # Active settings tap və ya yarat
        settings = VacationSetting.get_active()
        if not settings:
            settings = VacationSetting.objects.create(
                is_active=True,
                created_by=request.user
            )
        
        # String formatına çevir
        settings.non_working_days = [day.strftime('%Y-%m-%d') for day in non_working_days]
        settings.save()
        
        return Response({
            'message': 'Production calendar uğurla yeniləndi',
            'non_working_days': settings.non_working_days
        })
        
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@swagger_auto_schema(
    method='get',
    operation_description="Production Calendar məlumatlarını əldə et",
    operation_summary="Get Production Calendar",
    tags=['Vacation - Settings'],
    responses={
        200: openapi.Response(
            description='Production calendar məlumatları',
            examples={
                'application/json': {
                    'non_working_days': ['2025-01-01', '2025-01-20', '2025-03-08']
                }
            }
        )
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_production_calendar(request):
    """Production Calendar məlumatlarını əldə et"""
    try:
        settings = VacationSetting.get_active()
        
        return Response({
            'non_working_days': settings.non_working_days if settings else []
        })
        
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


# ==================== GENERAL VACATION SETTINGS ====================
@swagger_auto_schema(
    method='post',
    operation_description="Vacation ümumi parametrləri - balans, edit limiti, bildirişlər",
    operation_summary="Set General Vacation Settings",
    tags=['Vacation - Settings'],
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'allow_negative_balance': openapi.Schema(
                type=openapi.TYPE_BOOLEAN,
                description='Balans 0 olduqda request yaratmağa icazə ver',
                example=False
            ),
            'max_schedule_edits': openapi.Schema(
                type=openapi.TYPE_INTEGER,
                description='Schedule neçə dəfə edit oluna bilər',
                example=3
            ),
            'notification_days_before': openapi.Schema(
                type=openapi.TYPE_INTEGER,
                description='Məzuniyyət başlamazdan neçə gün əvvəl bildiriş göndər',
                example=7
            ),
            'notification_frequency': openapi.Schema(
                type=openapi.TYPE_INTEGER,
                description='Bildirişi neçə dəfə göndər',
                example=2
            ),
        }
    ),
    responses={
        200: openapi.Response(
            description='Ümumi parametrlər yeniləndi',
            examples={
                'application/json': {
                    'message': 'Vacation parametrləri uğurla yeniləndi',
                    'settings': {
                        'allow_negative_balance': False,
                        'max_schedule_edits': 3,
                        'notification_days_before': 7,
                        'notification_frequency': 2
                    }
                }
            }
        )
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def set_general_vacation_settings(request):
    """Vacation ümumi parametrləri"""
    try:
        serializer = GeneralVacationSettingsSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        data = serializer.validated_data
        
        # Active settings tap və ya yarat
        settings = VacationSetting.get_active()
        if not settings:
            settings = VacationSetting.objects.create(
                is_active=True,
                created_by=request.user
            )
        
        # Parametrləri yenilə
        if 'allow_negative_balance' in data:
            settings.allow_negative_balance = data['allow_negative_balance']
        
        if 'max_schedule_edits' in data:
            settings.max_schedule_edits = data['max_schedule_edits']
        
        if 'notification_days_before' in data:
            settings.notification_days_before = data['notification_days_before']
        
        if 'notification_frequency' in data:
            settings.notification_frequency = data['notification_frequency']
        
        settings.save()
        
        return Response({
            'message': 'Vacation parametrləri uğurla yeniləndi',
            'settings': {
                'allow_negative_balance': settings.allow_negative_balance,
                'max_schedule_edits': settings.max_schedule_edits,
                'notification_days_before': settings.notification_days_before,
                'notification_frequency': settings.notification_frequency
            }
        })
        
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@swagger_auto_schema(
    method='get',
    operation_description="Vacation ümumi parametrlərini əldə et",
    operation_summary="Get General Vacation Settings",
    tags=['Vacation - Settings'],
    responses={
        200: openapi.Response(
            description='Ümumi parametrlər',
            examples={
                'application/json': {
                    'allow_negative_balance': False,
                    'max_schedule_edits': 3,
                    'notification_days_before': 7,
                    'notification_frequency': 2
                }
            }
        )
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_general_vacation_settings(request):
    """Vacation ümumi parametrlərini əldə et"""
    try:
        settings = VacationSetting.get_active()
        
        if not settings:
            return Response({
                'allow_negative_balance': False,
                'max_schedule_edits': 3,
                'notification_days_before': 7,
                'notification_frequency': 2
            })
        
        return Response({
            'allow_negative_balance': settings.allow_negative_balance,
            'max_schedule_edits': settings.max_schedule_edits,
            'notification_days_before': settings.notification_days_before,
            'notification_frequency': settings.notification_frequency
        })
        
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


# ==================== HR REPRESENTATIVE SETTINGS ====================
@swagger_auto_schema(
    method='post',
    operation_description="Default HR nümayəndəsini təyin et",
    operation_summary="Set Default HR Representative",
    tags=['Vacation - Settings'],
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=['default_hr_representative_id'],
        properties={
            'default_hr_representative_id': openapi.Schema(
                type=openapi.TYPE_INTEGER,
                description='Default HR nümayəndəsi Employee ID',
                example=5
            ),
        }
    ),
    responses={
        200: openapi.Response(
            description='Default HR təyin edildi',
            examples={
                'application/json': {
                    'message': 'Default HR nümayəndəsi uğurla təyin edildi',
                    'hr_representative': {
                        'id': 5,
                        'name': 'Sarah Johnson',
                        'department': 'HR'
                    }
                }
            }
        )
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def set_default_hr_representative(request):
    """Default HR nümayəndəsini təyin et"""
    try:
        serializer = HRRepresentativeSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        hr_id = serializer.validated_data['default_hr_representative_id']
        hr_employee = Employee.objects.get(id=hr_id, is_deleted=False)
        
        # Active settings tap və ya yarat
        settings = VacationSetting.get_active()
        if not settings:
            settings = VacationSetting.objects.create(
                is_active=True,
                created_by=request.user
            )
        
        settings.default_hr_representative = hr_employee
        settings.save()
        
        return Response({
            'message': 'Default HR nümayəndəsi uğurla təyin edildi',
            'hr_representative': {
                'id': hr_employee.id,
                'name': hr_employee.full_name,
                'department': hr_employee.department.name if hr_employee.department else ''
            }
        })
        
    except Employee.DoesNotExist:
        return Response({
            'error': 'HR nümayəndəsi tapılmadı'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@swagger_auto_schema(
    method='get',
    operation_description="Mövcud HR nümayəndələrini əldə et",
    operation_summary="Get HR Representatives",
    tags=['Vacation - Settings'],
    responses={
        200: openapi.Response(
            description='HR nümayəndələri siyahısı',
            examples={
                'application/json': {
                    'current_default': {
                        'id': 5,
                        'name': 'Sarah Johnson',
                        'department': 'HR'
                    },
                    'hr_representatives': [
                        {
                            'id': 5,
                            'name': 'Sarah Johnson',
                            'department': 'HR',
                            'email': 'sarah@company.com',
                            'is_default': True
                        },
                        {
                            'id': 8,
                            'name': 'Mike Brown',
                            'department': 'HR',
                            'email': 'mike@company.com',
                            'is_default': False
                        }
                    ]
                }
            }
        )
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_hr_representatives(request):
    """HR nümayəndələrini əldə et"""
    try:
        settings = VacationSetting.get_active()
        current_default = settings.default_hr_representative if settings else None
        
        # HR departamentindəki işçilər
        hr_employees = Employee.objects.filter(
            department__name__icontains='HR',
            is_deleted=False
        )
        
        hr_list = []
        for emp in hr_employees:
            hr_list.append({
                'id': emp.id,
                'name': emp.full_name,
                'email': emp.email if hasattr(emp, 'email') else '',
                'phone': emp.phone,
                'department': emp.department.name if emp.department else '',
                'is_default': current_default and current_default.id == emp.id
            })
        
        return Response({
            'current_default': {
                'id': current_default.id,
                'name': current_default.full_name,
                'department': current_default.department.name if current_default.department else ''
            } if current_default else None,
            'hr_representatives': hr_list
        })
        
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


# ==================== DASHBOARD ====================
@swagger_auto_schema(
    method='get',
    operation_description="Dashboard məlumatları - 5 stat card və əsas statistika",
    operation_summary="Dashboard",
    tags=['Vacation - Dashboard'],
    responses={
        200: openapi.Response(
            description='Dashboard data',
            examples={
                'application/json': {
                    'balance': {
                        'total_balance': 28.0,
                        'yearly_balance': 28.0,
                        'used_days': 5.0,
                        'remaining_balance': 23.0,
                        'scheduled_days': 3.0,
                        'should_be_planned': 25.0
                    }
                }
            }
        )
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def vacation_dashboard(request):
    """Dashboard - 5 stat card"""
    try:
        emp = Employee.objects.get(user=request.user)
        balance = EmployeeVacationBalance.objects.get(employee=emp, year=date.today().year)
        
        return Response({
            'balance': {
                'total_balance': float(balance.total_balance),
                'yearly_balance': float(balance.yearly_balance),
                'used_days': float(balance.used_days),
                'remaining_balance': float(balance.remaining_balance),
                'scheduled_days': float(balance.scheduled_days),
                'should_be_planned': float(balance.should_be_planned)
            }
        })
    except:
        return Response({
            'balance': {'total_balance': 0, 'yearly_balance': 0, 'used_days': 0, 
                       'remaining_balance': 0, 'scheduled_days': 0, 'should_be_planned': 0}
        })



# ==================== REQUEST SUBMISSION FORM DATA ====================
@swagger_auto_schema(
    method='get',
    operation_description="Request/Schedule formları üçün lazım olan data",
    operation_summary="Form Data",
    tags=['Vacation - Request Submission'],
    responses={
        200: openapi.Response(
            description='Form data',
            examples={
                'application/json': {
                    'employee_info': {
                        'id': 1,
                        'name': 'John Doe',
                        'phone': '+994501234567',
                        'department': 'IT',
                        'business_function': 'Development',
                        'unit': 'Frontend',
                        'job_function': 'Senior Developer',
                        'line_manager': 'Jane Smith'
                    },
                    'direct_reports': [],
                    'hr_representatives': [],
                    'vacation_types': [],
                    'settings': {
                        'non_working_days': [],
                        'allow_negative_balance': False
                    }
                }
            }
        )
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_form_data(request):
    """Request/Schedule formları üçün lazım olan data"""
    try:
        emp = Employee.objects.get(user=request.user)
        settings = VacationSetting.get_active()
        
        # Direct reports
        direct_reports = Employee.objects.filter(line_manager=emp, is_deleted=False)
        
        # HR reps
        hr_reps = Employee.objects.filter(department__name__icontains='HR', is_deleted=False)
        
        # Vacation types
        vac_types = VacationType.objects.filter(is_active=True, is_deleted=False)
        
        return Response({
            'employee_info': {
                'id': emp.id,
                'name': emp.full_name,
                'phone': emp.phone,
                'department': emp.department.name if emp.department else '',
                'business_function': emp.business_function.name if emp.business_function else '',
                'unit': emp.unit.name if emp.unit else '',
                'job_function': emp.job_function.name if emp.job_function else '',
                'line_manager': emp.line_manager.full_name if emp.line_manager else ''
            },
            'direct_reports': [{'id': e.id, 'name': e.full_name, 'department': e.department.name if e.department else ''} for e in direct_reports],
            'hr_representatives': [{'id': h.id, 'name': h.full_name} for h in hr_reps],
            'vacation_types': VacationTypeSerializer(vac_types, many=True).data,
            'settings': {
                'non_working_days': settings.non_working_days if settings else [],
                'allow_negative_balance': settings.allow_negative_balance if settings else False
            }
        })
    except Exception as e:
        return Response({'error': f'Employee profili tapılmadı: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)

# ... (rest of the existing APIs remain the same) ...
# ==================== EMPLOYEE SEARCH ====================
@swagger_auto_schema(
    method='get',
    operation_description="Employee axtarışı - manual daxil etmək üçün",
    operation_summary="Search Employees",
    tags=['Vacation - Request Submission'],
    manual_parameters=[
        openapi.Parameter(
            'q',
            openapi.IN_QUERY,
            description="Axtarış sorğusu (ad, soyad, employee_id)",
            type=openapi.TYPE_STRING,
            required=True
        )
    ],
    responses={
        200: openapi.Response(
            description='Employee list',
            examples={
                'application/json': {
                    'employees': [
                        {
                            'id': 1,
                            'name': 'John Doe',
                            'employee_id': 'EMP001',
                            'department': 'IT',
                            'business_function': 'Development',
                            'unit': 'Frontend',
                            'job_function': 'Senior Developer',
                            'phone': '+994501234567'
                        }
                    ]
                }
            }
        )
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def search_employees(request):
    """Employee axtarışı"""
    query = request.GET.get('q', '').strip()
    
    if len(query) < 2:
        return Response({'employees': []})
    
    employees = Employee.objects.filter(
        Q(full_name__icontains=query) | 
        Q(employee_id__icontains=query) |
        Q(first_name__icontains=query) |
        Q(last_name__icontains=query),
        is_deleted=False
    )[:10]
    
    result = []
    for emp in employees:
        result.append({
            'id': emp.id,
            'name': emp.full_name,
            'employee_id': getattr(emp, 'employee_id', ''),
            'department': emp.department.name if emp.department else '',
            'business_function': emp.business_function.name if emp.business_function else '',
            'unit': emp.unit.name if emp.unit else '',
            'job_function': emp.job_function.name if emp.job_function else '',
            'phone': emp.phone
        })
    
    return Response({'employees': result})


# ==================== REQUEST IMMEDIATE ====================
@swagger_auto_schema(
    method='post',
    operation_description="Request Immediately yaratmaq",
    operation_summary="Create Immediate Request",
    tags=['Vacation - Request Submission'],
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=['requester_type', 'vacation_type_id', 'start_date', 'end_date'],
        properties={
            'requester_type': openapi.Schema(
                type=openapi.TYPE_STRING,
                enum=['for_me', 'for_my_employee'],
                description='Kimə görə request yaradırsan'
            ),
            'employee_id': openapi.Schema(
                type=openapi.TYPE_INTEGER,
                description='İşçi ID (yalnız for_my_employee üçün)',
                example=123
            ),
            'employee_manual': openapi.Schema(
                type=openapi.TYPE_OBJECT,
                description='Manual employee məlumatları (əgər sistemdə yoxdursa)',
                properties={
                    'name': openapi.Schema(type=openapi.TYPE_STRING, example='John Doe'),
                    'phone': openapi.Schema(type=openapi.TYPE_STRING, example='+994501234567'),
                    'department': openapi.Schema(type=openapi.TYPE_STRING, example='IT'),
                    'business_function': openapi.Schema(type=openapi.TYPE_STRING, example='Development'),
                    'unit': openapi.Schema(type=openapi.TYPE_STRING, example='Frontend'),
                    'job_function': openapi.Schema(type=openapi.TYPE_STRING, example='Developer')
                }
            ),
            'vacation_type_id': openapi.Schema(
                type=openapi.TYPE_INTEGER,
                description='Vacation növü ID',
                example=1
            ),
            'start_date': openapi.Schema(
                type=openapi.TYPE_STRING,
                format='date',
                description='Başlama tarixi (YYYY-MM-DD)',
                example='2025-10-15'
            ),
            'end_date': openapi.Schema(
                type=openapi.TYPE_STRING,
                format='date',
                description='Bitmə tarixi (YYYY-MM-DD)',
                example='2025-10-20'
            ),
            'comment': openapi.Schema(
                type=openapi.TYPE_STRING,
                description='Şərh (optional)',
                example='Ailə səbəbi'
            ),
            'hr_representative_id': openapi.Schema(
                type=openapi.TYPE_INTEGER,
                description='HR nümayəndəsi ID (optional)',
                example=5
            ),
        }
    ),
    responses={
        201: openapi.Response(
            description='Request yaradıldı',
            examples={
                'application/json': {
                    'message': 'Request yaradıldı və təsdiqə göndərildi',
                    'request': {
                        'id': 1,
                        'request_id': 'VR20250001',
                        'status': 'PENDING_LINE_MANAGER'
                    }
                }
            }
        )
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_immediate_request(request):
    """Request Immediately yarat"""
    serializer = VacationRequestCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    data = serializer.validated_data
    
    try:
        requester_emp = Employee.objects.get(user=request.user)
        
        # Employee seç
        if data['requester_type'] == 'for_me':
            employee = requester_emp
        else:
            if data.get('employee_id'):
                employee = Employee.objects.get(id=data['employee_id'])
                if employee.line_manager != requester_emp:
                    return Response({'error': 'Bu işçi sizin tabeliyinizdə deyil'}, status=status.HTTP_403_FORBIDDEN)
            else:
                # Manual employee yaradıb istifadə et
                manual_data = data.get('employee_manual', {})
                if not manual_data.get('name'):
                    return Response({'error': 'Employee adı mütləqdir'}, status=status.HTTP_400_BAD_REQUEST)
                
                # Sistemə əlavə et
                employee = Employee.objects.create(
                    full_name=manual_data.get('name', ''),
                    phone=manual_data.get('phone', ''),
                    line_manager=requester_emp
                )
        
        with transaction.atomic():
            vac_req = VacationRequest.objects.create(
                employee=employee,
                requester=request.user,
                request_type='IMMEDIATE',
                vacation_type_id=data['vacation_type_id'],
                start_date=data['start_date'],
                end_date=data['end_date'],
                comment=data.get('comment', ''),
                hr_representative_id=data.get('hr_representative_id')
            )
            
            vac_req.submit_request(request.user)
            
            return Response({
                'message': 'Request yaradıldı və təsdiqə göndərildi',
                'request': VacationRequestDetailSerializer(vac_req).data
            }, status=status.HTTP_201_CREATED)
    
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


# ==================== CREATE SCHEDULE ====================
@swagger_auto_schema(
    method='post',
    operation_description="Vacation Schedule yaratmaq (təsdiq tələb etmir)",
    operation_summary="Create Schedule",
    tags=['Vacation - Request Submission'],
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=['requester_type', 'vacation_type_id', 'start_date', 'end_date'],
        properties={
            'requester_type': openapi.Schema(
                type=openapi.TYPE_STRING,
                enum=['for_me', 'for_my_employee'],
                description='Kimə görə schedule yaradırsan'
            ),
            'employee_id': openapi.Schema(
                type=openapi.TYPE_INTEGER,
                description='İşçi ID (yalnız for_my_employee üçün)',
                example=123
            ),
            'employee_manual': openapi.Schema(
                type=openapi.TYPE_OBJECT,
                description='Manual employee məlumatları',
                properties={
                    'name': openapi.Schema(type=openapi.TYPE_STRING, example='John Doe'),
                    'phone': openapi.Schema(type=openapi.TYPE_STRING, example='+994501234567'),
                    'department': openapi.Schema(type=openapi.TYPE_STRING, example='IT')
                }
            ),
            'vacation_type_id': openapi.Schema(
                type=openapi.TYPE_INTEGER,
                description='Vacation növü ID',
                example=1
            ),
            'start_date': openapi.Schema(
                type=openapi.TYPE_STRING,
                format='date',
                description='Başlama tarixi',
                example='2025-11-10'
            ),
            'end_date': openapi.Schema(
                type=openapi.TYPE_STRING,
                format='date',
                description='Bitmə tarixi',
                example='2025-11-15'
            ),
            'comment': openapi.Schema(
                type=openapi.TYPE_STRING,
                description='Şərh',
                example='Planlı məzuniyyət'
            ),
        }
    ),
    responses={
        201: openapi.Response(
            description='Schedule yaradıldı',
            examples={
                'application/json': {
                    'message': 'Schedule yaradıldı',
                    'schedule': {
                        'id': 1,
                        'employee_name': 'John Doe',
                        'start_date': '2025-11-10',
                        'end_date': '2025-11-15',
                        'number_of_days': 4,
                        'status': 'SCHEDULED'
                    },
                    'conflicts': []
                }
            }
        )
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_schedule(request):
    """Schedule yarat"""
    serializer = VacationScheduleCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    data = serializer.validated_data
    
    try:
        requester_emp = Employee.objects.get(user=request.user)
        
        if data['requester_type'] == 'for_me':
            employee = requester_emp
        else:
            if data.get('employee_id'):
                employee = Employee.objects.get(id=data['employee_id'])
                if employee.line_manager != requester_emp:
                    return Response({'error': 'Bu işçi sizin tabeliyinizdə deyil'}, status=status.HTTP_403_FORBIDDEN)
            else:
                # Manual employee
                manual_data = data.get('employee_manual', {})
                if not manual_data.get('name'):
                    return Response({'error': 'Employee adı mütləqdir'}, status=status.HTTP_400_BAD_REQUEST)
                
                employee = Employee.objects.create(
                    full_name=manual_data.get('name', ''),
                    phone=manual_data.get('phone', ''),
                    line_manager=requester_emp
                )
        
        # Conflicting schedules tap
        conflicts = VacationSchedule.objects.filter(
            employee__in=Employee.objects.filter(
                Q(department=employee.department) | Q(line_manager=employee.line_manager)
            ).exclude(id=employee.id) if employee.id else Employee.objects.none(),
            start_date__lte=data['end_date'],
            end_date__gte=data['start_date'],
            status='SCHEDULED',
            is_deleted=False
        )
        
        schedule = VacationSchedule.objects.create(
            employee=employee,
            vacation_type_id=data['vacation_type_id'],
            start_date=data['start_date'],
            end_date=data['end_date'],
            comment=data.get('comment', ''),
            created_by=request.user
        )
        
        return Response({
            'message': 'Schedule yaradıldı',
            'schedule': VacationScheduleSerializer(schedule).data,
            'conflicts': VacationScheduleSerializer(conflicts, many=True).data
        }, status=status.HTTP_201_CREATED)
    
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


# ==================== MY SCHEDULE TABS ====================
@swagger_auto_schema(
    method='get',
    operation_description="Schedule tabları - upcoming, peers, all",
    operation_summary="My Schedule Tabs",
    tags=['Vacation - Request Submission'],
    responses={
        200: openapi.Response(
            description='Schedule tabs data',
            examples={
                'application/json': {
                    'upcoming': [],
                    'peers': [],
                    'all': []
                }
            }
        )
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_schedule_tabs(request):
    """Schedule tabları - upcoming, peers, all"""
    try:
        emp = Employee.objects.get(user=request.user)
        
        # Upcoming
        upcoming = VacationSchedule.objects.filter(
            employee=emp,
            start_date__gte=date.today(),
            status='SCHEDULED',
            is_deleted=False
        )
        
        # Peers
        peers = Employee.objects.filter(
            Q(department=emp.department) | Q(line_manager=emp.line_manager),
            is_deleted=False
        ).exclude(id=emp.id)
        
        peers_schedules = VacationSchedule.objects.filter(
            employee__in=peers,
            start_date__gte=date.today(),
            status='SCHEDULED',
            is_deleted=False
        )
        
        # All
        all_schedules = VacationSchedule.objects.filter(employee=emp, is_deleted=False)
        
        return Response({
            'upcoming': VacationScheduleSerializer(upcoming, many=True).data,
            'peers': VacationScheduleSerializer(peers_schedules, many=True).data,
            'all': VacationScheduleSerializer(all_schedules, many=True).data
        })
    except Exception as e:
        return Response({'error': f'Employee profili tapılmadı: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)


# ==================== REGISTER SCHEDULE ====================
@swagger_auto_schema(
    method='post',
    operation_description="Schedule-i registered et",
    operation_summary="Register Schedule",
    tags=['Vacation - Request Submission'],
    manual_parameters=[
        openapi.Parameter(
            'id',
            openapi.IN_PATH,
            description="Schedule ID",
            type=openapi.TYPE_INTEGER,
            required=True
        )
    ],
    responses={
        200: openapi.Response(
            description='Schedule registered edildi',
            examples={
                'application/json': {
                    'message': 'Schedule registered edildi',
                    'schedule': {}
                }
            }
        )
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def register_schedule(request, pk):
    """Schedule-i registered et"""
    try:
        schedule = VacationSchedule.objects.get(pk=pk, is_deleted=False)
        schedule.register_as_taken(request.user)
        
        return Response({
            'message': 'Schedule registered edildi',
            'schedule': VacationScheduleSerializer(schedule).data
        })
    except VacationSchedule.DoesNotExist:
        return Response({'error': 'Schedule tapılmadı'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


# ==================== APPROVAL PENDING ====================
@swagger_auto_schema(
    method='get',
    operation_description="Approval - Pending requestlər",
    operation_summary="Pending Requests",
    tags=['Vacation - Approval'],
    responses={
        200: openapi.Response(
            description='Pending requests',
            examples={
                'application/json': {
                    'line_manager_requests': [],
                    'hr_requests': [],
                    'total_pending': 0
                }
            }
        )
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def approval_pending_requests(request):
    """Approval - Pending requestlər"""
    try:
        emp = Employee.objects.get(user=request.user)
        
        # Line Manager olaraq
        lm_requests = VacationRequest.objects.filter(
            line_manager=emp,
            status='PENDING_LINE_MANAGER',
            is_deleted=False
        )
        
        # HR olaraq
        hr_requests = VacationRequest.objects.filter(
            hr_representative=emp,
            status='PENDING_HR',
            is_deleted=False
        )
        
        return Response({
            'line_manager_requests': VacationRequestListSerializer(lm_requests, many=True).data,
            'hr_requests': VacationRequestListSerializer(hr_requests, many=True).data,
            'total_pending': lm_requests.count() + hr_requests.count()
        })
    except Exception as e:
        return Response({'error': f'Employee profili tapılmadı: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)


# ==================== APPROVAL HISTORY ====================
@swagger_auto_schema(
    method='get',
    operation_description="Approval History",
    operation_summary="Approval History",
    tags=['Vacation - Approval'],
    responses={
        200: openapi.Response(
            description='Approval history',
            examples={
                'application/json': {
                    'history': []
                }
            }
        )
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def approval_history(request):
    """Approval History"""
    try:
        # Line Manager kimi təsdiq etdiklərim
        lm_approved = VacationRequest.objects.filter(
            line_manager_approved_by=request.user,
            is_deleted=False
        ).order_by('-line_manager_approved_at')[:20]
        
        # HR kimi təsdiq etdiklərim
        hr_approved = VacationRequest.objects.filter(
            hr_approved_by=request.user,
            is_deleted=False
        ).order_by('-hr_approved_at')[:20]
        
        # Reject etdiklərim
        rejected = VacationRequest.objects.filter(
            rejected_by=request.user,
            is_deleted=False
        ).order_by('-rejected_at')[:20]
        
        history = []
        
        for req in lm_approved:
            history.append({
                'request_id': req.request_id,
                'employee_name': req.employee.full_name,
                'vacation_type': req.vacation_type.name,
                'start_date': req.start_date.strftime('%Y-%m-%d'),
                'end_date': req.end_date.strftime('%Y-%m-%d'),
                'status': 'Approved (Line Manager)',
                'date': req.line_manager_approved_at
            })
        
        for req in hr_approved:
            history.append({
                'request_id': req.request_id,
                'employee_name': req.employee.full_name,
                'vacation_type': req.vacation_type.name,
                'start_date': req.start_date.strftime('%Y-%m-%d'),
                'end_date': req.end_date.strftime('%Y-%m-%d'),
                'status': 'Approved (HR)',
                'date': req.hr_approved_at
            })
        
        for req in rejected:
            history.append({
                'request_id': req.request_id,
                'employee_name': req.employee.full_name,
                'vacation_type': req.vacation_type.name,
                'start_date': req.start_date.strftime('%Y-%m-%d'),
                'end_date': req.end_date.strftime('%Y-%m-%d'),
                'status': req.get_status_display(),
                'date': req.rejected_at
            })
        
        history.sort(key=lambda x: x['date'], reverse=True)
        
        return Response({'history': history[:20]})
    except Exception as e:
        return Response({'error': f'History yüklənmədi: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)


# ==================== APPROVE/REJECT REQUEST ====================
@swagger_auto_schema(
    method='post',
    operation_description="Request-ə approve və ya reject ver",
    operation_summary="Approve/Reject Request",
    tags=['Vacation - Approval'],
    manual_parameters=[
        openapi.Parameter(
            'id',
            openapi.IN_PATH,
            description="Request ID",
            type=openapi.TYPE_INTEGER,
            required=True
        )
    ],
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=['action'],
        properties={
            'action': openapi.Schema(
                type=openapi.TYPE_STRING,
                enum=['approve', 'reject'],
                description='approve və ya reject',
                example='approve'
            ),
            'comment': openapi.Schema(
                type=openapi.TYPE_STRING,
                description='Şərh (approve üçün optional)',
                example='Razıyam'
            ),
            'reason': openapi.Schema(
                type=openapi.TYPE_STRING,
                description='İmtina səbəbi (reject üçün MÜTLƏQ)',
                example='Bu tarixdə başqa işçilər məzuniyyətdədir'
            ),
        }
    ),
    responses={
        200: openapi.Response(
            description='Uğurlu',
            examples={
                'application/json': {
                    'message': 'Line Manager tərəfindən təsdiq edildi',
                    'request': {}
                }
            }
        )
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def approve_reject_request(request, pk):
    """Requestə approve/reject ver"""
    serializer = VacationApprovalSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    data = serializer.validated_data
    
    try:
        vac_req = VacationRequest.objects.get(pk=pk, is_deleted=False)
        
        if vac_req.status == 'PENDING_LINE_MANAGER':
            if data['action'] == 'approve':
                vac_req.approve_by_line_manager(request.user, data.get('comment', ''))
                msg = 'Line Manager tərəfindən təsdiq edildi'
            else:
                vac_req.reject_by_line_manager(request.user, data.get('reason', ''))
                msg = 'Line Manager tərəfindən reject edildi'
        
        elif vac_req.status == 'PENDING_HR':
            if data['action'] == 'approve':
                vac_req.approve_by_hr(request.user, data.get('comment', ''))
                msg = 'HR tərəfindən təsdiq edildi'
            else:
                vac_req.reject_by_hr(request.user, data.get('reason', ''))
                msg = 'HR tərəfindən reject edildi'
        else:
            return Response({'error': 'Bu request təsdiq statusunda deyil'}, status=status.HTTP_400_BAD_REQUEST)
        
        return Response({
            'message': msg,
            'request': VacationRequestDetailSerializer(vac_req).data
        })
    
    except VacationRequest.DoesNotExist:
        return Response({'error': 'Request tapılmadı'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


# ==================== MY ALL REQUESTS & SCHEDULES ====================
@swagger_auto_schema(
    method='get',
    operation_description="İstifadəçinin bütün vacation request və schedulelərini göstər",
    operation_summary="My All Requests & Schedules",
    tags=['Vacation - My All'],
    responses={
        200: openapi.Response(
            description='Bütün records',
            examples={
                'application/json': {
                    'records': [
                        {
                            'id': 1,
                            'type': 'request',
                            'request_id': 'VR20250001',
                            'vacation_type': 'Annual Leave',
                            'start_date': '2025-10-15',
                            'end_date': '2025-10-20',
                            'days': 4.0,
                            'status': 'Approved',
                            'created_at': '2025-09-01T10:00:00Z'
                        },
                        {
                            'id': 2,
                            'type': 'schedule',
                            'request_id': 'SCH2',
                            'vacation_type': 'Annual Leave',
                            'start_date': '2025-11-10',
                            'end_date': '2025-11-15',
                            'days': 4.0,
                            'status': 'Scheduled',
                            'can_edit': True,
                            'created_at': '2025-09-05T14:30:00Z'
                        }
                    ]
                }
            }
        )
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_all_requests_schedules(request):
    """My All Requests & Schedules"""
    try:
        emp = Employee.objects.get(user=request.user)
        
        # All requests
        requests = VacationRequest.objects.filter(employee=emp, is_deleted=False).order_by('-created_at')
        
        # All schedules
        schedules = VacationSchedule.objects.filter(employee=emp, is_deleted=False).order_by('-start_date')
        
        # Combine
        combined = []
        
        for req in requests:
            combined.append({
                'id': req.id,
                'type': 'request',
                'request_id': req.request_id,
                'vacation_type': req.vacation_type.name,
                'start_date': req.start_date.strftime('%Y-%m-%d'),
                'end_date': req.end_date.strftime('%Y-%m-%d'),
                'days': float(req.number_of_days),
                'status': req.get_status_display(),
                'created_at': req.created_at
            })
        
        for sch in schedules:
            combined.append({
                'id': sch.id,
                'type': 'schedule',
                'request_id': f'SCH{sch.id}',
                'vacation_type': sch.vacation_type.name,
                'start_date': sch.start_date.strftime('%Y-%m-%d'),
                'end_date': sch.end_date.strftime('%Y-%m-%d'),
                'days': float(sch.number_of_days),
                'status': sch.get_status_display(),
                'created_at': sch.created_at,
                'can_edit': sch.can_edit()
            })
        
        combined.sort(key=lambda x: x['created_at'], reverse=True)
        
        return Response({'records': combined})
    except Exception as e:
        return Response({'error': f'Employee profili tapılmadı: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)


# ==================== SETTINGS VIEWSETS ====================

class VacationSettingViewSet(viewsets.ModelViewSet):
    """Vacation Settings CRUD"""
    queryset = VacationSetting.objects.filter(is_deleted=False)
    serializer_class = VacationSettingSerializer
    permission_classes = [IsAuthenticated]
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)


class VacationTypeViewSet(viewsets.ModelViewSet):
    """Vacation Types CRUD"""
    queryset = VacationType.objects.filter(is_deleted=False)
    serializer_class = VacationTypeSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        return queryset


class NotificationTemplateViewSet(viewsets.ModelViewSet):
    """Notification Templates CRUD"""
    queryset = NotificationTemplate.objects.filter(is_deleted=False)
    serializer_class = NotificationTemplateSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        request_type = self.request.query_params.get('request_type')
        stage = self.request.query_params.get('stage')
        
        if request_type:
            queryset = queryset.filter(request_type=request_type)
        if stage:
            queryset = queryset.filter(stage=stage)
            
        return queryset


# ==================== BALANCE MANAGEMENT ====================
@swagger_auto_schema(
    method='post',
    operation_description="Excel faylı ilə vacation balanslarını toplu yükle",
    operation_summary="Bulk Upload Balances",
    tags=['Vacation - Balance Management'],
    consumes=['multipart/form-data'],
    manual_parameters=[
        openapi.Parameter(
            'file',
            openapi.IN_FORM,
            description="Excel faylı (.xlsx)",
            type=openapi.TYPE_FILE,
            required=True
        ),
        openapi.Parameter(
            'year',
            openapi.IN_FORM,
            description="İl (məsələn: 2025)",
            type=openapi.TYPE_INTEGER,
            required=True
        )
    ],
    responses={
        200: openapi.Response(
            description='Upload successful',
            examples={
                'application/json': {
                    'message': '10 uğurlu, 0 səhv',
                    'results': {
                        'successful': 10,
                        'failed': 0,
                        'errors': []
                    }
                }
            }
        )
    }
)
@api_view(['POST'])
@parser_classes([MultiPartParser, FormParser])
@permission_classes([IsAuthenticated])
def bulk_upload_balances(request):
    """Excel ilə balance upload et"""
    if 'file' not in request.FILES:
        return Response({'error': 'File yoxdur'}, status=status.HTTP_400_BAD_REQUEST)
    
    file = request.FILES['file']
    year = int(request.data.get('year', date.today().year))
    
    try:
        df = pd.read_excel(file)
        
        # Required columns check
        required_cols = ['employee_id', 'start_balance', 'yearly_balance']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            return Response({
                'error': f'Missing columns: {", ".join(missing_cols)}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        results = {'successful': 0, 'failed': 0, 'errors': []}
        
        for idx, row in df.iterrows():
            try:
                # Skip empty rows
                if pd.isna(row['employee_id']):
                    continue
                
                emp = Employee.objects.get(employee_id=str(row['employee_id']).strip())
                
                EmployeeVacationBalance.objects.update_or_create(
                    employee=emp,
                    year=year,
                    defaults={
                        'start_balance': float(row['start_balance']) if pd.notna(row['start_balance']) else 0,
                        'yearly_balance': float(row['yearly_balance']) if pd.notna(row['yearly_balance']) else 0,
                        'updated_by': request.user
                    }
                )
                
                results['successful'] += 1
                
            except Employee.DoesNotExist:
                results['errors'].append(f"Sətir {idx+2}: Employee ID '{row['employee_id']}' tapılmadı")
                results['failed'] += 1
            except Exception as e:
                results['errors'].append(f"Sətir {idx+2}: {str(e)}")
                results['failed'] += 1
        
        return Response({
            'message': f"{results['successful']} uğurlu, {results['failed']} səhv",
            'results': results
        })
    
    except Exception as e:
        return Response({'error': f'File processing error: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)


@swagger_auto_schema(
    method='get',
    operation_description="Excel template endir",
    operation_summary="Download Balance Template",
    tags=['Vacation - Balance Management'],
    responses={
        200: openapi.Response(
            description='Excel file',
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def download_balance_template(request):
    """Excel template endir"""
    wb = Workbook()
    ws = wb.active
    ws.title = "Vacation Balances Template"
    
    # Headers with descriptions
    ws.append(['employee_id', 'start_balance', 'yearly_balance'])
    ws.append(['EMP001', 0, 28])
    ws.append(['EMP002', 5, 28])
    ws.append(['EMP003', 2, 28])
    
    # Add instructions
    ws.append([])
    ws.append(['Instructions:'])
    ws.append(['employee_id: Employee ID from system'])
    ws.append(['start_balance: Remaining balance from previous year'])
    ws.append(['yearly_balance: Annual vacation allocation'])
    
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename=vacation_balance_template.xlsx'
    wb.save(response)
    
    return response


@swagger_auto_schema(
    method='get',
    operation_description="Employee balanslarını Excel formatında export et",
    operation_summary="Export Balances",
    tags=['Vacation - Balance Management'],
    manual_parameters=[
        openapi.Parameter(
            'year',
            openapi.IN_QUERY,
            description="İl (məsələn: 2025)",
            type=openapi.TYPE_INTEGER,
            required=False
        ),
        openapi.Parameter(
            'department_id',
            openapi.IN_QUERY,
            description="Department ID (optional)",
            type=openapi.TYPE_INTEGER,
            required=False
        )
    ],
    responses={
        200: openapi.Response(
            description='Excel file',
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def export_balances(request):
    """Balance export et"""
    year = int(request.GET.get('year', date.today().year))
    department_id = request.GET.get('department_id')
    
    try:
        balances = EmployeeVacationBalance.objects.filter(year=year, is_deleted=False)
        
        if department_id:
            balances = balances.filter(employee__department_id=department_id)
        
        balances = balances.select_related('employee', 'employee__department')
        
        wb = Workbook()
        ws = wb.active
        ws.title = f"Vacation Balances {year}"
        
        # Headers
        headers = [
            'Employee ID', 'Employee Name', 'Department', 'Business Function',
            'Start Balance', 'Yearly Balance', 'Total Balance', 'Used Days', 
            'Scheduled Days', 'Remaining Balance', 'Should Plan', 'Last Updated'
        ]
        ws.append(headers)
        
        # Data
        for balance in balances:
            ws.append([
                getattr(balance.employee, 'employee_id', ''),
                balance.employee.full_name,
                balance.employee.department.name if balance.employee.department else '',
                balance.employee.business_function.name if balance.employee.business_function else '',
                float(balance.start_balance),
                float(balance.yearly_balance),
                float(balance.total_balance),
                float(balance.used_days),
                float(balance.scheduled_days),
                float(balance.remaining_balance),
                float(balance.should_be_planned),
                balance.updated_at.strftime('%Y-%m-%d %H:%M') if balance.updated_at else ''
            ])
        
        # Auto-adjust column widths
        for col in ws.columns:
            max_length = 0
            column = col[0].column_letter
            for cell in col:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 50)
            ws.column_dimensions[column].width = adjusted_width
        
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename=vacation_balances_{year}.xlsx'
        wb.save(response)
        
        return response
        
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


# ==================== UTILITIES ====================
@swagger_auto_schema(
    method='post',
    operation_description="İki tarix arasında iş günlərinin sayını hesabla",
    operation_summary="İş Günlərini Hesabla",
    tags=['Vacation - Utilities'],
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=['start_date', 'end_date'],
        properties={
            'start_date': openapi.Schema(
                type=openapi.TYPE_STRING,
                format='date',
                description='Başlama tarixi',
                example='2025-10-15'
            ),
            'end_date': openapi.Schema(
                type=openapi.TYPE_STRING,
                format='date',
                description='Bitmə tarixi',
                example='2025-10-20'
            ),
        }
    ),
    responses={
        200: openapi.Response(
            description='Hesablama nəticəsi',
            examples={
                'application/json': {
                    'working_days': 4,
                    'return_date': '2025-10-21'
                }
            }
        )
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def calculate_working_days(request):
    """İş günlərini hesabla"""
    start = request.data.get('start_date')
    end = request.data.get('end_date')
    
    if not start or not end:
        return Response({'error': 'start_date və end_date mütləqdir'}, status=status.HTTP_400_BAD_REQUEST)
    
    settings = VacationSetting.get_active()
    if settings:
        try:
            start_dt = datetime.strptime(start, '%Y-%m-%d').date()
            end_dt = datetime.strptime(end, '%Y-%m-%d').date()
            
            if start_dt > end_dt:
                return Response({'error': 'start_date end_date-dən kiçik olmalıdır'}, status=status.HTTP_400_BAD_REQUEST)
            
            days = settings.calculate_working_days(start_dt, end_dt)
            return_date = settings.calculate_return_date(end_dt)
            
            return Response({
                'working_days': days,
                'return_date': return_date.strftime('%Y-%m-%d'),
                'total_calendar_days': (end_dt - start_dt).days + 1
            })
            
        except ValueError:
            return Response({'error': 'Tarix formatı səhvdir. YYYY-MM-DD istifadə edin'}, status=status.HTTP_400_BAD_REQUEST)
    
    return Response({'error': 'Settings tapılmadı'}, status=status.HTTP_404_NOT_FOUND)


@swagger_auto_schema(
    method='get',
    operation_description="Production calendar məlumatı",
    operation_summary="Production Calendar",
    tags=['Vacation - Utilities'],
    responses={
        200: openapi.Response(
            description='Calendar data',
            examples={
                'application/json': {
                    'non_working_days': ['2025-01-01', '2025-01-20'],
                    'allow_negative_balance': False,
                    'max_schedule_edits': 3,
                    'notification_days_before': 7,
                    'notification_frequency': 2
                }
            }
        )
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def production_calendar(request):
    """Production calendar məlumatı"""
    settings = VacationSetting.get_active()
    
    if settings:
        return Response({
            'non_working_days': settings.non_working_days,
            'allow_negative_balance': settings.allow_negative_balance,
            'max_schedule_edits': settings.max_schedule_edits,
            'notification_days_before': settings.notification_days_before,
            'notification_frequency': settings.notification_frequency,
            'default_hr_representative': {
                'id': settings.default_hr_representative.id,
                'name': settings.default_hr_representative.full_name
            } if settings.default_hr_representative else None
        })
    
    return Response({'error': 'Settings tapılmadı'}, status=status.HTTP_404_NOT_FOUND)


# ==================== REPORTS ====================
@swagger_auto_schema(
    method='get',
    operation_description="Department üzrə vacation reportu",
    operation_summary="Department Report",
    tags=['Vacation - Reports'],
    manual_parameters=[
        openapi.Parameter(
            'department_id',
            openapi.IN_QUERY,
            description="Department ID (optional)",
            type=openapi.TYPE_INTEGER,
            required=False
        ),
        openapi.Parameter(
            'year',
            openapi.IN_QUERY,
            description="İl (məsələn: 2025)",
            type=openapi.TYPE_INTEGER,
            required=False
        )
    ],
    responses={
        200: openapi.Response(
            description='Department report',
            examples={
                'application/json': {
                    'summary': {
                        'total_employees': 25,
                        'total_used_days': 150,
                        'total_scheduled_days': 75,
                        'average_usage': 6.0
                    },
                    'departments': []
                }
            }
        )
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def department_vacation_report(request):
    """Department vacation reportu"""
    department_id = request.GET.get('department_id')
    year = int(request.GET.get('year', date.today().year))
    
    try:
        balances = EmployeeVacationBalance.objects.filter(
            year=year, 
            is_deleted=False
        ).select_related('employee', 'employee__department')
        
        if department_id:
            balances = balances.filter(employee__department_id=department_id)
        
        dept_data = defaultdict(lambda: {
            'employee_count': 0,
            'total_used_days': 0,
            'total_scheduled_days': 0,
            'total_remaining_balance': 0,
            'total_balance': 0,
            'employees': []
        })
        
        for balance in balances:
            dept_name = balance.employee.department.name if balance.employee.department else 'No Department'
            dept_data[dept_name]['employee_count'] += 1
            dept_data[dept_name]['total_used_days'] += float(balance.used_days)
            dept_data[dept_name]['total_scheduled_days'] += float(balance.scheduled_days)
            dept_data[dept_name]['total_remaining_balance'] += float(balance.remaining_balance)
            dept_data[dept_name]['total_balance'] += float(balance.total_balance)
            dept_data[dept_name]['employees'].append({
                'id': balance.employee.id,
                'name': balance.employee.full_name,
                'employee_id': getattr(balance.employee, 'employee_id', ''),
                'used_days': float(balance.used_days),
                'scheduled_days': float(balance.scheduled_days),
                'remaining_balance': float(balance.remaining_balance),
                'total_balance': float(balance.total_balance)
            })
        
        # Calculate summary
        total_employees = sum(d['employee_count'] for d in dept_data.values())
        total_used_days = sum(d['total_used_days'] for d in dept_data.values())
        total_scheduled_days = sum(d['total_scheduled_days'] for d in dept_data.values())
        total_balance = sum(d['total_balance'] for d in dept_data.values())
        average_usage = total_used_days / total_employees if total_employees > 0 else 0
        
        departments_list = []
        for dept_name, data in dept_data.items():
            departments_list.append({
                'name': dept_name,
                'employee_count': data['employee_count'],
                'total_used_days': data['total_used_days'],
                'total_scheduled_days': data['total_scheduled_days'],
                'total_remaining_balance': data['total_remaining_balance'],
                'total_balance': data['total_balance'],
                'average_usage': round(data['total_used_days'] / data['employee_count'], 2) if data['employee_count'] > 0 else 0,
                'usage_percentage': round((data['total_used_days'] / data['total_balance']) * 100, 2) if data['total_balance'] > 0 else 0,
                'employees': data['employees']
            })
        
        # Sort by employee count
        departments_list.sort(key=lambda x: x['employee_count'], reverse=True)
        
        return Response({
            'summary': {
                'total_employees': total_employees,
                'total_used_days': total_used_days,
                'total_scheduled_days': total_scheduled_days,
                'total_balance': total_balance,
                'average_usage': round(average_usage, 2),
                'overall_usage_percentage': round((total_used_days / total_balance) * 100, 2) if total_balance > 0 else 0
            },
            'departments': departments_list,
            'year': year
        })
        
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


# ==================== STATISTICS ====================
@swagger_auto_schema(
    method='get',
    operation_description="Vacation statistikaları",
    operation_summary="Vacation Statistics",
    tags=['Vacation - Reports'],
    manual_parameters=[
        openapi.Parameter(
            'year',
            openapi.IN_QUERY,
            description="İl (məsələn: 2025)",
            type=openapi.TYPE_INTEGER,
            required=False
        )
    ],
    responses={
        200: openapi.Response(
            description='Statistics',
            examples={
                'application/json': {
                    'requests_by_status': {},
                    'schedules_by_month': {},
                    'top_vacation_types': {},
                    'balance_distribution': {}
                }
            }
        )
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def vacation_statistics(request):
    """Vacation statistikaları"""
    try:
        year = int(request.GET.get('year', date.today().year))
        
        # Requests by status
        requests_by_status = dict(
            VacationRequest.objects.filter(
                start_date__year=year,
                is_deleted=False
            ).values('status').annotate(count=Count('id')).values_list('status', 'count')
        )
        
        # Schedules by month
        schedules_by_month = dict(
            VacationSchedule.objects.filter(
                start_date__year=year,
                is_deleted=False
            ).extra(
                select={'month': "EXTRACT(month FROM start_date)"}
            ).values('month').annotate(count=Count('id')).values_list('month', 'count')
        )
        
        # Top vacation types
        top_vacation_types = dict(
            VacationRequest.objects.filter(
                start_date__year=year,
                is_deleted=False
            ).values('vacation_type__name').annotate(
                count=Count('id')
            ).order_by('-count')[:5].values_list('vacation_type__name', 'count')
        )
        
        # Balance distribution
        balances = EmployeeVacationBalance.objects.filter(year=year, is_deleted=False)
        balance_ranges = {
            'Negative': 0,
            '0-5 days': 0,
            '6-10 days': 0,
            '11-20 days': 0,
            '21+ days': 0
        }
        
        for balance in balances:
            remaining = float(balance.remaining_balance)
            if remaining < 0:
                balance_ranges['Negative'] += 1
            elif remaining <= 5:
                balance_ranges['0-5 days'] += 1
            elif remaining <= 10:
                balance_ranges['6-10 days'] += 1
            elif remaining <= 20:
                balance_ranges['11-20 days'] += 1
            else:
                balance_ranges['21+ days'] += 1
        
        # Monthly request trends
        monthly_requests = dict(
            VacationRequest.objects.filter(
                created_at__year=year,
                is_deleted=False
            ).extra(
                select={'month': "EXTRACT(month FROM created_at)"}
            ).values('month').annotate(count=Count('id')).values_list('month', 'count')
        )
        
        return Response({
            'requests_by_status': requests_by_status,
            'schedules_by_month': schedules_by_month,
            'top_vacation_types': top_vacation_types,
            'balance_distribution': balance_ranges,
            'monthly_requests': monthly_requests,
            'year': year
        })
        
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)