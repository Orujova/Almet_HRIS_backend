# api/asset_serializers.py - SIMPLIFIED: Maintenance hissələri silinmiş

from rest_framework import serializers
from .asset_models import (
    AssetCategory, Asset, AssetAssignment, AssetActivity
)
from .models import Employee
from django.contrib.auth.models import User
from django.utils import timezone


# Basic serializers for related models
class AssetUserBasicSerializer(serializers.ModelSerializer):
    """User serializer for asset management - unique ref_name"""
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name']
        ref_name = 'AssetUserBasic'


class AssetEmployeeBasicSerializer(serializers.ModelSerializer):
    """Employee serializer for asset management - unique ref_name"""
    class Meta:
        model = Employee
        fields = ['id', 'employee_id', 'full_name', 'job_title', 'department']
        ref_name = 'AssetEmployeeBasic'


class AssetCategorySerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    asset_count = serializers.SerializerMethodField()
    
    class Meta:
        model = AssetCategory
        fields = [
            'id', 'name', 'description', 'is_active', 'asset_count',
            'created_at', 'created_by', 'created_by_name'
        ]
        read_only_fields = ['created_at', 'created_by']
        ref_name = 'AssetCategory'
    
    def get_asset_count(self, obj):
        return obj.asset_set.count()


class AssetAssignmentSerializer(serializers.ModelSerializer):
    employee_detail = AssetEmployeeBasicSerializer(source='employee', read_only=True)
    assigned_by_detail = AssetUserBasicSerializer(source='assigned_by', read_only=True)
    checked_in_by_detail = AssetUserBasicSerializer(source='checked_in_by', read_only=True)
    duration_days = serializers.SerializerMethodField()
    is_active = serializers.SerializerMethodField()
    
    class Meta:
        model = AssetAssignment
        fields = [
            'id', 'employee', 'employee_detail', 'check_out_date', 'check_in_date',
            'check_out_notes', 'check_in_notes', 'condition_on_checkout', 'condition_on_checkin',
            'assigned_by', 'assigned_by_detail', 'checked_in_by', 'checked_in_by_detail',
            'duration_days', 'is_active', 'created_at', 'updated_at'
        ]
        ref_name = 'AssetAssignment'
    
    def get_duration_days(self, obj):
        return obj.get_duration_days()
    
    def get_is_active(self, obj):
        return obj.is_active()


class AssetActivitySerializer(serializers.ModelSerializer):
    performed_by_detail = AssetUserBasicSerializer(source='performed_by', read_only=True)
    
    class Meta:
        model = AssetActivity
        fields = [
            'id', 'activity_type', 'description', 'performed_by', 
            'performed_by_detail', 'performed_at', 'metadata'
        ]
        ref_name = 'AssetActivity'

