"""Inventory app — stock tracking per product"""
from django.db import models


class Inventory(models.Model):
    """Tracks stock levels for each product."""
    product = models.OneToOneField('products.Product', on_delete=models.CASCADE, related_name='inventory')
    quantity_available = models.IntegerField(default=0)
    quantity_reserved = models.IntegerField(default=0)  # in open orders
    low_stock_threshold = models.IntegerField(default=10)
    reorder_point = models.IntegerField(default=5)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'inventory'
        verbose_name_plural = 'inventory'

    def __str__(self):
        return f"{self.product.name}: {self.quantity_available} available"

    @property
    def quantity_on_hand(self):
        return self.quantity_available - self.quantity_reserved

    @property
    def is_low_stock(self):
        return self.quantity_on_hand <= self.low_stock_threshold

    @property
    def is_out_of_stock(self):
        return self.quantity_on_hand <= 0


class StockMovement(models.Model):
    """Audit log of all stock changes."""
    MOVEMENT_TYPES = [
        ('purchase', 'Purchase (Inbound)'),
        ('sale', 'Sale (Outbound)'),
        ('return', 'Return'),
        ('adjustment', 'Manual Adjustment'),
        ('damage', 'Damage/Loss'),
    ]

    inventory = models.ForeignKey(Inventory, on_delete=models.CASCADE, related_name='movements')
    movement_type = models.CharField(max_length=20, choices=MOVEMENT_TYPES)
    quantity = models.IntegerField()  # positive = inbound, negative = outbound
    reference = models.CharField(max_length=200, blank=True)  # order ID, PO number etc
    notes = models.TextField(blank=True)
    performed_by = models.ForeignKey('users.User', null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'stock_movements'
        ordering = ['-created_at']
