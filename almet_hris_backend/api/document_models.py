# api/document_models.py - Simple Document Library

from django.db import models
from django.contrib.auth.models import User
from django.core.validators import FileExtensionValidator
from django.core.exceptions import ValidationError
import os
import logging

logger = logging.getLogger(__name__)


class DocumentCompany(models.Model):
    """
    Company for document organization
    """
    
    business_function = models.OneToOneField(
        'BusinessFunction',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='document_company',
        help_text="Link to business function if exists"
    )
    
    name = models.CharField(
        max_length=200,
        unique=True,
        help_text="Company name (e.g., 'Almet HR', 'Almet IT')"
    )
    
    code = models.CharField(
        max_length=50,
        unique=True,
        help_text="Company code (e.g., 'HR', 'IT')"
    )
    
  
    icon = models.CharField(max_length=10, default='🏢')

    is_active = models.BooleanField(default=True)
    
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_doc_companies'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['code', 'name']
        verbose_name = "Document Company"
        verbose_name_plural = "Document Companies"
    
    def __str__(self):
        return f"{self.code} - {self.name}"
    
    def get_total_documents(self):
        total = 0
        for folder in self.folders.filter(is_active=True):
            total += folder.documents.filter(is_active=True).count()
        return total


class DocumentFolder(models.Model):
    """
    Folder for organizing documents
    """
    
    company = models.ForeignKey(
        DocumentCompany,
        on_delete=models.CASCADE,
        related_name='folders'
    )
    
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=10, default='📁')
    
    order = models.PositiveIntegerField(
        default=0,
        help_text="Display order"
    )
    
    is_active = models.BooleanField(default=True)
    
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_doc_folders'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['company', 'order', 'name']
        unique_together = ['company', 'name']
        verbose_name = "Document Folder"
        verbose_name_plural = "Document Folders"
    
    def __str__(self):
        return f"{self.company.code} - {self.name}"
    
    def get_document_count(self):
        return self.documents.filter(is_active=True).count()


class Document(models.Model):
    """
    Universal document model
    """
    
    DOCUMENT_TYPES = [
        ('policy', 'Policy'),
        ('procedure', 'Procedure'),
        ('guideline', 'Guideline'),
        ('manual', 'Manual'),
        ('template', 'Template'),
        ('form', 'Form'),
        ('reference', 'Reference'),
        ('report', 'Report'),
        ('other', 'Other'),
    ]
    
    folder = models.ForeignKey(
        DocumentFolder,
        on_delete=models.CASCADE,
        related_name='documents'
    )
    
    document_type = models.CharField(
        max_length=20,
        choices=DOCUMENT_TYPES,
        default='other'
    )
    
    title = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    
    # File upload
    document_file = models.FileField(
        upload_to='documents/%Y/%m/',
        validators=[
            FileExtensionValidator(
                allowed_extensions=['pdf', 'docx', 'xlsx', 'pptx', 'txt', 'doc', 'xls', 'ppt']
            )
        ]
    )
    
    file_size = models.PositiveIntegerField(null=True, blank=True)
    

    
    # Tracking
    view_count = models.PositiveIntegerField(default=0)
    download_count = models.PositiveIntegerField(default=0)
    
    # Tags
    tags = models.JSONField(default=list, blank=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    is_archived = models.BooleanField(default=False)
    
    # Dates
    effective_date = models.DateField(null=True, blank=True)
    
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_documents'
    )
    
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='updated_documents'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-updated_at']
        verbose_name = "Document"
        verbose_name_plural = "Documents"
        indexes = [
            models.Index(fields=['folder', 'document_type', 'is_active']),
            models.Index(fields=['document_type', 'is_active']),
            models.Index(fields=['-updated_at']),
        ]
    
    def save(self, *args, **kwargs):
        if self.document_file:
            try:
                self.file_size = self.document_file.size
            except:
                pass
        super().save(*args, **kwargs)
    
    def clean(self):
        if self.document_file and self.document_file.size > 20 * 1024 * 1024:
            raise ValidationError("File size cannot exceed 20MB")
    
    def get_file_size_display(self):
        if self.file_size:
            if self.file_size < 1024:
                return f"{self.file_size} B"
            elif self.file_size < 1024 * 1024:
                return f"{self.file_size / 1024:.1f} KB"
            else:
                return f"{self.file_size / (1024 * 1024):.1f} MB"
        return "Unknown"
    
    def get_file_extension(self):
        if self.document_file:
            ext = os.path.splitext(self.document_file.name)[1][1:].upper()
            return ext if ext else 'FILE'
        return None
    
    def increment_view_count(self):
        self.view_count += 1
        self.save(update_fields=['view_count'])
    
    def increment_download_count(self):
        self.download_count += 1
        self.save(update_fields=['download_count'])
    

    
    def __str__(self):
        return f"[{self.get_document_type_display()}] {self.title}"


# Signal handlers
from django.db.models.signals import pre_delete
from django.dispatch import receiver

@receiver(pre_delete, sender=Document)
def delete_document_file(sender, instance, **kwargs):
    """Delete document file when document is deleted"""
    if instance.document_file:
        try:
            if os.path.isfile(instance.document_file.path):
                os.remove(instance.document_file.path)
                logger.info(f"Deleted document file: {instance.document_file.path}")
        except Exception as e:
            logger.error(f"Error deleting document file: {e}")