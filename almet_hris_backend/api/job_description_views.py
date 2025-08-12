# api/job_description_views.py

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Count, Case, When, Value
from django.db import transaction
from django.utils import timezone
from django.http import HttpResponse
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
import logging

from .job_description_models import (
    JobDescription, JobDescriptionSection, JobDescriptionSkill,
    JobDescriptionBehavioralCompetency, JobBusinessResource, AccessMatrix,
    CompanyBenefit, JobDescriptionActivity
)
from .job_description_serializers import (
    JobDescriptionListSerializer, JobDescriptionDetailSerializer,
    JobDescriptionCreateUpdateSerializer, JobDescriptionApprovalSerializer,
    JobDescriptionRejectionSerializer, JobDescriptionSubmissionSerializer,
    BulkJobDescriptionStatusUpdateSerializer, JobDescriptionStatsSerializer,
    JobDescriptionExportSerializer, JobBusinessResourceSerializer,
    AccessMatrixSerializer, CompanyBenefitSerializer, JobDescriptionActivitySerializer
)
from .competency_models import Skill, BehavioralCompetency
from .models import BusinessFunction, Department, Unit, PositionGroup, Employee

logger = logging.getLogger(__name__)


class JobDescriptionFilter:
    """Advanced filtering for job descriptions"""
    
    def __init__(self, queryset, params):
        self.queryset = queryset
        self.params = params
    
    def get_list_values(self, param_name):
        """Safely get list values from query params"""
        if hasattr(self.params, 'getlist'):
            return self.params.getlist(param_name)
        else:
            # Handle regular dict
            value = self.params.get(param_name)
            if value:
                if isinstance(value, list):
                    return value
                else:
                    return [value]
            return []
    
    def filter(self):
        queryset = self.queryset
        
        # Search across multiple fields
        search = self.params.get('search')
        if search:
            queryset = queryset.filter(
                Q(job_title__icontains=search) |
                Q(job_purpose__icontains=search) |
                Q(business_function__name__icontains=search) |
                Q(department__name__icontains=search) |
                Q(reports_to__full_name__icontains=search) |
                Q(grading_level__icontains=search)
            )
        
        # Business function filter
        business_functions = self.get_list_values('business_function')
        if business_functions:
            queryset = queryset.filter(business_function__id__in=business_functions)
        
        # Department filter
        departments = self.get_list_values('department')
        if departments:
            queryset = queryset.filter(department__id__in=departments)
        
        # Unit filter
        units = self.get_list_values('unit')
        if units:
            queryset = queryset.filter(unit__id__in=units)
        
        # Status filter
        statuses = self.get_list_values('status')
        if statuses:
            queryset = queryset.filter(status__in=statuses)
        
        # Position group filter
        position_groups = self.get_list_values('position_group')
        if position_groups:
            queryset = queryset.filter(position_group__id__in=position_groups)
        
        # Date range filters
        created_from = self.params.get('created_date_from')
        created_to = self.params.get('created_date_to')
        if created_from:
            try:
                from django.utils.dateparse import parse_date
                date_from = parse_date(created_from)
                if date_from:
                    queryset = queryset.filter(created_at__date__gte=date_from)
            except:
                pass
        if created_to:
            try:
                from django.utils.dateparse import parse_date
                date_to = parse_date(created_to)
                if date_to:
                    queryset = queryset.filter(created_at__date__lte=date_to)
            except:
                pass
        
        # Pending approval for current user
        pending_for_user = self.params.get('pending_approval_for_user')
        if pending_for_user and pending_for_user.lower() == 'true':
            user = self.params.get('request_user')
            if user:
                # Get job descriptions where user can approve
                queryset = queryset.filter(
                    Q(status='PENDING_LINE_MANAGER', reports_to__user=user) |
                    Q(status='PENDING_EMPLOYEE', assigned_employee__user=user)
                )
        
        # Version filter
        active_only = self.params.get('active_only')
        if active_only and active_only.lower() == 'true':
            queryset = queryset.filter(is_active=True)
        
        return queryset


