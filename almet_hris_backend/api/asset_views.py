# api/asset_views.py - SIMPLIFIED: Maintenance hissələri silinmiş

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Count, Sum, Avg
from django.db import transaction
from django.utils import timezone
from django.http import HttpResponse
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
import logging
import uuid
from datetime import datetime, timedelta
from io import BytesIO
import csv

logger = logging.getLogger(__name__)

from .asset_models import (
    AssetCategory, Asset, AssetAssignment, AssetActivity
)
from .asset_serializers import (
    AssetCategorySerializer, AssetListSerializer, AssetDetailSerializer,
    AssetCreateUpdateSerializer, AssetAssignmentSerializer, AssetAssignmentCreateSerializer,
    AssetCheckInSerializer, AssetActivitySerializer, AssetExportSerializer,AssetStatusChangeSerializer
)
from .models import Employee


class AssetFilter:
    """Advanced filtering for assets - UPDATED without removed fields"""
    
    def __init__(self, queryset, params):
        self.queryset = queryset
        if hasattr(params, 'dict'):
            self.params = params.dict()
        else:
            self.params = dict(params)
    
    def get_list_values(self, param_name):
        """Get list values from query params safely"""
        value = self.params.get(param_name)
        if not value:
            return []
        
        if isinstance(value, str):
            return [v.strip() for v in value.split(',') if v.strip()]
        elif isinstance(value, list):
            return value
        else:
            return [str(value)]
    
    def get_int_list_values(self, param_name):
        """Get integer list values"""
        string_values = self.get_list_values(param_name)
        int_values = []
        for val in string_values:
            try:
                int_values.append(int(val))
            except (ValueError, TypeError):
                continue
        return int_values
    
    def filter(self):
        queryset = self.queryset
        
   
        
        # Search filter - UPDATED to remove brand and model
        search = self.params.get('search')
        if search:
           
            queryset = queryset.filter(
                Q(asset_name__icontains=search) |
                Q(serial_number__icontains=search) |
                Q(category__name__icontains=search) |
                Q(assigned_to__full_name__icontains=search) |
                Q(assigned_to__employee_id__icontains=search)
            )
        
        # Status filter
        status_values = self.get_list_values('status')
        if status_values:
     
            queryset = queryset.filter(status__in=status_values)
        
        # Category filter
        category_ids = self.get_int_list_values('category')
        if category_ids:
        
            queryset = queryset.filter(category__id__in=category_ids)
        
        # Assigned to filter
        assigned_to_ids = self.get_int_list_values('assigned_to')
        if assigned_to_ids:
    
            queryset = queryset.filter(assigned_to__id__in=assigned_to_ids)
        
        # Department filter (through assigned employee)
        department_ids = self.get_int_list_values('department')
        if department_ids:
     
            queryset = queryset.filter(assigned_to__department__id__in=department_ids)
        
        # Purchase date range
        purchase_date_from = self.params.get('purchase_date_from')
        purchase_date_to = self.params.get('purchase_date_to')
        if purchase_date_from:
            try:
                from django.utils.dateparse import parse_date
                date_from = parse_date(purchase_date_from)
                if date_from:
                    queryset = queryset.filter(purchase_date__gte=date_from)
            except:
                pass
        if purchase_date_to:
            try:
                from django.utils.dateparse import parse_date
                date_to = parse_date(purchase_date_to)
                if date_to:
                    queryset = queryset.filter(purchase_date__lte=date_to)
            except:
                pass
        
        # Price range
        price_min = self.params.get('price_min')
        price_max = self.params.get('price_max')
        if price_min:
            try:
                min_price = float(price_min)
                queryset = queryset.filter(purchase_price__gte=min_price)
            except:
                pass
        if price_max:
            try:
                max_price = float(price_max)
                queryset = queryset.filter(purchase_price__lte=max_price)
            except:
                pass
        
        # Unassigned assets filter
        unassigned_only = self.params.get('unassigned_only')
        if unassigned_only and unassigned_only.lower() == 'true':
       
            queryset = queryset.filter(assigned_to__isnull=True)
        
        # Assigned assets filter
        assigned_only = self.params.get('assigned_only')
        if assigned_only and assigned_only.lower() == 'true':
  
            queryset = queryset.filter(assigned_to__isnull=False)
        
        final_count = queryset.count()
      
        
        return queryset

