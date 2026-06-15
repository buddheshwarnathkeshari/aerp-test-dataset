from django.urls import path
from .views import InventoryView

urlpatterns = [
    path('<int:product_id>/', InventoryView.as_view(), name='inventory-detail'),
]
