from django.conf import settings
from rest_framework.decorators import action
from django.db import transaction
from django.utils import timezone
from rest_framework import viewsets, request, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from borrowings.models import Borrowing
from borrowings.serializers import BorrowingSerializer
from payment.models import Payment
from payment.services import create_stripe_session


class BorrowingViewSet(viewsets.ModelViewSet):
    serializer_class = BorrowingSerializer
    permission_classes = (IsAuthenticated,)

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
            is_active_bool = is_active.lower() == "true"
            if is_active_bool:
                queryset = queryset.filter(actual_return_date__isnull=True)
            else:
                queryset = queryset.filter(actual_return_date__isnull=False)
        return queryset

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(methods=["POST"], detail=True, url_path="return")
    def return_book(self, request, pk=None):
        borrowing = self.get_object()

        if borrowing.actual_return_date is not None:
            return Response(
                {"error": "This book is already returned"},
                status=status.HTTP_400_BAD_REQUEST,
            )

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

                base_url = request.build_absolute_uri("/")[:-1]
                success_url = f"{base_url}/api/payment/success/?session_id={{CHECKOUT_SESSION_ID}}"
                cancel_url = f"{base_url}/api/payment/cancel/"

                try:
                    create_stripe_session(payment, success_url, cancel_url)
                except Exception as e:
                    print(f"Stripe session creation for fine failed: {e}")

            serializer = self.get_serializer(borrowing)
            return Response(serializer.data, status=status.HTTP_200_OK)
