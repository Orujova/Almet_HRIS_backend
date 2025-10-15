# api/job_description_models.py - UPDATED: Smart employee selection based on organizational hierarchy

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import MinLengthValidator
import uuid
import logging

logger = logging.getLogger(__name__)

def normalize_grading_level(grading_level):
        """
        Normalize grading level for comparison
        Removes underscores and spaces, converts to uppercase
        Examples: '_M' -> 'M', 'm' -> 'M', ' M ' -> 'M'
        """
        if not grading_level:
            return ""
        
        # Remove underscores, spaces, and convert to uppercase
        normalized = grading_level.strip().replace('_', '').replace(' ', '').upper()
        return normalized
class JobDescription(models.Model):
    """FIXED: Job Description with complete job title validation"""
    
    # Primary fields
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job_title = models.CharField(max_length=200, verbose_name="Job Title")
    
    # Hierarchical and organizational data
    business_function = models.ForeignKey(
        'BusinessFunction', 
        on_delete=models.CASCADE,
        verbose_name="Business Function"
    )
    department = models.ForeignKey(
        'Department', 
        on_delete=models.CASCADE,
        verbose_name="Department"
    )
    unit = models.ForeignKey(
        'Unit', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        verbose_name="Unit"
    )
    job_function = models.ForeignKey(
        'JobFunction',
        on_delete=models.CASCADE,
        verbose_name="Job Function"
    )
    position_group = models.ForeignKey(
        'PositionGroup', 
        on_delete=models.CASCADE,
        verbose_name="Position Group/Hierarchy"
    )
    grading_level = models.CharField(
        max_length=10, 
        help_text="Grading level from position group"
    )
    
    # Employee assignment
    assigned_employee = models.ForeignKey(
    'Employee',
    on_delete=models.CASCADE,
    null=True,  # EKLE
    blank=True,  # EKLE
    related_name='assigned_job_descriptions',
    verbose_name="Assigned Employee"
)
    
    # Auto-assigned manager
    reports_to = models.ForeignKey(
        'Employee', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='subordinate_job_descriptions',
        verbose_name="Reports To"
    )
    
    # Job details
    job_purpose = models.TextField(
        validators=[MinLengthValidator(5)],
        help_text="Main purpose and objectives of the role"
    )
    
    # Status and approval
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('PENDING_LINE_MANAGER', 'Pending Line Manager Approval'),
        ('PENDING_EMPLOYEE', 'Pending Employee Approval'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('REVISION_REQUIRED', 'Revision Required'),
    ]
    
    status = models.CharField(
        max_length=25, 
        choices=STATUS_CHOICES, 
        default='DRAFT'
    )
    
    # Approval workflow fields
    line_manager_approved_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='line_manager_approved_job_descriptions'
    )
    line_manager_approved_at = models.DateTimeField(null=True, blank=True)
    line_manager_comments = models.TextField(blank=True)
    
    employee_approved_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='employee_approved_job_descriptions'
    )
    employee_approved_at = models.DateTimeField(null=True, blank=True)
    employee_comments = models.TextField(blank=True)
    
    # Digital signatures
    line_manager_signature = models.FileField(
        upload_to='job_descriptions/signatures/line_managers/',
        null=True, 
        blank=True
    )
    employee_signature = models.FileField(
        upload_to='job_descriptions/signatures/employees/',
        null=True, 
        blank=True
    )
    
    # Metadata
    created_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True,
        related_name='created_job_descriptions'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True,
        related_name='updated_job_descriptions'
    )
    
    # Version control
    version = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'job_descriptions'
        verbose_name = 'Job Description'
        verbose_name_plural = 'Job Descriptions'
        ordering = ['-created_at']
    
    def __str__(self):
        employee_name = self.assigned_employee.full_name if self.assigned_employee else 'No Employee'
        return f"{self.job_title} - {employee_name} ({self.status})"
    
   
    
    
    @classmethod
    def get_eligible_employees_with_priority(cls, job_title=None, business_function_id=None, 
                                           department_id=None, unit_id=None, job_function_id=None, 
                                           position_group_id=None, grading_level=None):
        """COMPLETELY REWRITTEN: Get employees matching ALL criteria with detailed logging"""
        from .models import Employee
        import logging
        logger = logging.getLogger(__name__)
       
        logger.info(f"\n{'='*80}")
        logger.info(f"🔍 EMPLOYEE SEARCH STARTED")
        logger.info(f"{'='*80}")
        logger.info(f"Search Criteria:")
        logger.info(f"  📋 Job Title: '{job_title}'")
        logger.info(f"  🏢 Business Function ID: {business_function_id}")
        logger.info(f"  🏬 Department ID: {department_id}")
        logger.info(f"  🏪 Unit ID: {unit_id}")
        logger.info(f"  💼 Job Function ID: {job_function_id}")
        logger.info(f"  📊 Position Group ID: {position_group_id}")
        logger.info(f"  🎯 Grading Level: '{grading_level}'")
        logger.info(f"{'='*80}\n")
        
        # Start with all active employees
        queryset = Employee.objects.filter(
            is_deleted=False
        ).select_related(
            'business_function', 'department', 'unit', 'job_function', 
            'position_group', 'line_manager'
        )
        
        initial_count = queryset.count()
        logger.info(f"📊 STEP 0: Starting with {initial_count} total active employees\n")
        
        # 1. JOB TITLE FILTER - MOST CRITICAL
        if job_title:
            job_title_clean = job_title.strip()
            before = queryset.count()
            queryset = queryset.filter(job_title__iexact=job_title_clean)
            after = queryset.count()
            
            logger.info(f"📋 STEP 1: Job Title Filter")
            logger.info(f"  Searching for: '{job_title_clean}'")
            logger.info(f"  Result: {before} → {after} employees")
            
            if after == 0:
                logger.error(f"  ❌ ZERO employees found with job title '{job_title_clean}'")
                
                # Show what job titles exist
                all_titles = list(Employee.objects.filter(
                    is_deleted=False
                ).values_list('job_title', flat=True).distinct()[:30])
                logger.error(f"  Available job titles in database: {all_titles}")
                
                return Employee.objects.none()
            else:
                logger.info(f"  ✅ Found {after} employees with job title '{job_title_clean}'")
                for emp in queryset[:5]:
                    logger.info(f"    - {emp.full_name} ({emp.employee_id})")
            logger.info("")
        
        # 2. BUSINESS FUNCTION FILTER
        if business_function_id:
            before = queryset.count()
            queryset = queryset.filter(business_function_id=business_function_id)
            after = queryset.count()
            logger.info(f"🏢 STEP 2: Business Function Filter")
            logger.info(f"  Filter: business_function_id = {business_function_id}")
            logger.info(f"  Result: {before} → {after} employees")
            if after > 0:
                logger.info(f"  ✅ {after} employees remain")
            else:
                logger.error(f"  ❌ NO employees in this business function")
            logger.info("")
        
        # 3. DEPARTMENT FILTER
        # 3. DEPARTMENT FILTER - FLEXIBLE: Match by NAME, not strict ID
        if department_id:
            before = queryset.count()
            
            # Get the department object to find its name
            try:
                from .models import Department
                target_dept = Department.objects.get(id=department_id)
                dept_name = target_dept.name
                
                logger.info(f"🏬 STEP 3: Department Filter")
                logger.info(f"  Target: department_id={department_id}, name='{dept_name}'")
                logger.info(f"  Strategy: Match by NAME (flexible - any BF with this dept name)")
                
                # Show what employees have before filtering
                if before > 0 and before <= 5:
                    logger.info(f"  Employees BEFORE filter:")
                    for emp in queryset:
                        emp_dept_id = emp.department.id if emp.department else None
                        emp_dept_name = emp.department.name if emp.department else 'None'
                        emp_bf_name = emp.business_function.name if emp.business_function else 'None'
                        logger.info(f"    - {emp.full_name}: dept_id={emp_dept_id}, dept_name='{emp_dept_name}', BF='{emp_bf_name}'")
                
                # 🔥 KEY CHANGE: Filter by department NAME, not ID
                queryset = queryset.filter(department__name__iexact=dept_name)
                after = queryset.count()
                
                logger.info(f"  Result: {before} → {after} employees (matched by dept name '{dept_name}')")
                
                if after > 0:
                    logger.info(f"  ✅ {after} employees in departments named '{dept_name}'")
                    # Show which departments they're in
                    dept_ids = queryset.values_list('department_id', flat=True).distinct()
                    logger.info(f"     Found in department IDs: {list(dept_ids)}")
                else:
                    logger.error(f"  ❌ NO employees in any department named '{dept_name}'")
                    
            except Exception as dept_error:
                logger.error(f"  ⚠️  Error in flexible dept filter: {str(dept_error)}")
                logger.error(f"     Falling back to strict department_id filter")
                queryset = queryset.filter(department_id=department_id)
                after = queryset.count()
                logger.info(f"  Fallback result: {before} → {after} employees")
            
            logger.info("")
        
        # 4. UNIT FILTER (optional)
        if unit_id:
            before = queryset.count()
            queryset = queryset.filter(unit_id=unit_id)
            after = queryset.count()
            logger.info(f"🏪 STEP 4: Unit Filter")
            logger.info(f"  Filter: unit_id = {unit_id}")
            logger.info(f"  Result: {before} → {after} employees")
            logger.info("")
        
        # 5. JOB FUNCTION FILTER
        if job_function_id:
            before = queryset.count()
            queryset = queryset.filter(job_function_id=job_function_id)
            after = queryset.count()
            logger.info(f"💼 STEP 5: Job Function Filter")
            logger.info(f"  Filter: job_function_id = {job_function_id}")
            logger.info(f"  Result: {before} → {after} employees")
            if after > 0:
                logger.info(f"  ✅ {after} employees remain")
            else:
                logger.error(f"  ❌ NO employees in this job function")
            logger.info("")
        
        # 6. POSITION GROUP FILTER
        # 6. POSITION GROUP FILTER
        if position_group_id:
            before = queryset.count()
            
            logger.info(f"📊 STEP 6: Position Group Filter")
            logger.info(f"  Target position_group_id: {position_group_id}")
            logger.info(f"  Employees BEFORE filter: {before}")
            
            # DEBUG: Show what position groups the remaining employees have
            if before > 0:
                logger.info(f"  Current employees and their Position Groups:")
                try:
                    remaining_employees = list(queryset)  # Convert to list first
                    for emp in remaining_employees:
                        try:
                            emp_pg_id = emp.position_group.id if emp.position_group else None
                            emp_pg_name = emp.position_group.name if emp.position_group else 'None'
                            logger.info(f"    - {emp.full_name} ({emp.employee_id}): PG_ID={emp_pg_id}, PG_Name='{emp_pg_name}'")
                        except Exception as emp_error:
                            logger.error(f"    - Error reading {emp.full_name}: {str(emp_error)}")
                except Exception as list_error:
                    logger.error(f"  ❌ Error listing employees: {str(list_error)}")
            else:
                logger.warning(f"  ⚠️  No employees to check (before={before})")
            
            # Apply filter
            queryset = queryset.filter(position_group_id=position_group_id)
            after = queryset.count()
            
            logger.info(f"  Result: {before} → {after} employees")
            if after > 0:
                logger.info(f"  ✅ {after} employees remain")
            else:
                logger.error(f"  ❌ NO employees match position_group_id = {position_group_id}")
                logger.error(f"  🔍 This means the {before} employee(s) have DIFFERENT position group IDs!")
        
        # 7. GRADING LEVEL FILTER - Special handling with normalization
        if grading_level:
            grading_level_clean = grading_level.strip()
            normalized_target = normalize_grading_level(grading_level_clean)
            
            logger.info(f"🎯 STEP 7: Grading Level Filter")
            logger.info(f"  Target: '{grading_level_clean}' (normalized: '{normalized_target}')")
            
            # Manual filtering with normalization
            all_remaining = list(queryset)
            matching_ids = []
            
            logger.info(f"  Checking {len(all_remaining)} employees:")
            for emp in all_remaining:
                emp_grade = emp.grading_level.strip() if emp.grading_level else ""
                emp_normalized = normalize_grading_level(emp_grade)
                
                if emp_normalized == normalized_target:
                    matching_ids.append(emp.id)
                    logger.info(f"    ✅ {emp.full_name} ({emp.employee_id}): grade '{emp_grade}' MATCHES")
                else:
                    logger.info(f"    ❌ {emp.full_name} ({emp.employee_id}): grade '{emp_grade}' ≠ '{grading_level_clean}'")
            
            before = queryset.count()
            queryset = queryset.filter(id__in=matching_ids)
            after = queryset.count()
            logger.info(f"  Result: {before} → {after} employees")
            logger.info("")
        
        # FINAL RESULT
        final_count = queryset.count()
        logger.info(f"\n{'='*80}")
        logger.info(f"🎯 FINAL RESULT: {final_count} MATCHING EMPLOYEES FOUND")
        logger.info(f"{'='*80}")
        
        if final_count > 0:
            logger.info(f"✅ Matched Employees:")
            for idx, emp in enumerate(queryset[:10], 1):
                manager = emp.line_manager.full_name if emp.line_manager else "NO MANAGER"
                logger.info(f"  {idx}. {emp.full_name} ({emp.employee_id}) - {emp.job_title}")
                logger.info(f"     Manager: {manager}")
                logger.info(f"     Business Function: {emp.business_function.name if emp.business_function else 'N/A'}")
                logger.info(f"     Department: {emp.department.name if emp.department else 'N/A'}")
        else:
            logger.error(f"❌ NO EMPLOYEES MATCHED ALL CRITERIA")
        
        logger.info(f"{'='*80}\n")
        
        return queryset.order_by('line_manager_id', 'employee_id')
    @classmethod 
    def get_eligible_employees(cls, job_title=None, business_function=None, department=None, 
                             unit=None, job_function=None, position_group=None, grading_level=None):
        """Wrapper method for backward compatibility"""
        job_title_str = job_title
        business_function_id = business_function.id if hasattr(business_function, 'id') else business_function
        department_id = department.id if hasattr(department, 'id') else department  
        unit_id = unit.id if hasattr(unit, 'id') else unit
        job_function_id = job_function.id if hasattr(job_function, 'id') else job_function
        position_group_id = position_group.id if hasattr(position_group, 'id') else position_group
        
        return cls.get_eligible_employees_with_priority(
            job_title=job_title_str,
            business_function_id=business_function_id,
            department_id=department_id,
            unit_id=unit_id,
            job_function_id=job_function_id,
            position_group_id=position_group_id,
            grading_level=grading_level
        )
    
    def validate_employee_assignment(self):
        """FIXED: Validate employee against ALL criteria INCLUDING job title"""
        if not self.assigned_employee:
            return False, "No employee assigned"
        
        emp = self.assigned_employee
        errors = []
        
      
        # 1. JOB TITLE CHECK (Case insensitive, strip whitespace) - MOST IMPORTANT!
        if self.job_title:
            emp_title = emp.job_title.strip() if emp.job_title else ""
            jd_title = self.job_title.strip()
            if emp_title.upper() != jd_title.upper():
                errors.append(f"Job Title: Required '{jd_title}', Employee has '{emp_title}'")
                print(f"  ❌ Job Title mismatch: Required '{jd_title}' vs Employee '{emp_title}'")
            else:
                print(f"  ✅ Job Title matches: '{jd_title}'")
        
        # 2. BUSINESS FUNCTION CHECK
        if self.business_function:
            if not emp.business_function or emp.business_function.id != self.business_function.id:
                req_bf = self.business_function.name
                emp_bf = emp.business_function.name if emp.business_function else "None"
                errors.append(f"Business Function: Required '{req_bf}', Employee has '{emp_bf}'")
                print(f"  ❌ Business Function mismatch: Required '{req_bf}' vs Employee '{emp_bf}'")
            else:
                print(f"  ✅ Business Function matches: '{self.business_function.name}'")
        
        # 3. DEPARTMENT CHECK
        if self.department:
            if not emp.department or emp.department.id != self.department.id:
                req_dept = self.department.name
                emp_dept = emp.department.name if emp.department else "None"
                errors.append(f"Department: Required '{req_dept}', Employee has '{emp_dept}'")
                print(f"  ❌ Department mismatch: Required '{req_dept}' vs Employee '{emp_dept}'")
            else:
                print(f"  ✅ Department matches: '{self.department.name}'")
        
        # 4. UNIT CHECK (optional)
        if self.unit:
            if not emp.unit or emp.unit.id != self.unit.id:
                req_unit = self.unit.name
                emp_unit = emp.unit.name if emp.unit else "None"
                errors.append(f"Unit: Required '{req_unit}', Employee has '{emp_unit}'")
                print(f"  ❌ Unit mismatch: Required '{req_unit}' vs Employee '{emp_unit}'")
            else:
                print(f"  ✅ Unit matches: '{self.unit.name}'")
        
        # 5. JOB FUNCTION CHECK
        if self.job_function:
            if not emp.job_function or emp.job_function.id != self.job_function.id:
                req_jf = self.job_function.name
                emp_jf = emp.job_function.name if emp.job_function else "None"
                errors.append(f"Job Function: Required '{req_jf}', Employee has '{emp_jf}'")
                print(f"  ❌ Job Function mismatch: Required '{req_jf}' vs Employee '{emp_jf}'")
            else:
                print(f"  ✅ Job Function matches: '{self.job_function.name}'")
        
        # 6. POSITION GROUP CHECK
        if self.position_group:
            if not emp.position_group or emp.position_group.id != self.position_group.id:
                req_pg = self.position_group.name
                emp_pg = emp.position_group.name if emp.position_group else "None"
                errors.append(f"Position Group: Required '{req_pg}', Employee has '{emp_pg}'")
                print(f"  ❌ Position Group mismatch: Required '{req_pg}' vs Employee '{emp_pg}'")
            else:
                print(f"  ✅ Position Group matches: '{self.position_group.name}'")
        
        # 7. GRADING LEVEL CHECK
        if self.grading_level:
            emp_grade = emp.grading_level.strip() if emp.grading_level else ""
            jd_grade = self.grading_level.strip()
            
            # Normalize both for comparison
            emp_grade_normalized = normalize_grading_level(emp_grade)
            jd_grade_normalized = normalize_grading_level(jd_grade)
            
            if emp_grade_normalized != jd_grade_normalized:
                errors.append(f"Grading Level: Required '{jd_grade}', Employee has '{emp_grade}' (normalized: '{jd_grade_normalized}' vs '{emp_grade_normalized}')")
                print(f"  ❌ Grading Level mismatch: Required '{jd_grade}' vs Employee '{emp_grade}'")
                print(f"     Normalized: Required '{jd_grade_normalized}' vs Employee '{emp_grade_normalized}'")
            else:
                print(f"  ✅ Grading Level matches: '{jd_grade}' (normalized: '{jd_grade_normalized}')")
            
            if errors:
                error_msg = "; ".join(errors)
                print(f"  🚫 VALIDATION FAILED: {error_msg}")
                return False, error_msg
            
            print(f"  ✅ VALIDATION PASSED: All criteria match including job title")
            return True, "Employee matches all criteria including job title"
    
    def get_employee_matching_details(self):
        """Get detailed matching information for all criteria"""
        if not self.assigned_employee:
            return None
        
        emp = self.assigned_employee
        details = {
            'employee_info': {
                'id': emp.id,
                'name': emp.full_name,
                'employee_id': emp.employee_id
            },
            'matches': {},
            'overall_match': True,
            'mismatch_details': []
        }
        
        # JOB TITLE CHECK
        if self.job_title:
            emp_title = emp.job_title.strip() if emp.job_title else ""
            jd_title = self.job_title.strip()
            matches = (emp_title.upper() == jd_title.upper())
            
            details['matches']['job_title'] = {
                'required': jd_title,
                'employee_has': emp_title,
                'matches': matches
            }
            
            if not matches:
                details['overall_match'] = False
                details['mismatch_details'].append(f"Job Title: Required '{jd_title}', Employee has '{emp_title}'")
        
        # BUSINESS FUNCTION CHECK
        if self.business_function:
            req_bf = self.business_function.name
            emp_bf = emp.business_function.name if emp.business_function else "None"
            matches = (emp.business_function and emp.business_function.id == self.business_function.id)
            
            details['matches']['business_function'] = {
                'required': req_bf,
                'employee_has': emp_bf,
                'matches': matches
            }
            
            if not matches:
                details['overall_match'] = False
                details['mismatch_details'].append(f"Business Function: Required '{req_bf}', Employee has '{emp_bf}'")
        
        # DEPARTMENT CHECK
        if self.department:
            req_dept = self.department.name
            emp_dept = emp.department.name if emp.department else "None"
            matches = (emp.department and emp.department.id == self.department.id)
            
            details['matches']['department'] = {
                'required': req_dept,
                'employee_has': emp_dept,
                'matches': matches
            }
            
            if not matches:
                details['overall_match'] = False
                details['mismatch_details'].append(f"Department: Required '{req_dept}', Employee has '{emp_dept}'")
        
        # UNIT CHECK (optional)
        if self.unit:
            req_unit = self.unit.name
            emp_unit = emp.unit.name if emp.unit else "None"
            matches = (emp.unit and emp.unit.id == self.unit.id)
            
            details['matches']['unit'] = {
                'required': req_unit,
                'employee_has': emp_unit,
                'matches': matches
            }
            
            if not matches:
                details['overall_match'] = False
                details['mismatch_details'].append(f"Unit: Required '{req_unit}', Employee has '{emp_unit}'")
        
        # JOB FUNCTION CHECK
        if self.job_function:
            req_jf = self.job_function.name
            emp_jf = emp.job_function.name if emp.job_function else "None"
            matches = (emp.job_function and emp.job_function.id == self.job_function.id)
            
            details['matches']['job_function'] = {
                'required': req_jf,
                'employee_has': emp_jf,
                'matches': matches
            }
            
            if not matches:
                details['overall_match'] = False
                details['mismatch_details'].append(f"Job Function: Required '{req_jf}', Employee has '{emp_jf}'")
        
        # POSITION GROUP CHECK
        if self.position_group:
            req_pg = self.position_group.name
            emp_pg = emp.position_group.name if emp.position_group else "None"
            matches = (emp.position_group and emp.position_group.id == self.position_group.id)
            
            details['matches']['position_group'] = {
                'required': req_pg,
                'employee_has': emp_pg,
                'matches': matches
            }
            
            if not matches:
                details['overall_match'] = False
                details['mismatch_details'].append(f"Position Group: Required '{req_pg}', Employee has '{emp_pg}'")
        
        # GRADING LEVEL CHECK
        if self.grading_level:
            emp_grade = emp.grading_level.strip() if emp.grading_level else ""
            jd_grade = self.grading_level.strip()
            
            # Normalize both for comparison
            emp_grade_normalized = normalize_grading_level(emp_grade)
            jd_grade_normalized = normalize_grading_level(jd_grade)
            matches = (emp_grade_normalized == jd_grade_normalized)
            
            details['matches']['grading_level'] = {
                'required': jd_grade,
                'employee_has': emp_grade,
                'required_normalized': jd_grade_normalized,
                'employee_normalized': emp_grade_normalized,
                'matches': matches
            }
            
            if not matches:
                details['overall_match'] = False
                details['mismatch_details'].append(f"Grading Level: Required '{jd_grade}' (norm: '{jd_grade_normalized}'), Employee has '{emp_grade}' (norm: '{emp_grade_normalized}')")
    
        return details
    
    def save(self, *args, **kwargs):
        """Auto-assign reports_to from employee's line_manager"""
        if self.assigned_employee and self.assigned_employee.line_manager:
            self.reports_to = self.assigned_employee.line_manager
        elif self.assigned_employee:
            self.reports_to = None
        
        super().save(*args, **kwargs)
    
    def get_status_display_with_color(self):
        """Get status with color coding"""
        status_colors = {
            'DRAFT': '#6B7280',
            'PENDING_LINE_MANAGER': '#F59E0B',
            'PENDING_EMPLOYEE': '#3B82F6',
            'APPROVED': '#10B981',
            'REJECTED': '#EF4444',
            'REVISION_REQUIRED': '#8B5CF6',
        }
        return {
            'status': self.get_status_display(),
            'color': status_colors.get(self.status, '#6B7280')
        }
    
    def can_be_approved_by_line_manager(self, user):
        """Check if user can approve as line manager"""
        return (
            self.status == 'PENDING_LINE_MANAGER' and 
            self.reports_to and 
            hasattr(self.reports_to, 'user') and 
            self.reports_to.user == user
        )

    def can_be_approved_by_employee(self, user):
        """Check if user can approve as employee"""
        return (
            self.status == 'PENDING_EMPLOYEE' and 
            self.assigned_employee and 
            hasattr(self.assigned_employee, 'user') and 
            self.assigned_employee.user == user
        )
    
    def get_employee_info(self):
        """Get employee information"""
        if self.assigned_employee:
            return {
                'type': 'assigned',
                'id': self.assigned_employee.id,
                'name': self.assigned_employee.full_name,
                'phone': self.assigned_employee.phone,
                'employee_id': self.assigned_employee.employee_id,
                'email': getattr(self.assigned_employee, 'email', None)
            }
        return None
    
    def get_manager_info(self):
        """Get manager information"""
        if self.reports_to:
            return {
                'id': self.reports_to.id,
                'name': self.reports_to.full_name,
                'job_title': self.reports_to.job_title,
                'employee_id': self.reports_to.employee_id
            }
        return None

