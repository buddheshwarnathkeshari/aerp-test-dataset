from django.urls import path
from .views import OrderHistoryView, OrderDetailView, AdminDashboardView

urlpatterns = [
    path('', OrderHistoryView.as_view(), name='order-list'),
    path('<int:order_id>/', OrderDetailView.as_view(), name='order-detail'),
    path('admin/dashboard/', AdminDashboardView.as_view(), name='admin-dashboard'),
]
