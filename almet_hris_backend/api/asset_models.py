# api/asset_models.py - SIMPLIFIED: Maintenance hissələri silinmiş

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import MinValueValidator
from decimal import Decimal
import uuid
import logging

logger = logging.getLogger(__name__)


class AssetCategory(models.Model):
    """Asset categories for organization"""
    
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        db_table = 'asset_categories'
        verbose_name = 'Asset Category'
        verbose_name_plural = 'Asset Categories'
        ordering = ['name']
    
    def __str__(self):
        return self.name

class Asset(models.Model):
    """Main asset model - FIXED with proper method definitions"""
    
    STATUS_CHOICES = [
        ('IN_STOCK', 'In Stock'),
        ('IN_USE', 'In Use'),
        ('IN_REPAIR', 'In Repair'),
        ('ARCHIVED', 'Archived'),
    ]
    
    # Primary fields
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    asset_name = models.CharField(max_length=200, verbose_name="Asset Name")
    category = models.ForeignKey(
        AssetCategory, 
        on_delete=models.CASCADE,
        verbose_name="Category"
    )
    
    # Financial information
    purchase_price = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name="Purchase Price (AZN)"
    )
    purchase_date = models.DateField(verbose_name="Purchase Date")
    useful_life_years = models.PositiveIntegerField(
        verbose_name="Useful Life (Years)",
        validators=[MinValueValidator(1)]
    )
    
    # Asset identification
    serial_number = models.CharField(
        max_length=100, 
        unique=True,
        verbose_name="Serial Number"
    )
    
    # Status and location
    status = models.CharField(
        max_length=15, 
        choices=STATUS_CHOICES, 
        default='IN_STOCK'
    )
    
    # Current assignment
    assigned_to = models.ForeignKey(
        'Employee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_assets',
        verbose_name="Currently Assigned To"
    )
    
    # No additional optional fields - keeping only essentials
    
    # Metadata
    created_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True,
        related_name='created_assets'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True,
        related_name='updated_assets'
    )
    
    # Archive information
    archived_at = models.DateTimeField(null=True, blank=True)
    archived_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='archived_assets'
    )
    archive_reason = models.TextField(blank=True, null=True)
    
    class Meta:
        db_table = 'assets'
        verbose_name = 'Asset'
        verbose_name_plural = 'Assets'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['asset_name']),
            models.Index(fields=['serial_number']),
            models.Index(fields=['status']),
            models.Index(fields=['category']),
            models.Index(fields=['assigned_to']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.asset_name} ({self.serial_number})"
    
    def save(self, *args, **kwargs):
        """Override save to handle status changes"""
        if self.pk:  # Existing asset
            try:
                old_asset = Asset.objects.get(pk=self.pk)
                if old_asset.status != self.status:
                    logger.info(f"Asset {self.asset_name} status changed from {old_asset.status} to {self.status}")
                    
                    # Handle archive status
                    if self.status == 'ARCHIVED' and old_asset.status != 'ARCHIVED':
                        self.archived_at = timezone.now()
                    elif self.status != 'ARCHIVED' and old_asset.status == 'ARCHIVED':
                        self.archived_at = None
                        self.archived_by = None
                        self.archive_reason = ''
            except Asset.DoesNotExist:
                pass
        
        super().save(*args, **kwargs)
    
    def get_status_display_with_color(self):
        """Get status with color coding - FIXED METHOD"""
        status_colors = {
            'IN_STOCK': '#17a2b8',    # Info blue
            'IN_USE': '#28a745',      # Success green
            'IN_REPAIR': '#ffc107',   # Warning yellow
            'ARCHIVED': '#6c757d',    # Secondary gray
        }
        return {
            'status': self.get_status_display(),
            'color': status_colors.get(self.status, '#6c757d')
        }
    
    def get_current_assignment(self):
        """Get current assignment information - FIXED for JSON serialization"""
        if self.assigned_to:
            current_assignment = self.assignments.filter(
                check_in_date__isnull=True
            ).first()
            
            assignment_data = None
            if current_assignment:
                assignment_data = {
                    'id': current_assignment.id,
                    'check_out_date': current_assignment.check_out_date.isoformat(),
                    'check_out_notes': current_assignment.check_out_notes,
                    'condition_on_checkout': current_assignment.condition_on_checkout,
                    'duration_days': current_assignment.get_duration_days(),
                    'assigned_by': current_assignment.assigned_by.get_full_name() if current_assignment.assigned_by else None
                }
            
            return {
                'employee': {
                    'id': self.assigned_to.id,
                    'name': self.assigned_to.full_name,
                    'employee_id': self.assigned_to.employee_id
                },
                'assignment': assignment_data
            }
        return None
    
   
    def can_be_assigned(self):
        """Check if asset can be assigned to an employee"""
        return self.status in ['IN_STOCK'] and not self.assigned_to
    
    def can_be_checked_in(self):
        """Check if asset can be checked in"""
        return self.status == 'IN_USE' and self.assigned_to is not None