class JobDescriptionSection(models.Model):
    """Flexible sections for job descriptions"""
    
    SECTION_TYPES = [
        ('CRITICAL_DUTIES', 'Critical Duties'),
        ('MAIN_KPIS', 'Main KPIs'),
        ('JOB_DUTIES', 'Job Duties'),
        ('REQUIREMENTS', 'Requirements'),
        ('CUSTOM', 'Custom Section'),
    ]
    
    job_description = models.ForeignKey(
        JobDescription, 
        on_delete=models.CASCADE,
        related_name='sections'
    )
    section_type = models.CharField(max_length=20, choices=SECTION_TYPES)
    title = models.CharField(max_length=200)
    content = models.TextField()
    order = models.PositiveIntegerField(default=0)
    
    class Meta:
        db_table = 'job_description_sections'
        ordering = ['order', 'id']
        unique_together = ['job_description', 'section_type', 'order']
    
    def __str__(self):
        return f"{self.job_description.job_title} - {self.get_section_type_display()}"

class JobDescriptionSkill(models.Model):
    """Core skills for job descriptions"""
    
    PROFICIENCY_LEVELS = [
        ('BASIC', 'Basic'),
        ('INTERMEDIATE', 'Intermediate'),
        ('ADVANCED', 'Advanced'),
        ('EXPERT', 'Expert'),
    ]
    
    job_description = models.ForeignKey(
        JobDescription, 
        on_delete=models.CASCADE,
        related_name='required_skills'
    )
    skill = models.ForeignKey(
        'Skill', 
        on_delete=models.CASCADE,
        help_text="Skill from competency system"
    )
    proficiency_level = models.CharField(
        max_length=15, 
        choices=PROFICIENCY_LEVELS,
        default='INTERMEDIATE'
    )
    is_mandatory = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'job_description_skills'
        unique_together = ['job_description', 'skill']
    
    def __str__(self):
        return f"{self.skill.name} ({self.get_proficiency_level_display()})"

