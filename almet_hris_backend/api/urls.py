# api/urls.py - ENHANCED: Complete URL Configuration with All Endpoints

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from . import views

# Create router for viewsets
router = DefaultRouter()

# Business Structure URLs
router.register(r'business-functions', views.BusinessFunctionViewSet, basename='businessfunction')
router.register(r'departments', views.DepartmentViewSet, basename='department')
router.register(r'units', views.UnitViewSet, basename='unit')
router.register(r'job-functions', views.JobFunctionViewSet, basename='jobfunction')
router.register(r'position-groups', views.PositionGroupViewSet, basename='positiongroup')

# Employee Management URLs
router.register(r'employees', views.EmployeeViewSet, basename='employee')
router.register(r'employee-tags', views.EmployeeTagViewSet, basename='employeetag')
router.register(r'employee-statuses', views.EmployeeStatusViewSet, basename='employeestatus')

# Vacancy Management URLs
router.register(r'vacant-positions', views.VacantPositionViewSet, basename='vacantposition')

# Organizational Chart URLs
router.register(r'org-chart', views.OrgChartViewSet, basename='orgchart')

# Headcount Analytics URLs
router.register(r'headcount-summaries', views.HeadcountSummaryViewSet, basename='headcountsummary')

# Employee Grading Integration URLs
router.register(r'employee-grading', views.EmployeeGradingViewSet, basename='employeegrading')

