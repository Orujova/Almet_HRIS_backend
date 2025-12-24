# api/company_policies_models.py - FULL Company Policies Management System Models

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import FileExtensionValidator
from django.core.exceptions import ValidationError
import os
import logging

logger = logging.getLogger(__name__)


class PolicyFolder(models.Model):
    """
    Policy folders organized by business function
    
    Each business function can have multiple folders to organize policies
    Example: ALMET -> Employment Lifecycle, Legal & Compliance, Benefits & Leave
    """
    
    business_function = models.ForeignKey(
        'BusinessFunction',
        on_delete=models.CASCADE,
        related_name='policy_folders',
        help_text="Business function this folder belongs to"
    )
    
    name = models.CharField(
        max_length=200,
        help_text="Folder name (e.g., 'Employment Lifecycle', 'Legal & Compliance')"
    )
    
    description = models.TextField(
        blank=True,
        help_text="Description of what this folder contains"
    )
    
    icon = models.CharField(
        max_length=10,
        default='📁',
        help_text="Emoji icon for the folder (e.g., 👥, ⚖️, 🎁)"
    )
    
  
    
    # Status
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this folder is active and visible"
    )
    
    # Metadata
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_policy_folders',
        help_text="User who created this folder"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['business_function',  'name']
        unique_together = ['business_function', 'name']
        verbose_name = "Policy Folder"
        verbose_name_plural = "Policy Folders"
        indexes = [
            models.Index(fields=['business_function', 'is_active']),
          
            models.Index(fields=['created_at']),
        ]
    
    def get_policy_count(self):
        """Get count of active policies in this folder"""
        return self.policies.filter(is_active=True).count()
    

    
    def get_total_views(self):
        """Get total view count for all policies in folder"""
        return sum(policy.view_count for policy in self.policies.filter(is_active=True))
    
    def get_total_downloads(self):
        """Get total download count for all policies in folder"""
        return sum(policy.download_count for policy in self.policies.filter(is_active=True))
    
    def clean(self):
        """Validate folder data"""
        super().clean()
        
        # Check for duplicate names within same business function
        if self.business_function:
            existing = PolicyFolder.objects.filter(
                business_function=self.business_function,
                name__iexact=self.name
            ).exclude(pk=self.pk)
            
            if existing.exists():
                raise ValidationError(
                    f"A folder with name '{self.name}' already exists in {self.business_function.name}"
                )
    
    def __str__(self):
        return f"{self.business_function.code} - {self.name}"


