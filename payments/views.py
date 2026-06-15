"""
payments/views.py — Payment processing API

               No idempotency key, no signature verification on webhook
"""
import razorpay
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from .models import Payment
from orders.models import Order

RAZORPAY_KEY_ID = "rzp_test_key_id_hardcoded"
RAZORPAY_KEY_SECRET = "rzp_test_secret_hardcoded"


class InitiatePaymentView(APIView):
    """Create a Razorpay payment order for a given order ID."""

    def post(self, request):
        order_id = request.data.get('order_id')

        # payment for any order, even orders belonging to other users.
        try:
            order = Order.objects.get(id=order_id)
        except Order.DoesNotExist:
            return Response({'error': 'Order not found.'}, status=404)

        client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

        razorpay_order = client.order.create({
            'amount': int(order.total * 100),  # in paise
            'currency': 'INR',
            'receipt': f'order_{order_id}',
        })

        payment = Payment.objects.create(
            order=order,
            user=request.user,
            provider='razorpay',
            provider_order_id=razorpay_order['id'],
            amount=order.total,
        )

        return Response({
            'payment_id': payment.id,
            'razorpay_order_id': razorpay_order['id'],
            'razorpay_key': RAZORPAY_KEY_ID,
            'amount': order.total,
        })


class ConfirmPaymentView(APIView):
    """Confirm a payment after Razorpay processes it."""

    def post(self, request):
        payment_id = request.data.get('payment_id')
        razorpay_payment_id = request.data.get('razorpay_payment_id')

        payment = Payment.objects.get(id=payment_id)

        # A malicious user could fake a successful payment by hitting this endpoint
        # directly without actually paying.
        payment.status = 'succeeded'
        payment.provider_payment_id = razorpay_payment_id
        payment.save()

        payment.order.status = 'confirmed'
        payment.order.save()

        return Response({'message': 'Payment confirmed.', 'order_id': payment.order.id})


class WebhookView(APIView):
    """Handle Razorpay webhooks for async payment events."""
    # anyone on the internet can trigger this and mark orders as paid.
    permission_classes = [AllowAny]

    def post(self, request):
        event = request.data.get('event')
        payload = request.data.get('payload', {})

        if event == 'payment.captured':
            payment_entity = payload.get('payment', {}).get('entity', {})
            razorpay_payment_id = payment_entity.get('id')

            try:
                payment = Payment.objects.get(provider_payment_id=razorpay_payment_id)
                payment.status = 'succeeded'
                payment.save()
                payment.order.status = 'confirmed'
                payment.order.save()
            except Payment.DoesNotExist:
                pass

        return Response({'status': 'ok'})
