from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from . import views

# Create router and register viewsets
router = DefaultRouter()

# Reference data endpoints
router.register(r'Business function', views.BusinessFunctionViewSet, basename='businessfunction')
router.register(r'Department', views.DepartmentViewSet, basename='department')
router.register(r'Unit', views.UnitViewSet, basename='unit')
router.register(r'Job function', views.JobFunctionViewSet, basename='jobfunction')
router.register(r'Position group', views.PositionGroupViewSet, basename='positiongroup')
router.register(r'Employee statuses', views.EmployeeStatusViewSet, basename='employeestatus')
router.register(r'Employee tags', views.EmployeeTagViewSet, basename='employeetag')

# Main employee endpoints
router.register(r'Employees', views.EmployeeViewSet, basename='employee')
router.register(r'Employee Documents', views.EmployeeDocumentViewSet, basename='employeedocument')
router.register(r'Employee activities', views.EmployeeActivityViewSet, basename='employeeactivity')

urlpatterns = [
 
    
    # Authentication endpoints
    path('auth/microsoft/', views.authenticate_microsoft, name='auth_microsoft'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # User endpoints
    path('me/', views.user_info, name='user_info'),
    
    # ViewSet endpoints
    path('', include(router.urls)),
]