class CompanyPolicy(models.Model):
    """
    Company policy documents
    
    Stores policy documents (PDFs) with metadata, versioning, and tracking
    """
    
 
    
    # Relationships
    folder = models.ForeignKey(
        PolicyFolder,
        on_delete=models.CASCADE,
        related_name='policies',
        help_text="Folder this policy belongs to"
    )
    
    # Basic Information
    title = models.CharField(
        max_length=300,
        help_text="Policy title (e.g., 'Hiring Procedure', 'Vacation Policy')"
    )
    
    description = models.TextField(
        blank=True,
        help_text="Brief description of the policy"
    )
    
    # Document File
    policy_file = models.FileField(
        upload_to='company_policies/%Y/%m/',
        validators=[FileExtensionValidator(allowed_extensions=['pdf'])],
        help_text="Policy document (PDF only, max 10MB)"
    )
    
    file_size = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="File size in bytes (auto-calculated)"
    )
    

    

    
    requires_acknowledgment = models.BooleanField(
        default=False,
        help_text="Do employees need to acknowledge reading this policy?"
    )
    
    # Tracking
    download_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of times this policy has been downloaded"
    )
    
    view_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of times this policy has been viewed"
    )

    
    # Status
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this policy is active and visible"
    )
    
    # User Tracking
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_policies',
        help_text="User who created this policy"
    )
    
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='updated_policies',
        help_text="User who last updated this policy"
    )
    
 
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-updated_at']
        verbose_name = "Company Policy"
        verbose_name_plural = "Company Policies"
        indexes = [
            models.Index(fields=['folder', 'is_active']),
  
   
            models.Index(fields=['-updated_at']),
  
            models.Index(fields=['requires_acknowledgment']),
        ]
    
    def save(self, *args, **kwargs):
        """Auto-calculate file size and handle approval"""
        # Calculate file size
        if self.policy_file:
            try:
                self.file_size = self.policy_file.size
            except Exception as e:
                logger.warning(f"Could not calculate file size: {e}")
        
       
        
        super().save(*args, **kwargs)
    
    def clean(self):
        """Validate policy data"""
        super().clean()
        
        # Validate file size (10MB max)
        if self.policy_file:
            if self.policy_file.size > 10 * 1024 * 1024:
                raise ValidationError("File size cannot exceed 10MB")
        
      
    
    def get_file_size_display(self):
        """Human readable file size"""
        if self.file_size:
            if self.file_size < 1024:
                return f"{self.file_size} B"
            elif self.file_size < 1024 * 1024:
                return f"{self.file_size / 1024:.1f} KB"
            else:
                return f"{self.file_size / (1024 * 1024):.1f} MB"
        return "Unknown"
    
    def increment_view_count(self):
        """Increment view counter"""
        self.view_count += 1
     
        self.save(update_fields=['view_count'])
 
    
    def increment_download_count(self):
        """Increment download counter"""
        self.download_count += 1
    
        self.save(update_fields=['download_count'])
        
    
    def get_business_function(self):
        """Get the business function this policy belongs to"""
        return self.folder.business_function if self.folder else None
    
    def get_acknowledgment_count(self):
        """Get count of employee acknowledgments"""
        return self.acknowledgments.count()
    
    def get_acknowledgment_percentage(self):
        """Get percentage of employees who acknowledged this policy"""
        if not self.requires_acknowledgment:
            return None
        
        from .models import Employee
        total_employees = Employee.objects.filter(is_deleted=False).count()
        
        if total_employees == 0:
            return 0
        
        acknowledged = self.get_acknowledgment_count()
        return round((acknowledged / total_employees) * 100, 1)
    
    def is_acknowledged_by_employee(self, employee):
        """Check if employee has acknowledged this policy"""
        return self.acknowledgments.filter(employee=employee).exists()
    
    def __str__(self):
        bf_code = self.folder.business_function.code if self.folder and self.folder.business_function else 'N/A'
        return f"{bf_code} - {self.title} "


class PolicyAcknowledgment(models.Model):
    """
    Track employee acknowledgments of policies
    
    When an employee reads and acknowledges a policy, it's recorded here
    """
    
    policy = models.ForeignKey(
        CompanyPolicy,
        on_delete=models.CASCADE,
        related_name='acknowledgments',
        help_text="Policy that was acknowledged"
    )
    
    employee = models.ForeignKey(
        'Employee',
        on_delete=models.CASCADE,
        related_name='policy_acknowledgments',
        help_text="Employee who acknowledged the policy"
    )
    
    acknowledged_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the acknowledgment was made"
    )
    
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="IP address from which acknowledgment was made"
    )
    
    notes = models.TextField(
        blank=True,
        help_text="Additional notes or comments from employee"
    )
    
    class Meta:
        unique_together = ['policy', 'employee']
        ordering = ['-acknowledged_at']
        verbose_name = "Policy Acknowledgment"
        verbose_name_plural = "Policy Acknowledgments"
        indexes = [
            models.Index(fields=['policy', 'employee']),
            models.Index(fields=['-acknowledged_at']),
            models.Index(fields=['policy', '-acknowledged_at']),
        ]
    
    def __str__(self):
        return f"{self.employee.full_name} - {self.policy.title}"





# Signal handlers for automatic operations
from django.db.models.signals import pre_delete
from django.dispatch import receiver

@receiver(pre_delete, sender=CompanyPolicy)
def delete_policy_file(sender, instance, **kwargs):
    """Delete policy file when policy is deleted"""
    if instance.policy_file:
        try:
            if os.path.isfile(instance.policy_file.path):
                os.remove(instance.policy_file.path)
                logger.info(f"Deleted policy file: {instance.policy_file.path}")
        except Exception as e:
            logger.error(f"Error deleting policy file: {e}")

