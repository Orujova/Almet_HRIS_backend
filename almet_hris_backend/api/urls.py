# api/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from . import views

# Create router and register viewsets
router = DefaultRouter()

# Reference data endpoints with full CRUD
router.register(r'business-functions', views.BusinessFunctionViewSet, basename='businessfunction')
router.register(r'departments', views.DepartmentViewSet, basename='department')
router.register(r'units', views.UnitViewSet, basename='unit')
router.register(r'job-functions', views.JobFunctionViewSet, basename='jobfunction')
router.register(r'position-groups', views.PositionGroupViewSet, basename='positiongroup')
router.register(r'employee-statuses', views.EmployeeStatusViewSet, basename='employeestatus')
router.register(r'employee-tags', views.EmployeeTagViewSet, basename='employeetag')

# Main employee endpoints
router.register(r'employees', views.EmployeeViewSet, basename='employee')
router.register(r'employee-documents', views.EmployeeDocumentViewSet, basename='employeedocument')
router.register(r'employee-activities', views.EmployeeActivityViewSet, basename='employeeactivity')

urlpatterns = [
    # Authentication endpoints
    path('auth/microsoft/', views.authenticate_microsoft, name='auth_microsoft'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('employees/status-dashboard/', views.status_dashboard, name='status_dashboard'),
    # User endpoints
    path('me/', views.user_info, name='user_info'),
    
    # ViewSet endpoints (includes all CRUD operations and custom actions)
    path('', include(router.urls)),
]

# Available endpoints after this configuration:

# Authentication & User:
# POST /api/auth/microsoft/ - Microsoft authentication
# POST /api/auth/refresh/ - Refresh JWT token
# GET /api/me/ - Get current user info

# Business Functions:
# GET /api/business-functions/ - List all business functions (with pagination, search, filters)
# POST /api/business-functions/ - Create new business function
# GET /api/business-functions/{id}/ - Get specific business function
# PUT /api/business-functions/{id}/ - Update business function (full)
# PATCH /api/business-functions/{id}/ - Update business function (partial)
# DELETE /api/business-functions/{id}/ - Delete business function
# GET /api/business-functions/dropdown_options/ - Get simplified dropdown data

# Departments:
# GET /api/departments/ - List all departments (with pagination, search, filters)
# POST /api/departments/ - Create new department
# GET /api/departments/{id}/ - Get specific department
# PUT /api/departments/{id}/ - Update department (full)
# PATCH /api/departments/{id}/ - Update department (partial)
# DELETE /api/departments/{id}/ - Delete department
# GET /api/departments/dropdown_options/?business_function={id} - Get departments for dropdown

# Units:
# GET /api/units/ - List all units (with pagination, search, filters)
# POST /api/units/ - Create new unit
# GET /api/units/{id}/ - Get specific unit
# PUT /api/units/{id}/ - Update unit (full)
# PATCH /api/units/{id}/ - Update unit (partial)
# DELETE /api/units/{id}/ - Delete unit
# GET /api/units/dropdown_options/?department={id} - Get units for dropdown

# Job Functions:
# GET /api/job-functions/ - List all job functions (with pagination, search, filters)
# POST /api/job-functions/ - Create new job function
# GET /api/job-functions/{id}/ - Get specific job function
# PUT /api/job-functions/{id}/ - Update job function (full)
# PATCH /api/job-functions/{id}/ - Update job function (partial)
# DELETE /api/job-functions/{id}/ - Delete job function
# GET /api/job-functions/dropdown_options/ - Get simplified dropdown data

# Position Groups:
# GET /api/position-groups/ - List all position groups (with pagination, search, filters)
# POST /api/position-groups/ - Create new position group
# GET /api/position-groups/{id}/ - Get specific position group
# PUT /api/position-groups/{id}/ - Update position group (full)
# PATCH /api/position-groups/{id}/ - Update position group (partial)
# DELETE /api/position-groups/{id}/ - Delete position group
# GET /api/position-groups/by_hierarchy/ - Get position groups ordered by hierarchy
# GET /api/position-groups/dropdown_options/ - Get simplified dropdown data ordered by hierarchy

# Employee Statuses:
# GET /api/employee-statuses/ - List all employee statuses (with pagination, search, filters)
# POST /api/employee-statuses/ - Create new employee status
# GET /api/employee-statuses/{id}/ - Get specific employee status
# PUT /api/employee-statuses/{id}/ - Update employee status (full)
# PATCH /api/employee-statuses/{id}/ - Update employee status (partial)
# DELETE /api/employee-statuses/{id}/ - Delete employee status
# GET /api/employee-statuses/dropdown_options/ - Get simplified dropdown data

# Employee Tags:
# GET /api/employee-tags/ - List all employee tags (with pagination, search, filters)
# POST /api/employee-tags/ - Create new employee tag
# GET /api/employee-tags/{id}/ - Get specific employee tag
# PUT /api/employee-tags/{id}/ - Update employee tag (full)
# PATCH /api/employee-tags/{id}/ - Update employee tag (partial)
# DELETE /api/employee-tags/{id}/ - Delete employee tag
# GET /api/employee-tags/dropdown_options/?tag_type={type} - Get tags for dropdown

# Employees (Main Entity):
# GET /api/employees/ - List employees with advanced filtering, search, pagination, sorting
# POST /api/employees/ - Create new employee
# GET /api/employees/{id}/ - Get specific employee with full details
# PUT /api/employees/{id}/ - Update employee (full)
# PATCH /api/employees/{id}/ - Update employee (partial)
# DELETE /api/employees/{id}/ - Delete employee
# GET /api/employees/filter_options/ - Get all filter dropdown options
# GET /api/employees/dropdown_search/?field={field}&search={term} - Advanced dropdown search
# GET /api/employees/org_chart/ - Get organizational chart data
# PATCH /api/employees/update_org_chart_visibility/ - Bulk update org chart visibility
# PATCH /api/employees/{id}/org_chart_visibility/ - Update single employee org chart visibility
# GET /api/employees/statistics/ - Get employee statistics for dashboard
# POST /api/employees/bulk_update/ - Bulk update multiple employees
# GET /api/employees/export_data/?format={csv|excel} - Export employee data

# Employee Documents:
# GET /api/employee-documents/ - List all documents (with pagination, search, filters)
# POST /api/employee-documents/ - Upload new document
# GET /api/employee-documents/{id}/ - Get specific document
# PUT /api/employee-documents/{id}/ - Update document (full)
# PATCH /api/employee-documents/{id}/ - Update document (partial)
# DELETE /api/employee-documents/{id}/ - Delete document

# Employee Activities:
# GET /api/employee-activities/ - List all activities (with pagination, search, filters)
# GET /api/employee-activities/{id}/ - Get specific activity
# GET /api/employee-activities/recent_activities/?limit={number} - Get recent activities
# GET /api/employee-activities/activity_summary/ - Get activity statistics

# Query Parameters for Filtering (Employees):
# ?search={term} - Global search across multiple fields
# ?employee_id={id} - Filter by employee ID
# ?name={name} - Filter by employee name
# ?email={email} - Filter by email
# ?business_function={id,id,id} - Filter by business functions (multiple)
# ?department={id,id,id} - Filter by departments (multiple)
# ?unit={id,id,id} - Filter by units (multiple)
# ?job_function={id,id,id} - Filter by job functions (multiple)
# ?position_group={id,id,id} - Filter by position groups (multiple)
# ?status={id,id,id} - Filter by statuses (multiple)
# ?tags={id,id,id} - Filter by tags (multiple)
# ?line_manager={id} - Filter by line manager
# ?line_manager_name={name} - Filter by line manager name
# ?grade={1,2,3} - Filter by grades (multiple)
# ?grade_min={number} - Filter by minimum grade
# ?grade_max={number} - Filter by maximum grade
# ?gender={MALE,FEMALE} - Filter by gender (multiple)
# ?start_date_from={YYYY-MM-DD} - Filter by start date from
# ?start_date_to={YYYY-MM-DD} - Filter by start date to
# ?end_date_from={YYYY-MM-DD} - Filter by end date from
# ?end_date_to={YYYY-MM-DD} - Filter by end date to
# ?is_visible_in_org_chart={true|false} - Filter by org chart visibility
# ?ordering={field1,field2,-field3} - Multi-level sorting (- for descending)
# ?page={number} - Page number for pagination
# ?page_size={number} - Number of items per page

# Examples of Multi-field Sorting:
# ?ordering=position_group__hierarchy_level,start_date - Sort by hierarchy level, then start date
# ?ordering=-grade,user__last_name,user__first_name - Sort by grade desc, then last name, then first name
# ?ordering=department__name,-start_date - Sort by department name, then start date descending