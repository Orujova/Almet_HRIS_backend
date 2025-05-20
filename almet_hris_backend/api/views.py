# Backend problemi: views.py - EmployeeViewSet sinfi əlavə edildi

from django.shortcuts import render
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework import status, viewsets
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
import logging

from .models import Employee, Department, MicrosoftUser
from .serializers import EmployeeSerializer, DepartmentSerializer, UserSerializer
from .auth import MicrosoftTokenValidator

# Set up logger
logger = logging.getLogger(__name__)

@api_view(['POST'])
@permission_classes([AllowAny])
def authenticate_microsoft(request):
    """
    Authenticate with Microsoft token from frontend
    """
    id_token = request.data.get('id_token')
    
    if not id_token:
        logger.warning('Microsoft authentication attempt without ID token')
        return Response({"error": "ID token is required"}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        logger.info('Microsoft authentication attempt - validating token')
        # Validate token and get/create user
        user = MicrosoftTokenValidator.validate_token(id_token)
        
        logger.info(f'Token validated successfully for user: {user.username}')
        
        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        
        return Response({
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
            }
        })
    
    except Exception as e:
        logger.error(f'Microsoft authentication error: {str(e)}')
        return Response({"error": str(e)}, status=status.HTTP_401_UNAUTHORIZED)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_info(request):
    """
    Get current user info
    """
    serializer = UserSerializer(request.user)
    
    # Check if user has an employee profile
    try:
        employee = Employee.objects.get(user=request.user)
        employee_data = EmployeeSerializer(employee).data
    except Employee.DoesNotExist:
        employee_data = None
    
    return Response({
        'user': serializer.data,
        'employee': employee_data
    })

# Bu sinif əlavə edildi - urls.py-da istinad edilən EmployeeViewSet sinfi
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

# Bu sinif də əlavə edildi - urls.py-da istinad edilən DepartmentViewSet
class DepartmentViewSet(viewsets.ModelViewSet):
    """
    API endpoint for departments
    """
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    permission_classes = [IsAuthenticated]