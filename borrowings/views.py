import logging
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from borrowings.models import Borrowing
from borrowings.serializers import (
    BorrowingCreateSerializer,
    BorrowingReadSerializer,
)
from payment.models import Payment
from payment.services import create_stripe_session

logger = logging.getLogger(__name__)


class BorrowingViewSet(viewsets.ModelViewSet):
    permission_classes = (IsAuthenticated,)

    def get_serializer_class(self):
        if self.action in ("list", "retrieve"):
            return BorrowingReadSerializer
        return BorrowingCreateSerializer

    def get_queryset(self):
        user = self.request.user
        queryset = Borrowing.objects.select_related("user", "book")

        if not user.is_staff:
            queryset = queryset.filter(user=user)

        user_id = self.request.query_params.get("user_id")
        if user.is_staff and user_id:
            queryset = queryset.filter(user_id=user_id)

        is_active = self.request.query_params.get("is_active")
        if is_active is not None:
            if is_active.lower() not in ["true", "false"]:
                raise ValidationError(
                    {"is_active": "This parameter must be 'true' or 'false'."}
                )
            if is_active.lower() == "true":
                queryset = queryset.filter(actual_return_date__isnull=True)
            else:
                queryset = queryset.filter(actual_return_date__isnull=False)
        return queryset

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @extend_schema(
        summary="Get list of borrowings",
        description="Retrieve a list of borrowings. Non-admins see only their own borrowings.",
        parameters=[
            OpenApiParameter(
                name="user_id",
                type=OpenApiTypes.INT,
                description="Filter borrowings by user ID (admin only)",
                required=False,
            ),
            OpenApiParameter(
                name="is_active",
                type=OpenApiTypes.BOOL,
                description="Filter active borrowings (True = not returned, False = returned)",
                required=False,
            ),
        ],
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        summary="Return a borrowed book",
        description="Set actual return date, increase book inventory by 1, and create a FINE payment if overdue.",
        responses={
            status.HTTP_200_OK: BorrowingReadSerializer,
            status.HTTP_400_BAD_REQUEST: OpenApiTypes.OBJECT,
        },
    )
    @action(methods=["POST"], detail=True, url_path="return")
    def return_book(self, request, pk=None):
        borrowing = self.get_object()

        if borrowing.actual_return_date is not None:
            return Response(
                {"error": "This book is already returned"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        payment = None

        with transaction.atomic():
            borrowing.actual_return_date = timezone.now().date()
            borrowing.save()

            book = borrowing.book
            book.inventory += 1
            book.save()

            if borrowing.actual_return_date > borrowing.expected_return_date:
                overdue_days = (
                    borrowing.actual_return_date - borrowing.expected_return_date
                ).days
                fine_multiplier = getattr(settings, "FINE_MULTIPLIER", 2)
                money_to_pay = overdue_days * book.daily_fee * fine_multiplier

                payment = Payment.objects.create(
                    borrowing=borrowing,
                    type=Payment.TypeChoices.FINE,
                    money_to_pay=money_to_pay,
                )

        if payment:
            base_url = request.build_absolute_uri("/")[:-1]
            success_url = (
                f"{base_url}/api/payment/success/?session_id={{CHECKOUT_SESSION_ID}}"
            )
            cancel_url = f"{base_url}/api/payment/cancel/"

            try:
                create_stripe_session(payment, success_url, cancel_url)
            except Exception as e:
                logger.error("Stripe session creation for fine failed: %s", e)

        serializer = BorrowingReadSerializer(borrowing, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)