class JobDescriptionBehavioralCompetency(models.Model):
    """Behavioral competencies for job descriptions"""
    
    PROFICIENCY_LEVELS = [
        ('BASIC', 'Basic'),
        ('INTERMEDIATE', 'Intermediate'),
        ('ADVANCED', 'Advanced'),
        ('EXPERT', 'Expert'),
    ]
    
    job_description = models.ForeignKey(
        JobDescription, 
        on_delete=models.CASCADE,
        related_name='behavioral_competencies'
    )
    competency = models.ForeignKey(
        'BehavioralCompetency', 
        on_delete=models.CASCADE,
        help_text="Competency from competency system"
    )
    proficiency_level = models.CharField(
        max_length=15, 
        choices=PROFICIENCY_LEVELS,
        default='INTERMEDIATE'
    )
    is_mandatory = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'job_description_behavioral_competencies'
        unique_together = ['job_description', 'competency']
    
    def __str__(self):
        return f"{self.competency.name} ({self.get_proficiency_level_display()})"

class JobBusinessResource(models.Model):
    """Business resources for job descriptions"""
    
    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        db_table = 'job_business_resources'
        ordering = ['name']
    
    def __str__(self):
        return self.name

class AccessMatrix(models.Model):
    """Access rights matrix for job descriptions"""
    
    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        db_table = 'access_matrix'
        verbose_name_plural = 'Access Matrix'
        ordering = ['name']
    
    def __str__(self):
        return self.name

