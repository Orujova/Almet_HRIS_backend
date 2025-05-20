# api/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from . import views

router = DefaultRouter()
router.register(r'employees', views.EmployeeViewSet)
router.register(r'departments', views.DepartmentViewSet)

urlpatterns = [
    # Authentication endpoints
    path('auth/microsoft/', views.authenticate_microsoft, name='auth_microsoft'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # User endpoints
    path('me/', views.user_info, name='user_info'),
    
    # Include router URLs
    path('', include(router.urls)),
]