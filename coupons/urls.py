from django.urls import path
from .views import ApplyCouponView, ValidateCouponView

urlpatterns = [
    path('apply/', ApplyCouponView.as_view(), name='coupon-apply'),
    path('validate/', ValidateCouponView.as_view(), name='coupon-validate'),
]
