# api/admin.py

from django.contrib import admin
from .models import Employee, Department, MicrosoftUser

@admin.register(MicrosoftUser)
class MicrosoftUserAdmin(admin.ModelAdmin):
    list_display = ('user', 'microsoft_id')
    search_fields = ('user__username', 'user__email', 'microsoft_id')

@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ('employee_id', 'get_full_name', 'department', 'position', 'hire_date')
    search_fields = ('employee_id', 'user__first_name', 'user__last_name', 'department', 'position')
    list_filter = ('department', 'hire_date')
    
    def get_full_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}"
    get_full_name.short_description = 'Name'

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'manager_name')
    search_fields = ('name', 'description')
    
    def manager_name(self, obj):
        if obj.manager:
            return f"{obj.manager.user.first_name} {obj.manager.user.last_name}"
        return "No manager assigned"
    manager_name.short_description = 'Manager'