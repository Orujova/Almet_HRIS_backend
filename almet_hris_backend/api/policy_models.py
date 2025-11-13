from django.db import models
from django.core.validators import FileExtensionValidator
from django.contrib.auth.models import User


class PolicyCategory(models.Model):
    """Policy kateqoriyaları"""
    name = models.CharField(max_length=100, unique=True, verbose_name="Kateqoriya adı")
    description = models.TextField(blank=True, verbose_name="Təsvir")
    order = models.IntegerField(default=0, verbose_name="Sıralama")
    is_active = models.BooleanField(default=True, verbose_name="Aktiv")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaradılma tarixi")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Yenilənmə tarixi")

    class Meta:
        db_table = 'policy_categories'
        ordering = ['order', 'name']
        verbose_name = 'Policy Kateqoriyası'
        verbose_name_plural = 'Policy Kateqoriyaları'

    def __str__(self):
        return self.name


class CompanyPolicy(models.Model):
    """Şirkət siyasətləri və prosedurları"""
    
    title = models.CharField(max_length=200, verbose_name="Başlıq")
    slug = models.SlugField(max_length=200, unique=True, verbose_name="Slug")
    category = models.ForeignKey(
        PolicyCategory, 
        on_delete=models.CASCADE,
        related_name='policies',
        verbose_name="Kateqoriya"
    )
    icon = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name="İkon"
    )
    description = models.TextField(verbose_name="Təsvir")
    
    # PDF fayl
    pdf_file = models.FileField(
        upload_to='policies/pdfs/%Y/%m/',
        validators=[FileExtensionValidator(allowed_extensions=['pdf'])],
        help_text='PDF formatında olmalıdır',
        verbose_name="PDF Fayl"
    )
    
    # Metadata
    version = models.CharField(max_length=20, default='1.0', verbose_name="Versiya")
    effective_date = models.DateField(
        help_text='Policy-nin qüvvəyə minmə tarixi',
        verbose_name="Qüvvəyə minmə tarixi"
    )
    review_date = models.DateField(
        null=True, 
        blank=True,
        help_text='Növbəti baxış tarixi',
        verbose_name="Baxış tarixi"
    )
    
    # Status
    is_active = models.BooleanField(default=True, verbose_name="Aktiv")
    is_mandatory = models.BooleanField(
        default=False,
        help_text='Bütün əməkdaşlar üçün məcburidirmi?',
        verbose_name="Məcburi"
    )
    
    # Statistics
    download_count = models.IntegerField(default=0, verbose_name="Yükləmə sayı")
    view_count = models.IntegerField(default=0, verbose_name="Baxış sayı")
    
    # Audit fields
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_policies',
        verbose_name="Yaradan"
    )
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='updated_policies',
        verbose_name="Yeniləyən"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaradılma tarixi")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Yenilənmə tarixi")

    class Meta:
        db_table = 'company_policies'
        ordering = ['category__order', 'title']
        verbose_name = 'Şirkət Policy-si'
        verbose_name_plural = 'Şirkət Policy-ləri'
        indexes = [
            models.Index(fields=['category', 'is_active']),
            models.Index(fields=['slug']),
        ]

    def __str__(self):
        return f"{self.title} ({self.category.name})"

    def increment_view_count(self):
        """View sayını artır"""
        self.view_count += 1
        self.save(update_fields=['view_count'])

    def increment_download_count(self):
        """Download sayını artır"""
        self.download_count += 1
        self.save(update_fields=['download_count'])


class PolicyAcknowledgment(models.Model):
    """Əməkdaşların policy-ləri oxuduğunu təsdiq etməsi"""
    
    policy = models.ForeignKey(
        CompanyPolicy,
        on_delete=models.CASCADE,
        related_name='acknowledgments',
        verbose_name="Policy"
    )
    employee = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='policy_acknowledgments',
        verbose_name="Əməkdaş"
    )
    acknowledged_at = models.DateTimeField(auto_now_add=True, verbose_name="Təsdiq tarixi")
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name="IP ünvanı")
    notes = models.TextField(blank=True, verbose_name="Qeydlər")

    class Meta:
        db_table = 'policy_acknowledgments'
        unique_together = [['policy', 'employee']]
        ordering = ['-acknowledged_at']
        verbose_name = 'Policy Təsdiqi'
        verbose_name_plural = 'Policy Təsdiqləri'

    def __str__(self):
        return f"{self.employee.get_full_name()} - {self.policy.title}"