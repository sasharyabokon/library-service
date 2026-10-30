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
