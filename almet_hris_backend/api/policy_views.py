from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count, Q, Sum
from django.http import FileResponse, Http404
from django.utils.text import slugify
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from .policy_models import PolicyCategory, CompanyPolicy, PolicyAcknowledgment
from .policy_serializers import (
    PolicyCategorySerializer,
    CompanyPolicyListSerializer,
    CompanyPolicyDetailSerializer,
    PolicyAcknowledgmentSerializer,
    PolicyStatsSerializer
)


class PolicyCategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """Policy kateqoriyaları"""
    queryset = PolicyCategory.objects.filter(is_active=True)
    serializer_class = PolicyCategorySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return self.queryset.annotate(
            policies_count=Count(
                'policies',
                filter=Q(policies__is_active=True)
            )
        )


class CompanyPolicyViewSet(viewsets.ModelViewSet):
    """Şirkət policy-ləri CRUD"""
    queryset = CompanyPolicy.objects.filter(is_active=True).select_related(
        'category', 'created_by', 'updated_by'
    )
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'description', 'category__name']
    ordering_fields = ['title', 'created_at', 'view_count', 'download_count']
    ordering = ['category__order', 'title']
    lookup_field = 'slug'

    def get_serializer_class(self):
        if self.action == 'list':
            return CompanyPolicyListSerializer
        return CompanyPolicyDetailSerializer

    def get_queryset(self):
        queryset = self.queryset
        
        # Kateqoriya filtri
        category_id = self.request.query_params.get('category')
        if category_id:
            queryset = queryset.filter(category_id=category_id)
        
        # Məcburi policy-lər
        mandatory = self.request.query_params.get('mandatory')
        if mandatory is not None:
            queryset = queryset.filter(is_mandatory=mandatory.lower() == 'true')
        
        # Təsdiq edilməmiş policy-lər
        unacknowledged = self.request.query_params.get('unacknowledged')
        if unacknowledged and unacknowledged.lower() == 'true':
            acknowledged_ids = PolicyAcknowledgment.objects.filter(
                employee=self.request.user
            ).values_list('policy_id', flat=True)
            queryset = queryset.exclude(id__in=acknowledged_ids)
        
        return queryset

    def perform_create(self, serializer):
        """Policy yaradır - PDF məcburidir"""
        title = serializer.validated_data['title']
        slug = slugify(title)
        
        # Unikal slug
        original_slug = slug
        counter = 1
        while CompanyPolicy.objects.filter(slug=slug).exists():
            slug = f"{original_slug}-{counter}"
            counter += 1
        
        serializer.save(
            slug=slug,
            created_by=self.request.user,
            updated_by=self.request.user
        )

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)

    @action(detail=True, methods=['post'])
    def increment_view(self, request, slug=None):
        """View sayını artırır"""
        policy = self.get_object()
        policy.increment_view_count()
        return Response({'view_count': policy.view_count})

    @action(detail=True, methods=['post'])
    def increment_download(self, request, slug=None):
        """Download sayını artırır"""
        policy = self.get_object()
        policy.increment_download_count()
        return Response({'download_count': policy.download_count})

    @action(detail=True, methods=['get'])
    def download(self, request, slug=None):
        """PDF-i download edir"""
        policy = self.get_object()
        
        if not policy.pdf_file:
            raise Http404("PDF file not found")
        
        policy.increment_download_count()
        
        response = FileResponse(
            policy.pdf_file.open('rb'),
            content_type='application/pdf'
        )
        response['Content-Disposition'] = f'attachment; filename="{policy.title}.pdf"'
        return response

    @action(detail=True, methods=['post', 'put'])
    def upload_pdf(self, request, slug=None):
        """PDF faylını yüklə və ya yenilə"""
        policy = self.get_object()
        
        if 'pdf_file' not in request.FILES:
            return Response(
                {'detail': 'PDF file is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        pdf_file = request.FILES['pdf_file']
        
        # PDF format yoxlaması
        if not pdf_file.name.endswith('.pdf'):
            return Response(
                {'detail': 'Only PDF files are allowed'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Köhnə faylı sil (əgər varsa)
        if policy.pdf_file:
            policy.pdf_file.delete(save=False)
        
        # Yeni faylı yüklə
        policy.pdf_file = pdf_file
        policy.save()
        
        serializer = self.get_serializer(policy)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def acknowledge(self, request, slug=None):
        """Policy-ni təsdiq edir"""
        policy = self.get_object()
        
        if PolicyAcknowledgment.objects.filter(
            policy=policy,
            employee=request.user
        ).exists():
            return Response(
                {'detail': 'Already acknowledged'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = PolicyAcknowledgmentSerializer(
            data={'policy': policy.id, 'notes': request.data.get('notes', '')},
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Policy statistikası"""
        user = request.user
        
        total_policies = CompanyPolicy.objects.filter(is_active=True).count()
        mandatory_policies = CompanyPolicy.objects.filter(
            is_active=True,
            is_mandatory=True
        ).count()
        
        acknowledged_count = PolicyAcknowledgment.objects.filter(
            employee=user
        ).count()
        
        pending = mandatory_policies - PolicyAcknowledgment.objects.filter(
            employee=user,
            policy__is_mandatory=True
        ).count()
        
        categories_count = PolicyCategory.objects.filter(is_active=True).count()
        
        stats = CompanyPolicy.objects.filter(is_active=True).aggregate(
            total_views=Sum('view_count'),
            total_downloads=Sum('download_count')
        )
        
        data = {
            'total_policies': total_policies,
            'active_policies': total_policies,
            'mandatory_policies': mandatory_policies,
            'acknowledged_policies': acknowledged_count,
            'pending_acknowledgments': max(0, pending),
            'categories_count': categories_count,
            'total_views': stats['total_views'] or 0,
            'total_downloads': stats['total_downloads'] or 0
        }
        
        serializer = PolicyStatsSerializer(data)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def my_acknowledgments(self, request):
        """İstifadəçinin təsdiq etdiyi policy-lər"""
        acknowledgments = PolicyAcknowledgment.objects.filter(
            employee=request.user
        ).select_related('policy', 'policy__category')
        
        serializer = PolicyAcknowledgmentSerializer(
            acknowledgments,
            many=True,
            context={'request': request}
        )
        return Response(serializer.data)


class PolicyAcknowledgmentViewSet(viewsets.ReadOnlyModelViewSet):
    """Policy təsdiqləmələri (admin üçün)"""
    queryset = PolicyAcknowledgment.objects.all().select_related(
        'policy', 'employee'
    )
    serializer_class = PolicyAcknowledgmentSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = [
        'policy__title',
        'employee__first_name',
        'employee__last_name',
        'employee__email'
    ]
    ordering_fields = ['acknowledged_at']
    ordering = ['-acknowledged_at']

    def get_queryset(self):
        queryset = self.queryset
        
        # Policy filtri
        policy_id = self.request.query_params.get('policy')
        if policy_id:
            queryset = queryset.filter(policy_id=policy_id)
        
        # Employee filtri
        employee_id = self.request.query_params.get('employee')
        if employee_id:
            queryset = queryset.filter(employee_id=employee_id)
        
        return queryset

    @action(detail=False, methods=['get'])
    def by_policy(self, request):
        """Policy-ə görə təsdiq statistikası"""
        policy_id = request.query_params.get('policy_id')
        if not policy_id:
            return Response(
                {'detail': 'policy_id parameter required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            policy = CompanyPolicy.objects.get(id=policy_id)
        except CompanyPolicy.DoesNotExist:
            raise Http404("Policy not found")
        
        acknowledgments = self.queryset.filter(policy=policy)
        
        return Response({
            'policy': CompanyPolicyDetailSerializer(
                policy,
                context={'request': request}
            ).data,
            'total_acknowledgments': acknowledgments.count(),
            'acknowledgments': PolicyAcknowledgmentSerializer(
                acknowledgments,
                many=True
            ).data
        })