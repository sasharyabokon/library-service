import stripe
from django.conf import settings
from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
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
        description="Verify Stripe checkout session status using session_id and update payment status to PAID.",
        parameters=[
            OpenApiParameter(
                name="session_id",
                type=OpenApiTypes.STR,
                description="Stripe Checkout session ID",
                required=True,
            ),
        ],
        responses={
            status.HTTP_200_OK: OpenApiTypes.OBJECT,
            status.HTTP_400_BAD_REQUEST: OpenApiTypes.OBJECT,
        },
    )
    @action(detail=False, methods=["get"], url_path="success")
    def success(self, request):
        session_id = request.query_params.get("session_id")
        if not session_id:
            return Response(
                {"error": "session_id is required"}, status=status.HTTP_400_BAD_REQUEST
            )
        stripe.api_key = settings.STRIPE_SECRET_KEY
        session = stripe.checkout.Session.retrieve(session_id)

        payment = get_object_or_404(Payment, session_id=session_id)

        if session.payment_status == "paid":
            payment.status = Payment.StatusChoices.PAID
            payment.save()
            return Response(
                {"message": "Payment was successful!"}, status=status.HTTP_200_OK
            )
        return Response(
            {"message": "Payment is not completed yet."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    @extend_schema(
        summary="Handle cancelled Stripe payment",
        description="Returns a message indicating that payment was cancelled and the session remains active for 24 hours.",
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
