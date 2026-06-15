"""Payments app — payment processing, transactions, refunds"""
from django.db import models


class Payment(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('succeeded', 'Succeeded'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
        ('partially_refunded', 'Partially Refunded'),
    ]

    PROVIDER_CHOICES = [
        ('razorpay', 'Razorpay'),
        ('stripe', 'Stripe'),
        ('paytm', 'Paytm'),
        ('upi', 'UPI'),
        ('cod', 'Cash on Delivery'),
    ]

    order = models.ForeignKey('orders.Order', on_delete=models.PROTECT, related_name='payments')
    user = models.ForeignKey('users.User', on_delete=models.PROTECT)
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES)
    provider_payment_id = models.CharField(max_length=200, blank=True)
    provider_order_id = models.CharField(max_length=200, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default='INR')
    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default='pending')
    failure_reason = models.TextField(blank=True)
    refund_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'payments'
        indexes = [
            models.Index(fields=['order']),
            models.Index(fields=['user', 'status']),
            models.Index(fields=['provider_payment_id']),
        ]

    def __str__(self):
        return f"Payment #{self.pk} - {self.amount} {self.currency} ({self.status})"
