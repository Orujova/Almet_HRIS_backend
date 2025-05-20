# api/views.py

from django.shortcuts import render
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework import status, viewsets
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .models import Employee, Department, MicrosoftUser
from .serializers import EmployeeSerializer, DepartmentSerializer, UserSerializer
from .auth import MicrosoftTokenValidator

@api_view(['POST'])
@permission_classes([AllowAny])
def authenticate_microsoft(request):
    """
    Authenticate with Microsoft token from frontend
    """
    id_token = request.data.get('id_token')
    
    if not id_token:
        return Response({"error": "ID token is required"}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        # Validate token and get/create user
        user = MicrosoftTokenValidator.validate_token(id_token)
        
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