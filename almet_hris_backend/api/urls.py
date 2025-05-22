from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from . import views

router = DefaultRouter()

# ViewSet-ləri əlavə edin
if hasattr(views, 'EmployeeViewSet'):
    router.register(r'employees', views.EmployeeViewSet)

if hasattr(views, 'DepartmentViewSet'):
    router.register(r'departments', views.DepartmentViewSet)

urlpatterns = [
    # Test endpoints
    path('health/', views.health_check, name='health_check'),
    path('test/', views.test_endpoint, name='test_endpoint'),
  
    
    # Authentication endpoints
    path('auth/microsoft/', views.authenticate_microsoft, name='auth_microsoft'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # User endpoints
    path('me/', views.user_info, name='user_info'),
    
    # ViewSet endpoints
    path('', include(router.urls)),
]