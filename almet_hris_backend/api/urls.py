# api/urls.py - ENHANCED: Complete URL Configuration with All Endpoints

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
# api/urls.py

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
    
     path('auth/microsoft/', views.authenticate_microsoft, name='auth_microsoft'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
   
    # User endpoints
    path('me/', views.user_info, name='user_info'),
    # Include all router URLs
    path('', include(router.urls)),
    
    # Additional custom endpoints can be added here if needed
]

# API Endpoint Documentation
"""
ENHANCED HR HEADCOUNT SYSTEM API ENDPOINTS

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
DELETE /api/employees/{id}/                 - Delete employee

POST   /api/employees/bulk_update/          - Bulk update multiple employees
POST   /api/employees/bulk_delete/          - Bulk delete multiple employees
POST   /api/employees/update_org_chart_visibility/ - Update org chart visibility
GET    /api/employees/export_csv/           - Export employees to CSV
GET    /api/employees/statistics/           - Get employee statistics
GET    /api/employees/line_managers/        - Get potential line managers list
GET    /api/employees/{id}/activities/      - Get employee activity history
POST   /api/employees/{id}/update_contract/ - Update employee contract

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
- business_function: Filter by business function IDs
- department: Filter by department IDs
- position_group: Filter by position group IDs
- line_manager: Filter by line manager IDs
- tags: Filter by tag IDs
- contract_duration: Filter by contract duration types
- start_date_from: Filter employees starting from date
- start_date_to: Filter employees starting until date
- active_only: Show only active headcount (true/false)
- org_chart_visible: Show only org chart visible employees (true/false)

Employee List Sorting:
- ordering: Comma-separated list of fields to sort by
- Prefix with '-' for descending order
- Available fields: employee_id, name, email, start_date, end_date, 
  business_function, department, job_title, position_group, status, 
  line_manager, created_at, updated_at

Examples:
GET /api/employees/?search=john&status=ACTIVE&ordering=start_date,-name
GET /api/employees/?business_function=1,2&active_only=true&ordering=position_group,name
GET /api/employees/?contract_duration=PERMANENT&start_date_from=2024-01-01

=== GRADING SYSTEM INTEGRATION ===

Position Group Grading Levels:
Each position group has shorthand codes:
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

=== CONTRACT MANAGEMENT ===

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

=== STATUS MANAGEMENT WITH COLOR HIERARCHY ===

Employee Status Types with Auto-assigned Colors:
- ACTIVE: #10B981 (Green)
- ONBOARDING: #3B82F6 (Blue)
- PROBATION: #F59E0B (Yellow)
- NOTICE_PERIOD: #EF4444 (Red)
- TERMINATED: #6B7280 (Gray)
- RESIGNED: #6B7280 (Gray)
- SUSPENDED: #DC2626 (Dark Red)
- LEAVE: #8B5CF6 (Purple)
- VACANT: #F97316 (Orange)
- INACTIVE: #9CA3AF (Light Gray)

Status Properties:
- affects_headcount: Whether status counts toward active headcount
- allows_org_chart: Whether employees appear in organizational chart

=== BULK OPERATIONS ===

Bulk Update Employee Data:
POST /api/employees/bulk_update/
{
  "employee_ids": [1, 2, 3],
  "updates": {
    "status": 2,
    "line_manager": 5,
    "is_visible_in_org_chart": true
  }
}

Bulk Delete Employees:
POST /api/employees/bulk_delete/
{
  "employee_ids": [1, 2, 3]
}

Bulk Update Grades:
POST /api/employee-grading/bulk_update_grades/
{
  "updates": [
    {"employee_id": 1, "grade": "5000", "grading_level": "MGR_UQ"},
    {"employee_id": 2, "grade": "4500", "grading_level": "MGR_M"}
  ]
}

=== VACANCY INTEGRATION ===

When creating an employee, you can link them to a vacant position:
POST /api/employees/
{
  "vacancy_id": 123,
  "employee_id": "HC001",
  "first_name": "John",
  "last_name": "Doe",
  "email": "john.doe@company.com",
  ...
}

This will automatically:
- Mark the vacant position as filled
- Link the employee to the vacancy
- Log the activity

=== ACTIVITY LOGGING ===

All significant employee changes are automatically logged:
- Employee creation/updates
- Status changes
- Manager changes
- Position changes
- Contract updates
- Document uploads
- Grade changes
- Tag additions/removals
- Bulk operations

=== CSV EXPORT ===

Export filtered employee data to CSV:
GET /api/employees/export_csv/?status=ACTIVE&business_function=1

Includes all major employee fields in a spreadsheet-friendly format.

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
"""