# api/vacation_views.py - Reorganized Tags for Clean Documentation

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
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Border, Side, Alignment
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo
from openpyxl.chart import BarChart, Reference
from datetime import datetime, date
import pandas as pd
from .role_models import EmployeeRole
from django.http import HttpResponse
from openpyxl.styles import PatternFill
from .vacation_permissions import (
    has_vacation_permission, 
    has_any_vacation_permission, 
    check_vacation_permission,
    get_user_vacation_permissions
)


good_fill = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
warning_fill = PatternFill(start_color="FFEB9C", end_color="FFEB9C", fill_type="solid")

@swagger_auto_schema(
    method='get',
    operation_description="İstifadəçinin bütün vacation icazələrini əldə et",
    operation_summary="Get My Permissions",
    tags=['Vacation'],
    responses={
        200: openapi.Response(
            description='User permissions',
            examples={
                'application/json': {
                    'is_admin': False,
                    'permissions': [
                        'vacation.dashboard.view_own',
                        'vacation.request.create_own'
                    ],
                    'roles': ['Employee - Vacation']
                }
            }
        )
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_vacation_permissions(request):
    """İstifadəçinin vacation permissions-larını göstər"""
    from .vacation_permissions import is_admin_user
    
    is_admin = is_admin_user(request.user)
    permissions = get_user_vacation_permissions(request.user)
    
    # User roles
    try:
        emp = Employee.objects.get(user=request.user, is_deleted=False)
        roles = list(EmployeeRole.objects.filter(
            employee=emp,
            is_active=True
        ).values_list('role__name', flat=True))
    except Employee.DoesNotExist:
        roles = []
    
    return Response({
        'is_admin': is_admin,
        'permissions_count': len(permissions),
        'permissions': permissions,
        'roles_count': len(roles),
        'roles': roles
    })

# ==================== DASHBOARD ====================
@swagger_auto_schema(
    method='get',
    operation_description="Dashboard məlumatları - 6 stat card və əsas statistika",
    operation_summary="Dashboard",
    tags=['Vacation'],
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
@has_vacation_permission('vacation.dashboard.view_own')
@permission_classes([IsAuthenticated])
def vacation_dashboard(request):
    """Dashboard - 6 stat card"""
    try:
        emp = Employee.objects.get(user=request.user)
        year = date.today().year
        
        balance, created = EmployeeVacationBalance.objects.get_or_create(
            employee=emp, 
            year=year,
           
        )
        
        # ✅ Refresh from DB to ensure latest values
        balance.refresh_from_db()
        
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
    except Employee.DoesNotExist:
        return Response({
            'error': 'Employee profili tapılmadı'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            'balance': {
                'total_balance': 0, 
                'yearly_balance': 0, 
                'used_days': 0, 
                'remaining_balance': 0, 
                'scheduled_days': 0, 
                'should_be_planned': 0
            }
        })


# ==================== PRODUCTION CALENDAR SETTINGS ====================

@swagger_auto_schema(
    method='put',
    operation_description="Production Calendar - qeyri-iş günlərini yenilə",
    operation_summary="Update Non-Working Days",
    tags=['Vacation - Settings'],
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=['non_working_days'],
        properties={
            'non_working_days': openapi.Schema(
                type=openapi.TYPE_ARRAY,
                items=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'date': openapi.Schema(type=openapi.TYPE_STRING, format='date'),
                        'name': openapi.Schema(type=openapi.TYPE_STRING, description='Holiday name')
                    }
                ),
                description='Qeyri-iş günləri massivi',
                example=[
                    {'date': '2025-01-01', 'name': 'New Year'},
                    {'date': '2025-01-20', 'name': 'Martyrs Day'},
                    {'date': '2025-03-08', 'name': 'Women Day'},
                    {'date': '2025-03-20', 'name': 'Novruz Bayram'}
                ]
            ),
        }
    ),
    responses={
        200: openapi.Response(
            description='Production calendar yeniləndi',
            examples={
                'application/json': {
                    'message': 'Production calendar uğurla yeniləndi',
                    'non_working_days': [
                        {'date': '2025-01-01', 'name': 'New Year'},
                        {'date': '2025-01-20', 'name': 'Martyrs Day'}
                    ]
                }
            }
        )
    }
)
@api_view(['PUT'])
@permission_classes([IsAuthenticated])
@has_vacation_permission('vacation.settings.update_production_calendar')
def update_production_calendar(request):
    """Production Calendar - qeyri-iş günlərini yenilə"""
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
        
        # Dictionary formatında saxla
        settings.non_working_days = non_working_days
        settings.updated_by = request.user
        settings.save()
        
        return Response({
            'message': 'Production calendar uğurla yeniləndi',
            'non_working_days': settings.non_working_days,
            'updated_at': settings.updated_at,
            'updated_by': request.user.get_full_name() or request.user.username
        })
        
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

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
                items=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'date': openapi.Schema(type=openapi.TYPE_STRING, format='date'),
                        'name': openapi.Schema(type=openapi.TYPE_STRING, description='Holiday name')
                    }
                ),
                description='Qeyri-iş günləri massivi',
                example=[
                    {'date': '2025-01-01', 'name': 'New Year'},
                    {'date': '2025-01-20', 'name': 'Martyrs Day'},
                    {'date': '2025-03-08', 'name': 'Women Day'},
                    {'date': '2025-03-20', 'name': 'Novruz Bayram'}
                ]
            ),
        }
    ),
    responses={
        200: openapi.Response(
            description='Production calendar yeniləndi',
            examples={
                'application/json': {
                    'message': 'Production calendar uğurla yeniləndi',
                    'non_working_days': [
                        {'date': '2025-01-01', 'name': 'New Year'},
                        {'date': '2025-01-20', 'name': 'Martyrs Day'}
                    ]
                }
            }
        )
    }
)
@api_view(['POST'])
@has_vacation_permission('vacation.settings.update_production_calendar')
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
        
        # Dictionary formatında saxla
        settings.non_working_days = non_working_days
        settings.updated_by = request.user
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
                    'non_working_days': [
                        {'date': '2025-01-01', 'name': 'New Year'},
                        {'date': '2025-01-20', 'name': 'Martyrs Day'}
                    ]
                }
            }
        )
    }
)
@api_view(['GET'])
@has_vacation_permission('vacation.settings.view')
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

# ==================== GENERAL VACATION SETTINGS  ====================
@swagger_auto_schema(
    method='put',
    operation_description="Vacation ümumi parametrləri - balans, edit limiti, bildirişlər yenilə",
    operation_summary="Update General Vacation Settings",
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
                    },
                    'updated_at': '2025-09-25T10:30:00Z',
                    'updated_by': 'John Doe'
                }
            }
        )
    }
)
@api_view(['PUT'])
@has_vacation_permission('vacation.settings.update_general')
@permission_classes([IsAuthenticated])
def update_general_vacation_settings(request):
    """Vacation ümumi parametrlərini yenilə"""
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
        
        settings.updated_by = request.user
        settings.save()
        
        return Response({
            'message': 'Vacation parametrləri uğurla yeniləndi',
            'settings': {
                'allow_negative_balance': settings.allow_negative_balance,
                'max_schedule_edits': settings.max_schedule_edits,
                'notification_days_before': settings.notification_days_before,
                'notification_frequency': settings.notification_frequency
            },
            'updated_at': settings.updated_at,
            'updated_by': request.user.get_full_name() or request.user.username
        })
        
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

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
@has_vacation_permission('vacation.settings.update_general')
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
        
        settings.updated_by = request.user
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
@has_vacation_permission('vacation.settings.view')
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


# ==================== HR REPRESENTATIVE SETTINGS  ====================
@swagger_auto_schema(
    method='put',
    operation_description="Default HR nümayəndəsini yenilə",
    operation_summary="Update Default HR Representative",
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
            description='Default HR yeniləndi',
            examples={
                'application/json': {
                    'message': 'Default HR nümayəndəsi uğurla yeniləndi',
                    'previous_hr': {
                        'id': 3,
                        'name': 'Previous HR Rep',
                        'department': 'HR'
                    },
                    'current_hr': {
                        'id': 5,
                        'name': 'Sarah Johnson',
                        'department': 'HR'
                    },
                    'updated_at': '2025-09-25T10:30:00Z',
                    'updated_by': 'Admin User'
                }
            }
        )
    }
)
@api_view(['PUT'])
@has_vacation_permission('vacation.settings.update_hr_representative')
@permission_classes([IsAuthenticated])
def update_default_hr_representative(request):
    """Default HR nümayəndəsini yenilə"""
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
        
        # Əvvəlki HR-ı saxla
        previous_hr = settings.default_hr_representative
        previous_hr_info = None
        if previous_hr:
            previous_hr_info = {
                'id': previous_hr.id,
                'name': previous_hr.full_name,
                'department': previous_hr.department.name if previous_hr.department else ''
            }
        
        # Yeni HR təyin et
        settings.default_hr_representative = hr_employee
        settings.updated_by = request.user
        settings.save()
        
        return Response({
            'message': 'Default HR nümayəndəsi uğurla yeniləndi',
            'previous_hr': previous_hr_info,
            'current_hr': {
                'id': hr_employee.id,
                'name': hr_employee.full_name,
                'department': hr_employee.department.name if hr_employee.department else ''
            },
            'updated_at': settings.updated_at,
            'updated_by': request.user.get_full_name() or request.user.username
        })
        
    except Employee.DoesNotExist:
        return Response({
            'error': 'HR nümayəndəsi tapılmadı'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

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
@has_vacation_permission('vacation.settings.update_hr_representative')
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
        settings.updated_by = request.user
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
            description='HR nümayəndələri siyahısı'
        )
    }
)
@api_view(['GET'])
@has_vacation_permission('vacation.settings.view')
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
                'email': emp.user.email if emp.user else '',
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

