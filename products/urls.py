from django.urls import path
from .views import ProductListView, ProductSearchView, ProductDetailView

urlpatterns = [
    path('', ProductListView.as_view(), name='product-list'),
    path('search/', ProductSearchView.as_view(), name='product-search'),
    path('<int:pk>/', ProductDetailView.as_view(), name='product-detail'),
]
