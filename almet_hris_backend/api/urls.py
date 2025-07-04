# api/urls.py - ENHANCED: Complete URL Configuration with Bulk Employee Creation

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
ENHANCED HR HEADCOUNT SYSTEM API ENDPOINTS WITH BULK EMPLOYEE CREATION

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

# NEW: Bulk Employee Creation
GET    /api/employees/download_template/    - Download Excel template for bulk creation
POST   /api/employees/bulk_create/          - Bulk create employees from Excel file

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

=== NEW: BULK EMPLOYEE CREATION WORKFLOW ===

Step 1: Download Template
GET    /api/employees/download_template/
- Downloads Excel template with:
  - Pre-configured headers and validation
  - Dropdown lists for Business Functions, Departments, etc.
  - Sample data row
  - Instructions sheet
  - Reference sheets with valid values
  - Data validation rules

Step 2: Fill Template
Users fill the Excel template with employee data:
- Required fields: Employee ID, Name, Email, Business Function, Department, etc.
- Optional fields: DOB, Gender, Unit, Grading Level, Line Manager, etc.
- Validation occurs in Excel with dropdowns and rules

Step 3: Upload and Create
POST   /api/employees/bulk_create/
Content-Type: multipart/form-data
{
  "file": <excel_file>
}

Response Format:
{
  "total_rows": 100,
  "successful": 95,
  "failed": 5,
  "errors": [
    "Row 15: Email john@company.com already exists",
    "Row 23: Invalid Business Function: InvalidFunc",
    "Row 45: Missing required field: Job Title"
  ],
  "created_employees": [
    {
      "employee_id": "HC001",
      "name": "John Doe", 
      "email": "john.doe@company.com"
    },
    // ... more employees
  ]
}

=== BULK EMPLOYEE CREATION FEATURES ===

Template Features:
✅ Excel template with comprehensive validation
✅ Dropdown lists for all reference data
✅ Sample data and instructions
✅ Field validation and formatting
✅ Reference sheets with current system data
✅ Maximum 1000 employees per upload

Validation Features:
✅ Duplicate detection (within file and database)
✅ Foreign key validation (departments, positions, etc.)
✅ Email format validation
✅ Date format validation (YYYY-MM-DD)
✅ Grading level validation per position group
✅ Line manager existence validation

Processing Features:
✅ Atomic transactions (all or nothing per batch)
✅ Detailed error reporting with row numbers
✅ Activity logging for all created employees
✅ Tag creation and assignment
✅ Automatic status assignment
✅ Contract end date calculation
✅ Grading level auto-assignment

Error Handling:
✅ Comprehensive validation before processing
✅ Clear error messages with row numbers
✅ Partial success reporting
✅ Transaction rollback on critical errors
✅ Detailed logging for debugging

=== EXCEL TEMPLATE STRUCTURE ===

Required Fields (marked with *):
- Employee ID*: Unique identifier (e.g., HC001)
- First Name*: Employee's first name  
- Last Name*: Employee's last name
- Email*: Unique email address
- Business Function*: Must match from dropdown
- Department*: Must exist under Business Function
- Job Function*: Must match from dropdown
- Job Title*: Position title
- Position Group*: Must match from dropdown
- Start Date*: Format YYYY-MM-DD
- Contract Duration*: From dropdown (3_MONTHS, 6_MONTHS, 1_YEAR, etc.)

Optional Fields:
- Date of Birth: Format YYYY-MM-DD
- Gender: MALE or FEMALE
- Address: Text field
- Phone: Text field
- Emergency Contact: Text field
- Unit: Must exist under Department
- Grading Level: Must be valid for Position Group (e.g., MGR_M)
- Contract Start Date: Defaults to Start Date
- Line Manager Employee ID: Must be existing employee
- Is Visible in Org Chart: TRUE or FALSE (default TRUE)
- Tag Names: Comma separated, format TYPE:Name
- Notes: Additional information