# ==================== BULK BALANCE UPDATE - PUT ====================
@swagger_auto_schema(
    method='put',
    operation_description="Mövcud employee balanslarını fərdi yenilə",
    operation_summary="Update Individual Balance",
    tags=['Vacation - Settings'],
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=['employee_id', 'year'],
        properties={
            'employee_id': openapi.Schema(
                type=openapi.TYPE_INTEGER,
                description='Employee ID',
                example=15
            ),
            'year': openapi.Schema(
                type=openapi.TYPE_INTEGER,
                description='İl (məsələn: 2025)',
                example=2025
            ),
            'start_balance': openapi.Schema(
                type=openapi.TYPE_NUMBER,
                description='Əvvəlki ildən qalan balans',
                example=5.0
            ),
            'yearly_balance': openapi.Schema(
                type=openapi.TYPE_NUMBER,
                description='İllik məzuniyyət balansı',
                example=28.0
            ),
        }
    ),
    responses={
        200: openapi.Response(
            description='Balans yeniləndi',
            examples={
                'application/json': {
                    'message': 'Employee balansı uğurla yeniləndi',
                    'employee': {
                        'id': 15,
                        'name': 'John Doe',
                        'employee_id': 'EMP015'
                    },
                    'balance': {
                        'year': 2025,
                        'start_balance': 5.0,
                        'yearly_balance': 28.0,
                        'total_balance': 33.0,
                        'used_days': 0.0,
                        'scheduled_days': 0.0,
                        'remaining_balance': 33.0
                    },
                    'updated_at': '2025-09-25T10:30:00Z',
                    'updated_by': 'HR Manager'
                }
            }
        )
    }
)
@api_view(['PUT'])
@has_vacation_permission('vacation.balance.update')
@permission_classes([IsAuthenticated])
def update_individual_balance(request):
    """Fərdi employee balansını yenilə"""
    try:
        # Validate required fields
        required_fields = ['employee_id', 'year']
        for field in required_fields:
            if field not in request.data:
                return Response({'error': f'{field} mütləqdir'}, status=status.HTTP_400_BAD_REQUEST)
        
        employee_id = request.data['employee_id']
        year = int(request.data['year'])
        
        # Employee tap
        try:
            employee = Employee.objects.get(id=employee_id, is_deleted=False)
        except Employee.DoesNotExist:
            return Response({'error': 'Employee tapılmadı'}, status=status.HTTP_404_NOT_FOUND)
        
        # Balance tap və ya yarat
        balance, created = EmployeeVacationBalance.objects.get_or_create(
            employee=employee,
            year=year,
            defaults={
                'start_balance': 0,
                'yearly_balance': 28,  # Default
                'updated_by': request.user
            }
        )
        
        # Əvvəlki məlumatları saxla
        previous_data = {
            'start_balance': float(balance.start_balance),
            'yearly_balance': float(balance.yearly_balance),
            'total_balance': float(balance.total_balance)
        }
        
        # Yenilə (əgər göndərilmişsə)
        if 'start_balance' in request.data:
            balance.start_balance = float(request.data['start_balance'])
        
        if 'yearly_balance' in request.data:
            balance.yearly_balance = float(request.data['yearly_balance'])
        
        balance.updated_by = request.user
        balance.save()
        
        return Response({
            'message': 'Employee balansı uğurla yeniləndi',
            'action': 'created' if created else 'updated',
            'employee': {
                'id': employee.id,
                'name': employee.full_name,
                'employee_id': getattr(employee, 'employee_id', '')
            },
            'previous_data': None if created else previous_data,
            'current_balance': {
                'year': balance.year,
                'start_balance': float(balance.start_balance),
                'yearly_balance': float(balance.yearly_balance),
                'total_balance': float(balance.total_balance),
                'used_days': float(balance.used_days),
                'scheduled_days': float(balance.scheduled_days),
                'remaining_balance': float(balance.remaining_balance)
            },
            'updated_at': balance.updated_at,
            'updated_by': request.user.get_full_name() or request.user.username
        })
        
    except ValueError as e:
        return Response({'error': f'Məlumat formatı səhvdir: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


# ==================== RESET BALANCE - PUT ====================
@swagger_auto_schema(
    method='put',
    operation_description="Employee balansını sıfırla (used_days və scheduled_days-ı 0 et)",
    operation_summary="Reset Employee Balance",
    tags=['Vacation - Settings'],
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=['employee_id', 'year'],
        properties={
            'employee_id': openapi.Schema(
                type=openapi.TYPE_INTEGER,
                description='Employee ID',
                example=15
            ),
            'year': openapi.Schema(
                type=openapi.TYPE_INTEGER,
                description='İl (məsələn: 2025)',
                example=2025
            ),
            'reset_type': openapi.Schema(
                type=openapi.TYPE_STRING,
                enum=['used_only', 'scheduled_only', 'both'],
                description='Nəyi sıfırlamaq: used_only, scheduled_only, both',
                example='both'
            ),
        }
    ),
    responses={
        200: openapi.Response(
            description='Balans sıfırlandı',
            examples={
                'application/json': {
                    'message': 'Employee balansı sıfırlandı',
                    'employee': {
                        'id': 15,
                        'name': 'John Doe'
                    },
                    'reset_details': {
                        'previous_used_days': 10.0,
                        'previous_scheduled_days': 5.0,
                        'current_used_days': 0.0,
                        'current_scheduled_days': 0.0,
                        'reset_type': 'both'
                    }
                }
            }
        )
    }
)
@api_view(['PUT'])
@has_vacation_permission('vacation.balance.reset')
@permission_classes([IsAuthenticated])
def reset_employee_balance(request):
    """Employee balansını sıfırla"""
    try:
        employee_id = request.data.get('employee_id')
        year = request.data.get('year')
        reset_type = request.data.get('reset_type', 'both')
        
        if not employee_id or not year:
            return Response({'error': 'employee_id və year mütləqdir'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Employee və balance tap
        try:
            employee = Employee.objects.get(id=employee_id, is_deleted=False)
            balance = EmployeeVacationBalance.objects.get(employee=employee, year=year)
        except Employee.DoesNotExist:
            return Response({'error': 'Employee tapılmadı'}, status=status.HTTP_404_NOT_FOUND)
        except EmployeeVacationBalance.DoesNotExist:
            return Response({'error': f'{year} ili üçün balans tapılmadı'}, status=status.HTTP_404_NOT_FOUND)
        
        # Əvvəlki məlumatları saxla
        previous_used = float(balance.used_days)
        previous_scheduled = float(balance.scheduled_days)
        
        # Reset et
        if reset_type in ['used_only', 'both']:
            balance.used_days = 0
        
        if reset_type in ['scheduled_only', 'both']:
            balance.scheduled_days = 0
        
        balance.updated_by = request.user
        balance.save()
        
        return Response({
            'message': f'Employee balansı sıfırlandı ({reset_type})',
            'employee': {
                'id': employee.id,
                'name': employee.full_name,
                'employee_id': getattr(employee, 'employee_id', '')
            },
            'reset_details': {
                'previous_used_days': previous_used,
                'previous_scheduled_days': previous_scheduled,
                'current_used_days': float(balance.used_days),
                'current_scheduled_days': float(balance.scheduled_days),
                'reset_type': reset_type
            },
            'current_balance': {
                'total_balance': float(balance.total_balance),
                'remaining_balance': float(balance.remaining_balance)
            },
            'updated_at': balance.updated_at,
            'updated_by': request.user.get_full_name() or request.user.username
        })
        
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

# ==================== BALANCE MANAGEMENT ====================
@swagger_auto_schema(
    method='post',
    operation_description="Excel faylı ilə vacation balanslarını toplu yükle",
    operation_summary="Bulk Upload Balances",
    tags=['Vacation - Settings'],
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
@has_vacation_permission('vacation.balance.bulk_upload')
def bulk_upload_balances(request):
    """Excel ilə balance upload et"""
    if 'file' not in request.FILES:
        return Response({'error': 'File yoxdur'}, status=status.HTTP_400_BAD_REQUEST)
    
    file = request.FILES['file']
    year = int(request.data.get('year', date.today().year))
    
    try:
        # Read Excel - header at row 5 (index 4), skip row 6 (descriptions)
        # Only read up to row 100 to avoid footer text
        df = pd.read_excel(file, header=4, skiprows=[5], nrows=100)
        
        # Strip whitespace and normalize column names
        df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_')
        
        # Required columns check
        required_cols = ['employee_id', 'start_balance', 'yearly_balance']
        missing_cols = [col for col in required_cols if col not in df.columns]
        
        if missing_cols:
            return Response({
                'error': f'Missing columns: {", ".join(missing_cols)}',
                'found_columns': list(df.columns),
                'hint': 'Please use the downloaded template without modifications'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        results = {'successful': 0, 'failed': 0, 'errors': [], 'skipped': 0}
        
        for idx, row in df.iterrows():
            try:
                # Get employee_id and check if it's valid
                emp_id_raw = row.get('employee_id')
                
                # Skip if empty, NaN, or not a valid employee ID format
                if pd.isna(emp_id_raw):
                    results['skipped'] += 1
                    continue
                
                emp_id = str(emp_id_raw).strip()
                
                # Skip empty strings or very long strings (likely footer text)
                if not emp_id or len(emp_id) > 20:
                    results['skipped'] += 1
                    continue
                
                # Find employee
                emp = Employee.objects.get(
                    employee_id=emp_id, 
                    is_deleted=False
                )
                
                start_bal = float(row['start_balance']) if pd.notna(row['start_balance']) else 0
                yearly_bal = float(row['yearly_balance']) if pd.notna(row['yearly_balance']) else 0
                
                EmployeeVacationBalance.objects.update_or_create(
                    employee=emp,
                    year=year,
                    defaults={
                        'start_balance': start_bal,
                        'yearly_balance': yearly_bal,
                        'updated_by': request.user
                    }
                )
                
                results['successful'] += 1
                
            except Employee.DoesNotExist:
                results['errors'].append(f"Employee ID '{row['employee_id']}' sistemdə tapılmadı")
                results['failed'] += 1
            except ValueError as e:
                results['errors'].append(f"Employee ID '{row['employee_id']}': Rəqəm formatı səhvdir")
                results['failed'] += 1
            except Exception as e:
                results['errors'].append(f"Employee ID '{row['employee_id']}': {str(e)}")
                results['failed'] += 1
        
        # Return success only if at least one row was processed
        if results['successful'] == 0 and results['failed'] == 0:
            return Response({
                'error': 'Faylda heç bir məlumat tapılmadı',
                'hint': 'Please add employee data starting from row 7'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        return Response({
            'message': f"{results['successful']} uğurlu, {results['failed']} səhv",
            'results': results
        })
    
    except Exception as e:
        return Response({
            'error': f'File processing error: {str(e)}',
            'hint': 'Make sure you are using the latest template file'
        }, status=status.HTTP_400_BAD_REQUEST)
        
@swagger_auto_schema(
    method='get',
    operation_description="Excel template endir",
    operation_summary="Download Balance Template",
    tags=['Vacation - Settings'],
    responses={
        200: openapi.Response(
            description='Excel file',
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
@has_vacation_permission('vacation.balance.view_all')
def download_balance_template(request):
    """Enhanced Excel template with improved design"""
    wb = Workbook()
    ws = wb.active
    ws.title = "Balance Template"

    ws.sheet_view.showGridLines = False

    # Define styles
    header_fill = PatternFill(start_color="305496", end_color="305496", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True, size=12)
    title_font = Font(size=16, bold=True, color="305496")
    desc_font = Font(size=9, italic=True)
    border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )

    # Title
    ws.merge_cells('A1:C2')
    ws['A1'] = 'VACATION BALANCE TEMPLATE'
    ws['A1'].font = title_font
    ws['A1'].alignment = Alignment(horizontal='center', vertical='center')

    # Date info
    ws['A3'] = f'Generated on: {datetime.now().strftime("%B %d, %Y - %H:%M")}'
    ws['A3'].font = Font(size=10, italic=True, color="808080")

    # Column headers
    headers = ['employee_id', 'start_balance', 'yearly_balance']
    descriptions = [
        'Employee ID from system',
        'Remaining balance from previous year',
        'Annual vacation allocation',
    ]

    start_row = 5
    for col, (header, desc) in enumerate(zip(headers, descriptions), 1):
        # Header
        cell = ws.cell(row=start_row, column=col, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.border = border
        cell.alignment = Alignment(horizontal='center', vertical='center')
        # Description
        desc_cell = ws.cell(row=start_row + 1, column=col, value=desc)
        desc_cell.font = desc_font
        desc_cell.alignment = Alignment(horizontal='center', wrap_text=True)
        desc_cell.border = border

    # Add instruction in a separate area (far from data area)
    instruction_row = 15  # Much further down
    ws.merge_cells(f'A{instruction_row}:C{instruction_row}')
    ws[f'A{instruction_row}'] = "Instructions: Fill employee data starting from row 7. Do not modify this template structure."
    ws[f'A{instruction_row}'].font = Font(size=9, italic=True, color="808080")
    ws[f'A{instruction_row}'].alignment = Alignment(horizontal='left')

    # Auto-adjust column widths
    for col in range(1, len(headers) + 1):
        ws.column_dimensions[get_column_letter(col)].width = 25

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename=vacation_balance_template.xlsx'
    wb.save(response)
    return response

@swagger_auto_schema(
    method='get',
    operation_description="Employee balanslarını Excel formatında export et",
    operation_summary="Export Balances",
    tags=['Vacation - Settings'],
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
@has_vacation_permission('vacation.balance.export')
@permission_classes([IsAuthenticated])
def export_balances(request):
    """Enhanced balance export with statistics and charts"""
    year = int(request.GET.get('year', date.today().year))
    department_id = request.GET.get('department_id')
    include_charts = request.GET.get('include_charts', 'true').lower() == 'true'
    
    try:
        balances = EmployeeVacationBalance.objects.filter(year=year, is_deleted=False)
        
        if department_id:
            balances = balances.filter(employee__department_id=department_id)
        
        balances = balances.select_related('employee', 'employee__department', 'employee__business_function')
        
        wb = Workbook()
        
        # Summary sheet
        ws_summary = wb.active
        ws_summary.title = "Summary"
        
        # Define styles
        title_font = Font(size=16, bold=True, color="2B4C7E")
        header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
        header_font = Font(color="FFFFFF", bold=True, size=11)
        stat_fill = PatternFill(start_color="E6F3FF", end_color="E6F3FF", fill_type="solid")
        warning_fill = PatternFill(start_color="FFE6E6", end_color="FFE6E6", fill_type="solid")
        good_fill = PatternFill(start_color="E6FFE6", end_color="E6FFE6", fill_type="solid")
        
        # Title
        ws_summary['A1'] = f'VACATION BALANCE SUMMARY - {year}'
        ws_summary['A1'].font = title_font
        ws_summary.merge_cells('A1:D1')
        
        # Statistics
        total_employees = balances.count()
        total_balance = sum(float(b.total_balance) for b in balances)
        total_used = sum(float(b.used_days) for b in balances)
        total_scheduled = sum(float(b.scheduled_days) for b in balances)
        total_remaining = sum(float(b.remaining_balance) for b in balances)
        
        negative_balance_count = balances.filter(used_days__gt=models.F('start_balance') + models.F('yearly_balance')).count()
        low_balance_count = balances.filter(
            used_days__gt=(models.F('start_balance') + models.F('yearly_balance')) - 5
        ).count()
        
        stats = [
            ['Statistic', 'Value', 'Status'],
            ['Total Employees', total_employees, ''],
            ['Total Balance (Days)', f'{total_balance:.1f}', ''],
            ['Total Used (Days)', f'{total_used:.1f}', ''],
            ['Total Scheduled (Days)', f'{total_scheduled:.1f}', ''],
            ['Total Remaining (Days)', f'{total_remaining:.1f}', ''],
            ['Negative Balance Employees', negative_balance_count, 'Warning' if negative_balance_count > 0 else 'OK'],
            ['Low Balance Employees (<5 days)', low_balance_count, 'Warning' if low_balance_count > 0 else 'OK'],
            ['Average Balance per Employee', f'{total_balance/total_employees:.1f}' if total_employees > 0 else '0', ''],
            ['Balance Utilization %', f'{(total_used/total_balance)*100:.1f}%' if total_balance > 0 else '0%', '']
        ]
        
        for row, (stat, value, status) in enumerate(stats, 3):
            ws_summary[f'A{row}'] = stat
            ws_summary[f'B{row}'] = value
            ws_summary[f'C{row}'] = status
            
            if row == 3:  # Header row
                for col in ['A', 'B', 'C']:
                    cell = ws_summary[f'{col}{row}']
                    cell.fill = header_fill
                    cell.font = header_font
            else:
                if status == 'Warning':
                    for col in ['A', 'B', 'C']:
                        ws_summary[f'{col}{row}'].fill = warning_fill
                elif status == 'OK':
                    for col in ['A', 'B', 'C']:
                        ws_summary[f'{col}{row}'].fill = good_fill
                else:
                    for col in ['A', 'B']:
                        ws_summary[f'{col}{row}'].fill = stat_fill
        
        # Detailed data sheet
        ws_data = wb.create_sheet("Detailed Data")
        
        # Headers for detailed sheet
        detailed_headers = [
            'Employee ID', 'Employee Name', 'Department', 'Business Function',
            'Start Balance', 'Yearly Balance', 'Total Balance', 'Used Days', 
            'Scheduled Days', 'Remaining Balance', 'Should Plan', 'Utilization %',
            'Status', 'Last Updated'
        ]
        
        for col, header in enumerate(detailed_headers, 1):
            cell = ws_data.cell(row=1, column=col, value=header)
            cell.fill = header_fill
            cell.font = header_font
        
        # Data rows
        for row, balance in enumerate(balances, 2):
            utilization = (float(balance.used_days) / float(balance.total_balance)) * 100 if balance.total_balance > 0 else 0
            
            # Determine status
            if float(balance.remaining_balance) < 0:
                status = "Over-utilized"
                status_fill = warning_fill
            elif float(balance.remaining_balance) < 5:
                status = "Low Balance"
                status_fill = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")
            else:
                status = "Normal"
                status_fill = good_fill
            
            data = [
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
                f'{utilization:.1f}%',
                status,
                balance.updated_at.strftime('%Y-%m-%d') if balance.updated_at else ''
            ]
            
            for col, value in enumerate(data, 1):
                cell = ws_data.cell(row=row, column=col, value=value)
                if col == 13:  # Status column
                    cell.fill = status_fill
                if col in [5, 6, 7, 8, 9, 10, 11]:  # Numeric columns
                    cell.alignment = Alignment(horizontal='right')
        
        # Create table
        table_range = f"A1:{get_column_letter(len(detailed_headers))}{len(balances) + 1}"
        table = Table(displayName="BalanceTable", ref=table_range)
        style = TableStyleInfo(name="TableStyleMedium2", showFirstColumn=False,
                              showLastColumn=False, showRowStripes=True, showColumnStripes=False)
        table.tableStyleInfo = style
        ws_data.add_table(table)
        
        # Department breakdown sheet
        ws_dept = wb.create_sheet("Department Breakdown")
        
        # Department statistics
        dept_stats = balances.values('employee__department__name').annotate(
            employee_count=Count('employee'),
            total_balance=Sum('yearly_balance'),
            total_used=Sum('used_days'),
            total_remaining=Sum(models.F('start_balance') + models.F('yearly_balance') - models.F('used_days') - models.F('scheduled_days'))
        ).order_by('-total_balance')
        
        dept_headers = ['Department', 'Employees', 'Total Balance', 'Used Days', 'Remaining', 'Utilization %']
        for col, header in enumerate(dept_headers, 1):
            cell = ws_dept.cell(row=1, column=col, value=header)
            cell.fill = header_fill
            cell.font = header_font
        
        for row, dept in enumerate(dept_stats, 2):
            utilization = (dept['total_used'] / dept['total_balance']) * 100 if dept['total_balance'] > 0 else 0
            data = [
                dept['employee__department__name'] or 'No Department',
                dept['employee_count'],
                float(dept['total_balance']),
                float(dept['total_used']),
                float(dept['total_remaining']),
                f'{utilization:.1f}%'
            ]
            
            for col, value in enumerate(data, 1):
                ws_dept.cell(row=row, column=col, value=value)
        
        # Add chart if requested
        if include_charts and dept_stats.exists():
            chart = BarChart()
            chart.type = "col"
            chart.style = 10
            chart.title = "Balance by Department"
            chart.y_axis.title = 'Days'
            chart.x_axis.title = 'Department'
            
            data = Reference(ws_dept, min_col=3, min_row=1, max_row=len(dept_stats) + 1, max_col=5)
            cats = Reference(ws_dept, min_col=1, min_row=2, max_row=len(dept_stats) + 1)
            chart.add_data(data, titles_from_data=True)
            chart.set_categories(cats)
            
            ws_dept.add_chart(chart, "H2")
        
        # Auto-adjust all column widths
        for ws_current in [ws_summary, ws_data, ws_dept]:
            for column in ws_current.columns:
                max_length = 0
                column_letter = get_column_letter(column[0].column)
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 50)
                ws_current.column_dimensions[column_letter].width = adjusted_width
        
        # Generate filename
        dept_name = ""
        if department_id:
            try:
                from .models import Department
                dept = Department.objects.get(id=department_id)
                dept_name = f"_{dept.name.replace(' ', '_')}"
            except:
                pass
        
        filename = f'vacation_balances_enhanced_{year}{dept_name}_{date.today().strftime("%Y%m%d")}.xlsx'
        
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename={filename}'
        wb.save(response)
        
        return response
        
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)



# ==================== REQUEST IMMEDIATE ====================
@swagger_auto_schema(
    method='post',
    operation_description="Request Immediately yaratmaq",
    operation_summary="Create Immediate Request",
    tags=['Vacation'],
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
@has_vacation_permission('vacation.request.create_own')
@permission_classes([IsAuthenticated])
def create_immediate_request(request):
    """Request Immediately yarat"""
    serializer = VacationRequestCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    data = serializer.validated_data
    
    try:
        requester_emp = Employee.objects.get(
            user__email=request.user.email, 
            is_deleted=False
        )
       
        # Balance yoxla
        settings = VacationSetting.get_active()
        year = date.today().year
        
        # Employee seç
        if data['requester_type'] == 'for_me':
            employee = requester_emp
        else:
            if data.get('employee_id'):
                employee = Employee.objects.get(id=data['employee_id'])
                if employee.line_manager != requester_emp:
                    return Response({
                        'error': 'Bu işçi sizin tabeliyinizdə deyil'
                    }, status=status.HTTP_403_FORBIDDEN)
            else:
                manual_data = data.get('employee_manual', {})
                if not manual_data.get('name'):
                    return Response({
                        'error': 'Employee adı mütləqdir'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                employee = Employee.objects.create(
                    full_name=manual_data.get('name', ''),
                    phone=manual_data.get('phone', ''),
                    line_manager=requester_emp,
                    created_by=request.user
                )
        
        # Balance tap və ya yarat
        balance, created = EmployeeVacationBalance.objects.get_or_create(
            employee=employee,
            year=year,
            defaults={
                'start_balance': 0,
                'yearly_balance': 28,
                'updated_by': request.user
            }
        )
        
        # Calculate working days
        working_days = 0
        if settings:
            working_days = settings.calculate_working_days(
                data['start_date'], 
                data['end_date']
            )
        
        # Negative balance yoxla
        if settings and not settings.allow_negative_balance:
            if working_days > balance.remaining_balance:
                return Response({
                    'error': f'Qeyri-kafi balans. Sizin {balance.remaining_balance} gün qalıb. Mənfi balansa icazə yoxdur.',
                    'available_balance': float(balance.remaining_balance),
                    'requested_days': working_days
                }, status=status.HTTP_400_BAD_REQUEST)
        
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
            
            # Refresh balance to get updated values
            balance.refresh_from_db()
            
            return Response({
                'message': 'Request yaradıldı və təsdiqə göndərildi',
                'request': VacationRequestDetailSerializer(vac_req).data,
                'balance': {
                    'total_balance': float(balance.total_balance),
                    'yearly_balance': float(balance.yearly_balance),
                    'used_days': float(balance.used_days),
                    'remaining_balance': float(balance.remaining_balance),
                    'scheduled_days': float(balance.scheduled_days),
                    'should_be_planned': float(balance.should_be_planned)
                }
            }, status=status.HTTP_201_CREATED)
    
    except Employee.DoesNotExist:
        return Response({
            'error': 'Employee tapılmadı'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)

# ==================== CREATE SCHEDULE ====================
@swagger_auto_schema(
    method='post',
    operation_description="Vacation Schedule yaratmaq (təsdiq tələb etmir)",
    operation_summary="Create Schedule",
    tags=['Vacation'],
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
@has_vacation_permission('vacation.schedule.create_own')
@permission_classes([IsAuthenticated])
def create_schedule(request):
    """Schedule yarat"""
    serializer = VacationScheduleCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    data = serializer.validated_data
    
    try:
        requester_emp = Employee.objects.get(user=request.user)
        year = date.today().year
        
        if data['requester_type'] == 'for_me':
            employee = requester_emp
        else:
            if data.get('employee_id'):
                employee = Employee.objects.get(id=data['employee_id'])
                if employee.line_manager != requester_emp:
                    return Response({
                        'error': 'Bu işçi sizin tabeliyinizdə deyil'
                    }, status=status.HTTP_403_FORBIDDEN)
            else:
                manual_data = data.get('employee_manual', {})
                if not manual_data.get('name'):
                    return Response({
                        'error': 'Employee adı mütləqdir'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                employee = Employee.objects.create(
                    full_name=manual_data.get('name', ''),
                    phone=manual_data.get('phone', ''),
                    line_manager=requester_emp,
                    created_by=request.user
                )
        
        # Balance tap və ya yarat
        balance, created = EmployeeVacationBalance.objects.get_or_create(
            employee=employee,
            year=year,
            defaults={
                'start_balance': 0,
                'yearly_balance': 28,
                'updated_by': request.user
            }
        )
        
        # Calculate working days
        settings = VacationSetting.get_active()
        working_days = 0
        if settings:
            working_days = settings.calculate_working_days(
                data['start_date'], 
                data['end_date']
            )
        
        # Balance yoxla (schedule üçün scheduled_days artır)
        if settings and not settings.allow_negative_balance:
            total_planned = balance.scheduled_days + working_days
            if total_planned > balance.total_balance:
                return Response({
                    'error': f'Qeyri-kafi balans. Toplam planlaşdırılmış ({total_planned}) günlər balansı ({balance.total_balance}) keçir.',
                    'available_balance': float(balance.remaining_balance),
                    'requested_days': working_days,
                    'current_scheduled': float(balance.scheduled_days)
                }, status=status.HTTP_400_BAD_REQUEST)
        
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
        
        with transaction.atomic():
            schedule = VacationSchedule.objects.create(
                employee=employee,
                vacation_type_id=data['vacation_type_id'],
                start_date=data['start_date'],
                end_date=data['end_date'],
                comment=data.get('comment', ''),
                created_by=request.user
            )
            
            # Refresh balance
            balance.refresh_from_db()
            
            return Response({
                'message': 'Schedule yaradıldı',
                'schedule': VacationScheduleSerializer(schedule).data,
                'conflicts': VacationScheduleSerializer(conflicts, many=True).data,
                'balance': {
                    'total_balance': float(balance.total_balance),
                    'yearly_balance': float(balance.yearly_balance),
                    'used_days': float(balance.used_days),
                    'remaining_balance': float(balance.remaining_balance),
                    'scheduled_days': float(balance.scheduled_days),
                    'should_be_planned': float(balance.should_be_planned)
                }
            }, status=status.HTTP_201_CREATED)
    
    except Employee.DoesNotExist:
        return Response({
            'error': 'Employee tapılmadı'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)

# ==================== MY SCHEDULE TABS ====================
@swagger_auto_schema(
    method='get',
    operation_description="Schedule tabları - upcoming, peers, all",
    operation_summary="My Schedule Tabs",
    tags=['Vacation'],
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
@has_vacation_permission('vacation.schedule.view_own')
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
    except Employee.DoesNotExist:
        return Response({'error': 'Employee profili tapılmadı'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


# ==================== REGISTER SCHEDULE ====================
@swagger_auto_schema(
    method='post',
    operation_description="Schedule-i registered et",
    operation_summary="Register Schedule",
    tags=['Vacation'],
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
                    'schedule': {},
                    'updated_balance': {
                        'total_balance': 50.0,
                        'used_days': 30.0,
                        'scheduled_days': 0.0,
                        'remaining_balance': 20.0
                    }
                }
            }
        )
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
@has_vacation_permission('vacation.schedule.register')
def register_schedule(request, pk):
    """Schedule-i registered et"""
    try:
        schedule = VacationSchedule.objects.get(pk=pk, is_deleted=False)
        
        # Register et
        schedule.register_as_taken(request.user)
        
        # Balance-ı yenidən yüklə
        balance = EmployeeVacationBalance.objects.get(
            employee=schedule.employee,
            year=schedule.start_date.year
        )
        
        return Response({
            'message': 'Schedule registered edildi',
            'schedule': VacationScheduleSerializer(schedule).data,
            'updated_balance': {
                'total_balance': float(balance.total_balance),
                'yearly_balance': float(balance.yearly_balance),
                'used_days': float(balance.used_days),
                'scheduled_days': float(balance.scheduled_days),
                'remaining_balance': float(balance.remaining_balance),
                'should_be_planned': float(balance.should_be_planned)
            }
        })
    except VacationSchedule.DoesNotExist:
        return Response({'error': 'Schedule tapılmadı'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

# ==================== EDIT SCHEDULE ====================
@swagger_auto_schema(
    method='put',
    operation_description="Schedule-i edit et",
    operation_summary="Edit Schedule",
    tags=['Vacation'],
    manual_parameters=[
        openapi.Parameter(
            'id',
            openapi.IN_PATH,
            description="Schedule ID",
            type=openapi.TYPE_INTEGER,
            required=True
        )
    ],
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'vacation_type_id': openapi.Schema(
                type=openapi.TYPE_INTEGER,
                description='Vacation növü ID',
                example=1
            ),
            'start_date': openapi.Schema(
                type=openapi.TYPE_STRING,
                format='date',
                description='Başlama tarixi (YYYY-MM-DD)',
                example='2025-11-10'
            ),
            'end_date': openapi.Schema(
                type=openapi.TYPE_STRING,
                format='date',
                description='Bitmə tarixi (YYYY-MM-DD)',
                example='2025-11-15'
            ),
            'comment': openapi.Schema(
                type=openapi.TYPE_STRING,
                description='Şərh (optional)',
                example='Dəyişiklik edildi'
            )
        }
    ),
    responses={
        200: openapi.Response(
            description='Schedule yeniləndi',
            examples={
                'application/json': {
                    'message': 'Schedule yeniləndi',
                    'schedule': {
                        'id': 1,
                        'vacation_type_name': 'Annual Leave',
                        'start_date': '2025-11-10',
                        'end_date': '2025-11-15',
                        'number_of_days': 4,
                        'edit_count': 1,
                        'can_edit': True
                    }
                }
            }
        ),
        400: openapi.Response(description='Validation error'),
        403: openapi.Response(description='Permission denied'),
        404: openapi.Response(description='Schedule tapılmadı')
    }
)
@api_view(['PUT'])
@has_vacation_permission('vacation.schedule.update_own')
@permission_classes([IsAuthenticated])
def edit_schedule(request, pk):
    """Schedule-i edit et"""
    try:
        schedule = VacationSchedule.objects.get(pk=pk, is_deleted=False)
        emp = Employee.objects.get(user=request.user)
        
        # Yalnız schedule-in sahibi edit edə bilər
        if schedule.employee != emp:
            return Response({
                'error': 'Bu schedule-i edit etmək hüququnuz yoxdur'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Edit limiti yoxla
        if not schedule.can_edit():
            return Response({
                'error': 'Bu schedule-i daha edit edə bilməzsiniz'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Update fields
        if 'vacation_type_id' in request.data:
            schedule.vacation_type_id = request.data['vacation_type_id']
        if 'start_date' in request.data:
            schedule.start_date = request.data['start_date']
        if 'end_date' in request.data:
            schedule.end_date = request.data['end_date']
        if 'comment' in request.data:
            schedule.comment = request.data['comment']
        
        schedule.edit_count += 1
        schedule.last_edited_at = timezone.now()
        schedule.last_edited_by = request.user
        schedule.save()
        
        return Response({
            'message': 'Schedule yeniləndi',
            'schedule': VacationScheduleSerializer(schedule).data
        })
        
    except VacationSchedule.DoesNotExist:
        return Response({'error': 'Schedule tapılmadı'}, status=status.HTTP_404_NOT_FOUND)
    except Employee.DoesNotExist:
        return Response({'error': 'Employee profili tapılmadı'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

# ==================== DELETE SCHEDULE ====================
@swagger_auto_schema(
    method='delete',
    operation_description="Schedule-i sil",
    operation_summary="Delete Schedule",
    tags=['Vacation'],
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
        200: openapi.Response(description='Schedule silindi')
    }
)
@api_view(['DELETE'])
@has_vacation_permission('vacation.schedule.delete_own')
@permission_classes([IsAuthenticated])
def delete_schedule(request, pk):
    """Schedule-i sil"""
    try:
        schedule = VacationSchedule.objects.get(pk=pk, is_deleted=False)
        emp = Employee.objects.get(user=request.user)
        
        # Yalnız schedule-in sahibi və ya line manager silə bilər
        if schedule.employee != emp and schedule.employee.line_manager != emp:
            return Response({'error': 'Bu schedule-i silmək hüququnuz yoxdur'}, status=status.HTTP_403_FORBIDDEN)
        
        # Registered schedule-i silmək olmaz
        if schedule.status == 'REGISTERED':
            return Response({'error': 'Registered schedule-i silmək olmaz'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Soft delete
        schedule.is_deleted = True
        schedule.deleted_by = request.user
        schedule.deleted_at = timezone.now()
        schedule.save()
        
        # Scheduled days balansını azalt
        schedule._update_scheduled_balance(add=False)
        
        return Response({'message': 'Schedule silindi'})
        
    except VacationSchedule.DoesNotExist:
        return Response({'error': 'Schedule tapılmadı'}, status=status.HTTP_404_NOT_FOUND)
    except Employee.DoesNotExist:
        return Response({'error': 'Employee profili tapılmadı'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


# ==================== APPROVAL PENDING ====================
@swagger_auto_schema(
    method='get',
    operation_description="Approval - Pending requestlər (Admin bütün pending-ləri görür)",
    operation_summary="Pending Requests",
    tags=['Vacation'],
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
@has_any_vacation_permission([
    'vacation.request.approve_as_line_manager',
    'vacation.request.approve_as_hr'
])
@permission_classes([IsAuthenticated])
def approval_pending_requests(request):
    """Approval - Pending requestlər"""
    from .vacation_permissions import is_admin_user
    
    try:
        emp = Employee.objects.get(user=request.user)
        
        # Admin isə, BÜTÜN pending request-ləri göstər
        if is_admin_user(request.user):
            lm_requests = VacationRequest.objects.filter(
                status='PENDING_LINE_MANAGER',
                is_deleted=False
            ).order_by('-created_at')
            
            hr_requests = VacationRequest.objects.filter(
                status='PENDING_HR',
                is_deleted=False
            ).order_by('-created_at')
        else:
            # Normal user - yalnız onun line manager və ya HR olduğu requestlər
            lm_requests = VacationRequest.objects.filter(
                line_manager=emp,
                status='PENDING_LINE_MANAGER',
                is_deleted=False
            ).order_by('-created_at')
            
            hr_requests = VacationRequest.objects.filter(
                hr_representative=emp,
                status='PENDING_HR',
                is_deleted=False
            ).order_by('-created_at')
        
        return Response({
            'line_manager_requests': VacationRequestListSerializer(lm_requests, many=True).data,
            'hr_requests': VacationRequestListSerializer(hr_requests, many=True).data,
            'total_pending': lm_requests.count() + hr_requests.count(),
            'is_admin': is_admin_user(request.user)  # Frontend üçün
        })
    except Employee.DoesNotExist:
        return Response({'error': 'Employee profili tapılmadı'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

# ==================== APPROVAL HISTORY ====================
@swagger_auto_schema(
    method='get',
    operation_description="Approval History",
    operation_summary="Approval History",
    tags=['Vacation'],
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
@has_any_vacation_permission([
    'vacation.request.approve_as_line_manager',
    'vacation.request.approve_as_hr'
])
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
                'days': float(req.number_of_days),
                'status': 'Approved (Line Manager)',
                'action': 'Approved',
                'comment': req.line_manager_comment,
                'date': req.line_manager_approved_at
            })
        
        for req in hr_approved:
            history.append({
                'request_id': req.request_id,
                'employee_name': req.employee.full_name,
                'vacation_type': req.vacation_type.name,
                'start_date': req.start_date.strftime('%Y-%m-%d'),
                'end_date': req.end_date.strftime('%Y-%m-%d'),
                'days': float(req.number_of_days),
                'status': 'Approved (HR)',
                'action': 'Approved',
                'comment': req.hr_comment,
                'date': req.hr_approved_at
            })
        
        for req in rejected:
            history.append({
                'request_id': req.request_id,
                'employee_name': req.employee.full_name,
                'vacation_type': req.vacation_type.name,
                'start_date': req.start_date.strftime('%Y-%m-%d'),
                'end_date': req.end_date.strftime('%Y-%m-%d'),
                'days': float(req.number_of_days),
                'status': req.get_status_display(),
                'action': 'Rejected',
                'comment': req.rejection_reason,
                'date': req.rejected_at
            })
        
        history.sort(key=lambda x: x['date'] if x['date'] else datetime.min, reverse=True)
        
        return Response({'history': history[:20]})
    except Exception as e:
        return Response({'error': f'History yüklənmədi: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)


# ==================== APPROVE/REJECT REQUEST ====================
@swagger_auto_schema(
    method='post',
    operation_description="Request-ə approve və ya reject ver",
    operation_summary="Approve/Reject Request",
    tags=['Vacation'],
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
@has_any_vacation_permission([
    'vacation.request.approve_as_line_manager',
    'vacation.request.approve_as_hr'
])
@permission_classes([IsAuthenticated])
def approve_reject_request(request, pk):
    """Request-ə approve/reject ver (employee yoxlaması olmadan)"""
    serializer = VacationApprovalSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    data = serializer.validated_data
    
    try:
        vac_req = VacationRequest.objects.get(pk=pk, is_deleted=False)
        
        # Employee yoxlaması ləğv edildi - hamı approve/reject edə bilər
        
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
    operation_description="İstifadəçinin bütün vacation request və schedule-lərini göstər",
    operation_summary="My All Requests & Schedules",
    tags=['Vacation'],
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
                        }
                    ]
                }
            }
        )
    }
)
@api_view(['GET'])
@has_vacation_permission('vacation.request.view_own')
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
                'return_date': req.return_date.strftime('%Y-%m-%d') if req.return_date else '',
                'days': float(req.number_of_days),
                'status': req.get_status_display(),
                'comment': req.comment,
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
                'return_date': sch.return_date.strftime('%Y-%m-%d') if sch.return_date else '',
                'days': float(sch.number_of_days),
                'status': sch.get_status_display(),
                'comment': sch.comment,
                'created_at': sch.created_at,
                'can_edit': sch.can_edit(),
                'edit_count': sch.edit_count
            })
        
        combined.sort(key=lambda x: x['created_at'], reverse=True)
        
        return Response({'records': combined})
    except Employee.DoesNotExist:
        return Response({'error': 'Employee profili tapılmadı'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@swagger_auto_schema(
    method='get',
    operation_description="Bütün vacation request və schedule-ları göstər (hamı görə bilər)",
    operation_summary="All Vacation Records",
    tags=['Vacation'],
    manual_parameters=[
        openapi.Parameter(
            'status',
            openapi.IN_QUERY,
            description="Status filteri",
            type=openapi.TYPE_STRING,
            required=False
        ),
        openapi.Parameter(
            'vacation_type_id',
            openapi.IN_QUERY,
            description="Vacation type filteri",
            type=openapi.TYPE_INTEGER,
            required=False
        ),
        openapi.Parameter(
            'department_id',
            openapi.IN_QUERY,
            description="Department filteri",
            type=openapi.TYPE_INTEGER,
            required=False
        ),
        openapi.Parameter(
            'start_date',
            openapi.IN_QUERY,
            description="Başlama tarixi filteri (YYYY-MM-DD)",
            type=openapi.TYPE_STRING,
            required=False
        ),
        openapi.Parameter(
            'end_date',
            openapi.IN_QUERY,
            description="Bitmə tarixi filteri (YYYY-MM-DD)",
            type=openapi.TYPE_STRING,
            required=False
        ),
        openapi.Parameter(
            'employee_name',
            openapi.IN_QUERY,
            description="Employee adı filteri",
            type=openapi.TYPE_STRING,
            required=False
        )
    ],
    responses={
        200: openapi.Response(
            description='Bütün vacation records',
            examples={
                'application/json': {
                    'records': [
                        {
                            'id': 1,
                            'type': 'request',
                            'request_id': 'VR20250001',
                            'employee_name': 'John Doe',
                            'employee_id': 'EMP001',
                            'department': 'IT',
                            'vacation_type': 'Annual Leave',
                            'start_date': '2025-10-15',
                            'end_date': '2025-10-20',
                            'days': 4.0,
                            'status': 'Approved',
                            'created_at': '2025-09-01T10:00:00Z'
                        }
                    ],
                    'total_count': 150,
                    'requests_count': 75,
                    'schedules_count': 75
                }
            }
        )
    }
)
@api_view(['GET'])
@has_vacation_permission('vacation.request.view_all')
@permission_classes([IsAuthenticated])
def all_vacation_records(request):
    """Bütün vacation records-u enhanced formatda export et"""
    try:
        # Filter parameters
        status = request.GET.get('status')
        vacation_type_id = request.GET.get('vacation_type_id')
        department_id = request.GET.get('department_id')
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        employee_name = request.GET.get('employee_name')
        year = request.GET.get('year')
        export_format = request.GET.get('format', 'dashboard')
        include_charts = request.GET.get('include_charts', 'true').lower() == 'true'
        
        # All requests
        requests_qs = VacationRequest.objects.filter(is_deleted=False).select_related(
            'employee', 'employee__department', 'employee__business_function', 
            'vacation_type', 'line_manager', 'hr_representative',
            'line_manager_approved_by', 'hr_approved_by', 'rejected_by'
        )
        
        # All schedules  
        schedules_qs = VacationSchedule.objects.filter(is_deleted=False).select_related(
            'employee', 'employee__department', 'employee__business_function', 
            'vacation_type', 'created_by', 'last_edited_by'
        )
        
        # Apply filters
        if status:
            requests_qs = requests_qs.filter(status=status)
            schedules_qs = schedules_qs.filter(status=status)
        
        if vacation_type_id:
            requests_qs = requests_qs.filter(vacation_type_id=vacation_type_id)
            schedules_qs = schedules_qs.filter(vacation_type_id=vacation_type_id)
        
        if department_id:
            requests_qs = requests_qs.filter(employee__department_id=department_id)
            schedules_qs = schedules_qs.filter(employee__department_id=department_id)
        
        if start_date:
            requests_qs = requests_qs.filter(start_date__gte=start_date)
            schedules_qs = schedules_qs.filter(start_date__gte=start_date)
        
        if end_date:
            requests_qs = requests_qs.filter(end_date__lte=end_date)
            schedules_qs = schedules_qs.filter(end_date__lte=end_date)
        
        if employee_name:
            requests_qs = requests_qs.filter(employee__full_name__icontains=employee_name)
            schedules_qs = schedules_qs.filter(employee__full_name__icontains=employee_name)
        
        if year:
            requests_qs = requests_qs.filter(start_date__year=year)
            schedules_qs = schedules_qs.filter(start_date__year=year)
        
        # Get data
        requests = requests_qs.order_by('-created_at')
        schedules = schedules_qs.order_by('-created_at')
        
        wb = Workbook()
        
        # Define enhanced styles
        title_font = Font(size=18, bold=True, color="1F4E79")
        subtitle_font = Font(size=14, bold=True, color="2B4C7E")
        header_fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
        header_font = Font(color="FFFFFF", bold=True, size=11)
        
        # Status colors
        status_colors = {
            'APPROVED': PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid"),
            'PENDING_LINE_MANAGER': PatternFill(start_color="FFEB9C", end_color="FFEB9C", fill_type="solid"),
            'PENDING_HR': PatternFill(start_color="E6E6FA", end_color="E6E6FA", fill_type="solid"),
            'REJECTED_LINE_MANAGER': PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid"),
            'REJECTED_HR': PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid"),
            'SCHEDULED': PatternFill(start_color="DAEEF3", end_color="DAEEF3", fill_type="solid"),
            'REGISTERED': PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid"),
        }
        
        if export_format == 'dashboard':
            # DASHBOARD SHEET
            ws_dashboard = wb.active
            ws_dashboard.title = "Dashboard"
            
            # Main title
            ws_dashboard['A1'] = 'VACATION MANAGEMENT DASHBOARD'
            ws_dashboard['A1'].font = title_font
            ws_dashboard.merge_cells('A1:H1')
            ws_dashboard['A1'].alignment = Alignment(horizontal='center')
            
            # Applied filters info
            filter_info = []
            if status: filter_info.append(f"Status: {status}")
            if department_id: filter_info.append(f"Department ID: {department_id}")
            if year: filter_info.append(f"Year: {year}")
            if vacation_type_id: filter_info.append(f"Vacation Type ID: {vacation_type_id}")
            
            if filter_info:
                ws_dashboard['A2'] = f'Applied Filters: {", ".join(filter_info)}'
                ws_dashboard['A2'].font = Font(size=10, italic=True)
                ws_dashboard.merge_cells('A2:H2')
            
            ws_dashboard['A3'] = f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
            ws_dashboard['A3'].font = Font(size=10)
            
            # Key Statistics
            ws_dashboard['A5'] = 'KEY STATISTICS'
            ws_dashboard['A5'].font = subtitle_font
            
            # Calculate statistics
            total_requests = requests.count()
            total_schedules = schedules.count()
            approved_requests = requests.filter(status='APPROVED').count()
            pending_requests = requests.exclude(status__in=['APPROVED', 'REJECTED_LINE_MANAGER', 'REJECTED_HR']).count()
            rejected_requests = requests.filter(status__in=['REJECTED_LINE_MANAGER', 'REJECTED_HR']).count()
            
            total_vacation_days = sum(float(req.number_of_days) for req in requests) + sum(float(sch.number_of_days) for sch in schedules)
            
            # Unique employees
            unique_employees = set()
            for req in requests:
                unique_employees.add(req.employee.id)
            for sch in schedules:
                unique_employees.add(sch.employee.id)
            
            stats_data = [
                ['Metric', 'Value', 'Percentage'],
                ['Total Requests', total_requests, ''],
                ['Approved Requests', approved_requests, f'{(approved_requests/total_requests*100):.1f}%' if total_requests > 0 else '0%'],
                ['Pending Requests', pending_requests, f'{(pending_requests/total_requests*100):.1f}%' if total_requests > 0 else '0%'],
                ['Rejected Requests', rejected_requests, f'{(rejected_requests/total_requests*100):.1f}%' if total_requests > 0 else '0%'],
                ['Total Schedules', total_schedules, ''],
                ['Total Records', total_requests + total_schedules, ''],
                ['Unique Employees', len(unique_employees), ''],
                ['Total Vacation Days', f'{total_vacation_days:.1f}', ''],
                ['Avg Days per Request', f'{total_vacation_days/(total_requests+total_schedules):.1f}' if (total_requests+total_schedules) > 0 else '0', '']
            ]
            
            for row, (metric, value, percentage) in enumerate(stats_data, 7):
                ws_dashboard[f'A{row}'] = metric
                ws_dashboard[f'B{row}'] = value
                ws_dashboard[f'C{row}'] = percentage
                
                if row == 7:  # Header
                    for col in ['A', 'B', 'C']:
                        cell = ws_dashboard[f'{col}{row}']
                        cell.fill = header_fill
                        cell.font = header_font
                        cell.border = Border(
                            left=Side(style='thin'), right=Side(style='thin'),
                            top=Side(style='thin'), bottom=Side(style='thin')
                        )
                else:
                    # Color code certain rows
                    if 'Approved' in metric:
                        fill = status_colors.get('APPROVED')
                    elif 'Rejected' in metric:
                        fill = status_colors.get('REJECTED_LINE_MANAGER')
                    elif 'Pending' in metric:
                        fill = status_colors.get('PENDING_LINE_MANAGER')
                    else:
                        fill = PatternFill(start_color="F8F9FA", end_color="F8F9FA", fill_type="solid")
                    
                    for col in ['A', 'B', 'C']:
                        ws_dashboard[f'{col}{row}'].fill = fill
            
            # Department Breakdown
            ws_dashboard['E5'] = 'DEPARTMENT BREAKDOWN'
            ws_dashboard['E5'].font = subtitle_font
            
            # Get department statistics
            from django.db.models import Count, Sum
            dept_requests = requests.values('employee__department__name').annotate(
                count=Count('id'),
                total_days=Sum('number_of_days')
            ).order_by('-count')[:10]
            
            dept_headers = ['Department', 'Requests', 'Total Days']
            for col, header in enumerate(dept_headers, 5):  # Column E, F, G
                cell = ws_dashboard.cell(row=7, column=col, value=header)
                cell.fill = header_fill
                cell.font = header_font
            
            for row, dept in enumerate(dept_requests, 8):
                ws_dashboard[f'E{row}'] = dept['employee__department__name'] or 'No Department'
                ws_dashboard[f'F{row}'] = dept['count']
                ws_dashboard[f'G{row}'] = float(dept['total_days'] or 0)
            
            if year:
                ws_dashboard['A18'] = 'MONTHLY TREND'
                ws_dashboard['A18'].font = subtitle_font
                
                # ✅ Yalnız data olan ayları tap
                monthly_data = []
                for month in range(1, 13):
                    month_requests = requests.filter(start_date__year=year, start_date__month=month).count()
                    month_schedules = schedules.filter(start_date__year=year, start_date__month=month).count()
                    
                    # ✅ Yalnız data varsa əlavə et
                    if month_requests > 0 or month_schedules > 0:
                        monthly_data.append([
                            datetime(int(year), month, 1).strftime('%B'),
                            month_requests,
                            month_schedules,
                            month_requests + month_schedules
                        ])
                
                # ✅ Əgər data varsa göstər
                if monthly_data:
                    monthly_headers = ['Month', 'Requests', 'Schedules', 'Total']
                    for col, header in enumerate(monthly_headers, 1):
                        cell = ws_dashboard.cell(row=20, column=col, value=header)
                        cell.fill = header_fill
                        cell.font = header_font
                    
                    for row, data in enumerate(monthly_data, 21):
                        for col, value in enumerate(data, 1):
                            ws_dashboard.cell(row=row, column=col, value=value)
                    # COMBINED DATA SHEET (always include)
                    ws_combined = wb.create_sheet("All Records") if export_format == 'dashboard' else wb.active
                    if export_format != 'dashboard':
                        ws_combined.title = "All Records"
        
        # Enhanced headers with more details
        combined_headers = [
            'Type', 'ID', 'Employee Name', 'Employee ID', 'Department', 'Business Function',
            'Vacation Type', 'Start Date', 'End Date', 'Return Date', 'Working Days',
            'Status', 'Comment', 'Approval Chain', 'Timeline', 'Performance Score',
            'Created At', 'Updated At'
        ]
        
        # Apply header styling
        for col, header in enumerate(combined_headers, 1):
            cell = ws_combined.cell(row=1, column=col, value=header)
            cell.fill = header_fill
            cell.font = header_font
            cell.border = Border(
                left=Side(style='thin'), right=Side(style='thin'),
                top=Side(style='thin'), bottom=Side(style='thin')
            )
        
        # Combine and process all records
        all_records = []
        
        # Add requests with enhanced data
        for req in requests:
            # Create approval chain
            approval_chain = []
            if req.line_manager_approved_at:
                approval_chain.append('LM ✓')
            elif req.status == 'PENDING_LINE_MANAGER':
                approval_chain.append('LM ⏳')
            elif req.status == 'REJECTED_LINE_MANAGER':
                approval_chain.append('LM ✗')
            
            if req.hr_approved_at:
                approval_chain.append('HR ✓')
            elif req.status == 'PENDING_HR':
                approval_chain.append('HR ⏳')
            elif req.status == 'REJECTED_HR':
                approval_chain.append('HR ✗')
            
            # Create timeline
            timeline = f"Created: {req.created_at.strftime('%m/%d')}"
            if req.line_manager_approved_at:
                timeline += f" → LM: {req.line_manager_approved_at.strftime('%m/%d')}"
            if req.hr_approved_at:
                timeline += f" → HR: {req.hr_approved_at.strftime('%m/%d')}"
            if req.rejected_at:
                timeline += f" → Rejected: {req.rejected_at.strftime('%m/%d')}"
            
            # Performance score (days from creation to approval)
            perf_score = 'N/A'
            if req.status == 'APPROVED' and req.hr_approved_at:
                days_to_approve = (req.hr_approved_at.date() - req.created_at.date()).days
                if days_to_approve <= 3:
                    perf_score = 'Excellent'
                elif days_to_approve <= 7:
                    perf_score = 'Good'
                elif days_to_approve <= 14:
                    perf_score = 'Fair'
                else:
                    perf_score = 'Slow'
            
            all_records.append({
                'type': 'Request',
                'id': req.request_id,
                'employee_name': req.employee.full_name,
                'employee_id': getattr(req.employee, 'employee_id', ''),
                'department': req.employee.department.name if req.employee.department else '',
                'business_function': req.employee.business_function.name if req.employee.business_function else '',
                'vacation_type': req.vacation_type.name,
                'start_date': req.start_date.strftime('%Y-%m-%d'),
                'end_date': req.end_date.strftime('%Y-%m-%d'),
                'return_date': req.return_date.strftime('%Y-%m-%d') if req.return_date else '',
                'working_days': float(req.number_of_days),
                'status': req.get_status_display(),
                'comment': req.comment,
                'approval_chain': ' | '.join(approval_chain),
                'timeline': timeline,
                'performance_score': perf_score,
                'created_at': req.created_at,
                'updated_at': req.updated_at,
                'status_raw': req.status
            })
        
        # Add schedules with enhanced data
        for sch in schedules:
            timeline = f"Created: {sch.created_at.strftime('%m/%d')}"
            if sch.last_edited_at:
                timeline += f" → Edited: {sch.last_edited_at.strftime('%m/%d')}"
            
            all_records.append({
                'type': 'Schedule',
                'id': f'SCH{sch.id}',
                'employee_name': sch.employee.full_name,
                'employee_id': getattr(sch.employee, 'employee_id', ''),
                'department': sch.employee.department.name if sch.employee.department else '',
                'business_function': sch.employee.business_function.name if sch.employee.business_function else '',
                'vacation_type': sch.vacation_type.name,
                'start_date': sch.start_date.strftime('%Y-%m-%d'),
                'end_date': sch.end_date.strftime('%Y-%m-%d'),
                'return_date': sch.return_date.strftime('%Y-%m-%d') if sch.return_date else '',
                'working_days': float(sch.number_of_days),
                'status': sch.get_status_display(),
                'comment': sch.comment,
                'approval_chain': 'No Approval Required',
                'timeline': timeline,
                'performance_score': f'Edits: {sch.edit_count}',
                'created_at': sch.created_at,
                'updated_at': sch.updated_at,
                'status_raw': sch.status
            })
        
        # Sort by created_at desc
        all_records.sort(key=lambda x: x['created_at'] if x['created_at'] else datetime.min, reverse=True)
        
        # Add enhanced data to combined sheet
        for row, record in enumerate(all_records, 2):
            data_row = [
                record['type'],
                record['id'],
                record['employee_name'],
                record['employee_id'],
                record['department'],
                record['business_function'],
                record['vacation_type'],
                record['start_date'],
                record['end_date'],
                record['return_date'],
                record['working_days'],
                record['status'],
                record['comment'],
                record['approval_chain'],
                record['timeline'],
                record['performance_score'],
                record['created_at'].strftime('%Y-%m-%d %H:%M') if record['created_at'] else '',
                record['updated_at'].strftime('%Y-%m-%d %H:%M') if record['updated_at'] else ''
            ]
            
            for col, value in enumerate(data_row, 1):
                cell = ws_combined.cell(row=row, column=col, value=value)
                
                # Apply status color coding
                if col == 12:  # Status column
                    cell.fill = status_colors.get(record['status_raw'], PatternFill())
                
                # Apply conditional formatting
                if col == 16:  # Performance score
                    if value == 'Excellent':
                        cell.fill = status_colors.get('APPROVED')
                    elif value == 'Slow':
                        cell.fill = status_colors.get('REJECTED_LINE_MANAGER')
                
                # Center align certain columns
                if col in [1, 11, 12, 16]:
                    cell.alignment = Alignment(horizontal='center')
                elif col in [11]:  # Working days - right align
                    cell.alignment = Alignment(horizontal='right')
        
        # Create table for better formatting
        if len(all_records) > 0:
            table_range = f"A1:{get_column_letter(len(combined_headers))}{len(all_records) + 1}"
            table = Table(displayName="VacationRecords", ref=table_range)
            style = TableStyleInfo(
                name="TableStyleMedium9", 
                showFirstColumn=False,
                showLastColumn=False, 
                showRowStripes=True, 
                showColumnStripes=False
            )
            table.tableStyleInfo = style
            ws_combined.add_table(table)
        
        # Add charts if requested
        if include_charts and len(all_records) > 0 and export_format == 'dashboard':
            # Status distribution chart on dashboard
            ws_chart = wb.create_sheet("Analytics")
            
            # Status distribution data
            status_counts = {}
            for record in all_records:
                status = record['status_raw']
                status_counts[status] = status_counts.get(status, 0) + 1
            
            # Create status chart data
            chart_headers = ['Status', 'Count']
            ws_chart.cell(row=1, column=1, value=chart_headers[0]).font = header_font
            ws_chart.cell(row=1, column=2, value=chart_headers[1]).font = header_font
            
            for row, (status, count) in enumerate(status_counts.items(), 2):
                ws_chart.cell(row=row, column=1, value=status)
                ws_chart.cell(row=row, column=2, value=count)
            
            # Create chart
            from openpyxl.chart import PieChart
            chart = PieChart()
            chart.title = "Status Distribution"
            chart.style = 26
            
            data = Reference(ws_chart, min_col=2, min_row=1, max_row=len(status_counts) + 1)
            cats = Reference(ws_chart, min_col=1, min_row=2, max_row=len(status_counts) + 1)
            chart.add_data(data, titles_from_data=True)
            chart.set_categories(cats)
            
            ws_chart.add_chart(chart, "D2")
        
        # Auto-adjust column widths for all sheets
        for ws_current in wb.worksheets:
            for column in ws_current.columns:
                max_length = 0
                column_letter = get_column_letter(column[0].column)
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 60)
                ws_current.column_dimensions[column_letter].width = adjusted_width
        
        # Generate enhanced filename
        filter_parts = []
        if status: filter_parts.append(f"status_{status}")
        if department_id: filter_parts.append(f"dept_{department_id}")
        if year: filter_parts.append(f"year_{year}")
        if vacation_type_id: filter_parts.append(f"type_{vacation_type_id}")
        
        filter_str = "_".join(filter_parts) if filter_parts else "all"
        filename = f'vacation_records_enhanced_{filter_str}_{export_format}_{date.today().strftime("%Y%m%d")}.xlsx'
        
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename={filename}'
        wb.save(response)
        
        return response
        
    except Exception as e:
        return Response({'error': f'Export error: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)

@swagger_auto_schema(
    method='get',
    operation_description="Bütün vacation records-u Excel formatında export et (filterlər dəstəklənir)",
    operation_summary="Export All Vacation Records",
    tags=['Vacation'],
    manual_parameters=[
        openapi.Parameter(
            'status',
            openapi.IN_QUERY,
            description="Status filteri",
            type=openapi.TYPE_STRING,
            required=False
        ),
        openapi.Parameter(
            'vacation_type_id',
            openapi.IN_QUERY,
            description="Vacation type filteri",
            type=openapi.TYPE_INTEGER,
            required=False
        ),
        openapi.Parameter(
            'department_id',
            openapi.IN_QUERY,
            description="Department filteri",
            type=openapi.TYPE_INTEGER,
            required=False
        ),
        openapi.Parameter(
            'start_date',
            openapi.IN_QUERY,
            description="Başlama tarixi filteri (YYYY-MM-DD)",
            type=openapi.TYPE_STRING,
            required=False
        ),
        openapi.Parameter(
            'end_date',
            openapi.IN_QUERY,
            description="Bitmə tarixi filteri (YYYY-MM-DD)",
            type=openapi.TYPE_STRING,
            required=False
        ),
        openapi.Parameter(
            'employee_name',
            openapi.IN_QUERY,
            description="Employee adı filteri",
            type=openapi.TYPE_STRING,
            required=False
        ),
        openapi.Parameter(
            'year',
            openapi.IN_QUERY,
            description="İl filteri (məsələn: 2025)",
            type=openapi.TYPE_INTEGER,
            required=False
        ),
        openapi.Parameter(
            'format',
            openapi.IN_QUERY,
            description="Export formatı: 'combined' (hər şey bir sheet-də) və ya 'separated' (ayrı sheet-lər)",
            type=openapi.TYPE_STRING,
            enum=['combined', 'separated'],
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
@has_any_vacation_permission([
    'vacation.request.export_all',  # HR və Admin
    'vacation.request.export_team'   # Line Manager (öz team-i)
])
@permission_classes([IsAuthenticated])
def export_all_vacation_records(request):
    """Bütün vacation records-u enhanced formatda export et"""
    from .vacation_permissions import is_admin_user
    
    try:
        # Filter parameters
        status = request.GET.get('status')
        vacation_type_id = request.GET.get('vacation_type_id')
        department_id = request.GET.get('department_id')
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        employee_name = request.GET.get('employee_name')
        year = request.GET.get('year')
        export_format = request.GET.get('format', 'dashboard')
        include_charts = request.GET.get('include_charts', 'true').lower() == 'true'
        
        # ✅ Permission-based filtering
        is_admin = is_admin_user(request.user)
        has_hr_permission, _ = check_vacation_permission(request.user, 'vacation.request.export_all')
        has_team_permission, _ = check_vacation_permission(request.user, 'vacation.request.export_team')
        
        # All requests base query
        requests_qs = VacationRequest.objects.filter(is_deleted=False).select_related(
            'employee', 'employee__department', 'employee__business_function', 
            'vacation_type', 'line_manager', 'hr_representative',
            'line_manager_approved_by', 'hr_approved_by', 'rejected_by'
        )
        
        # All schedules base query
        schedules_qs = VacationSchedule.objects.filter(is_deleted=False).select_related(
            'employee', 'employee__department', 'employee__business_function', 
            'vacation_type', 'created_by', 'last_edited_by'
        )
        
        # ✅ PERMISSION FILTERING
        if is_admin or has_hr_permission:
            # Admin və HR - bütün data
            pass
        elif has_team_permission:
            # Line Manager - yalnız öz team-i və özü
            try:
                emp = Employee.objects.get(user=request.user, is_deleted=False)
                
                # Öz team-indəki işçilər
                team_employees = Employee.objects.filter(
                    line_manager=emp,
                    is_deleted=False
                ).values_list('id', flat=True)
                
                # Özü + team
                allowed_employee_ids = list(team_employees) + [emp.id]
                
                requests_qs = requests_qs.filter(employee_id__in=allowed_employee_ids)
                schedules_qs = schedules_qs.filter(employee_id__in=allowed_employee_ids)
                
            except Employee.DoesNotExist:
                # Employee yoxdursa, yalnız özünü
                requests_qs = requests_qs.filter(employee__user=request.user)
                schedules_qs = schedules_qs.filter(employee__user=request.user)
        else:
            # Başqa istifadəçilər - yalnız özü (bu hal baş verməməlidir, amma safety)
            requests_qs = requests_qs.filter(employee__user=request.user)
            schedules_qs = schedules_qs.filter(employee__user=request.user)
        
        # Apply other filters (existing code)
        if status:
            requests_qs = requests_qs.filter(status=status)
            schedules_qs = schedules_qs.filter(status=status)
        
        if vacation_type_id:
            requests_qs = requests_qs.filter(vacation_type_id=vacation_type_id)
            schedules_qs = schedules_qs.filter(vacation_type_id=vacation_type_id)
        
        if department_id:
            requests_qs = requests_qs.filter(employee__department_id=department_id)
            schedules_qs = schedules_qs.filter(employee__department_id=department_id)
        
        if start_date:
            requests_qs = requests_qs.filter(start_date__gte=start_date)
            schedules_qs = schedules_qs.filter(start_date__gte=start_date)
        
        if end_date:
            requests_qs = requests_qs.filter(end_date__lte=end_date)
            schedules_qs = schedules_qs.filter(end_date__lte=end_date)
        
        if employee_name:
            requests_qs = requests_qs.filter(employee__full_name__icontains=employee_name)
            schedules_qs = schedules_qs.filter(employee__full_name__icontains=employee_name)
        
        if year:
            requests_qs = requests_qs.filter(start_date__year=year)
            schedules_qs = schedules_qs.filter(start_date__year=year)
        
        # Get data
        requests = requests_qs.order_by('-created_at')
        schedules = schedules_qs.order_by('-created_at')
        
      
        
        wb = Workbook()
        
        if export_format == 'separated':
            # Ayrı sheet-lər
            
            # Requests sheet
            ws_req = wb.active
            ws_req.title = "Vacation Requests"
            
            req_headers = [
                'Request ID', 'Employee Name', 'Employee ID', 'Department', 'Business Function',
                'Vacation Type', 'Start Date', 'End Date', 'Return Date', 'Working Days',
                'Status', 'Comment', 'Request Type',
                'Line Manager', 'LM Comment', 'LM Approved At', 'LM Approved By',
                'HR Representative', 'HR Comment', 'HR Approved At', 'HR Approved By',
                'Rejected By', 'Rejection Reason', 'Rejected At',
                'Created At', 'Updated At'
            ]
            ws_req.append(req_headers)
            
            for req in requests:
                ws_req.append([
                    req.request_id,
                    req.employee.full_name,
                    getattr(req.employee, 'employee_id', ''),
                    req.employee.department.name if req.employee.department else '',
                    req.employee.business_function.name if req.employee.business_function else '',
                    req.vacation_type.name,
                    req.start_date.strftime('%Y-%m-%d'),
                    req.end_date.strftime('%Y-%m-%d'),
                    req.return_date.strftime('%Y-%m-%d') if req.return_date else '',
                    float(req.number_of_days),
                    req.get_status_display(),
                    req.comment,
                    req.get_request_type_display(),
                    req.line_manager.full_name if req.line_manager else '',
                    req.line_manager_comment,
                    req.line_manager_approved_at.strftime('%Y-%m-%d %H:%M') if req.line_manager_approved_at else '',
                    req.line_manager_approved_by.get_full_name() if req.line_manager_approved_by else '',
                    req.hr_representative.full_name if req.hr_representative else '',
                    req.hr_comment,
                    req.hr_approved_at.strftime('%Y-%m-%d %H:%M') if req.hr_approved_at else '',
                    req.hr_approved_by.get_full_name() if req.hr_approved_by else '',
                    req.rejected_by.get_full_name() if req.rejected_by else '',
                    req.rejection_reason,
                    req.rejected_at.strftime('%Y-%m-%d %H:%M') if req.rejected_at else '',
                    req.created_at.strftime('%Y-%m-%d %H:%M') if req.created_at else '',
                    req.updated_at.strftime('%Y-%m-%d %H:%M') if req.updated_at else ''
                ])
            
            # Schedules sheet
            ws_sch = wb.create_sheet("Vacation Schedules")
            
            sch_headers = [
                'Schedule ID', 'Employee Name', 'Employee ID', 'Department', 'Business Function',
                'Vacation Type', 'Start Date', 'End Date', 'Return Date', 'Working Days',
                'Status', 'Comment', 
                'Edit Count', 'Can Edit', 'Last Edited By', 'Last Edited At',
                'Created By', 'Created At', 'Updated At'
            ]
            ws_sch.append(sch_headers)
            
            for sch in schedules:
                ws_sch.append([
                    f'SCH{sch.id}',
                    sch.employee.full_name,
                    getattr(sch.employee, 'employee_id', ''),
                    sch.employee.department.name if sch.employee.department else '',
                    sch.employee.business_function.name if sch.employee.business_function else '',
                    sch.vacation_type.name,
                    sch.start_date.strftime('%Y-%m-%d'),
                    sch.end_date.strftime('%Y-%m-%d'),
                    sch.return_date.strftime('%Y-%m-%d') if sch.return_date else '',
                    float(sch.number_of_days),
                    sch.get_status_display(),
                    sch.comment,
                    sch.edit_count,
                    'Yes' if sch.can_edit() else 'No',
                    sch.last_edited_by.get_full_name() if sch.last_edited_by else '',
                    sch.last_edited_at.strftime('%Y-%m-%d %H:%M') if sch.last_edited_at else '',
                    sch.created_by.get_full_name() if sch.created_by else '',
                    sch.created_at.strftime('%Y-%m-%d %H:%M') if sch.created_at else '',
                    sch.updated_at.strftime('%Y-%m-%d %H:%M') if sch.updated_at else ''
                ])
            
        else:
            # Combined sheet (default)
            ws = wb.active
            ws.title = "All Vacation Records"
            
            headers = [
                'Type', 'ID', 'Employee Name', 'Employee ID', 'Department', 'Business Function',
                'Vacation Type', 'Start Date', 'End Date', 'Return Date', 'Working Days',
                'Status', 'Comment', 
                'Line Manager/Created By', 'HR Representative', 'Approval Status',
                'Edit Count', 'Created At', 'Updated At'
            ]
            ws.append(headers)
            
            # Combine and sort all records
            all_records = []
            
            # Add requests
            for req in requests:
                approval_status = []
                if req.line_manager_approved_at:
                    approval_status.append('LM ✓')
                elif req.status == 'PENDING_LINE_MANAGER':
                    approval_status.append('LM ⏳')
                elif req.status == 'REJECTED_LINE_MANAGER':
                    approval_status.append('LM ❌')
                
                if req.hr_approved_at:
                    approval_status.append('HR ✓')
                elif req.status == 'PENDING_HR':
                    approval_status.append('HR ⏳')
                elif req.status == 'REJECTED_HR':
                    approval_status.append('HR ❌')
                
                all_records.append({
                    'type': 'Request',
                    'id': req.request_id,
                    'employee_name': req.employee.full_name,
                    'employee_id': getattr(req.employee, 'employee_id', ''),
                    'department': req.employee.department.name if req.employee.department else '',
                    'business_function': req.employee.business_function.name if req.employee.business_function else '',
                    'vacation_type': req.vacation_type.name,
                    'start_date': req.start_date.strftime('%Y-%m-%d'),
                    'end_date': req.end_date.strftime('%Y-%m-%d'),
                    'return_date': req.return_date.strftime('%Y-%m-%d') if req.return_date else '',
                    'working_days': float(req.number_of_days),
                    'status': req.get_status_display(),
                    'comment': req.comment,
                    'manager_created_by': req.line_manager.full_name if req.line_manager else '',
                    'hr_representative': req.hr_representative.full_name if req.hr_representative else '',
                    'approval_status': ' | '.join(approval_status),
                    'edit_count': '',
                    'created_at': req.created_at,
                    'updated_at': req.updated_at
                })
            
            # Add schedules
            for sch in schedules:
                all_records.append({
                    'type': 'Schedule',
                    'id': f'SCH{sch.id}',
                    'employee_name': sch.employee.full_name,
                    'employee_id': getattr(sch.employee, 'employee_id', ''),
                    'department': sch.employee.department.name if sch.employee.department else '',
                    'business_function': sch.employee.business_function.name if sch.employee.business_function else '',
                    'vacation_type': sch.vacation_type.name,
                    'start_date': sch.start_date.strftime('%Y-%m-%d'),
                    'end_date': sch.end_date.strftime('%Y-%m-%d'),
                    'return_date': sch.return_date.strftime('%Y-%m-%d') if sch.return_date else '',
                    'working_days': float(sch.number_of_days),
                    'status': sch.get_status_display(),
                    'comment': sch.comment,
                    'manager_created_by': sch.created_by.get_full_name() if sch.created_by else '',
                    'hr_representative': '',
                    'approval_status': 'No Approval Needed',
                    'edit_count': sch.edit_count,
                    'created_at': sch.created_at,
                    'updated_at': sch.updated_at
                })
            
            # Sort by created_at desc
            all_records.sort(key=lambda x: x['created_at'] if x['created_at'] else datetime.min, reverse=True)
            
            # Add data to sheet
            for record in all_records:
                ws.append([
                    record['type'],
                    record['id'],
                    record['employee_name'],
                    record['employee_id'],
                    record['department'],
                    record['business_function'],
                    record['vacation_type'],
                    record['start_date'],
                    record['end_date'],
                    record['return_date'],
                    record['working_days'],
                    record['status'],
                    record['comment'],
                    record['manager_created_by'],
                    record['hr_representative'],
                    record['approval_status'],
                    record['edit_count'],
                    record['created_at'].strftime('%Y-%m-%d %H:%M') if record['created_at'] else '',
                    record['updated_at'].strftime('%Y-%m-%d %H:%M') if record['updated_at'] else ''
                ])
        
        # Auto-adjust column widths for all sheets
        for ws in wb.worksheets:
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
        
        # Generate filename
        filter_parts = []
        if status:
            filter_parts.append(f"status_{status}")
        if department_id:
            filter_parts.append(f"dept_{department_id}")
        if year:
            filter_parts.append(f"year_{year}")
        

   
        
        permission_indicator = 'admin' if is_admin else ('hr' if has_hr_permission else 'team')
        filename = f'vacation_records_{permission_indicator}_{export_format}_{date.today().strftime("%Y%m%d")}.xlsx'
        
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename={filename}'
        wb.save(response)
        
        return response
        
    except Exception as e:
        return Response({'error': f'Export error: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)

# ==================== EXPORT REQUESTS & SCHEDULES ====================

@swagger_auto_schema(
    method='get',
    operation_description="İstifadəçinin bütün vacation məlumatlarını Excel formatında export et",
    operation_summary="Export My Vacations",
    tags=['Vacation'],
    responses={
        200: openapi.Response(
            description='Excel file',
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    }
)
@api_view(['GET'])
@has_vacation_permission('vacation.request.export_own')
@permission_classes([IsAuthenticated])
def export_my_vacations(request):
    """İstifadəçinin vacation məlumatlarını enhanced formatda export et"""
    try:
        emp = Employee.objects.get(user=request.user)
        
        # All requests and schedules
        requests = VacationRequest.objects.filter(employee=emp, is_deleted=False).order_by('-created_at')
        schedules = VacationSchedule.objects.filter(employee=emp, is_deleted=False).order_by('-start_date')
        
        wb = Workbook()
        
        # Summary sheet
        ws_summary = wb.active
        ws_summary.title = "Personal Summary"
        ws_summary.sheet_view.showGridLines = False
        
        # Styles
        title_font = Font(size=16, bold=True, color="2B4C7E")
        header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
        header_font = Font(color="FFFFFF", bold=True, size=11)
        stat_fill = PatternFill(start_color="F0F4F8", end_color="F0F4F8", fill_type="solid")
        
        # Personal info header
        ws_summary['A1'] = f'VACATION SUMMARY - {emp.full_name}'
        ws_summary['A1'].font = title_font
        ws_summary.merge_cells('A1:E1')
        
        ws_summary['A2'] = f'Employee ID: {getattr(emp, "employee_id", "N/A")}'
        ws_summary['A3'] = f'Department: {emp.department.name if emp.department else "N/A"}'
        ws_summary['A4'] = f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")}'
        
        # ✅ DÜZƏLTMƏ: Yalnız data olan illəri tap
        years_with_data = set()
        
        # Requests-dən illəri tap
        for req in requests:
            years_with_data.add(req.start_date.year)
        
        # Schedules-dən illəri tap
        for sch in schedules:
            years_with_data.add(sch.start_date.year)
        
        # Balansı olan illəri tap
        balances_with_data = EmployeeVacationBalance.objects.filter(
            employee=emp,
            is_deleted=False
        ).exclude(
            yearly_balance=0,
            used_days=0,
            scheduled_days=0
        ).values_list('year', flat=True)
        
        years_with_data.update(balances_with_data)
        
        # ✅ Əgər heç bir data yoxdursa, cari ili əlavə et
        if not years_with_data:
            years_with_data.add(date.today().year)
        
        # Sort years
        sorted_years = sorted(years_with_data, reverse=True)
        
        ws_summary['A6'] = 'YEARLY STATISTICS'
        ws_summary['A6'].font = Font(size=14, bold=True, color="2B4C7E")
        
        year_headers = ['Year', 'Total Balance', 'Used Days', 'Scheduled Days', 'Remaining', 'Requests', 'Schedules']
        for col, header in enumerate(year_headers, 1):
            cell = ws_summary.cell(row=8, column=col, value=header)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal='center')
        
        for i, year in enumerate(sorted_years, 9):
            balance = EmployeeVacationBalance.objects.filter(employee=emp, year=year).first()
            year_requests = requests.filter(start_date__year=year).count()
            year_schedules = schedules.filter(start_date__year=year).count()
            
            if balance:
                data = [
                    year,
                    float(balance.total_balance),
                    float(balance.used_days),
                    float(balance.scheduled_days),
                    float(balance.remaining_balance),
                    year_requests,
                    year_schedules
                ]
            else:
                data = [year, 0, 0, 0, 0, year_requests, year_schedules]
            
            for col, value in enumerate(data, 1):
                cell = ws_summary.cell(row=i, column=col, value=value)
                if col > 1:
                    cell.fill = stat_fill
                cell.alignment = Alignment(horizontal='center' if col == 1 else 'right')
        
        # Requests sheet
        ws_requests = wb.create_sheet("Vacation Requests")
        
        req_headers = [
            'Request ID', 'Type', 'Vacation Type', 'Start Date', 'End Date', 'Return Date',
            'Days', 'Status', 'Comment', 'Line Manager', 'LM Comment', 'HR Comment', 
            'Created At', 'Timeline'
        ]
        
        for col, header in enumerate(req_headers, 1):
            cell = ws_requests.cell(row=1, column=col, value=header)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal='center')
        
        # Status colors
        status_colors = {
            'APPROVED': good_fill,
            'PENDING_LINE_MANAGER': PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid"),
            'PENDING_HR': PatternFill(start_color="E6E6FA", end_color="E6E6FA", fill_type="solid"),
            'REJECTED_LINE_MANAGER': warning_fill,
            'REJECTED_HR': warning_fill,
        }
        
        for row, req in enumerate(requests, 2):
            timeline = f"Created: {req.created_at.strftime('%Y-%m-%d')}"
            if req.line_manager_approved_at:
                timeline += f" → LM: {req.line_manager_approved_at.strftime('%Y-%m-%d')}"
            if req.hr_approved_at:
                timeline += f" → HR: {req.hr_approved_at.strftime('%Y-%m-%d')}"
            if req.rejected_at:
                timeline += f" → Rejected: {req.rejected_at.strftime('%Y-%m-%d')}"
            
            data = [
                req.request_id,
                req.get_request_type_display(),
                req.vacation_type.name,
                req.start_date.strftime('%Y-%m-%d'),
                req.end_date.strftime('%Y-%m-%d'),
                req.return_date.strftime('%Y-%m-%d') if req.return_date else '',
                float(req.number_of_days),
                req.get_status_display(),
                req.comment,
                req.line_manager.full_name if req.line_manager else '',
                req.line_manager_comment,
                req.hr_comment,
                req.created_at.strftime('%Y-%m-%d %H:%M'),
                timeline
            ]
            
            for col, value in enumerate(data, 1):
                cell = ws_requests.cell(row=row, column=col, value=value)
                if col == 8:  # Status column
                    cell.fill = status_colors.get(req.status, PatternFill())
        
        # Schedules sheet
        ws_schedules = wb.create_sheet("Vacation Schedules")
        
        sch_headers = [
            'Schedule ID', 'Vacation Type', 'Start Date', 'End Date', 'Return Date',
            'Days', 'Status', 'Comment', 'Edit Count', 'Can Edit', 'Created At',
            'Last Edited', 'Timeline'
        ]
        
        for col, header in enumerate(sch_headers, 1):
            cell = ws_schedules.cell(row=1, column=col, value=header)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal='center')
        
        for row, sch in enumerate(schedules, 2):
            timeline = f"Created: {sch.created_at.strftime('%Y-%m-%d')}"
            if sch.last_edited_at:
                timeline += f" → Last Edit: {sch.last_edited_at.strftime('%Y-%m-%d')}"
            
            data = [
                f'SCH{sch.id}',
                sch.vacation_type.name,
                sch.start_date.strftime('%Y-%m-%d'),
                sch.end_date.strftime('%Y-%m-%d'),
                sch.return_date.strftime('%Y-%m-%d') if sch.return_date else '',
                float(sch.number_of_days),
                sch.get_status_display(),
                sch.comment,
                sch.edit_count,
                'Yes' if sch.can_edit() else 'No',
                sch.created_at.strftime('%Y-%m-%d %H:%M'),
                sch.last_edited_at.strftime('%Y-%m-%d %H:%M') if sch.last_edited_at else '',
                timeline
            ]
            
            for col, value in enumerate(data, 1):
                cell = ws_schedules.cell(row=row, column=col, value=value)
                if col == 7:  # Status column
                    if sch.status == 'REGISTERED':
                        cell.fill = good_fill
                    else:
                        cell.fill = PatternFill(start_color="E6F3FF", end_color="E6F3FF", fill_type="solid")
        
        # Auto-adjust column widths
        for ws_current in [ws_summary, ws_requests, ws_schedules]:
            for column in ws_current.columns:
                max_length = 0
                column_letter = get_column_letter(column[0].column)
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 60)
                ws_current.column_dimensions[column_letter].width = adjusted_width
        
        filename = f'my_vacations_{emp.full_name.replace(" ", "_")}_{date.today().strftime("%Y%m%d")}.xlsx'
        
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename={filename}'
        wb.save(response)
        
        return response
        
    except Employee.DoesNotExist:
        return Response({'error': 'Employee profili tapılmadı'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

# ==================== SETTINGS VIEWSETS ====================

class VacationSettingViewSet(viewsets.ModelViewSet):
    """Vacation Settings CRUD"""
    queryset = VacationSetting.objects.filter(is_deleted=False)
    serializer_class = VacationSettingSerializer
    permission_classes = [IsAuthenticated]
    
    def get_swagger_tags(self):
        return ['Vacation - Settings']
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)
class VacationTypeViewSet(viewsets.ModelViewSet):
    queryset = VacationType.objects.filter(is_deleted=False)
    serializer_class = VacationTypeSerializer
    permission_classes = [IsAuthenticated]
    
    def list(self, request, *args, **kwargs):
        has_perm, _ = check_vacation_permission(request.user, 'vacation.type.view')
        if not has_perm:
            return Response({
                'error': 'İcazə yoxdur',
                'required_permission': 'vacation.type.view'
            }, status=status.HTTP_403_FORBIDDEN)
        return super().list(request, *args, **kwargs)
    
    def create(self, request, *args, **kwargs):
        has_perm, _ = check_vacation_permission(request.user, 'vacation.type.create')
        if not has_perm:
            return Response({
                'error': 'İcazə yoxdur',
                'required_permission': 'vacation.type.create'
            }, status=status.HTTP_403_FORBIDDEN)
        return super().create(request, *args, **kwargs)
    
    def update(self, request, *args, **kwargs):
        has_perm, _ = check_vacation_permission(request.user, 'vacation.type.update')
        if not has_perm:
            return Response({
                'error': 'İcazə yoxdur',
                'required_permission': 'vacation.type.update'
            }, status=status.HTTP_403_FORBIDDEN)
        return super().update(request, *args, **kwargs)
    
    def partial_update(self, request, *args, **kwargs):
        has_perm, _ = check_vacation_permission(request.user, 'vacation.type.update')
        if not has_perm:
            return Response({
                'error': 'İcazə yoxdur',
                'required_permission': 'vacation.type.update'
            }, status=status.HTTP_403_FORBIDDEN)
        return super().partial_update(request, *args, **kwargs)
    
    def destroy(self, request, *args, **kwargs):
        has_perm, _ = check_vacation_permission(request.user, 'vacation.type.delete')
        if not has_perm:
            return Response({
                'error': 'İcazə yoxdur',
                'required_permission': 'vacation.type.delete'
            }, status=status.HTTP_403_FORBIDDEN)
        return super().destroy(request, *args, **kwargs)

class NotificationTemplateViewSet(viewsets.ModelViewSet):
    queryset = NotificationTemplate.objects.filter(is_deleted=False)
    serializer_class = NotificationTemplateSerializer
    permission_classes = [IsAuthenticated]
    
    def list(self, request, *args, **kwargs):
        has_perm, _ = check_vacation_permission(request.user, 'vacation.notification.view')
        if not has_perm:
            return Response({
                'error': 'İcazə yoxdur',
                'required_permission': 'vacation.notification.view'
            }, status=status.HTTP_403_FORBIDDEN)
        return super().list(request, *args, **kwargs)
    
    def create(self, request, *args, **kwargs):
        has_perm, _ = check_vacation_permission(request.user, 'vacation.notification.update')
        if not has_perm:
            return Response({
                'error': 'İcazə yoxdur',
                'required_permission': 'vacation.notification.update'
            }, status=status.HTTP_403_FORBIDDEN)
        return super().create(request, *args, **kwargs)
    
    def update(self, request, *args, **kwargs):
        has_perm, _ = check_vacation_permission(request.user, 'vacation.notification.update')
        if not has_perm:
            return Response({
                'error': 'İcazə yoxdur',
                'required_permission': 'vacation.notification.update'
            }, status=status.HTTP_403_FORBIDDEN)
        return super().update(request, *args, **kwargs)
    
    def partial_update(self, request, *args, **kwargs):
        has_perm, _ = check_vacation_permission(request.user, 'vacation.notification.update')
        if not has_perm:
            return Response({
                'error': 'İcazə yoxdur',
                'required_permission': 'vacation.notification.update'
            }, status=status.HTTP_403_FORBIDDEN)
        return super().partial_update(request, *args, **kwargs)
    
    def destroy(self, request, *args, **kwargs):
        has_perm, _ = check_vacation_permission(request.user, 'vacation.notification.update')
        if not has_perm:
            return Response({
                'error': 'İcazə yoxdur',
                'required_permission': 'vacation.notification.update'
            }, status=status.HTTP_403_FORBIDDEN)
        return super().destroy(request, *args, **kwargs)

# ==================== UTILITIES ====================
@swagger_auto_schema(
    method='post',
    operation_description="İki tarix arasında iş günlərinin sayını hesabla",
    operation_summary="İş Günlərini Hesabla",
    tags=['Vacation'],
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