class CompanyBenefit(models.Model):
    """Company benefits for job descriptions"""
    
    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        db_table = 'company_benefits'
        ordering = ['name']
    
    def __str__(self):
        return self.name

class JobDescriptionBusinessResource(models.Model):
    """Link job descriptions to business resources"""
    
    job_description = models.ForeignKey(
        JobDescription, 
        on_delete=models.CASCADE,
        related_name='business_resources'
    )
    resource = models.ForeignKey(JobBusinessResource, on_delete=models.CASCADE)
    
    class Meta:
        db_table = 'job_description_business_resources'
        unique_together = ['job_description', 'resource']

class JobDescriptionAccessMatrix(models.Model):
    """Link job descriptions to access rights"""
    
    job_description = models.ForeignKey(
        JobDescription, 
        on_delete=models.CASCADE,
        related_name='access_rights'
    )
    access_matrix = models.ForeignKey(AccessMatrix, on_delete=models.CASCADE)
    
    class Meta:
        db_table = 'job_description_access_matrix'
        unique_together = ['job_description', 'access_matrix']

class JobDescriptionCompanyBenefit(models.Model):
    """Link job descriptions to company benefits"""
    
    job_description = models.ForeignKey(
        JobDescription, 
        on_delete=models.CASCADE,
        related_name='company_benefits'
    )
    benefit = models.ForeignKey(CompanyBenefit, on_delete=models.CASCADE)
    
    class Meta:
        db_table = 'job_description_company_benefits'
        unique_together = ['job_description', 'benefit']

class JobDescriptionActivity(models.Model):
    """Activity log for job descriptions"""
    
    ACTIVITY_TYPES = [
        ('CREATED', 'Created'),
        ('UPDATED', 'Updated'),
        ('SUBMITTED_FOR_APPROVAL', 'Submitted for Approval'),
        ('APPROVED_BY_LINE_MANAGER', 'Approved by Line Manager'),
        ('APPROVED_BY_EMPLOYEE', 'Approved by Employee'),
        ('REJECTED', 'Rejected'),
        ('REVISION_REQUESTED', 'Revision Requested'),
        ('RESUBMITTED', 'Resubmitted'),
    ]
    
    job_description = models.ForeignKey(
        JobDescription, 
        on_delete=models.CASCADE,
        related_name='activities'
    )
    activity_type = models.CharField(max_length=30, choices=ACTIVITY_TYPES)
    description = models.TextField()
    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    performed_at = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        db_table = 'job_description_activities'
        ordering = ['-performed_at']
    
    def __str__(self):
        return f"{self.job_description.job_title} - {self.get_activity_type_display()}"