urlpatterns = [
    # Authentication endpoints
    path('auth/microsoft/', views.authenticate_microsoft, name='auth_microsoft'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
   
    # User endpoints
    path('me/', views.user_info, name='user_info'),
    
    # Include all router URLs
    path('', include(router.urls)),
]

# API Endpoint Documentation
"""
ENHANCED HR HEADCOUNT SYSTEM API ENDPOINTS

=== AUTHENTICATION ===
POST   /api/auth/microsoft/                - Microsoft authentication
POST   /api/auth/refresh/                  - Refresh JWT token
GET    /api/me/                           - Get current user info

=== BUSINESS STRUCTURE ===
GET    /api/business-functions/              - List all business functions
POST   /api/business-functions/              - Create business function
GET    /api/business-functions/{id}/         - Get business function details
PUT    /api/business-functions/{id}/         - Update business function
DELETE /api/business-functions/{id}/         - Delete business function

GET    /api/departments/                     - List all departments
POST   /api/departments/                     - Create department
GET    /api/departments/{id}/                - Get department details
PUT    /api/departments/{id}/                - Update department
DELETE /api/departments/{id}/                - Delete department

GET    /api/units/                          - List all units
POST   /api/units/                          - Create unit
GET    /api/units/{id}/                     - Get unit details
PUT    /api/units/{id}/                     - Update unit
DELETE /api/units/{id}/                     - Delete unit

GET    /api/job-functions/                  - List all job functions
POST   /api/job-functions/                  - Create job function
GET    /api/job-functions/{id}/             - Get job function details
PUT    /api/job-functions/{id}/             - Update job function
DELETE /api/job-functions/{id}/             - Delete job function

GET    /api/position-groups/                - List all position groups
POST   /api/position-groups/                - Create position group
GET    /api/position-groups/{id}/           - Get position group details
PUT    /api/position-groups/{id}/           - Update position group
DELETE /api/position-groups/{id}/           - Delete position group
GET    /api/position-groups/{id}/grading-levels/ - Get grading levels for position

=== EMPLOYEE MANAGEMENT ===
GET    /api/employees/                      - List employees (with advanced filtering & sorting)
POST   /api/employees/                      - Create new employee
GET    /api/employees/{id}/                 - Get employee details
PUT    /api/employees/{id}/                 - Update employee
DELETE /api/employees/{id}/                 - Soft delete employee

# Line Manager Management
POST   /api/employees/bulk_update_line_manager/    - Bulk update line manager
POST   /api/employees/update_single_line_manager/  - Update single line manager

# Tag Management
POST   /api/employees/add_tag/              - Add tag to employee
POST   /api/employees/remove_tag/           - Remove tag from employee
POST   /api/employees/bulk_add_tag/         - Add tag to multiple employees
POST   /api/employees/bulk_remove_tag/      - Remove tag from multiple employees

# Soft Delete Management
POST   /api/employees/soft_delete/          - Soft delete multiple employees
POST   /api/employees/restore/              - Restore soft-deleted employees

# Export Functions
POST   /api/employees/export_selected/      - Export selected employees (CSV/Excel)

# Status Management
POST   /api/employees/update_status/        - Update status for multiple employees
POST   /api/employees/auto_update_status/   - Auto-update statuses based on contract

# Other Actions
GET    /api/employees/statistics/           - Get employee statistics
GET    /api/employees/line_managers/        - Get potential line managers list
GET    /api/employees/{id}/activities/      - Get employee activity history

GET    /api/employee-tags/                  - List all employee tags
POST   /api/employee-tags/                  - Create employee tag
GET    /api/employee-tags/{id}/             - Get tag details
PUT    /api/employee-tags/{id}/             - Update tag
DELETE /api/employee-tags/{id}/             - Delete tag

GET    /api/employee-statuses/              - List all employee statuses
POST   /api/employee-statuses/              - Create employee status
GET    /api/employee-statuses/{id}/         - Get status details
PUT    /api/employee-statuses/{id}/         - Update status
DELETE /api/employee-statuses/{id}/         - Delete status

=== VACANCY MANAGEMENT ===
GET    /api/vacant-positions/               - List vacant positions
POST   /api/vacant-positions/               - Create vacant position
GET    /api/vacant-positions/{id}/          - Get vacancy details
PUT    /api/vacant-positions/{id}/          - Update vacancy
DELETE /api/vacant-positions/{id}/          - Delete vacancy
POST   /api/vacant-positions/{id}/mark_filled/ - Mark position as filled
GET    /api/vacant-positions/statistics/    - Get vacancy statistics

=== ORGANIZATIONAL CHART ===
GET    /api/org-chart/                      - Get org chart root nodes
GET    /api/org-chart/full_tree/            - Get complete organizational chart

=== HEADCOUNT ANALYTICS ===
GET    /api/headcount-summaries/            - List headcount summaries
GET    /api/headcount-summaries/{id}/       - Get summary details
POST   /api/headcount-summaries/generate_current/ - Generate current summary
GET    /api/headcount-summaries/latest/     - Get latest summary

=== EMPLOYEE GRADING INTEGRATION ===
GET    /api/employee-grading/               - List employees with grading info
POST   /api/employee-grading/bulk_update_grades/ - Bulk update employee grades

=== ADVANCED FILTERING OPTIONS ===

Employee List Filtering:
- search: Text search across name, employee_id, email, job_title, etc.
- status: Filter by status names (multiple values supported)
- business_function: Filter by business function IDs (multiple values)
- department: Filter by department IDs (multiple values)
- position_group: Filter by position group IDs (multiple values)
- line_manager: Filter by line manager IDs (multiple values)
- tags: Filter by tag IDs (multiple values)
- contract_duration: Filter by contract duration types (multiple values)
- start_date_from: Filter employees starting from date
- start_date_to: Filter employees starting until date
- active_only: Show only active headcount (true/false)
- org_chart_visible: Show only org chart visible employees (true/false)
- include_deleted: Include soft-deleted employees (true/false)

Employee List Sorting (Excel-like multi-field sorting):
- ordering: Comma-separated list of fields to sort by
- Prefix with '-' for descending order
- Available fields: employee_id, name, email, start_date, end_date, 
  business_function, department, unit, job_title, position_group, 
  grading_level, status, line_manager, contract_duration, 
  contract_end_date, years_of_service, created_at, updated_at

Examples:
GET /api/employees/?search=john&status=ACTIVE,PROBATION&ordering=start_date,-name
GET /api/employees/?business_function=1,2&active_only=true&ordering=position_group,name
GET /api/employees/?contract_duration=PERMANENT,1_YEAR&start_date_from=2024-01-01

=== GRADING SYSTEM INTEGRATION ===

Position Group Grading Levels:
Each position group has shorthand codes with full names:
- VC (Vice Chairman): VC_LD, VC_LQ, VC_M, VC_UQ, VC_UD
- DIR (Director): DIR_LD, DIR_LQ, DIR_M, DIR_UQ, DIR_UD
- MGR (Manager): MGR_LD, MGR_LQ, MGR_M, MGR_UQ, MGR_UD
- HOD (Head of Department): HOD_LD, HOD_LQ, HOD_M, HOD_UQ, HOD_UD
- SS (Senior Specialist): SS_LD, SS_LQ, SS_M, SS_UQ, SS_UD
- SP (Specialist): SP_LD, SP_LQ, SP_M, SP_UQ, SP_UD
- JS (Junior Specialist): JS_LD, JS_LQ, JS_M, JS_UQ, JS_UD
- BC (Blue Collar): BC_LD, BC_LQ, BC_M, BC_UQ, BC_UD

Where:
- LD = Lower Decile
- LQ = Lower Quartile
- M = Median
- UQ = Upper Quartile
- UD = Upper Decile

=== CONTRACT & STATUS MANAGEMENT ===

Contract Duration Options:
- 3_MONTHS: 3 Months
- 6_MONTHS: 6 Months
- 1_YEAR: 1 Year
- 2_YEARS: 2 Years
- 3_YEARS: 3 Years
- PERMANENT: Permanent

Auto-calculated fields:
- contract_end_date: Automatically calculated based on contract_start_date and duration
- full_name: Auto-generated from user first_name + last_name
- grading_level: Auto-assigned based on position_group (defaults to median)
- status: Auto-assigned based on start date and contract duration

Automatic Status Transitions:
- ONBOARDING: First 7 days (configurable)
- PROBATION: Based on contract duration (configurable per contract type)
- ACTIVE: After onboarding and probation periods
- INACTIVE: Based on end_date

Default Probation Durations (configurable):
- 3 Months Contract: 7 days
- 6 Months Contract: 14 days
- 1+ Year Contracts: 90 days
- Permanent: 0 days (no probation)

=== SOFT DELETE SYSTEM ===

Soft Delete Features:
- Employees are not permanently deleted, only marked as deleted
- Soft-deleted employees can be restored
- Activities are logged for all delete/restore operations
- Filtering supports including/excluding deleted employees
- Queries exclude soft-deleted by default

=== BULK OPERATIONS ===

Line Manager Operations:
POST /api/employees/bulk_update_line_manager/
{
  "employee_ids": [1, 2, 3],
  "line_manager_id": 5
}

POST /api/employees/update_single_line_manager/
{
  "employee_id": 1,
  "line_manager_id": 5
}

Tag Operations:
POST /api/employees/add_tag/
{
  "employee_id": 1,
  "tag_id": 2
}

POST /api/employees/bulk_add_tag/
{
  "employee_ids": [1, 2, 3],
  "tag_id": 2
}

Status Operations:
POST /api/employees/update_status/
{
  "employee_ids": [1, 2, 3],
  "status_id": 2
}

POST /api/employees/auto_update_status/
{
  "employee_ids": [1, 2, 3],  // Optional - if empty, updates all
  "force_update": false
}

Soft Delete Operations:
POST /api/employees/soft_delete/
{
  "employee_ids": [1, 2, 3]
}

POST /api/employees/restore/
{
  "employee_ids": [1, 2, 3]
}

Grade Updates:
POST /api/employee-grading/bulk_update_grades/
{
  "updates": [
    {"employee_id": 1, "grading_level": "MGR_UQ"},
    {"employee_id": 2, "grading_level": "MGR_M"}
  ]
}

=== EXPORT FUNCTIONALITY ===

Enhanced Export with Field Selection:
POST /api/employees/export_selected/
{
  "employee_ids": [1, 2, 3],  // Optional - if empty, exports filtered results
  "export_format": "excel",   // "excel" or "csv"
  "include_fields": [          // Optional - uses defaults if not specified
    "employee_id",
    "name", 
    "email",
    "job_title",
    "business_function_name",
    "department_name",
    "grading_display",
    "status_name",
    "start_date"
  ]
}

Available Export Fields:
- employee_id, name, email, job_title
- business_function_name, department_name, unit_name
- position_group_name, grading_display, status_name
- line_manager_name, start_date, contract_duration_display
- phone, years_of_service

Excel Export Features:
- Professional styling with headers
- Auto-adjusted column widths
- Proper formatting for dates and numbers
- Clear, readable layout

=== ACTIVITY LOGGING ===

All significant employee changes are automatically logged:
- Employee creation/updates
- Status changes (manual and automatic)
- Manager changes
- Position changes
- Contract updates
- Document uploads
- Grade changes
- Tag additions/removals
- Soft delete/restore operations
- Bulk operations

Activity Types:
- CREATED, UPDATED, STATUS_CHANGED, MANAGER_CHANGED
- POSITION_CHANGED, CONTRACT_UPDATED, DOCUMENT_UPLOADED
- GRADE_CHANGED, TAG_ADDED, TAG_REMOVED
- SOFT_DELETED, RESTORED

=== VACANCY INTEGRATION ===

When creating an employee, you can link them to a vacant position:
POST /api/employees/
{
  "vacancy_id": 123,
  "employee_id": "HC001",
  "first_name": "John",
  "last_name": "Doe",
  "email": "john.doe@company.com",
  "position_group": 3,
  "grading_level": "MGR_M",
  // ... other fields
}

This will automatically:
- Mark the vacant position as filled
- Link the employee to the vacancy
- Log the activity

=== ANALYTICS & REPORTING ===

Employee Statistics:
GET /api/employees/statistics/
Returns comprehensive breakdown by status, business function, position group, 
contract types, recent hires, upcoming contract endings, etc.

Vacancy Statistics:
GET /api/vacant-positions/statistics/
Returns open/filled vacancy counts by urgency and business function.

Headcount Summary:
GET /api/headcount-summaries/latest/
Returns latest comprehensive headcount analytics including trends and breakdowns.

=== EMPLOYEE CREATION FLOW ===

Enhanced Employee Creation:
1. Status is automatically assigned (ONBOARDING by default)
2. Grading level is auto-assigned based on position group (defaults to median)
3. Contract end date is automatically calculated
4. Full name is auto-generated from first/last name
5. Activity is logged
6. Optional vacancy linking
7. Optional document uploads (not mandatory)

Required Fields:
- employee_id, first_name, last_name, email
- business_function, department, job_function, job_title
- position_group, start_date, contract_duration
- grading_level (selected from available levels for position)

Optional Fields:
- unit, line_manager, contract_start_date
- date_of_birth, gender, address, phone
- emergency_contact, profile_image, notes
- tag_ids, vacancy_id

=== ERROR HANDLING ===

All endpoints include comprehensive error handling:
- Validation errors with detailed field-specific messages
- 404 errors for missing resources
- 400 errors for bad requests
- 500 errors for server issues (logged for debugging)
- Transaction rollback for bulk operations on error

=== PERMISSIONS ===

All endpoints require authentication:
- JWT token required in Authorization header
- Microsoft authentication supported
- Token refresh capability
- User info endpoint for current user details
"""