from rest_framework import serializers
from .policy_models import PolicyCategory, CompanyPolicy, PolicyAcknowledgment


class PolicyCategorySerializer(serializers.ModelSerializer):
    """Kateqoriya serializer"""
    policies_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = PolicyCategory
        fields = [
            'id', 
            'name', 
            'description', 
            'order',
            'is_active',
            'policies_count',
            'created_at',
            'updated_at'
        ]


class CompanyPolicyListSerializer(serializers.ModelSerializer):
    """Policy list üçün sadələşdirilmiş serializer"""
    category_name = serializers.CharField(source='category.name', read_only=True)
    pdf_url = serializers.SerializerMethodField()
    is_acknowledged = serializers.SerializerMethodField()
    
    class Meta:
        model = CompanyPolicy
        fields = [
            'id',
            'slug',
            'title',
            'category_name',
            'icon',
            'description',
            'pdf_url',
            'version',
            'effective_date',
            'is_mandatory',
            'view_count',
            'download_count',
            'is_acknowledged',
            'updated_at'
        ]

    def get_pdf_url(self, obj):
        """PDF URL-ini qaytarır"""
        request = self.context.get('request')
        if obj.pdf_file and request:
            return request.build_absolute_uri(obj.pdf_file.url)
        return None

    def get_is_acknowledged(self, obj):
        """İstifadəçi bu policy-ni təsdiq edibmi?"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return PolicyAcknowledgment.objects.filter(
                policy=obj,
                employee=request.user
            ).exists()
        return False


class CompanyPolicyDetailSerializer(serializers.ModelSerializer):
    """Policy detail üçün tam məlumat"""
    category = PolicyCategorySerializer(read_only=True)
    category_id = serializers.IntegerField(write_only=True, required=False)
    pdf_url = serializers.SerializerMethodField()
    pdf_file = serializers.FileField(required=False)  # Update zamanı optional
    created_by_name = serializers.CharField(
        source='created_by.get_full_name', 
        read_only=True
    )
    updated_by_name = serializers.CharField(
        source='updated_by.get_full_name', 
        read_only=True
    )
    is_acknowledged = serializers.SerializerMethodField()
    acknowledgment_date = serializers.SerializerMethodField()
    
    def validate(self, data):
        """Create zamanı PDF məcburidir"""
        request = self.context.get('request')
        
        # Yalnız CREATE zamanı yoxla
        if request and request.method == 'POST':
            if 'pdf_file' not in request.FILES:
                raise serializers.ValidationError({
                    'pdf_file': 'PDF file is required when creating a policy'
                })
        
        return data
    
    class Meta:
        model = CompanyPolicy
        fields = [
            'id',
            'slug',
            'title',
            'category',
            'category_id',
            'icon',
            'description',
            'pdf_file',
            'pdf_url',
            'version',
            'effective_date',
            'review_date',
            'is_active',
            'is_mandatory',
            'view_count',
            'download_count',
            'created_by_name',
            'updated_by_name',
            'created_at',
            'updated_at',
            'is_acknowledged',
            'acknowledgment_date'
        ]
        read_only_fields = [
            'slug',
            'view_count',
            'download_count',
            'created_at',
            'updated_at'
        ]

    def get_pdf_url(self, obj):
        request = self.context.get('request')
        if obj.pdf_file and request:
            return request.build_absolute_uri(obj.pdf_file.url)
        return None

    def get_is_acknowledged(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return PolicyAcknowledgment.objects.filter(
                policy=obj,
                employee=request.user
            ).exists()
        return False

    def get_acknowledgment_date(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            ack = PolicyAcknowledgment.objects.filter(
                policy=obj,
                employee=request.user
            ).first()
            return ack.acknowledged_at if ack else None
        return None


class PolicyAcknowledgmentSerializer(serializers.ModelSerializer):
    """Policy təsdiq serializer"""
    employee_name = serializers.CharField(
        source='employee.get_full_name', 
        read_only=True
    )
    employee_email = serializers.EmailField(
        source='employee.email',
        read_only=True
    )
    policy_title = serializers.CharField(
        source='policy.title', 
        read_only=True
    )

    class Meta:
        model = PolicyAcknowledgment
        fields = [
            'id',
            'policy',
            'policy_title',
            'employee',
            'employee_name',
            'employee_email',
            'acknowledged_at',
            'ip_address',
            'notes'
        ]
        read_only_fields = ['employee', 'acknowledged_at', 'ip_address']

    def create(self, validated_data):
        request = self.context.get('request')
        validated_data['employee'] = request.user
        validated_data['ip_address'] = self.get_client_ip(request)
        return super().create(validated_data)

    def get_client_ip(self, request):
        """İstifadəçinin IP ünvanını alır"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class PolicyStatsSerializer(serializers.Serializer):
    """Policy statistikası"""
    total_policies = serializers.IntegerField()
    active_policies = serializers.IntegerField()
    mandatory_policies = serializers.IntegerField()
    acknowledged_policies = serializers.IntegerField()
    pending_acknowledgments = serializers.IntegerField()
    categories_count = serializers.IntegerField()
    total_views = serializers.IntegerField()
    total_downloads = serializers.IntegerField()