Reference Sheets in Template:
1. "Business Functions" - Available business functions
2. "Departments" - Departments by business function  
3. "Units" - Units by department
4. "Job Functions" - Available job functions
5. "Position Groups" - Position groups with grading levels
6. "Options" - Gender, contract duration, boolean options
7. "Instructions" - Detailed usage instructions

Data Validations:
- Dropdown lists for all reference fields
- Date format validation
- Email format validation
- Boolean value validation
- Text length limits

=== BULK CREATION WORKFLOW EXAMPLE ===

1. User clicks "Bulk Create Employees"
2. System shows "Download Template" button
3. User downloads Excel template with:
   - All current business functions, departments, etc.
   - Validation rules and dropdowns
   - Sample data and instructions
4. User fills template with employee data
5. User uploads completed template
6. System validates all data before processing
7. System creates employees in batches with full validation
8. System returns detailed results with:
   - Success count
   - Error details with row numbers
   - List of created employees
9. System logs all activities for audit trail

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
- M = Median (default if not specified)
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

=== BULK OPERATIONS ===

Line Manager Operations:
POST /api/employees/bulk_update_line_manager/
{
  "employee_ids": [1, 2, 3],
  "line_manager_id": 5
}

Tag Operations:
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

Bulk Employee Creation:
POST /api/employees/bulk_create/
Content-Type: multipart/form-data
- file: Excel file with employee data
- Max 1000 employees per upload
- Comprehensive validation and error reporting

Grade Updates:
POST /api/employee-grading/bulk_update_grades/
{
  "updates": [
    {"employee_id": 1, "grading_level": "MGR_UQ"},
    {"employee_id": 2, "grading_level": "MGR_M"}
  ]
}

=== ENHANCED EXPORT FUNCTIONALITY ===

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

=== BULK CREATION ERROR HANDLING ===

Common Validation Errors:
1. "Employee ID HC001 already exists" - Duplicate employee ID
2. "Email john@company.com already exists" - Duplicate email
3. "Invalid Business Function: InvalidFunc" - Non-existent business function
4. "Invalid Department: HR for Business Function: IT" - Department doesn't belong to business function
5. "Invalid Grading Level: MGR_XX for Position Group: SPECIALIST" - Invalid grading for position
6. "Line Manager not found: HC999" - Non-existent line manager
7. "Invalid Date of Birth format: 15-01-1990 (use YYYY-MM-DD)" - Wrong date format
8. "Missing required field: Job Title" - Required field empty

Success Response Example:
{
  "total_rows": 50,
  "successful": 47,
  "failed": 3,
  "errors": [
    "Row 12: Email duplicate@company.com already exists",
    "Row 25: Invalid Business Function: Sales",
    "Row 38: Missing required field: Start Date"
  ],
  "created_employees": [
    {
      "employee_id": "HC001",
      "name": "John Doe",
      "email": "john.doe@company.com"
    },
    {
      "employee_id": "HC002", 
      "name": "Jane Smith",
      "email": "jane.smith@company.com"
    }
    // ... 45 more employees
  ]
}

=== ACTIVITY LOGGING ===

All significant employee changes are automatically logged:
- Employee creation/updates (including bulk creation)
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

Bulk Creation Activity Example:
{
  "employee": employee_object,
  "activity_type": "CREATED",
  "description": "Employee John Doe was created via bulk upload",
  "performed_by": current_user,
  "metadata": {
    "bulk_creation": true,
    "row_number": 15,
    "template_file": "employee_bulk_template_2024-01-15.xlsx"
  }
}

=== VACANCY INTEGRATION ===

When creating an employee (single or bulk), you can link them to a vacant position:
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

For bulk creation, include vacancy_id in Excel template or data.
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

=== BULK CREATION BEST PRACTICES ===

Template Preparation:
1. Download latest template to ensure current reference data
2. Review instructions sheet thoroughly
3. Use provided sample data as reference
4. Validate data in Excel before upload