class AssetAssignment(models.Model):
    """Asset assignment history"""
    
    # Primary relationships
    asset = models.ForeignKey(
        Asset, 
        on_delete=models.CASCADE,
        related_name='assignments'
    )
    employee = models.ForeignKey(
        'Employee', 
        on_delete=models.CASCADE,
        related_name='asset_assignments'
    )
    
    # Assignment dates
    check_out_date = models.DateField(verbose_name="Check-out Date")
    check_in_date = models.DateField(
        null=True, 
        blank=True,
        verbose_name="Check-in Date"
    )
    
    # Assignment details
    check_out_notes = models.TextField(
        blank=True,
        verbose_name="Check-out Notes"
    )
    check_in_notes = models.TextField(
        blank=True,
        verbose_name="Check-in Notes"
    )
    
    # Asset condition
    condition_on_checkout = models.CharField(
        max_length=20,
        choices=[
            ('EXCELLENT', 'Excellent'),
            ('GOOD', 'Good'),
            ('FAIR', 'Fair'),
            ('POOR', 'Poor'),
        ],
        default='GOOD'
    )
    condition_on_checkin = models.CharField(
        max_length=20,
        choices=[
            ('EXCELLENT', 'Excellent'),
            ('GOOD', 'Good'),
            ('FAIR', 'Fair'),
            ('POOR', 'Poor'),
            ('DAMAGED', 'Damaged'),
        ],
        blank=True
    )
    
    # Metadata
    assigned_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='assigned_assets_by'
    )
    checked_in_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='checked_in_assets_by'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'asset_assignments'
        verbose_name = 'Asset Assignment'
        verbose_name_plural = 'Asset Assignments'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['asset', 'check_out_date']),
            models.Index(fields=['employee', 'check_out_date']),
            models.Index(fields=['check_out_date']),
            models.Index(fields=['check_in_date']),
        ]
    
    def __str__(self):
        status = "Active" if not self.check_in_date else "Completed"
        return f"{self.asset.asset_name} -> {self.employee.full_name} ({status})"
    
    def is_active(self):
        """Check if assignment is currently active"""
        return self.check_in_date is None
    
    def get_duration_days(self):
        """Get assignment duration in days"""
        if self.check_in_date:
            return (self.check_in_date - self.check_out_date).days
        else:
            return (timezone.now().date() - self.check_out_date).days


class AssetActivity(models.Model):
    """Activity log for assets"""
    
    ACTIVITY_TYPES = [
        ('CREATED', 'Created'),
        ('UPDATED', 'Updated'),
        ('ASSIGNED', 'Assigned to Employee'),
        ('CHECKED_IN', 'Checked In'),
        ('STATUS_CHANGED', 'Status Changed'),
        ('ARCHIVED', 'Archived'),
        ('RESTORED', 'Restored from Archive'),
    ]
    
    asset = models.ForeignKey(
        Asset, 
        on_delete=models.CASCADE,
        related_name='activities'
    )
    activity_type = models.CharField(max_length=30, choices=ACTIVITY_TYPES)
    description = models.TextField()
    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    performed_at = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        db_table = 'asset_activities'
        verbose_name = 'Asset Activity'
        verbose_name_plural = 'Asset Activities'
        ordering = ['-performed_at']
    
    def __str__(self):
        return f"{self.asset.asset_name} - {self.get_activity_type_display()}"