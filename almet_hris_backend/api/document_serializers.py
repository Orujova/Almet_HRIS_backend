# api/document_serializers.py - FIXED VERSION

from rest_framework import serializers
from .document_models import DocumentCompany, DocumentFolder, Document


# ==================== DOCUMENT COMPANY SERIALIZERS ====================

class DocumentCompanySerializer(serializers.ModelSerializer):
    """Serializer for document companies"""
    
    folder_count = serializers.SerializerMethodField()
    total_documents = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    is_auto_created = serializers.SerializerMethodField()
    
    class Meta:
        model = DocumentCompany
        fields = [
            'id', 'business_function', 'name', 'code', 
            'icon',  'folder_count', 'total_documents', 
            'is_active', 'is_auto_created',
            'created_by', 'created_by_name', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_by', 'created_at', 'updated_at']
    
    def get_is_auto_created(self, obj):
        """Check if this was auto-created from BusinessFunction"""
        return obj.business_function is not None
    
    def get_folder_count(self, obj):
        return obj.folders.filter(is_active=True).count()
    
    def get_total_documents(self, obj):
        return obj.get_total_documents()
    
    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.username
        return None


class DocumentCompanyCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating MANUAL companies only"""
    
    class Meta:
        model = DocumentCompany
        fields = ['id', 'name', 'code',  'icon', 'is_active']
    
    def validate_name(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Company name cannot be empty")
        
        instance_pk = self.instance.pk if self.instance else None
        if DocumentCompany.objects.filter(name__iexact=value.strip()).exclude(pk=instance_pk).exists():
            raise serializers.ValidationError(f"Company '{value}' already exists")
        
        return value.strip()
    
    def validate_code(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Company code cannot be empty")
        
        instance_pk = self.instance.pk if self.instance else None
        if DocumentCompany.objects.filter(code__iexact=value.strip()).exclude(pk=instance_pk).exists():
            raise serializers.ValidationError(f"Code '{value}' already exists")
        
        return value.strip().upper()


# ==================== DOCUMENT FOLDER SERIALIZERS ====================

class DocumentFolderSerializer(serializers.ModelSerializer):
    """Serializer for document folders"""
    
    company_name = serializers.CharField(source='company.name', read_only=True)
    company_code = serializers.CharField(source='company.code', read_only=True)
    document_count = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    
    class Meta:
        model = DocumentFolder
        fields = [
            'id', 'company', 'company_name', 'company_code',
            'name', 'description', 'icon', 'order',
            'document_count', 'is_active',
            'created_by', 'created_by_name', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_by', 'created_at', 'updated_at']
    
    def get_document_count(self, obj):
        return obj.get_document_count()
    
    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.username
        return None


class DocumentFolderCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating folders"""
    
    class Meta:
        model = DocumentFolder
        fields = ['id', 'company', 'name', 'description', 'icon', 'order', 'is_active']
    
    def validate_name(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Folder name cannot be empty")
        return value.strip()
    
    def validate(self, data):
        company = data.get('company')
        name = data.get('name')
        
        if company and name:
            instance_pk = self.instance.pk if self.instance else None
            existing = DocumentFolder.objects.filter(
                company=company,
                name__iexact=name.strip()
            ).exclude(pk=instance_pk)
            
            if existing.exists():
                raise serializers.ValidationError({
                    'name': f"Folder '{name}' already exists in {company.name}"
                })
        
        return data


# ==================== DOCUMENT SERIALIZERS ====================

class DocumentListSerializer(serializers.ModelSerializer):
    """Serializer for document list view"""
    
    folder_name = serializers.CharField(source='folder.name', read_only=True)
    company_name = serializers.CharField(source='folder.company.name', read_only=True)
    company_code = serializers.CharField(source='folder.company.code', read_only=True)
    file_size_display = serializers.CharField(source='get_file_size_display', read_only=True)
    file_extension = serializers.CharField(source='get_file_extension', read_only=True)
    document_url = serializers.SerializerMethodField()

    
    class Meta:
        model = Document
        fields = [
            'id', 'folder', 'folder_name', 'company_name', 'company_code',
            'document_type',  'title', 'description',
             'file_size', 'file_size_display', 'file_extension',
            'view_count', 'download_count', 'document_url',
            'tags', 'is_active', 'is_archived', 'effective_date',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['file_size', 'view_count', 'download_count', 'created_at', 'updated_at']
    
    def get_document_url(self, obj):
        if obj.document_file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.document_file.url)
            return obj.document_file.url
        return None


class DocumentDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for single document"""
    
    folder_details = DocumentFolderSerializer(source='folder', read_only=True)
    file_size_display = serializers.CharField(source='get_file_size_display', read_only=True)
    file_extension = serializers.CharField(source='get_file_extension', read_only=True)
    document_url = serializers.SerializerMethodField()
  
    created_by_name = serializers.SerializerMethodField()
    updated_by_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Document
        fields = [
            'id', 'folder', 'folder_details', 'document_type',
            'title', 'description', 'document_file', 'document_url',
            'file_size', 'file_size_display', 'file_extension',
        'view_count', 'download_count',
            'tags', 'is_active', 'is_archived', 'effective_date',
            'created_by', 'created_by_name', 'updated_by', 'updated_by_name',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_by', 'created_at', 'updated_at', 'file_size', 'view_count', 'download_count']
    
    def get_document_url(self, obj):
        if obj.document_file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.document_file.url)
            return obj.document_file.url
        return None
    
    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.username
        return None
    
    def get_updated_by_name(self, obj):
        if obj.updated_by:
            return obj.updated_by.get_full_name() or obj.updated_by.username
        return None


class DocumentCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating documents"""
    
    document_file = serializers.FileField(required=False)
    
    class Meta:
        model = Document
        fields = [
            'id', 'folder', 'document_type', 'title', 'description',
            'document_file',  'tags', 'is_active', 'is_archived',
            'effective_date'
        ]
    
    def validate_document_file(self, value):
        if value and value.size > 20 * 1024 * 1024:
            raise serializers.ValidationError(
                f"File size cannot exceed 20MB (current: {value.size / (1024 * 1024):.2f}MB)"
            )
        
        if value:
            allowed_extensions = ['pdf', 'docx', 'xlsx', 'pptx', 'txt', 'doc', 'xls', 'ppt']
            ext = value.name.split('.')[-1].lower()
            
            if ext not in allowed_extensions:
                raise serializers.ValidationError(
                    f"File type '.{ext}' not allowed. Allowed: {', '.join(allowed_extensions)}"
                )
        
        return value
    
    def validate_title(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Document title cannot be empty")
        return value.strip()
    
    def create(self, validated_data):
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            validated_data['created_by'] = request.user
        return super().create(validated_data)
    
    def update(self, instance, validated_data):
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            validated_data['updated_by'] = request.user
        return super().update(instance, validated_data)
    
    def to_representation(self, instance):
        """Return detailed representation after create/update"""
        return DocumentDetailSerializer(instance, context=self.context).data


# ==================== STATISTICS SERIALIZER ====================

class DocumentStatisticsSerializer(serializers.Serializer):
    """Serializer for document statistics"""
    
    total_companies = serializers.IntegerField()
    total_folders = serializers.IntegerField()
    total_documents = serializers.IntegerField()
    documents_by_type = serializers.DictField()
    total_views = serializers.IntegerField()
    total_downloads = serializers.IntegerField()
    recent_documents = DocumentListSerializer(many=True)