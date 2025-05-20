# api/serializers.py

from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Employee, Department, MicrosoftUser

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']
        read_only_fields = ['id', 'username']

class MicrosoftUserSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = MicrosoftUser
        fields = ['id', 'user', 'microsoft_id']
        read_only_fields = ['id', 'microsoft_id']

class EmployeeSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = Employee
        fields = ['id', 'user', 'employee_id', 'department', 'position', 'hire_date']

class DepartmentSerializer(serializers.ModelSerializer):
    manager_name = serializers.CharField(source='manager.user.get_full_name', read_only=True)
    
    class Meta:
        model = Department
        fields = ['id', 'name', 'description', 'manager', 'manager_name']