class JobDescriptionViewSet(viewsets.ModelViewSet):
    """ViewSet for Job Description management"""
    
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['job_title', 'job_purpose', 'business_function__name', 'department__name']
    ordering_fields = ['job_title', 'created_at', 'status', 'business_function__name']
    ordering = ['-created_at']
    
    def get_queryset(self):
        return JobDescription.objects.select_related(
            'business_function', 'department', 'unit', 'position_group',
            'reports_to', 'created_by', 'updated_by',
            'line_manager_approved_by', 'employee_approved_by'
        ).prefetch_related(
            'sections', 'required_skills__skill', 'behavioral_competencies__competency',
            'business_resources__resource', 'access_rights__access_matrix',
            'company_benefits__benefit'
        ).all()
    
    def get_serializer_class(self):
        if self.action == 'list':
            return JobDescriptionListSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return JobDescriptionCreateUpdateSerializer
        else:
            return JobDescriptionDetailSerializer
    
    def list(self, request, *args, **kwargs):
        """Enhanced list with filtering"""
        try:
            queryset = self.get_queryset()
            
            # Apply custom filtering
            jd_filter = JobDescriptionFilter(queryset, request.query_params)
            jd_filter.params['request_user'] = request.user
            queryset = jd_filter.filter()
            
            # Apply ordering
            ordering = request.query_params.get('ordering', '-created_at')
            if ordering:
                queryset = queryset.order_by(ordering)
            
            # Paginate
            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)
            
            serializer = self.get_serializer(queryset, many=True)
            return Response({
                'count': queryset.count(),
                'results': serializer.data
            })
            
        except Exception as e:
            logger.error(f"Error in job description list: {str(e)}")
            return Response(
                {'error': f'Failed to retrieve job descriptions: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def perform_create(self, serializer):
        """Set created_by on creation"""
        serializer.save(created_by=self.request.user)
    
    def perform_update(self, serializer):
        """Set updated_by on update"""
        serializer.save(updated_by=self.request.user)
    
    @swagger_auto_schema(
        method='post',
        operation_description="Submit job description for approval workflow",
        request_body=JobDescriptionSubmissionSerializer,
        responses={200: "Submitted successfully"}
    )
    @action(detail=True, methods=['post'])
    def submit_for_approval(self, request, pk=None):
        """Submit job description for approval"""
        job_description = self.get_object()
        
        # Check if user can submit
        if job_description.created_by != request.user:
            return Response(
                {'error': 'Only the creator can submit job description for approval'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if job_description.status not in ['DRAFT', 'REVISION_REQUIRED']:
            return Response(
                {'error': f'Cannot submit job description with status: {job_description.get_status_display()}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = JobDescriptionSubmissionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            with transaction.atomic():
                # Update status to pending line manager approval
                job_description.status = 'PENDING_LINE_MANAGER'
                job_description.save()
                
                # Log activity
                JobDescriptionActivity.objects.create(
                    job_description=job_description,
                    activity_type='SUBMITTED_FOR_APPROVAL',
                    description=f"Job description submitted for approval by {request.user.get_full_name()}",
                    performed_by=request.user,
                    metadata={
                        'comments': serializer.validated_data.get('comments', ''),
                        'submit_to_line_manager': serializer.validated_data.get('submit_to_line_manager', True)
                    }
                )
                
                return Response({
                    'message': 'Job description submitted for approval',
                    'status': job_description.get_status_display(),
                    'next_approver': job_description.reports_to.line_manager.full_name if job_description.reports_to and job_description.reports_to.line_manager else 'N/A'
                })
                
        except Exception as e:
            logger.error(f"Error submitting job description: {str(e)}")
            return Response(
                {'error': f'Failed to submit job description: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @swagger_auto_schema(
        method='post',
        operation_description="Approve job description as line manager",
        request_body=JobDescriptionApprovalSerializer,
        responses={200: "Approved successfully"}
    )
    @action(detail=True, methods=['post'])
    def approve_as_line_manager(self, request, pk=None):
        """Approve job description as line manager"""
        job_description = self.get_object()
        
        if not job_description.can_be_approved_by_line_manager(request.user):
            return Response(
                {'error': 'You are not authorized to approve this job description as line manager'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = JobDescriptionApprovalSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            with transaction.atomic():
                job_description.approve_by_line_manager(
                    user=request.user,
                    comments=serializer.validated_data.get('comments', ''),
                    signature=serializer.validated_data.get('signature')
                )
                
                # Log activity
                JobDescriptionActivity.objects.create(
                    job_description=job_description,
                    activity_type='APPROVED_BY_LINE_MANAGER',
                    description=f"Approved by line manager: {request.user.get_full_name()}",
                    performed_by=request.user,
                    metadata={
                        'comments': serializer.validated_data.get('comments', ''),
                        'has_signature': bool(serializer.validated_data.get('signature'))
                    }
                )
                
                return Response({
                    'message': 'Job description approved by line manager',
                    'status': job_description.get_status_display(),
                    'next_step': 'Waiting for employee approval'
                })
                
        except Exception as e:
            logger.error(f"Error approving as line manager: {str(e)}")
            return Response(
                {'error': f'Failed to approve: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @swagger_auto_schema(
        method='post',
        operation_description="Approve job description as employee",
        request_body=JobDescriptionApprovalSerializer,
        responses={200: "Approved successfully"}
    )
    @action(detail=True, methods=['post'])
    def approve_as_employee(self, request, pk=None):
        """Approve job description as employee"""
        job_description = self.get_object()
        
        if not job_description.can_be_approved_by_employee(request.user):
            return Response(
                {'error': 'You are not authorized to approve this job description as employee'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = JobDescriptionApprovalSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            with transaction.atomic():
                job_description.approve_by_employee(
                    user=request.user,
                    comments=serializer.validated_data.get('comments', ''),
                    signature=serializer.validated_data.get('signature')
                )
                
                # Log activity
                JobDescriptionActivity.objects.create(
                    job_description=job_description,
                    activity_type='APPROVED_BY_EMPLOYEE',
                    description=f"Approved by employee: {request.user.get_full_name()}",
                    performed_by=request.user,
                    metadata={
                        'comments': serializer.validated_data.get('comments', ''),
                        'has_signature': bool(serializer.validated_data.get('signature'))
                    }
                )
                
                return Response({
                    'message': 'Job description fully approved',
                    'status': job_description.get_status_display(),
                    'completion': 'Job description approval process completed'
                })
                
        except Exception as e:
            logger.error(f"Error approving as employee: {str(e)}")
            return Response(
                {'error': f'Failed to approve: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @swagger_auto_schema(
        method='post',
        operation_description="Reject job description",
        request_body=JobDescriptionRejectionSerializer,
        responses={200: "Rejected successfully"}
    )
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Reject job description"""
        job_description = self.get_object()
        
        # Check if user can reject
        can_reject = (
            job_description.can_be_approved_by_line_manager(request.user) or
            job_description.can_be_approved_by_employee(request.user)
        )
        
        if not can_reject:
            return Response(
                {'error': 'You are not authorized to reject this job description'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = JobDescriptionRejectionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            with transaction.atomic():
                job_description.reject(
                    user=request.user,
                    reason=serializer.validated_data['reason']
                )
                
                # Log activity
                JobDescriptionActivity.objects.create(
                    job_description=job_description,
                    activity_type='REJECTED',
                    description=f"Rejected by {request.user.get_full_name()}: {serializer.validated_data['reason']}",
                    performed_by=request.user,
                    metadata={'rejection_reason': serializer.validated_data['reason']}
                )
                
                return Response({
                    'message': 'Job description rejected',
                    'status': job_description.get_status_display(),
                    'reason': serializer.validated_data['reason']
                })
                
        except Exception as e:
            logger.error(f"Error rejecting job description: {str(e)}")
            return Response(
                {'error': f'Failed to reject: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @swagger_auto_schema(
        method='post',
        operation_description="Request revision for job description",
        request_body=JobDescriptionRejectionSerializer,
        responses={200: "Revision requested successfully"}
    )
    @action(detail=True, methods=['post'])
    def request_revision(self, request, pk=None):
        """Request revision for job description"""
        job_description = self.get_object()
        
        # Check if user can request revision
        can_request = (
            job_description.can_be_approved_by_line_manager(request.user) or
            job_description.can_be_approved_by_employee(request.user)
        )
        
        if not can_request:
            return Response(
                {'error': 'You are not authorized to request revision for this job description'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = JobDescriptionRejectionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            with transaction.atomic():
                job_description.request_revision(
                    user=request.user,
                    reason=serializer.validated_data['reason']
                )
                
                # Log activity
                JobDescriptionActivity.objects.create(
                    job_description=job_description,
                    activity_type='REVISION_REQUESTED',
                    description=f"Revision requested by {request.user.get_full_name()}: {serializer.validated_data['reason']}",
                    performed_by=request.user,
                    metadata={'revision_reason': serializer.validated_data['reason']}
                )
                
                return Response({
                    'message': 'Revision requested',
                    'status': job_description.get_status_display(),
                    'reason': serializer.validated_data['reason']
                })
                
        except Exception as e:
            logger.error(f"Error requesting revision: {str(e)}")
            return Response(
                {'error': f'Failed to request revision: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def activities(self, request, pk=None):
        """Get activity history for job description"""
        job_description = self.get_object()
        activities = job_description.activities.all()[:50]  # Last 50 activities
        serializer = JobDescriptionActivitySerializer(activities, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def pending_approvals(self, request):
        """Get job descriptions pending approval for current user"""
        user = request.user
        
        # Job descriptions where user is the reports_to manager and needs to approve
        line_manager_pending = JobDescription.objects.filter(
            status='PENDING_LINE_MANAGER',
            reports_to__user=user
        ).select_related('business_function', 'department', 'assigned_employee', 'created_by')
        
        # Job descriptions where user is the assigned employee and needs to approve
        employee_pending = JobDescription.objects.filter(
            status='PENDING_EMPLOYEE',
            assigned_employee__user=user
        ).select_related('business_function', 'department', 'assigned_employee', 'created_by')
        
        line_manager_serializer = JobDescriptionListSerializer(line_manager_pending, many=True)
        employee_serializer = JobDescriptionListSerializer(employee_pending, many=True)
        
        return Response({
            'pending_as_line_manager': {
                'count': line_manager_pending.count(),
                'job_descriptions': line_manager_serializer.data
            },
            'pending_as_employee': {
                'count': employee_pending.count(),
                'job_descriptions': employee_serializer.data
            },
            'total_pending': line_manager_pending.count() + employee_pending.count()
        })
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get comprehensive job description statistics"""
        queryset = self.get_queryset()
        
        # Apply filters if provided
        jd_filter = JobDescriptionFilter(queryset, request.query_params)
        queryset = jd_filter.filter()
        
        total_job_descriptions = queryset.count()
        
        # By status
        status_stats = {}
        for status_choice in JobDescription.STATUS_CHOICES:
            status_code = status_choice[0]
            count = queryset.filter(status=status_code).count()
            if count > 0:
                status_stats[status_choice[1]] = count
        
        # By department
        department_stats = {}
        dept_counts = queryset.values('department__name').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        for item in dept_counts:
            department_stats[item['department__name']] = item['count']
        
        # By position group
        position_stats = {}
        pos_counts = queryset.values('position_group__name').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        for item in pos_counts:
            position_stats[item['position_group__name']] = item['count']
        
        # Pending approvals
        pending_approvals = queryset.filter(
            status__in=['PENDING_LINE_MANAGER', 'PENDING_EMPLOYEE']
        ).count()
        
        # Recent activities
        recent_activities = JobDescriptionActivity.objects.select_related(
            'job_description', 'performed_by'
        ).order_by('-performed_at')[:10]
        
        # Approval workflow stats
        approval_stats = {
            'pending_line_manager': queryset.filter(status='PENDING_LINE_MANAGER').count(),
            'pending_employee': queryset.filter(status='PENDING_EMPLOYEE').count(),
            'approved': queryset.filter(status='APPROVED').count(),
            'rejected': queryset.filter(status='REJECTED').count(),
            'revision_required': queryset.filter(status='REVISION_REQUIRED').count()
        }
        
        return Response({
            'total_job_descriptions': total_job_descriptions,
            'by_status': status_stats,
            'by_department': department_stats,
            'by_position_group': position_stats,
            'pending_approvals': pending_approvals,
            'recent_activities': JobDescriptionActivitySerializer(recent_activities, many=True).data,
            'approval_workflow_stats': approval_stats
        })
    
    @swagger_auto_schema(
        method='post',
        operation_description="Export job descriptions to PDF/Excel/Word",
        request_body=JobDescriptionExportSerializer,
        responses={200: "Export file"}
    )
    @action(detail=False, methods=['post'])
    def export(self, request):
        """Export job descriptions in various formats"""
        serializer = JobDescriptionExportSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        job_description_ids = serializer.validated_data.get('job_description_ids', [])
        export_format = serializer.validated_data.get('export_format', 'pdf')
        include_signatures = serializer.validated_data.get('include_signatures', True)
        include_activities = serializer.validated_data.get('include_activities', False)
        
        # Get job descriptions
        if job_description_ids:
            queryset = self.get_queryset().filter(id__in=job_description_ids)
        else:
            # Export filtered results
            queryset = self.get_queryset()
            jd_filter = JobDescriptionFilter(queryset, request.query_params)
            queryset = jd_filter.filter()
        
        try:
            if export_format == 'pdf':
                return self._export_to_pdf(queryset, include_signatures, include_activities)
            elif export_format == 'excel':
                return self._export_to_excel(queryset, include_signatures, include_activities)
            elif export_format == 'word':
                return self._export_to_word(queryset, include_signatures, include_activities)
            else:
                return Response(
                    {'error': 'Invalid export format'},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        except Exception as e:
            logger.error(f"Export failed: {str(e)}")
            return Response(
                {'error': f'Export failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _export_to_pdf(self, queryset, include_signatures, include_activities):
        """Export to PDF format"""
        from reportlab.lib.pagesizes import letter, A4
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.lib import colors
        import io
        
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        styles = getSampleStyleSheet()
        story = []
        
        # Title
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            spaceAfter=30,
            alignment=1  # Center
        )
        story.append(Paragraph("Job Descriptions Export", title_style))
        story.append(Spacer(1, 12))
        
        for job_desc in queryset:
            # Job Description Header
            story.append(Paragraph(f"<b>{job_desc.job_title}</b>", styles['Heading2']))
            story.append(Spacer(1, 6))
            
            # Basic Info Table
            data = [
                ['Department:', job_desc.department.name],
                ['Business Function:', job_desc.business_function.name],
                ['Position Group:', job_desc.position_group.get_name_display()],
                ['Grade:', job_desc.grading_level],
                ['Reports To:', job_desc.reports_to.full_name if job_desc.reports_to else 'N/A'],
                ['Status:', job_desc.get_status_display()]
            ]
            
            table = Table(data, colWidths=[2*inch, 4*inch])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            story.append(table)
            story.append(Spacer(1, 12))
            
            # Job Purpose
            story.append(Paragraph("<b>Job Purpose:</b>", styles['Heading3']))
            story.append(Paragraph(job_desc.job_purpose, styles['Normal']))
            story.append(Spacer(1, 12))
            
            # Sections
            for section in job_desc.sections.all():
                story.append(Paragraph(f"<b>{section.title}:</b>", styles['Heading3']))
                story.append(Paragraph(section.content, styles['Normal']))
                story.append(Spacer(1, 8))
            
            # Page break between job descriptions
            story.append(Spacer(1, 24))
        
        doc.build(story)
        buffer.seek(0)
        
        response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="job_descriptions_export.pdf"'
        return response
    
    def _export_to_excel(self, queryset, include_signatures, include_activities):
        """Export to Excel format"""
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment
        import io
        
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Job Descriptions"
        
        # Headers
        headers = [
            'Job Title', 'Department', 'Business Function', 'Position Group',
            'Grade', 'Reports To', 'Status', 'Job Purpose', 'Created Date',
            'Created By'
        ]
        
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
            cell.alignment = Alignment(horizontal="center")
        
        # Data
        for row, job_desc in enumerate(queryset, 2):
            ws.cell(row=row, column=1, value=job_desc.job_title)
            ws.cell(row=row, column=2, value=job_desc.department.name)
            ws.cell(row=row, column=3, value=job_desc.business_function.name)
            ws.cell(row=row, column=4, value=job_desc.position_group.get_name_display())
            ws.cell(row=row, column=5, value=job_desc.grading_level)
            ws.cell(row=row, column=6, value=job_desc.reports_to.full_name if job_desc.reports_to else '')
            ws.cell(row=row, column=7, value=job_desc.get_status_display())
            ws.cell(row=row, column=8, value=job_desc.job_purpose)
            ws.cell(row=row, column=9, value=job_desc.created_at.strftime('%Y-%m-%d'))
            ws.cell(row=row, column=10, value=job_desc.created_by.get_full_name() if job_desc.created_by else '')
        
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
        
        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        
        response = HttpResponse(
            buffer.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="job_descriptions_export.xlsx"'
        return response
    
    def _export_to_word(self, queryset, include_signatures, include_activities):
        """Export to Word format"""
        from docx import Document
        from docx.shared import Inches
        import io
        
        doc = Document()
        doc.add_heading('Job Descriptions Export', 0)
        
        for job_desc in queryset:
            doc.add_heading(job_desc.job_title, level=1)
            
            # Basic info table
            table = doc.add_table(rows=6, cols=2)
            table.style = 'Table Grid'
            
            table.cell(0, 0).text = 'Department:'
            table.cell(0, 1).text = job_desc.department.name
            table.cell(1, 0).text = 'Business Function:'
            table.cell(1, 1).text = job_desc.business_function.name
            table.cell(2, 0).text = 'Position Group:'
            table.cell(2, 1).text = job_desc.position_group.get_name_display()
            table.cell(3, 0).text = 'Grade:'
            table.cell(3, 1).text = job_desc.grading_level
            table.cell(4, 0).text = 'Reports To:'
            table.cell(4, 1).text = job_desc.reports_to.full_name if job_desc.reports_to else 'N/A'
            table.cell(5, 0).text = 'Status:'
            table.cell(5, 1).text = job_desc.get_status_display()
            
            doc.add_paragraph()
            
            # Job Purpose
            doc.add_heading('Job Purpose', level=2)
            doc.add_paragraph(job_desc.job_purpose)
            
            # Sections
            for section in job_desc.sections.all():
                doc.add_heading(section.title, level=2)
                doc.add_paragraph(section.content)
            
            doc.add_page_break()
        
        buffer = io.BytesIO()
        doc.save(buffer)
        buffer.seek(0)
        
        response = HttpResponse(
            buffer.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )
        response['Content-Disposition'] = f'attachment; filename="job_descriptions_export.docx"'
        return response


# Extra table ViewSets for CRUD operations

class JobBusinessResourceViewSet(viewsets.ModelViewSet):
    """ViewSet for Job Business Resources"""
    
    queryset = JobBusinessResource.objects.all()
    serializer_class = JobBusinessResourceSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['category', 'is_active']
    search_fields = ['name', 'description', 'category']
    ordering = ['category', 'name']
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class AccessMatrixViewSet(viewsets.ModelViewSet):
    """ViewSet for Access Matrix"""
    
    queryset = AccessMatrix.objects.all()
    serializer_class = AccessMatrixSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['access_level', 'is_active']
    search_fields = ['name', 'description', 'access_level']
    ordering = ['access_level', 'name']
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class CompanyBenefitViewSet(viewsets.ModelViewSet):
    """ViewSet for Company Benefits"""
    
    queryset = CompanyBenefit.objects.all()
    serializer_class = CompanyBenefitSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['benefit_type', 'is_active']
    search_fields = ['name', 'description', 'benefit_type']
    ordering = ['benefit_type', 'name']
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


# Statistics ViewSet
class JobDescriptionStatsViewSet(viewsets.ViewSet):
    """ViewSet for Job Description Statistics"""
    
    permission_classes = [IsAuthenticated]
    
    def list(self, request):
        """Get comprehensive statistics"""
        # This will be called by the statistics action in JobDescriptionViewSet
        pass