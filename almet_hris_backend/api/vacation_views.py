# api/vacation_views.py - Updated Vacation Management System Views

from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q, Count, Sum, Avg
from django.db import transaction
from django.http import HttpResponse
from rest_framework import status, viewsets, filters
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django_filters.rest_framework import DjangoFilterBackend
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from datetime import date, timedelta
import logging
import pandas as pd
import io
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment

from .vacation_models import (
    VacationSetting, VacationType, EmployeeVacationBalance,
    VacationRequest, VacationActivity, VacationSchedule
)
from .vacation_serializers import (
    VacationSettingSerializer, VacationTypeSerializer, EmployeeVacationBalanceSerializer,
    VacationRequestListSerializer, VacationRequestDetailSerializer, VacationRequestCreateSerializer,
    VacationRequestUpdateSerializer, VacationApprovalSerializer, VacationScheduleSerializer,
    VacationStatisticsSerializer, BulkVacationBalanceSerializer, VacationExportSerializer,
    MyVacationSummarySerializer, TeamVacationOverviewSerializer, VacationScheduleCreateSerializer
)
from .models import Employee
from .serializers import EmployeeListSerializer

logger = logging.getLogger(__name__)

class VacationPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

class VacationSettingViewSet(viewsets.ModelViewSet):
    """Vacation settings management"""
    
    queryset = VacationSetting.objects.all()
    serializer_class = VacationSettingSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None  # Settings don't need pagination
    
    def get_queryset(self):
        return VacationSetting.objects.filter(is_deleted=False).order_by('-is_active', '-created_at')
    
    def perform_create(self, serializer):
        # Deactivate other settings if this one is active
        if serializer.validated_data.get('is_active', True):
            VacationSetting.objects.filter(is_active=True).update(is_active=False)
        
        serializer.save(created_by=self.request.user)
    
    def perform_update(self, serializer):
        # Deactivate other settings if this one is active
        if serializer.validated_data.get('is_active', False):
            VacationSetting.objects.exclude(id=self.get_object().id).update(is_active=False)
        
        serializer.save()
    
    @action(detail=False, methods=['get'])
    def active(self, request):
        """Get active vacation settings"""
        active_settings = VacationSetting.get_active_settings()
        if active_settings:
            serializer = self.get_serializer(active_settings)
            return Response(serializer.data)
        else:
            return Response(
                {'message': 'No active vacation settings found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Activate specific vacation settings"""
        setting = self.get_object()
        
        # Deactivate all other settings
        VacationSetting.objects.exclude(id=setting.id).update(is_active=False)
        
        # Activate this setting
        setting.is_active = True
        setting.save()
        
        return Response({
            'message': f'Vacation settings activated successfully',
            'settings': VacationSettingSerializer(setting).data
        })

class VacationTypeViewSet(viewsets.ModelViewSet):
    """Vacation types management"""
    
    queryset = VacationType.objects.all()
    serializer_class = VacationTypeSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['is_active', 'requires_approval', 'affects_balance']
    search_fields = ['name', 'code', 'description']
    ordering = ['name']
    
    def get_queryset(self):
        return VacationType.objects.filter(is_deleted=False)

class EmployeeVacationBalanceViewSet(viewsets.ModelViewSet):
    """Employee vacation balance management"""
    
    queryset = EmployeeVacationBalance.objects.all()
    serializer_class = EmployeeVacationBalanceSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = VacationPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['year', 'employee__department', 'employee__business_function']
    search_fields = ['employee__full_name', 'employee__employee_id']
    ordering = ['-year', 'employee__employee_id']
    
    def get_queryset(self):
        return EmployeeVacationBalance.objects.filter(
            is_deleted=False,
            employee__is_deleted=False
        ).select_related('employee', 'employee__department', 'employee__business_function')
    
    @action(detail=False, methods=['get'])
    def my_balance(self, request):
        """Get current user's vacation balance"""
        try:
            user_employee = Employee.objects.get(user=request.user)
        except Employee.DoesNotExist:
            return Response({
                'error': 'User does not have an employee profile'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        year = request.query_params.get('year', date.today().year)
        
        try:
            balance = EmployeeVacationBalance.objects.get(
                employee=user_employee,
                year=year
            )
            serializer = self.get_serializer(balance)
            return Response(serializer.data)
        except EmployeeVacationBalance.DoesNotExist:
            return Response({
                'error': f'No vacation balance found for year {year}'
            }, status=status.HTTP_404_NOT_FOUND)
    
    @swagger_auto_schema(
        operation_description="Bulk upload vacation balances from Excel file",
        request_body=BulkVacationBalanceSerializer,
        responses={200: "Upload successful", 400: "Upload failed"}
    )
    @action(detail=False, methods=['post'])
    def bulk_upload(self, request):
        """Bulk upload vacation balances from Excel"""
        serializer = BulkVacationBalanceSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        file = serializer.validated_data['file']
        year = serializer.validated_data['year']
        
        try:
            # Read Excel file
            df = pd.read_excel(file)
            
            # Expected columns
            required_columns = ['employee_id', 'start_balance', 'yearly_balance']
            
            if not all(col in df.columns for col in required_columns):
                return Response({
                    'error': f'Excel file must contain columns: {", ".join(required_columns)}'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            results = {
                'total_rows': len(df),
                'successful': 0,
                'failed': 0,
                'errors': []
            }
            
            with transaction.atomic():
                for index, row in df.iterrows():
                    try:
                        employee_id = str(row['employee_id']).strip()
                        start_balance = float(row['start_balance'])
                        yearly_balance = float(row['yearly_balance'])
                        
                        # Find employee
                        try:
                            employee = Employee.objects.get(employee_id=employee_id)
                        except Employee.DoesNotExist:
                            results['errors'].append(f"Row {index + 2}: Employee {employee_id} not found")
                            results['failed'] += 1
                            continue
                        
                        # Create or update balance
                        balance, created = EmployeeVacationBalance.objects.update_or_create(
                            employee=employee,
                            year=year,
                            defaults={
                                'start_balance': start_balance,
                                'yearly_balance': yearly_balance,
                                'updated_by': request.user
                            }
                        )
                        
                        results['successful'] += 1
                        
                    except Exception as e:
                        results['errors'].append(f"Row {index + 2}: {str(e)}")
                        results['failed'] += 1
            
            return Response({
                'message': f'Upload completed: {results["successful"]} successful, {results["failed"]} failed',
                'results': results
            })
            
        except Exception as e:
            logger.error(f"Bulk upload failed: {str(e)}")
            return Response({
                'error': f'Failed to process file: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def export_template(self, request):
        """Download Excel template for bulk upload"""
        try:
            wb = Workbook()
            ws = wb.active
            ws.title = "Vacation Balances Template"
            
            # Headers
            headers = ['employee_id', 'start_balance', 'yearly_balance', 'notes']
            ws.append(headers)
            
            # Style headers
            header_font = Font(bold=True, color="FFFFFF")
            header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
            
            for cell in ws[1]:
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = Alignment(horizontal="center")
            
            # Sample data
            sample_data = ['EMP001', 25.0, 25.0, 'Annual vacation allowance']
            ws.append(sample_data)
            
            # Auto-adjust column widths
            for column in ws.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 50)
                ws.column_dimensions[column_letter].width = adjusted_width
            
            # Save to memory
            output = io.BytesIO()
            wb.save(output)
            output.seek(0)
            
            response = HttpResponse(
                output.getvalue(),
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = f'attachment; filename="vacation_balance_template_{date.today()}.xlsx"'
            
            return response
            
        except Exception as e:
            logger.error(f"Template generation failed: {str(e)}")
            return Response({
                'error': 'Failed to generate template'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class VacationRequestViewSet(viewsets.ModelViewSet):
    """Vacation requests management"""
    
    permission_classes = [IsAuthenticated]
    pagination_class = VacationPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = [
        'status', 'request_type', 'vacation_type', 'employee__department',
        'employee__business_function', 'line_manager', 'hr_representative'
    ]
    search_fields = [
        'request_id', 'employee__full_name', 'employee__employee_id', 'comment'
    ]
    ordering = ['-created_at']
    
    def get_queryset(self):
        user = self.request.user
        
        # Get user's employee profile
        try:
            user_employee = Employee.objects.get(user=user)
        except Employee.DoesNotExist:
            return VacationRequest.objects.none()
        
        # Base queryset
        queryset = VacationRequest.objects.filter(is_deleted=False).select_related(
            'employee', 'requester', 'vacation_type', 'line_manager', 'hr_representative'
        )
        
        # Filter based on user role and permissions
        view_type = self.request.query_params.get('view_type', 'my_requests')
        
        if view_type == 'my_requests':
            # Employee's own requests
            queryset = queryset.filter(employee=user_employee)
        elif view_type == 'my_team':
            # Requests from direct reports (for managers)
            queryset = queryset.filter(line_manager=user_employee)
        elif view_type == 'hr_approval':
            # Requests pending HR approval (for HR staff)
            queryset = queryset.filter(hr_representative=user_employee)
        elif view_type == 'pending_approvals':
            # All pending approvals for this user
            queryset = queryset.filter(
                Q(line_manager=user_employee, status='PENDING_LINE_MANAGER') |
                Q(hr_representative=user_employee, status='PENDING_HR')
            )
        elif view_type == 'all':
            # All requests (for admin/HR)
            # Check if user has HR privileges
            if not user_employee.department or 'HR' not in user_employee.department.name.upper():
                # Limit to own requests and team if not HR
                queryset = queryset.filter(
                    Q(employee=user_employee) | Q(line_manager=user_employee)
                )
        else:
            # Default: own requests
            queryset = queryset.filter(employee=user_employee)
        
        return queryset
    
    def get_serializer_class(self):
        if self.action == 'list':
            return VacationRequestListSerializer
        elif self.action in ['create']:
            return VacationRequestCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return VacationRequestUpdateSerializer
        else:
            return VacationRequestDetailSerializer
    
    def perform_create(self, serializer):
        """Create vacation request"""
        vacation_request = serializer.save()
        
        # Create activity log
        VacationActivity.objects.create(
            vacation_request=vacation_request,
            activity_type='CREATED',
            description=f"Request created by {vacation_request.requester.get_full_name()}",
            performed_by=vacation_request.requester
        )
        
        # Auto-submit immediate requests
        if vacation_request.request_type == 'IMMEDIATE':
            try:
                vacation_request.submit_request(self.request.user)
                
                # Log submission activity
                VacationActivity.objects.create(
                    vacation_request=vacation_request,
                    activity_type='SUBMITTED',
                    description=f"Request auto-submitted by {self.request.user.get_full_name()}",
                    performed_by=self.request.user
                )
                
            except Exception as e:
                logger.error(f"Failed to auto-submit immediate request: {str(e)}")
    
    @swagger_auto_schema(
        operation_description="Submit vacation request for approval",
        responses={200: "Request submitted successfully", 400: "Submission failed"}
    )
    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """Submit vacation request for approval"""
        vacation_request = self.get_object()
        
        try:
            vacation_request.submit_request(request.user)
            
            # Create activity log
            VacationActivity.objects.create(
                vacation_request=vacation_request,
                activity_type='SUBMITTED',
                description=f"Request submitted for approval by {request.user.get_full_name()}",
                performed_by=request.user
            )
            
            return Response({
                'message': 'Request submitted successfully',
                'status': vacation_request.status,
                'request': VacationRequestDetailSerializer(vacation_request, context={'request': request}).data
            })
            
        except Exception as e:
            logger.error(f"Failed to submit vacation request: {str(e)}")
            return Response({
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @swagger_auto_schema(
        operation_description="Approve or reject vacation request",
        request_body=VacationApprovalSerializer,
        responses={200: "Action completed successfully", 400: "Action failed"}
    )
    @action(detail=True, methods=['post'])
    def approve_reject(self, request, pk=None):
        """Approve or reject vacation request"""
        vacation_request = self.get_object()
        serializer = VacationApprovalSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        action = serializer.validated_data['action']
        comment = serializer.validated_data.get('comment', '')
        reason = serializer.validated_data.get('reason', '')
        
        try:
            # Get user's employee profile
            user_employee = Employee.objects.get(user=request.user)
            
            # Determine approval type
            if vacation_request.status == 'PENDING_LINE_MANAGER':
                if action == 'approve':
                    vacation_request.approve_by_line_manager(request.user, comment)
                    activity_type = 'APPROVED_LINE_MANAGER'
                    message = 'Request approved by line manager'
                else:
                    vacation_request.reject_by_line_manager(request.user, reason)
                    activity_type = 'REJECTED_LINE_MANAGER'
                    message = 'Request rejected by line manager'
                    
            elif vacation_request.status == 'PENDING_HR':
                if action == 'approve':
                    vacation_request.approve_by_hr(request.user, comment)
                    activity_type = 'APPROVED_HR'
                    message = 'Request approved by HR'
                else:
                    vacation_request.reject_by_hr(request.user, reason)
                    activity_type = 'REJECTED_HR'
                    message = 'Request rejected by HR'
            else:
                return Response({
                    'error': 'Request is not in a state that allows approval/rejection'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Create activity log
            VacationActivity.objects.create(
                vacation_request=vacation_request,
                activity_type=activity_type,
                description=f"{message}: {comment or reason}",
                performed_by=request.user,
                metadata={'action': action, 'comment': comment, 'reason': reason}
            )
            
            return Response({
                'message': message,
                'status': vacation_request.status,
                'request': VacationRequestDetailSerializer(vacation_request, context={'request': request}).data
            })
            
        except Employee.DoesNotExist:
            return Response({
                'error': 'User does not have an employee profile'
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Failed to process approval/rejection: {str(e)}")
            return Response({
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['get'])
    def conflicts(self, request, pk=None):
        """Get conflicting vacation requests and schedules"""
        vacation_request = self.get_object()
        
        conflicting_requests = vacation_request.get_conflicting_requests()
        conflicting_schedules = vacation_request.get_conflicting_schedules()
        
        return Response({
            'conflicting_requests': VacationRequestListSerializer(
                conflicting_requests, 
                many=True, 
                context={'request': request}
            ).data,
            'conflicting_schedules': VacationScheduleSerializer(
                conflicting_schedules, 
                many=True
            ).data,
            'total_conflicts': conflicting_requests.count() + conflicting_schedules.count()
        })
    
    @action(detail=False, methods=['get'])
    def dashboard_stats(self, request):
        """Get dashboard statistics for current user"""
        try:
            user_employee = Employee.objects.get(user=request.user)
        except Employee.DoesNotExist:
            return Response({
                'error': 'User does not have an employee profile'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        current_year = date.today().year
        
        # Get current balance
        try:
            current_balance = EmployeeVacationBalance.objects.get(
                employee=user_employee,
                year=current_year
            )
            balance_data = {
                'total_balance': float(current_balance.total_balance),
                'yearly_balance': float(current_balance.yearly_balance),
                'used_days': float(current_balance.used_days),
                'remaining_balance': float(current_balance.remaining_balance),
                'scheduled_days': float(current_balance.scheduled_days),
                'should_be_planned': float(current_balance.should_be_planned)
            }
        except EmployeeVacationBalance.DoesNotExist:
            balance_data = {
                'total_balance': 0,
                'yearly_balance': 0,
                'used_days': 0,
                'remaining_balance': 0,
                'scheduled_days': 0,
                'should_be_planned': 0
            }
        
        # Get pending approvals count (if manager or HR)
        pending_approvals_count = VacationRequest.objects.filter(
            Q(line_manager=user_employee, status='PENDING_LINE_MANAGER') |
            Q(hr_representative=user_employee, status='PENDING_HR'),
            is_deleted=False
        ).count()
        
        # Get upcoming schedules count
        upcoming_schedules_count = VacationSchedule.objects.filter(
            employee=user_employee,
            start_date__gte=date.today(),
            status='SCHEDULED',
            is_deleted=False
        ).count()
        
        return Response({
            'balance': balance_data,
            'pending_approvals_count': pending_approvals_count,
            'upcoming_schedules_count': upcoming_schedules_count
        })

class VacationScheduleViewSet(viewsets.ModelViewSet):
    """Vacation schedules management"""
    
    permission_classes = [IsAuthenticated]
    pagination_class = VacationPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['status', 'vacation_type', 'employee__department']
    search_fields = ['employee__full_name', 'employee__employee_id', 'notes']
    ordering = ['start_date']
    
    def get_queryset(self):
        user = self.request.user
        
        # Get user's employee profile
        try:
            user_employee = Employee.objects.get(user=user)
        except Employee.DoesNotExist:
            return VacationSchedule.objects.none()
        
        # Base queryset
        queryset = VacationSchedule.objects.filter(is_deleted=False).select_related(
            'employee', 'vacation_type'
        )
        
        # Filter based on user role
        view_type = self.request.query_params.get('view_type', 'my_schedules')
        
        if view_type == 'my_schedules':
            queryset = queryset.filter(employee=user_employee)
        elif view_type == 'my_team':
            # Schedules for direct reports
            team_members = Employee.objects.filter(line_manager=user_employee)
            queryset = queryset.filter(employee__in=team_members)
        elif view_type == 'my_peers':
            # Schedules for peers (same department or line manager)
            peers = Employee.objects.filter(
                Q(department=user_employee.department) | 
                Q(line_manager=user_employee.line_manager),
                status__affects_headcount=True,
                is_deleted=False
            ).exclude(id=user_employee.id)
            queryset = queryset.filter(employee__in=peers)
        elif view_type == 'upcoming':
            # Upcoming schedules for user
            queryset = queryset.filter(
                employee=user_employee,
                start_date__gte=date.today()
            )
        elif view_type == 'all':
            # All schedules (for HR/admin)
            if not user_employee.department or 'HR' not in user_employee.department.name.upper():
                # Limit to own and team if not HR
                team_members = Employee.objects.filter(line_manager=user_employee)
                queryset = queryset.filter(
                    Q(employee=user_employee) | Q(employee__in=team_members)
                )
        
        return queryset
    
    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return VacationScheduleCreateSerializer
        return VacationScheduleSerializer
    
    def perform_create(self, serializer):
        """Create vacation schedule"""
        schedule = serializer.save(created_by=self.request.user)
        
        # Create activity log
        VacationActivity.objects.create(
            vacation_schedule=schedule,
            activity_type='SCHEDULE_CREATED',
            description=f"Schedule created by {self.request.user.get_full_name()}",
            performed_by=self.request.user
        )
    
    def perform_update(self, serializer):
        """Update vacation schedule"""
        old_schedule = self.get_object()
        
        # Track edit count
        serializer.validated_data['edit_count'] = old_schedule.edit_count + 1
        serializer.validated_data['last_edited_at'] = timezone.now()
        serializer.validated_data['last_edited_by'] = self.request.user
        
        schedule = serializer.save()
        
        # Create activity log
        VacationActivity.objects.create(
            vacation_schedule=schedule,
            activity_type='SCHEDULE_EDITED',
            description=f"Schedule edited by {self.request.user.get_full_name()}",
            performed_by=self.request.user
        )
    
    @action(detail=True, methods=['post'])
    def register_as_taken(self, request, pk=None):
        """Register scheduled vacation as taken"""
        schedule = self.get_object()
        
        if schedule.status != 'SCHEDULED':
            return Response({
                'error': 'Only scheduled vacations can be registered'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            with transaction.atomic():
                # Update balance
                balance = schedule.get_employee_balance()
                if balance:
                    balance.use_days(schedule.number_of_days)
                
                # Update schedule status
                schedule.status = 'REGISTERED'
                schedule.save()
                
                # Create activity log
                VacationActivity.objects.create(
                    vacation_schedule=schedule,
                    activity_type='REGISTERED',
                    description=f"Schedule registered as taken by {request.user.get_full_name()}",
                    performed_by=request.user
                )
            
            return Response({
                'message': 'Schedule registered as taken successfully',
                'schedule': VacationScheduleSerializer(schedule).data
            })
            
        except Exception as e:
            logger.error(f"Failed to register schedule: {str(e)}")
            return Response({
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['get'])
    def conflicts(self, request, pk=None):
        """Get conflicting schedules for this schedule"""
        schedule = self.get_object()
        conflicting_schedules = schedule.get_conflicting_schedules()
        
        return Response({
            'conflicts': VacationScheduleSerializer(conflicting_schedules, many=True).data,
            'total_conflicts': conflicting_schedules.count()
        })

class VacationStatisticsViewSet(viewsets.ViewSet):
    """Vacation statistics and analytics"""
    
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def overview(self, request):
        """Get vacation system overview statistics"""
        try:
            user_employee = Employee.objects.get(user=request.user)
        except Employee.DoesNotExist:
            return Response({
                'error': 'User does not have an employee profile'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        current_year = date.today().year
        
        # Total requests
        total_requests = VacationRequest.objects.filter(is_deleted=False).count()
        pending_requests = VacationRequest.objects.filter(
            status__in=['PENDING_LINE_MANAGER', 'PENDING_HR'],
            is_deleted=False
        ).count()
        approved_requests = VacationRequest.objects.filter(
            status='APPROVED',
            is_deleted=False
        ).count()
        rejected_requests = VacationRequest.objects.filter(
            status__in=['REJECTED_LINE_MANAGER', 'REJECTED_HR'],
            is_deleted=False
        ).count()
        
        # Status breakdown
        status_breakdown = {}
        status_counts = VacationRequest.objects.filter(is_deleted=False).values('status').annotate(count=Count('id'))
        for item in status_counts:
            status_breakdown[item['status']] = item['count']
        
        # Type breakdown
        type_breakdown = {}
        type_counts = VacationRequest.objects.filter(is_deleted=False).values('vacation_type__name').annotate(count=Count('id'))
        for item in type_counts:
            type_breakdown[item['vacation_type__name']] = item['count']
        
        # Monthly trends (last 12 months)
        monthly_trends = []
        start_date = date.today().replace(day=1) - timedelta(days=365)
        
        for i in range(12):
            month_start = start_date.replace(month=start_date.month + i if start_date.month + i <= 12 else start_date.month + i - 12,
                                          year=start_date.year if start_date.month + i <= 12 else start_date.year + 1)
            next_month = month_start.replace(month=month_start.month + 1 if month_start.month < 12 else 1,
                                          year=month_start.year if month_start.month < 12 else month_start.year + 1)
            
            count = VacationRequest.objects.filter(
                created_at__gte=month_start,
                created_at__lt=next_month,
                is_deleted=False
            ).count()
            
            monthly_trends.append({
                'month': month_start.strftime('%Y-%m'),
                'requests': count
            })
        
        # Balance statistics
        balance_stats = {}
        current_balances = EmployeeVacationBalance.objects.filter(year=current_year, is_deleted=False)
        
        if current_balances.exists():
            balance_stats = {
                'total_employees_with_balance': current_balances.count(),
                'average_remaining_balance': current_balances.aggregate(
                    avg_remaining=Avg('yearly_balance') - Avg('used_days') - Avg('scheduled_days')
                )['avg_remaining'] or 0,
                'total_used_days': current_balances.aggregate(Sum('used_days'))['used_days__sum'] or 0,
                'total_scheduled_days': current_balances.aggregate(Sum('scheduled_days'))['scheduled_days__sum'] or 0,
            }
        
        stats_data = {
            'total_requests': total_requests,
            'pending_requests': pending_requests,
            'approved_requests': approved_requests,
            'rejected_requests': rejected_requests,
            'status_breakdown': status_breakdown,
            'type_breakdown': type_breakdown,
            'monthly_trends': monthly_trends,
            'balance_stats': balance_stats
        }
        
        return Response(stats_data)
    
    @action(detail=False, methods=['get'])
    def department_analysis(self, request):
        """Get vacation statistics by department"""
        department_id = request.query_params.get('department_id')
        year = request.query_params.get('year', date.today().year)
        
        queryset = VacationRequest.objects.filter(is_deleted=False, start_date__year=year)
        
        if department_id:
            queryset = queryset.filter(employee__department_id=department_id)
        
        # Department breakdown
        dept_stats = queryset.values('employee__department__name').annotate(
            total_requests=Count('id'),
            approved_requests=Count('id', filter=Q(status='APPROVED')),
            pending_requests=Count('id', filter=Q(status__in=['PENDING_LINE_MANAGER', 'PENDING_HR'])),
            rejected_requests=Count('id', filter=Q(status__in=['REJECTED_LINE_MANAGER', 'REJECTED_HR']))
        ).order_by('employee__department__name')
        
        return Response({
            'department_statistics': list(dept_stats),
            'year': year,
            'total_departments': dept_stats.count()
        })