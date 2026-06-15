from django.urls import path
from .views import InitiatePaymentView, ConfirmPaymentView, WebhookView

urlpatterns = [
    path('initiate/', InitiatePaymentView.as_view(), name='payment-initiate'),
    path('confirm/', ConfirmPaymentView.as_view(), name='payment-confirm'),
    path('webhook/', WebhookView.as_view(), name='payment-webhook'),
]
