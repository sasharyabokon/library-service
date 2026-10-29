import stripe
from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, mixins, status
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
