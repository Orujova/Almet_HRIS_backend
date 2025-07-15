# almet_hris_backend/urls.py

from django.contrib import admin
from django.urls import path, include
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

# Swagger schema configuration
schema_view = get_schema_view(
   openapi.Info(
      title="Almetcentral HRIS API",
      default_version='v1',

   
   ),
   public=True,
   permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    # Admin interface
    path('admin/', admin.site.urls),
    
    # API endpoints
    path('api/', include('api.urls')),
    path('api/grading/', include('grading.urls')),  # ADD GRADING URLS HERE
    
    # API Documentation
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
    path('api/docs/', schema_view.with_ui('swagger', cache_timeout=0), name='api-docs'),
]

# Add this for development - serve media files
from django.conf import settings
from django.conf.urls.static import static

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# API Endpoint Summary (for documentation):
"""
Employee Management APIs:
- /api/employees/ - Employee CRUD operations
- /api/business-functions/ - Business function management
- /api/departments/ - Department management
- /api/units/ - Unit management
- /api/position-groups/ - Position group management
- /api/employee-statuses/ - Employee status management

Grading System APIs:
- /api/grading/systems/ - Grading system management
- /api/grading/salary-grades/ - Current salary grades
- /api/grading/scenarios/ - Scenario management
- /api/grading/scenarios/{id}/calculate/ - Calculate scenario
- /api/grading/scenarios/{id}/apply/ - Apply scenario
- /api/grading/scenarios/current/ - Get current scenario
- /api/grading/growth-rates/ - Vertical growth rates
- /api/grading/horizontal-rates/ - Horizontal growth rates
- /api/grading/history/ - Scenario history

Authentication & Documentation:
- /api/auth/microsoft/ - Microsoft OAuth authentication
- /api/me/ - Current user information
- /swagger/ - API documentation (Swagger UI)
- /redoc/ - API documentation (ReDoc)
- /admin/ - Django admin interface
"""