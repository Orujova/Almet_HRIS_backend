# grading/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'systems', views.GradingSystemViewSet, basename='gradingsystem')
router.register(r'salary-grades', views.SalaryGradeViewSet, basename='salarygrade')
router.register(r'growth-rates', views.GrowthRateViewSet, basename='growthrate')
router.register(r'horizontal-rates', views.HorizontalRateViewSet, basename='horizontalrate')
router.register(r'scenarios', views.SalaryScenarioViewSet, basename='salaryScenario')
router.register(r'history', views.ScenarioHistoryViewSet, basename='scenariohistory')

urlpatterns = [
    path('', include(router.urls)),
]

# Available endpoints:
# 
# Grading Systems:
# GET    /grading/systems/                     - List grading systems
# POST   /grading/systems/                     - Create grading system
# GET    /grading/systems/{id}/                - Get grading system details
# PUT    /grading/systems/{id}/                - Update grading system
# DELETE /grading/systems/{id}/                - Delete grading system
# GET    /grading/systems/dropdowns/           - Get dropdown data
# 
# Salary Grades:
# GET    /grading/salary-grades/               - List salary grades
# POST   /grading/salary-grades/               - Create salary grade
# GET    /grading/salary-grades/{id}/          - Get salary grade details
# PUT    /grading/salary-grades/{id}/          - Update salary grade
# DELETE /grading/salary-grades/{id}/          - Delete salary grade
# GET    /grading/salary-grades/by_system/     - Get grades by system
# 
# Growth Rates (Vertical):
# GET    /grading/growth-rates/                - List growth rates
# POST   /grading/growth-rates/                - Create growth rate
# GET    /grading/growth-rates/{id}/           - Get growth rate details
# PUT    /grading/growth-rates/{id}/           - Update growth rate
# DELETE /grading/growth-rates/{id}/           - Delete growth rate
# POST   /grading/growth-rates/bulk_create/    - Bulk create growth rates
# 
# Horizontal Rates:
# GET    /grading/horizontal-rates/            - List horizontal rates
# POST   /grading/horizontal-rates/            - Create horizontal rate
# GET    /grading/horizontal-rates/{id}/       - Get horizontal rate details
# PUT    /grading/horizontal-rates/{id}/       - Update horizontal rate
# DELETE /grading/horizontal-rates/{id}/       - Delete horizontal rate
# POST   /grading/horizontal-rates/bulk_create/ - Bulk create horizontal rates
# 
# Scenarios:
# GET    /grading/scenarios/                   - List scenarios
# POST   /grading/scenarios/                   - Create scenario
# GET    /grading/scenarios/{id}/              - Get scenario details
# PUT    /grading/scenarios/{id}/              - Update scenario
# DELETE /grading/scenarios/{id}/              - Delete scenario
# POST   /grading/scenarios/{id}/calculate/    - Calculate scenario (final)
# POST   /grading/scenarios/{id}/apply/        - Apply scenario as current
# POST   /grading/scenarios/{id}/archive/      - Archive scenario
# POST   /grading/scenarios/{id}/duplicate/    - Duplicate scenario
# GET    /grading/scenarios/current/           - Get current scenario
# GET    /grading/scenarios/statistics/        - Get scenario statistics
# 
# NEW DYNAMIC SCENARIO ENDPOINTS:
# POST   /grading/scenarios/initialize_scenario/ - Initialize new scenario with base value
# POST   /grading/scenarios/calculate_dynamic/   - Calculate scenario dynamically as rates are entered
# POST   /grading/scenarios/save_scenario/       - Save scenario with all data
# 
# History:
# GET    /grading/history/                     - List scenario history
# GET    /grading/history/{id}/                - Get history entry details
# GET    /grading/history/recent/              - Get recent history entries


# API Usage Examples for Dynamic Scenario Creation:

