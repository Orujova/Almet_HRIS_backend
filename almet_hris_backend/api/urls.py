# Backend problemi: urls.py - sadələşdirilmiş versiya

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from . import views

# Əvvəlcə yoxlayaq ki, ViewSet sinifləri views modulunda mövcuddur
# Əgər yoxdursa, onları qeydiyyatdan keçirməyə cəhd etməyin
router = DefaultRouter()

# Əsas URL patternləri - ViewSet olmadan işləyən endpointlər
urlpatterns = [
    # Authentication endpoints
    path('auth/microsoft/', views.authenticate_microsoft, name='auth_microsoft'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # User endpoints
    path('me/', views.user_info, name='user_info'),
]

# ViewSet-ləri əlavə edin - lakin əvvəlcə onların mövcudluğunu yoxlayın
if hasattr(views, 'EmployeeViewSet'):
    router.register(r'employees', views.EmployeeViewSet)

if hasattr(views, 'DepartmentViewSet'):
    router.register(r'departments', views.DepartmentViewSet)

# Router URL-ləri əlavə edin
urlpatterns += router.urls