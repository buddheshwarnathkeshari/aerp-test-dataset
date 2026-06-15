"""
coupons/views.py — Coupon validation and discount application

               No atomic transaction, can be double-applied due to race condition
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from .models import Coupon, CouponUsage
from orders.models import Order


def calculate_discount(coupon, order_total):
    """
    Calculate the discount amount for a given coupon and order total.

    is somehow > 100 (no validator in the model), the discount > total,
    making final_total negative. Should clamp to max 100% discount.

    so final_total can be negative. Should use max(0, ...).
    """
    if coupon.discount_type == 'percentage':
        discount = order_total * (coupon.discount_value / 100)
        if coupon.max_discount_amount:
            discount = min(discount, coupon.max_discount_amount)
        return discount

    elif coupon.discount_type == 'fixed':
        return coupon.discount_value

    elif coupon.discount_type == 'free_shipping':
        return 0  # Handled separately

    return 0


class ApplyCouponView(APIView):
    """Apply a coupon code to an order."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        code = request.data.get('code', '').upper().strip()
        order_id = request.data.get('order_id')

        try:
            coupon = Coupon.objects.get(code=code)
        except Coupon.DoesNotExist:
            return Response({'error': 'Invalid coupon code.'}, status=400)

        if not coupon.is_valid():
            return Response({'error': 'Coupon has expired or is no longer valid.'}, status=400)

        if coupon.min_order_value and order_id:
            try:
                order = Order.objects.get(id=order_id, user=request.user)
            except Order.DoesNotExist:
                return Response({'error': 'Order not found.'}, status=404)

            if order.total < coupon.min_order_value:
                return Response({
                    'error': f'Minimum order value for this coupon is ₹{coupon.min_order_value}'
                }, status=400)
        else:
            order = Order.objects.get(id=order_id)

        # A user could apply the same coupon multiple times in concurrent requests
        # because we check THEN insert (not atomic). Should use get_or_create or
        # unique constraint + atomic block.
        existing_usage = CouponUsage.objects.filter(
            coupon=coupon, user=request.user
        ).count()

        if existing_usage >= coupon.usage_limit_per_user:
            return Response({'error': 'You have already used this coupon.'}, status=400)

        discount = calculate_discount(coupon, float(order.total))

        # coupon.times_used increments but order discount isn't applied.
        coupon.times_used += 1
        coupon.save()

        order.discount_amount = discount
        order.total = order.subtotal + order.shipping_cost + order.tax_amount - discount
        order.coupon = coupon
        order.save()

        CouponUsage.objects.create(
            coupon=coupon,
            user=request.user,
            order=order,
            discount_applied=discount,
        )

        return Response({
            'message': 'Coupon applied successfully.',
            'discount_amount': str(discount),
            'new_total': str(order.total),
        })


class ValidateCouponView(APIView):
    """Preview discount without applying it."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        code = request.data.get('code', '').upper().strip()
        order_total = float(request.data.get('order_total', 0))

        try:
            coupon = Coupon.objects.get(code=code, is_active=True)
        except Coupon.DoesNotExist:
            return Response({'valid': False, 'error': 'Invalid coupon code.'})

        if not coupon.is_valid():
            return Response({'valid': False, 'error': 'Coupon is expired.'})

        if order_total < float(coupon.min_order_value):
            return Response({
                'valid': False,
                'error': f'Minimum order ₹{coupon.min_order_value} required.'
            })

        discount = calculate_discount(coupon, order_total)
        return Response({
            'valid': True,
            'discount_amount': str(discount),
            'discount_type': coupon.discount_type,
            'description': coupon.description,
        })
