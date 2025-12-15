# api/celebration_test_views.py
"""
OPTIONAL: Test endpoints for celebration notifications
Use these to manually trigger notifications for testing
"""

import logging
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .celebration_notification_service import celebration_notification_service
from .models import Employee

logger = logging.getLogger(__name__)


@swagger_auto_schema(
    method='post',
    operation_description="🧪 TEST: Send birthday notification for specific employee",
    operation_summary="Test Birthday Notification",
    tags=['Celebrations - Test'],
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=['employee_id'],
        properties={
            'employee_id': openapi.Schema(type=openapi.TYPE_INTEGER, description='Employee ID')
        }
    ),
    responses={200: openapi.Response(description='Success')}
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def test_birthday_notification(request):
    """Test birthday notification for specific employee"""
    try:
        employee_id = request.data.get('employee_id')
        
        if not employee_id:
            return Response({
                'error': 'employee_id is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            employee = Employee.objects.get(id=employee_id)
        except Employee.DoesNotExist:
            return Response({
                'error': 'Employee not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        if not employee.date_of_birth:
            return Response({
                'error': 'Employee has no birth date'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        logger.info(f"🧪 Testing birthday notification for {employee.first_name} {employee.last_name}")
        
        success = celebration_notification_service.send_birthday_notification(employee)
        
        if success:
            return Response({
                'success': True,
                'message': f'Birthday notification sent for {employee.first_name} {employee.last_name}',
                'employee': {
                    'id': employee.id,
                    'name': f'{employee.first_name} {employee.last_name}',
                    'birth_date': employee.date_of_birth
                }
            })
        else:
            return Response({
                'success': False,
                'error': 'Failed to send notification'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    except Exception as e:
        logger.error(f"Error in test birthday notification: {e}")
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@swagger_auto_schema(
    method='post',
    operation_description="🧪 TEST: Send anniversary notification for specific employee",
    operation_summary="Test Anniversary Notification",
    tags=['Celebrations - Test'],
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=['employee_id', 'years'],
        properties={
            'employee_id': openapi.Schema(type=openapi.TYPE_INTEGER, description='Employee ID'),
            'years': openapi.Schema(type=openapi.TYPE_INTEGER, description='Years of service')
        }
    ),
    responses={200: openapi.Response(description='Success')}
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def test_anniversary_notification(request):
    """Test work anniversary notification for specific employee"""
    try:
        employee_id = request.data.get('employee_id')
        years = request.data.get('years')
        
        if not employee_id or not years:
            return Response({
                'error': 'employee_id and years are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            employee = Employee.objects.get(id=employee_id)
        except Employee.DoesNotExist:
            return Response({
                'error': 'Employee not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        if not employee.start_date:
            return Response({
                'error': 'Employee has no start date'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        logger.info(f"🧪 Testing {years}-year anniversary notification for {employee.first_name} {employee.last_name}")
        
        success = celebration_notification_service.send_work_anniversary_notification(employee, years)
        
        if success:
            return Response({
                'success': True,
                'message': f'{years}-year anniversary notification sent for {employee.first_name} {employee.last_name}',
                'employee': {
                    'id': employee.id,
                    'name': f'{employee.first_name} {employee.last_name}',
                    'start_date': employee.start_date,
                    'years': years
                }
            })
        else:
            return Response({
                'success': False,
                'error': 'Failed to send notification'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    except Exception as e:
        logger.error(f"Error in test anniversary notification: {e}")
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@swagger_auto_schema(
    method='post',
    operation_description="🧪 TEST: Send position change notification",
    operation_summary="Test Position Change Notification",
    tags=['Celebrations - Test'],
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=['employee_id', 'old_position', 'new_position'],
        properties={
            'employee_id': openapi.Schema(type=openapi.TYPE_INTEGER, description='Employee ID'),
            'old_position': openapi.Schema(type=openapi.TYPE_STRING, description='Old position'),
            'new_position': openapi.Schema(type=openapi.TYPE_STRING, description='New position'),
            'change_type': openapi.Schema(
                type=openapi.TYPE_STRING, 
                enum=['promotion', 'transfer'],
                default='promotion',
                description='Type of change'
            )
        }
    ),
    responses={200: openapi.Response(description='Success')}
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def test_position_change_notification(request):
    """Test position change notification"""
    try:
        employee_id = request.data.get('employee_id')
        old_position = request.data.get('old_position')
        new_position = request.data.get('new_position')
        change_type = request.data.get('change_type', 'promotion')
        
        if not all([employee_id, old_position, new_position]):
            return Response({
                'error': 'employee_id, old_position, and new_position are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            employee = Employee.objects.get(id=employee_id)
        except Employee.DoesNotExist:
            return Response({
                'error': 'Employee not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        logger.info(f"🧪 Testing position change notification for {employee.first_name} {employee.last_name}")
        
        success = celebration_notification_service.send_position_change_notification(
            employee=employee,
            old_position=old_position,
            new_position=new_position,
            change_type=change_type
        )
        
        if success:
            return Response({
                'success': True,
                'message': f'Position change notification sent for {employee.first_name} {employee.last_name}',
                'employee': {
                    'id': employee.id,
                    'name': f'{employee.first_name} {employee.last_name}',
                    'old_position': old_position,
                    'new_position': new_position,
                    'change_type': change_type
                }
            })
        else:
            return Response({
                'success': False,
                'error': 'Failed to send notification'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    except Exception as e:
        logger.error(f"Error in test position change notification: {e}")
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@swagger_auto_schema(
    method='post',
    operation_description="🧪 TEST: Run daily celebration check manually",
    operation_summary="Test Daily Celebration Check",
    tags=['Celebrations - Test'],
    responses={200: openapi.Response(description='Success')}
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def test_daily_celebration_check(request):
    """Manually trigger daily celebration check"""
    try:
        logger.info("🧪 Manually triggering daily celebration check")
        
        results = celebration_notification_service.check_and_send_daily_celebrations()
        
        return Response({
            'success': True,
            'results': results
        })
        
    except Exception as e:
        logger.error(f"Error in test daily celebration check: {e}")
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@swagger_auto_schema(
    method='post',
    operation_description="🧪 TEST: Send welcome email to specific employee",
    operation_summary="Test Welcome Email",
    tags=['Celebrations - Test'],
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=['employee_id'],
        properties={
            'employee_id': openapi.Schema(type=openapi.TYPE_INTEGER, description='Employee ID')
        }
    ),
    responses={200: openapi.Response(description='Success')}
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def test_welcome_email(request):
    """Test welcome email for specific employee"""
    try:
        employee_id = request.data.get('employee_id')
        
        if not employee_id:
            return Response({
                'error': 'employee_id is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            employee = Employee.objects.get(id=employee_id)
        except Employee.DoesNotExist:
            return Response({
                'error': 'Employee not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        logger.info(f"🧪 Testing welcome email for {employee.first_name} {employee.last_name}")
        
        success = celebration_notification_service.send_welcome_email(employee)
        
        if success:
            return Response({
                'success': True,
                'message': f'Welcome email sent for {employee.first_name} {employee.last_name}',
                'employee': {
                    'id': employee.id,
                    'name': f'{employee.first_name} {employee.last_name}',
                    'position': str(employee.position_group) if employee.position_group else None,
                    'department': str(employee.department) if employee.department else None,
                    'start_date': employee.start_date
                }
            })
        else:
            return Response({
                'success': False,
                'error': 'Failed to send notification'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    except Exception as e:
        logger.error(f"Error in test welcome email: {e}")
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)