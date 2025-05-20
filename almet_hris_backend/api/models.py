# api/models.py

from django.db import models
from django.contrib.auth.models import User

class MicrosoftUser(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='microsoft_user')
    microsoft_id = models.CharField(max_length=255, unique=True)
    access_token = models.TextField(blank=True, null=True)
    refresh_token = models.TextField(blank=True, null=True)
    token_expires = models.DateTimeField(blank=True, null=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.microsoft_id}"

class Employee(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    employee_id = models.CharField(max_length=50, unique=True)
    department = models.CharField(max_length=100)
    position = models.CharField(max_length=100)
    hire_date = models.DateField()
    
    def __str__(self):
        return f"{self.user.first_name} {self.user.last_name} - {self.position}"

class Department(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    manager = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, related_name='managed_departments')
    
    def __str__(self):
        return self.name