Data Entry Guidelines:
1. Employee IDs must be unique and follow company format
2. Use exact spelling for Business Functions, Departments, etc.
3. Date format must be YYYY-MM-DD
4. Grading levels must match position group requirements
5. Line managers must exist before assigning them
6. Remove sample data row before upload

Upload Process:
1. Start with small batches (10-50 employees) for testing
2. Review error messages carefully
3. Fix issues in Excel and re-upload
4. Monitor activity logs for verification
5. Export created employees for record keeping

Error Resolution:
1. Most errors can be fixed by updating Excel data
2. Reference data issues may require admin setup first
3. Duplicate errors require choosing different IDs/emails
4. Date format errors need YYYY-MM-DD format
5. Missing data errors need all required fields filled

=== SECURITY & PERMISSIONS ===

All endpoints require authentication:
- JWT token required in Authorization header
- Microsoft authentication supported
- Token refresh capability
- User info endpoint for current user details

Bulk creation permissions:
- Only authenticated users can download template
- Only authenticated users can upload employee data
- All activities are logged with user information
- File size limits (10MB) and row limits (1000) enforced

=== PERFORMANCE CONSIDERATIONS ===

Bulk Creation Optimization:
- Batch processing with transaction management
- Foreign key validation in batches
- Efficient duplicate detection
- Memory-efficient Excel processing
- Progress tracking for large uploads

Template Generation:
- Cached reference data for performance
- Optimized Excel generation
- Minimal memory footprint
- Fast download response

Database Operations:
- Atomic transactions for data integrity
- Bulk insert operations where possible
- Efficient foreign key lookups
- Optimized query patterns

=== ERROR HANDLING ===

All endpoints include comprehensive error handling:
- Validation errors with detailed field-specific messages
- 404 errors for missing resources
- 400 errors for bad requests
- 413 errors for file size limits
- 422 errors for validation failures
- 500 errors for server issues (logged for debugging)
- Transaction rollback for bulk operations on error

File Upload Specific Errors:
- Invalid file format (must be .xlsx or .xls)
- File too large (max 10MB)
- Too many rows (max 1000)
- Corrupted Excel file
- Missing required sheets
- Invalid data structure

=== FRONTEND INTEGRATION GUIDELINES ===

Bulk Employee Creation UI Flow:
1. Show "Bulk Create Employees" button
2. Display download template option with instructions
3. Provide file upload area with validation
4. Show progress indicator during upload
5. Display detailed results with success/error counts
6. Allow download of error report for fixing
7. Provide link to view created employees

Template Download:
- Single click download
- Clear file naming (employee_bulk_template_YYYY-MM-DD.xlsx)
- Instructions overlay or modal

File Upload:
- Drag & drop support
- File type validation
- Progress bar during upload
- Cancel option for long uploads

Results Display:
- Success/failure summary
- Expandable error list with row numbers
- List of successfully created employees
- Option to export results
- Link to employee list with new employees highlighted

Error Handling:
- User-friendly error messages
- Guidance on fixing common issues
- Option to download corrected template
- Link to help documentation

=== MAINTENANCE & MONITORING ===

Logging:
- All bulk operations logged with details
- Error tracking for common issues
- Performance metrics for optimization
- User activity monitoring

Monitoring:
- Upload success/failure rates
- Common error patterns
- Performance bottlenecks
- File size and row count trends

Maintenance:
- Regular template updates with current data
- Error message improvements
- Performance optimizations
- Feature enhancements based on usage

Data Cleanup:
- Failed upload cleanup
- Temporary file management
- Activity log archiving
- Performance data cleanup

This comprehensive bulk employee creation system provides:
✅ User-friendly Excel template with validation
✅ Robust data validation and error handling
✅ Efficient bulk processing with transaction safety
✅ Detailed reporting and activity logging
✅ Integration with existing employee management features
✅ Scalable architecture for large datasets
✅ Professional error handling and user feedback
"""