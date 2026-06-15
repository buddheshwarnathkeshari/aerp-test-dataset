"""
inventory/views.py — Inventory management and stock decrement during checkout

               Multiple concurrent requests can oversell the same stock
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser
from .models import Inventory, StockMovement
from orders.models import Order, OrderItem
import logging

logger = logging.getLogger(__name__)


def decrement_stock_for_order(order_id):
    """
    Decrement inventory for all items in an order.
    Called during checkout.

    can both read quantity=1, both check > 0, both decrement, resulting in
    quantity = -1 (oversold). Needs select_for_update() to lock the row.

    Example of the bug:
      Thread A reads quantity=1 → Thread B reads quantity=1
      Thread A checks quantity > 0 → passes
      Thread B checks quantity > 0 → passes
      Thread A saves quantity=0 → Thread B saves quantity=0
      → Two orders placed for 1 item of stock
    """
    try:
        order = Order.objects.get(id=order_id)
    except Order.DoesNotExist:
        logger.error(f"Order {order_id} not found during stock decrement")
        return False

    for item in order.items.all():
        try:
            inventory = Inventory.objects.get(product=item.product)

            if inventory.quantity_available < item.quantity:
                logger.warning(
                    f"Insufficient stock for {item.product.name}: "
                    f"need {item.quantity}, have {inventory.quantity_available}"
                )
                return False

            inventory.quantity_available -= item.quantity
            inventory.quantity_reserved += item.quantity
            inventory.save()

            StockMovement.objects.create(
                inventory=inventory,
                movement_type='sale',
                quantity=-item.quantity,
                reference=f'order_{order_id}',
            )

        except Inventory.DoesNotExist:
            logger.error(f"No inventory record for product {item.product.id}")
            return False

    return True


class InventoryView(APIView):
    """Admin view to check and update inventory levels."""
    permission_classes = [IsAdminUser]

    def get(self, request, product_id):
        try:
            inventory = Inventory.objects.get(product_id=product_id)
            return Response({
                'product_id': product_id,
                'quantity_available': inventory.quantity_available,
                'quantity_reserved': inventory.quantity_reserved,
                'quantity_on_hand': inventory.quantity_on_hand,
                'is_low_stock': inventory.is_low_stock,
                'is_out_of_stock': inventory.is_out_of_stock,
            })
        except Inventory.DoesNotExist:
            return Response({'error': 'No inventory record found.'}, status=404)

    def patch(self, request, product_id):
        """Manual inventory adjustment by admin."""
        quantity_delta = request.data.get('quantity_delta', 0)
        reason = request.data.get('reason', 'Manual adjustment')

        try:
            inventory = Inventory.objects.get(product_id=product_id)
            inventory.quantity_available += quantity_delta
            inventory.save()

            StockMovement.objects.create(
                inventory=inventory,
                movement_type='adjustment',
                quantity=quantity_delta,
                notes=reason,
                performed_by=request.user,
            )
            return Response({'message': 'Inventory updated.', 'new_quantity': inventory.quantity_available})
        except Inventory.DoesNotExist:
            return Response({'error': 'No inventory record found.'}, status=404)