class AssetListSerializer(serializers.ModelSerializer):
    """Serializer for asset list view - MINIMAL"""
    
    category_name = serializers.CharField(source='category.name', read_only=True)
    assigned_to_name = serializers.CharField(source='assigned_to.full_name', read_only=True)
    assigned_to_employee_id = serializers.CharField(source='assigned_to.employee_id', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    current_value = serializers.SerializerMethodField()
    depreciation_percentage = serializers.SerializerMethodField()
    days_since_purchase = serializers.SerializerMethodField()
    
    class Meta:
        model = Asset
        fields = [
            'id', 'asset_name', 'category_name', 'serial_number',
            'status', 'status_display', 'assigned_to_name', 'assigned_to_employee_id',
            'purchase_price', 'purchase_date', 'current_value', 'depreciation_percentage',
            'days_since_purchase', 'useful_life_years', 'created_at', 'created_by_name'
        ]
        ref_name = 'AssetList'
    
    def get_current_value(self, obj):
        """Get current value with proper Decimal handling"""
        depreciation = obj.calculate_depreciation()
        if depreciation:
            return depreciation['current_value']
        return float(obj.purchase_price)
    
    def get_depreciation_percentage(self, obj):
        """Get depreciation percentage with proper Decimal handling"""
        depreciation = obj.calculate_depreciation()
        if depreciation:
            return depreciation['depreciation_percentage']
        return 0.0
    
    def get_days_since_purchase(self, obj):
        if obj.purchase_date:
            return (timezone.now().date() - obj.purchase_date).days
        return None

class AssetDetailSerializer(serializers.ModelSerializer):
    """Serializer for asset detail view - MINIMAL"""
    
    # Related object details
    category = AssetCategorySerializer(read_only=True)
    assigned_to = AssetEmployeeBasicSerializer(read_only=True)
    
    # User details
    created_by_detail = AssetUserBasicSerializer(source='created_by', read_only=True)
    updated_by_detail = AssetUserBasicSerializer(source='updated_by', read_only=True)
    archived_by_detail = AssetUserBasicSerializer(source='archived_by', read_only=True)
    
    # Calculated fields
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    depreciation_info = serializers.SerializerMethodField()
    current_assignment = serializers.SerializerMethodField()
    
    # Related components
    assignments = AssetAssignmentSerializer(many=True, read_only=True)
    activities = AssetActivitySerializer(many=True, read_only=True)
    
    # Business logic
    can_be_assigned = serializers.SerializerMethodField()
    can_be_checked_in = serializers.SerializerMethodField()
    
    class Meta:
        model = Asset
        fields = [
            # Basic info
            'id', 'asset_name', 'category', 'serial_number',
            
            # Financial info
            'purchase_price', 'purchase_date', 'useful_life_years', 'depreciation_info',
            
            # Status and assignment
            'status', 'status_display', 'assigned_to', 'current_assignment',
            
            # Archive info
            'archived_at', 'archived_by', 'archived_by_detail', 'archive_reason',
            
            # Metadata
            'created_by', 'created_by_detail', 'created_at',
            'updated_by', 'updated_by_detail', 'updated_at',
            
            # Related components
            'assignments', 'activities',
            
            # Business logic
            'can_be_assigned', 'can_be_checked_in'
        ]
        ref_name = 'AssetDetail'
    
    def get_depreciation_info(self, obj):
        return obj.calculate_depreciation()
    
    def get_current_assignment(self, obj):
        return obj.get_current_assignment()
    
    def get_can_be_assigned(self, obj):
        return obj.can_be_assigned()
    
    def get_can_be_checked_in(self, obj):
        return obj.can_be_checked_in()

class AssetCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating and updating assets - MINIMAL FIELDS ONLY"""
    
    class Meta:
        model = Asset
        fields = [
            'asset_name', 
            'category', 
            'serial_number',
            'purchase_price', 
            'purchase_date', 
            'useful_life_years',
            'status'
        ]
        ref_name = 'AssetCreateUpdate'
    
    def validate_serial_number(self, value):
        """Validate serial number uniqueness"""
        if self.instance:
            # Update case - exclude current instance
            if Asset.objects.exclude(pk=self.instance.pk).filter(serial_number=value).exists():
                raise serializers.ValidationError("Asset with this serial number already exists.")
        else:
            # Create case
            if Asset.objects.filter(serial_number=value).exists():
                raise serializers.ValidationError("Asset with this serial number already exists.")
        return value
    
    def validate_purchase_date(self, value):
        """Validate purchase date is not in future"""
        if value > timezone.now().date():
            raise serializers.ValidationError("Purchase date cannot be in the future.")
        return value
    
    def validate_useful_life_years(self, value):
        """Validate useful life years"""
        if value < 1 or value > 50:
            raise serializers.ValidationError("Useful life must be between 1 and 50 years.")
        return value
    
    def validate_purchase_price(self, value):
        """Validate purchase price"""
        if value <= 0:
            raise serializers.ValidationError("Purchase price must be greater than 0.")
        return value
    
    def create(self, validated_data):
        """Create asset with activity logging"""
        validated_data.pop('created_by', None)
        
        asset = Asset(**validated_data)
        asset.save()
        
        # Log creation activity
        AssetActivity.objects.create(
            asset=asset,
            activity_type='CREATED',
            description=f"Asset '{asset.asset_name}' created with serial number {asset.serial_number}",
            performed_by=self.context['request'].user,
            metadata={
                'asset_name': asset.asset_name,
                'serial_number': asset.serial_number,
                'category': asset.category.name,
                'purchase_price': str(asset.purchase_price),
                'status': asset.status
            }
        )
        
        return asset
    
    def update(self, instance, validated_data):
        """Update asset with activity logging"""
        old_values = {
            'asset_name': instance.asset_name,
            'status': instance.status,
        }
        
        validated_data.pop('created_by', None)
        validated_data.pop('updated_by', None)
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save()
        
        # Log update activity if fields changed
        changed_fields = []
        for field, old_value in old_values.items():
            new_value = getattr(instance, field)
            if old_value != new_value:
                changed_fields.append(field)
        
        if changed_fields:
            AssetActivity.objects.create(
                asset=instance,
                activity_type='UPDATED',
                description=f"Asset updated. Changed fields: {', '.join(changed_fields)}",
                performed_by=self.context['request'].user,
                metadata={
                    'changed_fields': changed_fields,
                    'old_values': old_values
                }
            )
        
        return instance

class AssetAssignmentCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating asset assignments"""
    
    class Meta:
        model = AssetAssignment
        fields = [
            'asset', 'employee', 'check_out_date', 'check_out_notes', 'condition_on_checkout'
        ]
        ref_name = 'AssetAssignmentCreate'
    
    def validate_asset(self, value):
        """Validate asset can be assigned"""
        if not value.can_be_assigned():
            raise serializers.ValidationError(
                f"Asset '{value.asset_name}' cannot be assigned. Current status: {value.get_status_display()}"
            )
        return value
    
    def validate_check_out_date(self, value):
        """Validate check out date"""
        if value > timezone.now().date():
            raise serializers.ValidationError("Check-out date cannot be in the future.")
        return value
    
    def create(self, validated_data):
        """Create assignment and update asset status"""
        from django.db import transaction
        
        with transaction.atomic():
            assignment = AssetAssignment.objects.create(
                **validated_data,
                assigned_by=self.context['request'].user
            )
            
            # Update asset status and assignment
            asset = assignment.asset
            asset.status = 'IN_USE'
            asset.assigned_to = assignment.employee
            asset.save()
            
            # Log activities
            AssetActivity.objects.create(
                asset=asset,
                activity_type='ASSIGNED',
                description=f"Asset assigned to {assignment.employee.full_name} ({assignment.employee.employee_id})",
                performed_by=self.context['request'].user,
                metadata={
                    'employee_id': assignment.employee.employee_id,
                    'employee_name': assignment.employee.full_name,
                    'check_out_date': assignment.check_out_date.isoformat(),
                    'condition': assignment.condition_on_checkout,
                    'notes': assignment.check_out_notes
                }
            )
            
            return assignment

class AssetCheckInSerializer(serializers.Serializer):
    """Serializer for checking in assets"""
    
    check_in_date = serializers.DateField()
    check_in_notes = serializers.CharField(required=False, allow_blank=True)
    condition_on_checkin = serializers.ChoiceField(
        choices=[
            ('EXCELLENT', 'Excellent'),
            ('GOOD', 'Good'),
            ('FAIR', 'Fair'),
            ('POOR', 'Poor'),
            ('DAMAGED', 'Damaged'),
        ]
    )
    
    class Meta:
        ref_name = 'AssetCheckIn'
    
    def validate_check_in_date(self, value):
        """Validate check in date"""
        if value > timezone.now().date():
            raise serializers.ValidationError("Check-in date cannot be in the future.")
        return value

class AssetStatusChangeSerializer(serializers.Serializer):
    """Simple serializer for changing asset status"""
    
    status = serializers.ChoiceField(
        choices=Asset.STATUS_CHOICES,
        help_text="New status for the asset"
    )
    reason = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=500,
        help_text="Reason for status change (optional)"
    )
    
    class Meta:
        ref_name = 'AssetStatusChange'
    
    def validate_status(self, value):
        """Validate status value"""
        valid_statuses = [choice[0] for choice in Asset.STATUS_CHOICES]
        if value not in valid_statuses:
            raise serializers.ValidationError(f"Invalid status. Must be one of: {', '.join(valid_statuses)}")
        return value

class AssetExportSerializer(serializers.Serializer):
    """Enhanced serializer for asset export functionality"""
    
    asset_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        allow_empty=True,
        help_text="List of asset UUIDs to export. Only used when export_type=selected"
    )
    export_format = serializers.ChoiceField(
        choices=[('csv', 'CSV'), ('excel', 'Excel')],
        default='excel'
    )
    include_assignments = serializers.BooleanField(default=True)
    include_depreciation = serializers.BooleanField(default=True)
    date_range_from = serializers.DateField(required=False)
    date_range_to = serializers.DateField(required=False)
    
    class Meta:
        ref_name = 'AssetExport'
    
    def validate_asset_ids(self, value):
        """Validate that asset IDs exist - only when they're actually used"""
        # This validation will be handled in the view based on export_type
        return value
    
    def validate(self, attrs):
        """Validate date range"""
        date_from = attrs.get('date_range_from')
        date_to = attrs.get('date_range_to')
        
        if date_from and date_to and date_from > date_to:
            raise serializers.ValidationError("Date range 'from' cannot be after 'to'")
        
        return attrs