class AssetCategoryViewSet(viewsets.ModelViewSet):
    """ViewSet for Asset Categories"""
    
    queryset = AssetCategory.objects.all()
    serializer_class = AssetCategorySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['is_active']
    search_fields = ['name', 'description']
    ordering = ['name']
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

class AssetViewSet(viewsets.ModelViewSet):
    """ViewSet for Asset management - UPDATED"""
    
    queryset = Asset.objects.select_related(
        'category', 'assigned_to', 'created_by', 'updated_by', 'archived_by'
    ).prefetch_related(
        'assignments__employee', 'activities'
    ).all()
    
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    
    # UPDATED search_fields - removed brand and model
    search_fields = ['asset_name', 'serial_number', 'category__name']
    
    ordering_fields = ['asset_name', 'purchase_date', 'purchase_price', 'created_at', 'status']
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return AssetListSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return AssetCreateUpdateSerializer
        else:
            return AssetDetailSerializer
    
    def perform_create(self, serializer):
        """Override perform_create to set created_by"""
        asset = serializer.save()
        asset.created_by = self.request.user
        asset.save()
    
    def perform_update(self, serializer):
        """Override perform_update to set updated_by"""
        asset = serializer.save()
        asset.updated_by = self.request.user
        asset.save()
    
    def get_object(self):
        """Override get_object to handle UUID properly"""
        queryset = self.filter_queryset(self.get_queryset())
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        lookup_value = self.kwargs[lookup_url_kwarg]
        
        try:
            if len(lookup_value) == 36 and '-' in lookup_value:
                uuid_obj = uuid.UUID(lookup_value)
                filter_kwargs = {'id': uuid_obj}
            else:
                filter_kwargs = {'id': int(lookup_value)}
        except (ValueError, TypeError):
            filter_kwargs = {'id': lookup_value}
        
        try:
            obj = queryset.get(**filter_kwargs)
        except Asset.DoesNotExist:
            logger.error(f"Asset not found with lookup: {lookup_value}")
            from rest_framework.exceptions import NotFound
            raise NotFound('Asset not found.')
        except Asset.MultipleObjectsReturned:
            logger.error(f"Multiple Assets found with lookup: {lookup_value}")
            from rest_framework.exceptions import ValidationError
            raise ValidationError('Multiple assets found.')
        
        self.check_object_permissions(self.request, obj)
        return obj
    
    def list(self, request, *args, **kwargs):
        """List assets with advanced filtering"""
        queryset = self.get_queryset()
        
        # Apply custom filters
        asset_filter = AssetFilter(queryset, request.query_params)
        queryset = asset_filter.filter()
        
        # Apply ordering
        queryset = self.filter_queryset(queryset)
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    
   
    @swagger_auto_schema(
        method='post',
        operation_description="Assign asset to employee",
        request_body=AssetAssignmentCreateSerializer,
        responses={200: "Asset assigned successfully"}
    )
    @action(detail=True, methods=['post'])
    def assign_to_employee(self, request, pk=None):
        """Assign asset to an employee - UPDATED for approval workflow"""
        try:
            asset = self.get_object()
            
            if not asset.can_be_assigned():
                return Response(
                    {'error': f'Asset cannot be assigned. Current status: {asset.get_status_display()}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            serializer = AssetAssignmentCreateSerializer(
                data=request.data,
                context={'request': request}
            )
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
            with transaction.atomic():
                assignment = AssetAssignment.objects.create(
                    **serializer.validated_data,
                    assigned_by=request.user
                )
                
                # Update asset status to ASSIGNED (pending approval)
                asset = assignment.asset
                asset.status = 'ASSIGNED'  # DEYİŞİKLİK: IN_USE əvəzinə ASSIGNED
                asset.assigned_to = assignment.employee
                asset.save()
                
                # Log activities
                AssetActivity.objects.create(
                    asset=asset,
                    activity_type='ASSIGNED',
                    description=f"Asset assigned to {assignment.employee.full_name} - awaiting employee confirmation",
                    performed_by=request.user,
                    metadata={
                        'employee_id': assignment.employee.employee_id,
                        'employee_name': assignment.employee.full_name,
                        'check_out_date': assignment.check_out_date.isoformat(),
                        'condition': assignment.condition_on_checkout,
                        'status': 'PENDING_APPROVAL',
                        'awaiting_confirmation': True
                    }
                )
            
            return Response({
                'success': True,
                'message': f'Asset assigned to {assignment.employee.full_name} - awaiting employee confirmation',
                'asset_id': str(asset.id),
                'assignment_id': assignment.id,
                'employee': {
                    'id': assignment.employee.id,
                    'name': assignment.employee.full_name,
                    'employee_id': assignment.employee.employee_id
                },
                'check_out_date': assignment.check_out_date,
                'status': asset.get_status_display(),
                'requires_approval': True,
                'approval_status': 'PENDING'
            })
        except Exception as e:
            logger.error(f"Error assigning asset {pk}: {str(e)}")
            return Response(
                {'error': f'Failed to assign asset: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    @swagger_auto_schema(
        method='post',
        operation_description="Check in asset from employee",
        request_body=AssetCheckInSerializer,
        responses={200: "Asset checked in successfully"}
    )
    @action(detail=True, methods=['post'])
    def check_in_asset(self, request, pk=None):
        """Check in asset from employee"""
        try:
            asset = self.get_object()
            
            # Validate asset can be checked in
            if not asset.can_be_checked_in():
                return Response(
                    {'error': f'Asset cannot be checked in. Current status: {asset.get_status_display()}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Get active assignment
            active_assignment = asset.assignments.filter(check_in_date__isnull=True).first()
            if not active_assignment:
                return Response(
                    {'error': 'No active assignment found for this asset'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Validate request data
            serializer = AssetCheckInSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
            # Validate check-in date is not before check-out date
            check_in_date = serializer.validated_data['check_in_date']
            if check_in_date < active_assignment.check_out_date:
                return Response(
                    {'error': 'Check-in date cannot be before check-out date'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            with transaction.atomic():
                # Update assignment
                active_assignment.check_in_date = check_in_date
                active_assignment.check_in_notes = serializer.validated_data.get('check_in_notes', '')
                active_assignment.condition_on_checkin = serializer.validated_data['condition_on_checkin']
                active_assignment.checked_in_by = request.user
                active_assignment.save()
                
                # Update asset
                old_employee = asset.assigned_to
                asset.assigned_to = None
                
                # Set status based on condition
                condition = serializer.validated_data['condition_on_checkin']
                if condition == 'DAMAGED':
                    asset.status = 'IN_REPAIR'
                else:
                    asset.status = 'IN_STOCK'
                
                asset.save()
                
                # Log activity
                AssetActivity.objects.create(
                    asset=asset,
                    activity_type='CHECKED_IN',
                    description=f"Asset checked in from {old_employee.full_name} ({old_employee.employee_id})",
                    performed_by=request.user,
                    metadata={
                        'previous_employee_id': old_employee.employee_id,
                        'previous_employee_name': old_employee.full_name,
                        'check_in_date': check_in_date.isoformat(),
                        'condition_on_checkin': condition,
                        'assignment_duration_days': active_assignment.get_duration_days(),
                        'notes': serializer.validated_data.get('check_in_notes', '')
                    }
                )
                
                return Response({
                    'success': True,
                    'message': f'Asset successfully checked in from {old_employee.full_name}',
                    'asset_id': str(asset.id),
                    'assignment_id': active_assignment.id,
                    'check_in_date': check_in_date,
                    'condition': condition,
                    'duration_days': active_assignment.get_duration_days(),
                    'new_status': asset.get_status_display()
                })
                
        except Exception as e:
            logger.error(f"Error checking in asset {pk}: {str(e)}")
            return Response(
                {'error': f'Failed to check in asset: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @swagger_auto_schema(
    method='post',
    operation_description="Change asset status with optional reason",
    request_body=AssetStatusChangeSerializer,
    responses={
        200: openapi.Response(
            description="Status changed successfully",
            examples={
                "application/json": {
                    "success": True,
                    "message": "Asset status changed to In Repair",
                    "asset_id": "43f11b14-5d6e-4874-aa84-e9dea660799e",
                    "old_status": "IN_STOCK",
                    "new_status": "IN_REPAIR",
                    "reason": "Laptop screen broken",
                    "status_display": {
                        "status": "In Repair",
                        "color": "#ffc107"
                    }
                }
            }
        ),
        400: "Bad Request - Invalid status or validation error",
        404: "Asset not found",
        500: "Internal Server Error"
    }
)
    @action(detail=True, methods=['post'])
    def change_status(self, request, pk=None):
        """Change asset status - SIMPLIFIED and PRACTICAL"""
        try:
            asset = self.get_object()
            
            # Validate request data with simple serializer
            serializer = AssetStatusChangeSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(
                    {
                        'error': 'Invalid data provided',
                        'details': serializer.errors
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            new_status = serializer.validated_data['status']
            reason = serializer.validated_data.get('reason', '')
            old_status = asset.status
            
            # Check if status is actually changing
            if old_status == new_status:
                return Response(
                    {
                        'error': f'Asset is already in {asset.get_status_display()} status',
                        'current_status': new_status
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Business logic validation
            validation_error = self._validate_status_change(asset, old_status, new_status)
            if validation_error:
                return Response(
                    {'error': validation_error},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            with transaction.atomic():
                # Handle status-specific logic
                if new_status == 'ARCHIVED':
                    asset.archived_at = timezone.now()
                    asset.archived_by = request.user
                    asset.archive_reason = reason
                    asset.assigned_to = None  # Clear assignment when archiving
                    
                elif old_status == 'ARCHIVED' and new_status != 'ARCHIVED':
                    # Restoring from archive
                    asset.archived_at = None
                    asset.archived_by = None
                    asset.archive_reason = ''
                    
                elif new_status == 'IN_STOCK':
                    # Moving to stock - clear assignment
                    asset.assigned_to = None
                
                # Update status
                asset.status = new_status
                asset.save()
                
                # Log activity
                activity_type = self._get_activity_type(old_status, new_status)
                activity_description = self._get_activity_description(asset, old_status, new_status, reason)
                
                AssetActivity.objects.create(
                    asset=asset,
                    activity_type=activity_type,
                    description=activity_description,
                    performed_by=request.user,
                    metadata={
                        'old_status': old_status,
                        'new_status': new_status,
                        'reason': reason,
                        'changed_by': request.user.get_full_name() or request.user.username
                    }
                )
                
                return Response({
                    'success': True,
                    'message': f'Asset status changed to {asset.get_status_display()}',
                    'asset_id': str(asset.id),
                    'asset_name': asset.asset_name,
                    'old_status': old_status,
                    'new_status': new_status,
                    'reason': reason,
                    'status_display': asset.get_status_display_with_color(),
                    'timestamp': timezone.now().isoformat()
                })
                
        except Exception as e:
            logger.error(f"Error changing asset status {pk}: {str(e)}")
            return Response(
                {'error': f'Failed to change status: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _validate_status_change(self, asset, old_status, new_status):
        """Validate if status change is allowed"""
        
        # If asset is currently assigned, only allow certain transitions
        if asset.assigned_to:
            if new_status == 'IN_STOCK':
                return "Cannot move assigned asset to stock. Please check in the asset first."
            elif new_status == 'ARCHIVED' and old_status == 'IN_USE':
                # Allow archiving from IN_USE (will auto check-in)
                pass
        
        # Validate specific transitions
        invalid_transitions = {
            'ARCHIVED': ['IN_USE'],  # Can't go directly from archived to in use
        }
        
        if old_status in invalid_transitions:
            if new_status in invalid_transitions[old_status]:
                return f"Cannot change status from {dict(Asset.STATUS_CHOICES)[old_status]} directly to {dict(Asset.STATUS_CHOICES)[new_status]}"
        
        return None
    
    def _get_activity_type(self, old_status, new_status):
        """Get appropriate activity type for status change"""
        if new_status == 'ARCHIVED':
            return 'ARCHIVED'
        elif old_status == 'ARCHIVED':
            return 'RESTORED'
        else:
            return 'STATUS_CHANGED'
    
    def _get_activity_description(self, asset, old_status, new_status, reason):
        """Generate activity description"""
        old_display = dict(Asset.STATUS_CHOICES).get(old_status, old_status)
        new_display = dict(Asset.STATUS_CHOICES).get(new_status, new_status)
        
        description = f"Status changed from {old_display} to {new_display}"
        if reason:
            description += f". Reason: {reason}"
        
        return description
    
    @action(detail=True, methods=['get'])
    def assignment_history(self, request, pk=None):
        """Get assignment history for asset - FIXED"""
        try:
            asset = self.get_object()
            assignments = asset.assignments.all().order_by('-check_out_date')
            serializer = AssetAssignmentSerializer(assignments, many=True)
            
            # Get current assignment data properly
            current_assignment_data = None
            current_assignment = asset.get_current_assignment()
            if current_assignment:
                current_assignment_data = {
                    'employee': current_assignment['employee'],
                    'assignment_details': current_assignment['assignment']
                }
            
            return Response({
                'asset_id': str(asset.id),
                'asset_name': asset.asset_name,
                'total_assignments': assignments.count(),
                'current_assignment': current_assignment_data,
                'assignment_history': serializer.data
            })
            
        except Exception as e:
            logger.error(f"Error getting assignment history for asset {pk}: {str(e)}")
            return Response(
                {'error': f'Failed to get assignment history: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def activities(self, request, pk=None):
        """Get activity history for asset"""
        try:
            asset = self.get_object()
            activities = asset.activities.all()[:50]  # Last 50 activities
            serializer = AssetActivitySerializer(activities, many=True)
            
            return Response({
                'asset_id': str(asset.id),
                'asset_name': asset.asset_name,
                'activities': serializer.data
            })
            
        except Exception as e:
            logger.error(f"Error getting activities for asset {pk}: {str(e)}")
            return Response(
                {'error': f'Failed to get activities: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    
    @swagger_auto_schema(
    method='post',
    operation_description="Export assets to CSV or Excel format",
    request_body=AssetExportSerializer,
    responses={
        200: openapi.Response(
            description="File download (CSV or Excel)",
            content_type="application/octet-stream"
        ),
        400: "Bad Request - Invalid export parameters",
        500: "Internal Server Error"
    },
    manual_parameters=[
        openapi.Parameter(
            'export_type',
            openapi.IN_QUERY,
            description="Export type: 'all' for all assets, 'filtered' for current filters, 'selected' for specific IDs",
            type=openapi.TYPE_STRING,
            enum=['all', 'filtered', 'selected'],
            default='all'
        )
    ]
)
    @action(detail=False, methods=['post'], url_path='export')
    def export_assets(self, request):
        """Export assets to CSV or Excel format - ENHANCED with better validation"""
        try:
            # Validate request data
            serializer = AssetExportSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
            # Get base queryset
            queryset = self.get_queryset()
            
            # Determine export type
            export_type = request.query_params.get('export_type', 'all')
            asset_ids = serializer.validated_data.get('asset_ids', [])
            
            # Apply filtering based on export type
            if export_type == 'selected':
                if not asset_ids:
                    return Response(
                        {'error': 'asset_ids are required when export_type=selected'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Validate asset IDs exist
                existing_assets = queryset.filter(id__in=asset_ids)
                existing_ids = set(str(asset.id) for asset in existing_assets)
                provided_ids = set(str(id) for id in asset_ids)
                
                if len(existing_ids) != len(provided_ids):
                    missing_ids = provided_ids - existing_ids
                    return Response(
                        {
                            'error': 'Some asset IDs do not exist',
                            'missing_ids': list(missing_ids),
                            'valid_ids': list(existing_ids),
                            'provided_count': len(provided_ids),
                            'valid_count': len(existing_ids)
                        },
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                queryset = existing_assets
               
                
            elif export_type == 'filtered':
                # Export assets with current filters applied
                asset_filter = AssetFilter(queryset, request.query_params)
                queryset = asset_filter.filter()
              
                
            elif export_type == 'all':
                # Export all assets (no additional filtering)
                logger.info(f"Exporting all {queryset.count()} assets")
                
            else:
                return Response(
                    {
                        'error': 'Invalid export_type',
                        'valid_options': ['all', 'filtered', 'selected'],
                        'provided': export_type
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Apply date range filter if provided
            date_from = serializer.validated_data.get('date_range_from')
            date_to = serializer.validated_data.get('date_range_to')
            
            if date_from:
                queryset = queryset.filter(created_at__date__gte=date_from)
            if date_to:
                queryset = queryset.filter(created_at__date__lte=date_to)
            
            # Check if queryset is empty
            if not queryset.exists():
                return Response(
                    {
                        'error': 'No assets found to export with the given criteria',
                        'export_type': export_type,
                        'filters_applied': {
                            'date_from': date_from.isoformat() if date_from else None,
                            'date_to': date_to.isoformat() if date_to else None,
                            'asset_ids_count': len(asset_ids) if asset_ids else 0
                        }
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Add export metadata to options
            export_options = serializer.validated_data.copy()
            export_options.update({
                'export_type': export_type,
                'total_count': queryset.count(),
                'exported_by': request.user.get_full_name() or request.user.username,
                'export_timestamp': timezone.now()
            })
            
            return self._export_file(queryset, export_options)
                    
        except Exception as e:
            logger.error(f"Error exporting assets: {str(e)}")
            return Response(
                {
                    'error': f'Failed to export assets: {str(e)}',
                    'export_type': request.query_params.get('export_type', 'unknown'),
                    'timestamp': timezone.now().isoformat()
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _export_file(self, queryset, options):
        """Export assets to CSV or Excel based on format choice"""
        export_format = options.get('export_format', 'excel')
        
        if export_format == 'excel':
            return self._export_excel(queryset, options)
        else:
            return self._export_csv(queryset, options)
    
    def _export_excel(self, queryset, options):
        """Export assets to Excel with professional formatting - ENHANCED"""
        from django.http import HttpResponse
        from datetime import datetime
        import io
        import xlsxwriter
        
        # Create Excel file in memory
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Assets')
        
        # Define formats
        title_format = workbook.add_format({
            'bold': True,
            'font_size': 16,
            'font_color': '#1F4E79',
            'align': 'left'
        })
        
        info_format = workbook.add_format({
            'font_size': 10,
            'font_color': '#555555',
            'align': 'left'
        })
        
        header_format = workbook.add_format({
            'bold': True,
            'font_size': 12,
            'bg_color': '#4472C4',
            'font_color': 'white',
            'border': 1,
            'align': 'center',
            'valign': 'vcenter'
        })
        
        cell_format = workbook.add_format({
            'border': 1,
            'align': 'left',
            'valign': 'vcenter',
            'text_wrap': True
        })
        
        number_format = workbook.add_format({
            'border': 1,
            'align': 'right',
            'valign': 'vcenter',
            'num_format': '#,##0.00'
        })
        
        date_format = workbook.add_format({
            'border': 1,
            'align': 'center',
            'valign': 'vcenter',
            'num_format': 'dd/mm/yyyy'
        })
        
        status_formats = {
            'IN_STOCK': workbook.add_format({
                'border': 1, 'align': 'center', 'bg_color': '#E3F2FD', 'font_color': '#1976D2', 'bold': True
            }),
            'IN_USE': workbook.add_format({
                'border': 1, 'align': 'center', 'bg_color': '#E8F5E8', 'font_color': '#388E3C', 'bold': True
            }),
            'IN_REPAIR': workbook.add_format({
                'border': 1, 'align': 'center', 'bg_color': '#FFF3E0', 'font_color': '#F57C00', 'bold': True
            }),
            'ARCHIVED': workbook.add_format({
                'border': 1, 'align': 'center', 'bg_color': '#FAFAFA', 'font_color': '#757575', 'bold': True
            })
        }
        
        # Add title and metadata
        current_row = 0
   
       
        # Headers
        headers = [
            'Asset Name', 'Category', 'Serial Number', 'Status', 
            'Purchase Price (AZN)', 'Purchase Date', 'Useful Life (Years)',
            'Assigned To', 'Employee ID', 'Created Date'
        ]
        
    
        
        if options.get('include_assignments'):
            headers.extend(['Total Assignments', 'Current Assignment Days', 'Assignment Status'])
        
        # Write headers
        header_row = current_row
        for col, header in enumerate(headers):
            worksheet.write(header_row, col, header, header_format)
        
        # Set column widths
        column_widths = [25, 18, 18, 15, 18, 15, 15, 25, 15, 15]
       
        if options.get('include_assignments'):
            column_widths.extend([18, 20, 18])
        
        for col, width in enumerate(column_widths):
            worksheet.set_column(col, col, width)
        
        # Write data
        data_start_row = header_row + 1
        for row_num, asset in enumerate(queryset):
            current_row = data_start_row + row_num
            col = 0
            
            # Basic asset info
            worksheet.write(current_row, col, asset.asset_name, cell_format)
            col += 1
            worksheet.write(current_row, col, asset.category.name, cell_format)
            col += 1
            worksheet.write(current_row, col, asset.serial_number, cell_format)
            col += 1
            
            # Status with color
            status_format = status_formats.get(asset.status, cell_format)
            worksheet.write(current_row, col, asset.get_status_display(), status_format)
            col += 1
            
            # Financial info
            worksheet.write(current_row, col, float(asset.purchase_price), number_format)
            col += 1
            
            if asset.purchase_date:
                worksheet.write_datetime(current_row, col, asset.purchase_date, date_format)
            else:
                worksheet.write(current_row, col, '', cell_format)
            col += 1
            
            worksheet.write(current_row, col, asset.useful_life_years, cell_format)
            col += 1
            
            # Assignment info
            worksheet.write(current_row, col, asset.assigned_to.full_name if asset.assigned_to else '', cell_format)
            col += 1
            worksheet.write(current_row, col, asset.assigned_to.employee_id if asset.assigned_to else '', cell_format)
            col += 1
            
            # Created date
            if asset.created_at:
                worksheet.write_datetime(current_row, col, asset.created_at.date(), date_format)
            else:
                worksheet.write(current_row, col, '', cell_format)
            col += 1
            
            
            # Assignment info
            if options.get('include_assignments'):
                total_assignments = asset.assignments.count()
                worksheet.write(current_row, col, total_assignments, cell_format)
                col += 1
                
                current_assignment = asset.get_current_assignment()
                current_days = ''
                assignment_status = 'Not Assigned'
                
                if current_assignment and current_assignment['assignment']:
                    active_assignment = asset.assignments.filter(check_in_date__isnull=True).first()
                    if active_assignment:
                        current_days = active_assignment.get_duration_days()
                        assignment_status = 'Currently Assigned'
                elif total_assignments > 0:
                    assignment_status = 'Previously Assigned'
                
                worksheet.write(current_row, col, current_days, cell_format)
                col += 1
                worksheet.write(current_row, col, assignment_status, cell_format)
        
        # Add comprehensive summary section
        summary_start_row = data_start_row + queryset.count() + 2
        worksheet.write(summary_start_row, 0, 'DETAILED SUMMARY', title_format)
        summary_start_row += 1
        
        # Basic statistics
        worksheet.write(summary_start_row, 0, f'Total Assets Exported: {queryset.count()}', info_format)
        summary_start_row += 1
        
        # Status breakdown
        worksheet.write(summary_start_row, 0, 'Status Breakdown:', info_format)
        summary_start_row += 1
        
        total_value = 0
        for choice in Asset.STATUS_CHOICES:
            count = queryset.filter(status=choice[0]).count()
            if count > 0:
                status_assets = queryset.filter(status=choice[0])
                status_value = sum(float(asset.purchase_price) for asset in status_assets)
                total_value += status_value
                
                worksheet.write(summary_start_row, 0, f'  • {choice[1]}: {count} assets', info_format)
                worksheet.write(summary_start_row, 2, f'{status_value:,.2f} AZN', info_format)
                summary_start_row += 1
        
        summary_start_row += 1
        worksheet.write(summary_start_row, 0, f'Total Value: {total_value:,.2f} AZN', title_format)
        
        # Add filters (autofilter)
        worksheet.autofilter(header_row, 0, data_start_row + queryset.count() - 1, len(headers) - 1)
        
        # Freeze panes
        worksheet.freeze_panes(header_row + 1, 0)
        
        workbook.close()
        output.seek(0)
        
        # Return Excel file
        response = HttpResponse(
            output.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        export_type = options.get('export_type', 'all')
        response['Content-Disposition'] = f'attachment; filename="assets_{export_type}_export_{datetime.now().strftime("%Y%m%d_%H%M")}.xlsx"'
        
        return response
    def _export_csv(self, queryset, options):
        """Export assets to CSV - UPDATED without removed fields"""
        from django.http import HttpResponse
        from datetime import datetime
        import csv
        
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="assets_export_{datetime.now().strftime("%Y%m%d_%H%M")}.csv"'
        
        writer = csv.writer(response)
        
        # Headers - UPDATED without brand/model
        headers = [
            'Asset Name', 'Category', 'Serial Number',
            'Status', 'Purchase Price (AZN)', 'Purchase Date', 'Useful Life (Years)',
            'Assigned To', 'Employee ID', 'Created Date'
        ]
        
       
        
        if options.get('include_assignments'):
            headers.extend(['Total Assignments', 'Current Assignment Days'])
        
        writer.writerow(headers)
        
        # Data rows - UPDATED without brand/model
        for asset in queryset:
            row = [
                asset.asset_name,
                asset.category.name,
                asset.serial_number,
                asset.get_status_display(),
                str(asset.purchase_price),
                asset.purchase_date.strftime('%Y-%m-%d') if asset.purchase_date else '',
                asset.useful_life_years,
                asset.assigned_to.full_name if asset.assigned_to else '',
                asset.assigned_to.employee_id if asset.assigned_to else '',
                asset.created_at.strftime('%Y-%m-%d') if asset.created_at else ''
            ]
            
           
            
            if options.get('include_assignments'):
                total_assignments = asset.assignments.count()
                current_assignment = asset.get_current_assignment()
                current_days = ''
                if current_assignment and current_assignment['assignment']:
                    active_assignment = asset.assignments.filter(check_in_date__isnull=True).first()
                    if active_assignment:
                        current_days = str(active_assignment.get_duration_days())
                
                row.extend([total_assignments, current_days])
            
            writer.writerow(row)
        
        return response


