import stripe
from django.conf import settings
from django.http import HttpResponse
from rest_framework.views import APIView
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from payment.models import Payment
from payment.serializers import PaymentSerializer


class PaymentViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = PaymentSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        user = self.request.user
        queryset = Payment.objects.select_related("borrowing")
        if user.is_staff:
            return queryset.all()
        return queryset.filter(borrowing__user=user)

    @extend_schema(
        summary="Handle successful Stripe payment",
        description="Endpoint user is redirected to after successful payment. Status is updated via webhook.",
        responses={
            status.HTTP_200_OK: OpenApiTypes.OBJECT,
        },
    )
    @action(detail=False, methods=["get"], url_path="success")
    def success(self, request):
        session_id = request.query_params.get("session_id")
        if not session_id:
            return Response(
                {"error": "session_id is required"}, status=status.HTTP_400_BAD_REQUEST
            )
        return Response(
            {
                "message": "Payment successful! The status will be updated shortly via webhook."
            },
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        summary="Handle cancelled Stripe payment",
        description=(
            "Returns a message indicating that payment was cancelled "
            "and the session remains active for 24 hours."
        ),
        responses={status.HTTP_200_OK: OpenApiTypes.OBJECT},
    )
    @action(detail=False, methods=["get"], url_path="cancel")
    def cancel(self, request):
        return Response(
            {
                "message": (
                    "Payment was cancelled. "
                    "You can pay later using the session URL, "
                    "which is active for 24 hours."
                )
            },
            status=status.HTTP_200_OK,
        )


class StripeWebhookView(APIView):
    permission_classes = []

    def post(self, request, *args, **kwargs):
        payload = request.body
        sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")
        endpoint_secret = getattr(settings, "STRIPE_WEBHOOK_SECRET", None)

        try:
            if endpoint_secret:
                event = stripe.Webhook.construct_event(
                    payload, sig_header, endpoint_secret
                )
            else:
                event = request.data
        except (ValueError, stripe.error.SignatureVerificationError):
            return HttpResponse(status=400)

        if event.get("type") == "checkout.session.completed":
            session = event["data"]["object"]
            session_id = session.get("id")

            try:
                payment = Payment.objects.get(session_id=session_id)
                payment.status = Payment.StatusChoices.PAID
                payment.save()
            except Payment.DoesNotExist:
                return HttpResponse(status=404)

        return HttpResponse(status=200)
