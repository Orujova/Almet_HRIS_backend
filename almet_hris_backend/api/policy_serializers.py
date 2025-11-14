# api/company_policies_serializers.py - FULL Serializers

from rest_framework import serializers
from .policy_models import (
    PolicyFolder, CompanyPolicy, PolicyAcknowledgment,
    PolicyAccessLog, PolicyVersion
)
from .models import BusinessFunction, Employee
from django.contrib.auth.models import User
from django.utils import timezone


# ==================== BUSINESS FUNCTION SERIALIZERS ====================

class BusinessFunctionSimpleSerializer(serializers.ModelSerializer):
    """Simple serializer for business function - used in nested relations"""
    
    class Meta:
        model = BusinessFunction
        fields = ['id', 'name', 'code', 'is_active']
        read_only_fields = ['id', 'name', 'code', 'is_active']


class BusinessFunctionWithFoldersSerializer(serializers.ModelSerializer):
    """Business function with all its policy folders and statistics"""
    
    folders = serializers.SerializerMethodField()
    folder_count = serializers.SerializerMethodField()
    total_policy_count = serializers.SerializerMethodField()
    
    class Meta:
        model = BusinessFunction
        fields = [
            'id', 'name', 'code', 'folder_count', 'total_policy_count',
            'folders', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']
    
    def get_folders(self, obj):
        """Get active folders with policy counts"""
        folders = obj.policy_folders.filter(is_active=True).order_by('order', 'name')
        return PolicyFolderSerializer(folders, many=True, context=self.context).data
    
    def get_folder_count(self, obj):
        """Get count of active folders"""
        return obj.policy_folders.filter(is_active=True).count()
    
    def get_total_policy_count(self, obj):
        """Get total count of active policies across all folders"""
        total = 0
        for folder in obj.policy_folders.filter(is_active=True):
            total += folder.get_policy_count()
        return total


# ==================== POLICY FOLDER SERIALIZERS ====================

class PolicyFolderSerializer(serializers.ModelSerializer):
    """Full serializer for policy folders"""
    
    # Related fields
    business_function_name = serializers.CharField(
        source='business_function.name',
        read_only=True
    )
    business_function_code = serializers.CharField(
        source='business_function.code',
        read_only=True
    )
    
    # Computed fields
    policy_count = serializers.SerializerMethodField()
    mandatory_policy_count = serializers.SerializerMethodField()
    total_views = serializers.SerializerMethodField()
    total_downloads = serializers.SerializerMethodField()
    
    # User tracking
    created_by_name = serializers.SerializerMethodField()
    
    class Meta:
        model = PolicyFolder
        fields = [
            'id', 'business_function', 'business_function_name',
            'business_function_code', 'name', 'description', 'icon',
            'order', 'is_active', 'policy_count', 'mandatory_policy_count',
            'total_views', 'total_downloads', 'created_by',
            'created_by_name', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_by', 'created_at', 'updated_at']
    
    def get_policy_count(self, obj):
        """Get count of active policies"""
        return obj.get_policy_count()
    
    def get_mandatory_policy_count(self, obj):
        """Get count of mandatory policies"""
        return obj.get_mandatory_policy_count()
    
    def get_total_views(self, obj):
        """Get total view count"""
        return obj.get_total_views()
    
    def get_total_downloads(self, obj):
        """Get total download count"""
        return obj.get_total_downloads()
    
    def get_created_by_name(self, obj):
        """Get creator name"""
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.username
        return None


class PolicyFolderCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating folders"""
    
    class Meta:
        model = PolicyFolder
        fields = [
            'id', 'business_function', 'name', 'description',
            'icon', 'order', 'is_active'
        ]
    
    def validate_name(self, value):
        """Validate folder name"""
        if not value or not value.strip():
            raise serializers.ValidationError("Folder name cannot be empty")
        
        # Check length
        if len(value) > 200:
            raise serializers.ValidationError("Folder name is too long (max 200 characters)")
        
        return value.strip()
    
    def validate(self, data):
        """Validate complete folder data"""
        # Check for duplicate name in same business function
        business_function = data.get('business_function')
        name = data.get('name')
        
        if business_function and name:
            # Get instance pk if updating
            instance_pk = self.instance.pk if self.instance else None
            
            existing = PolicyFolder.objects.filter(
                business_function=business_function,
                name__iexact=name.strip()
            ).exclude(pk=instance_pk)
            
            if existing.exists():
                raise serializers.ValidationError({
                    'name': f"A folder with this name already exists in {business_function.name}"
                })
        
        return data


# ==================== COMPANY POLICY SERIALIZERS ====================

class CompanyPolicyListSerializer(serializers.ModelSerializer):
    """Serializer for policy list view - lightweight"""
    
    # Related fields
    folder_name = serializers.CharField(source='folder.name', read_only=True)
    business_function_code = serializers.CharField(
        source='folder.business_function.code',
        read_only=True
    )
    business_function_name = serializers.CharField(
        source='folder.business_function.name',
        read_only=True
    )
    
    # Computed fields
    file_size_display = serializers.CharField(
        source='get_file_size_display',
        read_only=True
    )
    policy_url = serializers.SerializerMethodField()
    
    class Meta:
        model = CompanyPolicy
        fields = [
            'id', 'folder', 'folder_name', 'business_function_code',
            'business_function_name', 'title', 'description', 'version',
            'status', 'effective_date', 'review_date', 'is_mandatory',
            'requires_acknowledgment', 'file_size', 'file_size_display',
            'download_count', 'view_count', 'last_accessed',
            'policy_url', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'file_size', 'download_count', 'view_count',
            'last_accessed', 'created_at', 'updated_at'
        ]
    
    def get_policy_url(self, obj):
        """Get absolute URL for policy file"""
        if obj.policy_file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.policy_file.url)
            return obj.policy_file.url
        return None


class CompanyPolicyDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for single policy view"""
    
    # Related objects
    folder_details = PolicyFolderSerializer(source='folder', read_only=True)
    
    # Computed fields
    file_size_display = serializers.CharField(
        source='get_file_size_display',
        read_only=True
    )
    policy_url = serializers.SerializerMethodField()
    acknowledgment_count = serializers.SerializerMethodField()
    acknowledgment_percentage = serializers.SerializerMethodField()
    
    # User tracking
    created_by_name = serializers.SerializerMethodField()
    updated_by_name = serializers.SerializerMethodField()
    approved_by_name = serializers.SerializerMethodField()
    
    # Business function info
    business_function_code = serializers.CharField(
        source='folder.business_function.code',
        read_only=True
    )
    business_function_name = serializers.CharField(
        source='folder.business_function.name',
        read_only=True
    )
    
    class Meta:
        model = CompanyPolicy
        fields = [
            'id', 'folder', 'folder_details', 'business_function_code',
            'business_function_name', 'title', 'description',
            'policy_file', 'policy_url', 'file_size', 'file_size_display',
            'version', 'status', 'effective_date', 'review_date',
            'is_mandatory', 'requires_acknowledgment', 'download_count',
            'view_count', 'last_accessed', 'is_active', 'created_by',
            'created_by_name', 'updated_by', 'updated_by_name',
            'approved_by', 'approved_by_name', 'approved_at',
            'acknowledgment_count', 'acknowledgment_percentage',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'created_by', 'created_at', 'updated_at', 'approved_by',
            'approved_at', 'file_size', 'download_count', 'view_count',
            'last_accessed'
        ]
    
    def get_policy_url(self, obj):
        """Get absolute URL for policy file"""
        if obj.policy_file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.policy_file.url)
            return obj.policy_file.url
        return None
    
    def get_acknowledgment_count(self, obj):
        """Get total acknowledgment count"""
        return obj.get_acknowledgment_count()
    
    def get_acknowledgment_percentage(self, obj):
        """Get acknowledgment percentage"""
        return obj.get_acknowledgment_percentage()
    
    def get_created_by_name(self, obj):
        """Get creator name"""
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.username
        return None
    
    def get_updated_by_name(self, obj):
        """Get updater name"""
        if obj.updated_by:
            return obj.updated_by.get_full_name() or obj.updated_by.username
        return None
    
    def get_approved_by_name(self, obj):
        """Get approver name"""
        if obj.approved_by:
            return obj.approved_by.get_full_name() or obj.approved_by.username
        return None


class CompanyPolicyCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating policies"""
    
    # CRITICAL: Explicitly define file field for proper Swagger documentation
    policy_file = serializers.FileField(
        required=True,
        help_text="PDF file (max 10MB)",
        allow_empty_file=False,
        use_url=True
    )
    
    class Meta:
        model = CompanyPolicy
        fields = [
            'id', 
            'folder', 
            'title', 
            'description', 
            'policy_file',  # IMPORTANT: Must be included in fields
            'version', 
            'status', 
            'effective_date', 
            'review_date',
            'is_mandatory', 
            'requires_acknowledgment', 
            'is_active'
        ]
        extra_kwargs = {
            'policy_file': {
                'required': True,
                'allow_null': False,
                'use_url': True
            }
        }
    
    def validate_policy_file(self, value):
        """Validate uploaded file"""
        if value:
            # Check file size (max 10MB)
            if value.size > 10 * 1024 * 1024:
                raise serializers.ValidationError(
                    "File size cannot exceed 10MB (current: {:.2f}MB)".format(
                        value.size / (1024 * 1024)
                    )
                )
            
            # Check file extension
            if not value.name.lower().endswith('.pdf'):
                raise serializers.ValidationError(
                    "Only PDF files are allowed. Current file: {}".format(value.name)
                )
            
            # Check MIME type
            import mimetypes
            mime_type, _ = mimetypes.guess_type(value.name)
            if mime_type != 'application/pdf':
                raise serializers.ValidationError(
                    "Invalid file type. Must be application/pdf"
                )
        else:
            raise serializers.ValidationError("Policy file is required")
        
        return value
    
    def validate_title(self, value):
        """Validate policy title"""
        if not value or not value.strip():
            raise serializers.ValidationError("Policy title cannot be empty")
        
        if len(value) > 300:
            raise serializers.ValidationError("Title is too long (max 300 characters)")
        
        return value.strip()
    
    def validate_version(self, value):
        """Validate version format"""
        if not value or not value.strip():
            return "1.0"  # Default version
        
        return value.strip()
    
    def validate_folder(self, value):
        """Validate folder exists and is active"""
        if not value:
            raise serializers.ValidationError("Folder is required")
        
        if not value.is_active:
            raise serializers.ValidationError(
                f"Folder '{value.name}' is not active"
            )
        
        return value
    
    def validate(self, data):
        """Validate complete policy data"""
        # Validate dates
        effective_date = data.get('effective_date')
        review_date = data.get('review_date')
        
        if effective_date and review_date:
            if review_date <= effective_date:
                raise serializers.ValidationError({
                    'review_date': 'Review date must be after effective date'
                })
        
        # Validate status
        status = data.get('status', 'DRAFT')
        valid_statuses = [choice[0] for choice in CompanyPolicy.STATUS_CHOICES]
        if status not in valid_statuses:
            raise serializers.ValidationError({
                'status': f'Invalid status. Must be one of: {", ".join(valid_statuses)}'
            })
        
        return data
    
    def create(self, validated_data):
        """Create policy with user tracking"""
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            validated_data['created_by'] = request.user
        
        # Log policy creation
        import logging
        logger = logging.getLogger(__name__)
        logger.info(
            f"Creating policy: {validated_data.get('title')} "
            f"in folder: {validated_data.get('folder').name}"
        )
        
        return super().create(validated_data)
    
    def update(self, instance, validated_data):
        """Update policy with user tracking and version control"""
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            validated_data['updated_by'] = request.user
            
            # If status is being changed to APPROVED, set approved_by
            if (validated_data.get('status') == 'APPROVED' and 
                instance.status != 'APPROVED'):
                validated_data['approved_by'] = request.user
                validated_data['approved_at'] = timezone.now()
            
            # If file is being updated, create version history
            if 'policy_file' in validated_data and validated_data['policy_file'] != instance.policy_file:
                # Create version from old file
                from .policy_models import PolicyVersion
                PolicyVersion.objects.create(
                    policy=instance,
                    version=instance.version,
                    policy_file=instance.policy_file,
                    changes_summary=f"Updated by {request.user.username}",
                    created_by=request.user
                )
        
        return super().update(instance, validated_data)
    
    def to_representation(self, instance):
        """Custom representation with full policy URL"""
        representation = super().to_representation(instance)
        
        # Add full URL for policy file
        if instance.policy_file:
            request = self.context.get('request')
            if request:
                representation['policy_url'] = request.build_absolute_uri(
                    instance.policy_file.url
                )
            else:
                representation['policy_url'] = instance.policy_file.url
        
        return representation

# ==================== ACKNOWLEDGMENT SERIALIZERS ====================

class PolicyAcknowledgmentSerializer(serializers.ModelSerializer):
    """Serializer for policy acknowledgments"""
    
    # Employee fields
    employee_name = serializers.CharField(
        source='employee.full_name',
        read_only=True
    )
    employee_id = serializers.CharField(
        source='employee.employee_id',
        read_only=True
    )
    employee_email = serializers.CharField(
        source='employee.email',
        read_only=True
    )
    
    # Policy fields
    policy_title = serializers.CharField(
        source='policy.title',
        read_only=True
    )
    policy_version = serializers.CharField(
        source='policy.version',
        read_only=True
    )
    
    class Meta:
        model = PolicyAcknowledgment
        fields = [
            'id', 'policy', 'policy_title', 'policy_version',
            'employee', 'employee_name', 'employee_id', 'employee_email',
            'acknowledged_at', 'ip_address', 'notes'
        ]
        read_only_fields = ['acknowledged_at']
    
    def validate(self, data):
        """Validate acknowledgment data"""
        policy = data.get('policy')
        employee = data.get('employee')
        
        # Check if already acknowledged
        if PolicyAcknowledgment.objects.filter(
            policy=policy,
            employee=employee
        ).exists():
            raise serializers.ValidationError(
                "This policy has already been acknowledged by this employee"
            )
        
        return data


# ==================== ACCESS LOG SERIALIZERS ====================

class PolicyAccessLogSerializer(serializers.ModelSerializer):
    """Serializer for policy access logs"""
    
    # User fields
    user_name = serializers.SerializerMethodField()
    employee_name = serializers.CharField(
        source='employee.full_name',
        read_only=True
    )
    employee_id = serializers.CharField(
        source='employee.employee_id',
        read_only=True
    )
    
    # Policy fields
    policy_title = serializers.CharField(source='policy.title', read_only=True)
    policy_version = serializers.CharField(source='policy.version', read_only=True)
    
    class Meta:
        model = PolicyAccessLog
        fields = [
            'id', 'policy', 'policy_title', 'policy_version',
            'user', 'user_name', 'employee', 'employee_name',
            'employee_id', 'action', 'ip_address', 'user_agent',
            'accessed_at'
        ]
        read_only_fields = ['accessed_at']
    
    def get_user_name(self, obj):
        """Get user display name"""
        return obj.get_user_display()


# ==================== VERSION SERIALIZERS ====================

class PolicyVersionSerializer(serializers.ModelSerializer):
    """Serializer for policy version history"""
    
    # User fields
    created_by_name = serializers.SerializerMethodField()
    
    # Computed fields
    file_size_display = serializers.SerializerMethodField()
    file_url = serializers.SerializerMethodField()
    
    # Policy fields
    policy_title = serializers.CharField(source='policy.title', read_only=True)
    
    class Meta:
        model = PolicyVersion
        fields = [
            'id', 'policy', 'policy_title', 'version', 'policy_file',
            'file_url', 'file_size', 'file_size_display',
            'changes_summary', 'created_by', 'created_by_name',
            'created_at'
        ]
        read_only_fields = ['created_by', 'created_at', 'file_size']
    
    def get_file_size_display(self, obj):
        """Get human readable file size"""
        return obj.get_file_size_display()
    
    def get_file_url(self, obj):
        """Get absolute URL for version file"""
        if obj.policy_file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.policy_file.url)
            return obj.policy_file.url
        return None
    
    def get_created_by_name(self, obj):
        """Get creator name"""
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.username
        return None


class PolicyVersionCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating new versions"""
    
    class Meta:
        model = PolicyVersion
        fields = ['policy', 'version', 'policy_file', 'changes_summary']
    
    def validate_policy_file(self, value):
        """Validate uploaded file"""
        if value:
            # Check file size (max 10MB)
            if value.size > 10 * 1024 * 1024:
                raise serializers.ValidationError(
                    "File size cannot exceed 10MB"
                )
            
            # Check file extension
            if not value.name.lower().endswith('.pdf'):
                raise serializers.ValidationError(
                    "Only PDF files are allowed"
                )
        
        return value
    
    def create(self, validated_data):
        """Create version with user tracking"""
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            validated_data['created_by'] = request.user
        
        return super().create(validated_data)


# ==================== STATISTICS SERIALIZERS ====================

class PolicyStatisticsSerializer(serializers.Serializer):
    """Serializer for policy statistics"""
    
    total_policies = serializers.IntegerField()
    total_folders = serializers.IntegerField()
    total_business_functions = serializers.IntegerField()
    mandatory_policies = serializers.IntegerField()
    policies_requiring_acknowledgment = serializers.IntegerField()
    total_views = serializers.IntegerField()
    total_downloads = serializers.IntegerField()
    policies_by_status = serializers.ListField()


class BusinessFunctionStatisticsSerializer(serializers.Serializer):
    """Serializer for business function statistics"""
    
    business_function_id = serializers.IntegerField()
    business_function_name = serializers.CharField()
    business_function_code = serializers.CharField()
    folder_count = serializers.IntegerField()
    policy_count = serializers.IntegerField()
    mandatory_policy_count = serializers.IntegerField()
    total_views = serializers.IntegerField()
    total_downloads = serializers.IntegerField()