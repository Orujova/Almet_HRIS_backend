from django.shortcuts import render
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework import status, viewsets
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
import logging
import traceback

from .models import Employee, Department, MicrosoftUser
from .serializers import EmployeeSerializer, DepartmentSerializer, UserSerializer
from .auth import MicrosoftTokenValidator

# Set up logger
logger = logging.getLogger(__name__)

@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """
    Health check endpoint
    """
    return Response({
        'status': 'healthy',
        'message': 'HRIS Backend is running',
        'time': str(timezone.now())
    }, status=status.HTTP_200_OK)

@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def test_endpoint(request):
    """
    Test endpoint to check if backend is working
    """
    if request.method == 'GET':
        return Response({
            'status': 'Backend is working',
            'method': 'GET',
            'time': str(timezone.now())
        }, status=status.HTTP_200_OK)
    
    elif request.method == 'POST':
        return Response({
            'status': 'Backend received POST request',
            'data': request.data,
            'headers': dict(request.headers),
            'time': str(timezone.now())
        }, status=status.HTTP_200_OK)

@api_view(['POST'])
@permission_classes([AllowAny])
def authenticate_microsoft(request):
    """
    Authenticate with Microsoft token from frontend
    """
    try:
        logger.info('=== Microsoft authentication request received ===')
        logger.info(f'Request method: {request.method}')
        logger.info(f'Request headers: {dict(request.headers)}')
        logger.info(f'Request data keys: {list(request.data.keys()) if request.data else "No data"}')
        
        id_token = request.data.get('id_token')
        
        if not id_token:
            logger.warning('Microsoft authentication attempt without ID token')
            return Response({
                "error": "ID token is required",
                "success": False
            }, status=status.HTTP_400_BAD_REQUEST)
        
        logger.info('Microsoft authentication attempt - validating token')
        logger.info(f'Token length: {len(id_token)}')
        
        # Validate token and get/create user
        user = MicrosoftTokenValidator.validate_token(id_token)
        
        logger.info(f'Token validated successfully for user: {user.username}')
        
        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        refresh_token = str(refresh)
        
        logger.info(f'JWT tokens generated for user: {user.username}')
        
        response_data = {
            'success': True,
            'access': access_token,
            'refresh': refresh_token,
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'name': f"{user.first_name} {user.last_name}".strip(),
            }
        }
        
        logger.info(f'Returning successful response for user: {user.username}')
        return Response(response_data, status=status.HTTP_200_OK)
    
    except Exception as e:
        logger.error(f'Microsoft authentication error: {str(e)}')
        logger.error(f'Exception type: {type(e).__name__}')
        logger.error(f'Traceback: {traceback.format_exc()}')
        return Response({
            "error": f"Authentication failed: {str(e)}",
            "success": False,
            "details": str(e)
        }, status=status.HTTP_401_UNAUTHORIZED)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_info(request):
    """
    Get current user info
    """
    try:
        logger.info(f'User info request for user: {request.user.username}')
        
        serializer = UserSerializer(request.user)
        
        # Check if user has an employee profile
        try:
            employee = Employee.objects.get(user=request.user)
            employee_data = EmployeeSerializer(employee).data
        except Employee.DoesNotExist:
            employee_data = None
        
        return Response({
            'success': True,
            'user': serializer.data,
            'employee': employee_data
        }, status=status.HTTP_200_OK)
    
    except Exception as e:
        logger.error(f'User info error: {str(e)}')
        return Response({
            "error": f"Failed to get user info: {str(e)}",
            "success": False
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class EmployeeViewSet(viewsets.ModelViewSet):
    """
    API endpoint for employees
    """
    queryset = Employee.objects.all()
    serializer_class = EmployeeSerializer
    permission_classes = [IsAuthenticated]
    
    @swagger_auto_schema(
        operation_description="Get list of all employees",
        responses={200: EmployeeSerializer(many=True)}
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)
    
    @swagger_auto_schema(
        operation_description="Create a new employee",
        request_body=EmployeeSerializer,
        responses={201: EmployeeSerializer}
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

class DepartmentViewSet(viewsets.ModelViewSet):
    """
    API endpoint for departments
    """
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    permission_classes = [IsAuthenticated]