"""
orders/views.py — Order history and admin dashboard stats

"""
from rest_framework import generics, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import Count, Sum, Avg
from django.db.models.functions import TruncMonth
from django.utils import timezone
from datetime import timedelta
from .models import Order, OrderItem


class OrderHistoryView(generics.ListAPIView):
    """
    Returns the authenticated user's order history.
    Properly scoped to the requesting user only.
    """
    permission_classes = [permissions.IsAuthenticated]

    def list(self, request, *args, **kwargs):
        orders = Order.objects.filter(
            user=request.user
        ).select_related(
            'shipping_address', 'coupon'
        ).prefetch_related(
            'items__product'
        ).order_by('-created_at')

        result = []
        for order in orders:
            items = [
                {
                    'product_id': item.product.id,
                    'product_name': item.product.name,
                    'quantity': item.quantity,
                    'unit_price': str(item.unit_price),
                    'total_price': str(item.total_price),
                }
                for item in order.items.all()
            ]

            result.append({
                'order_id': order.id,
                'status': order.status,
                'total': str(order.total),
                'item_count': len(items),
                'items': items,
                'created_at': order.created_at.isoformat(),
                'tracking_number': order.tracking_number or None,
            })

        return Response({'orders': result, 'count': len(result)})


class OrderDetailView(APIView):
    """Returns details of a single order, scoped to the requesting user."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, order_id):
        try:
            order = Order.objects.select_related(
                'shipping_address', 'coupon'
            ).prefetch_related(
                'items__product__images'
            ).get(id=order_id, user=request.user)  # user=request.user ensures ownership
        except Order.DoesNotExist:
            return Response({'error': 'Order not found.'}, status=404)

        items = [
            {
                'product_id': item.product.id,
                'name': item.product.name,
                'sku': item.product.sku,
                'quantity': item.quantity,
                'unit_price': str(item.unit_price),
                'total_price': str(item.total_price),
            }
            for item in order.items.all()
        ]

        return Response({
            'order_id': order.id,
            'status': order.status,
            'subtotal': str(order.subtotal),
            'discount_amount': str(order.discount_amount),
            'shipping_cost': str(order.shipping_cost),
            'tax_amount': str(order.tax_amount),
            'total': str(order.total),
            'items': items,
            'shipping_address': {
                'street': order.shipping_address.street,
                'city': order.shipping_address.city,
                'state': order.shipping_address.state,
                'postal_code': order.shipping_address.postal_code,
                'country': order.shipping_address.country,
            },
            'tracking_number': order.tracking_number or None,
            'created_at': order.created_at.isoformat(),
        })


class AdminDashboardView(APIView):
    """Admin-only dashboard with sales metrics."""
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        days = int(request.query_params.get('days', 30))
        since = timezone.now() - timedelta(days=days)

        stats = Order.objects.filter(
            created_at__gte=since,
            status__in=['confirmed', 'processing', 'shipped', 'delivered']
        ).aggregate(
            total_orders=Count('id'),
            total_revenue=Sum('total'),
            avg_order_value=Avg('total'),
        )

        monthly = list(
            Order.objects.filter(
                status__in=['confirmed', 'processing', 'shipped', 'delivered']
            ).annotate(
                month=TruncMonth('created_at')
            ).values('month').annotate(
                orders=Count('id'),
                revenue=Sum('total')
            ).order_by('month')
        )

        return Response({
            'period_days': days,
            'total_orders': stats['total_orders'] or 0,
            'total_revenue': str(stats['total_revenue'] or 0),
            'avg_order_value': str(stats['avg_order_value'] or 0),
            'monthly_breakdown': [
                {
                    'month': m['month'].strftime('%Y-%m'),
                    'orders': m['orders'],
                    'revenue': str(m['revenue']),
                }
                for m in monthly
            ],
        })
