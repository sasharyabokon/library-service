from django.db import transaction
from rest_framework import serializers

from borrowings.models import Borrowing
from borrowings.telegram import send_telegram_message
from payment.models import Payment
from payment.serializers import PaymentSerializer
from payment.services import create_stripe_session


class BorrowingSerializer(serializers.ModelSerializer):
    payments = PaymentSerializer(many=True, read_only=True, source="payment_set")

    class Meta:
        model = Borrowing
        fields = (
            "id",
            "user",
            "book",
            "borrow_date",
            "expected_return_date",
            "actual_return_date",
            "payments",
        )
        read_only_fields = (
            "id",
            "user",
            "borrow_date",
            "actual_return_date",
            "payments",
        )

    def validate(self, attrs):
        book = attrs.get("book")

        if book.inventory <= 0:
            raise serializers.ValidationError({"book": "this book is out of inventory"})
        return attrs

    def create(self, validated_data):
        with transaction.atomic():
            book = validated_data.get("book")
            book.inventory = book.inventory - 1
            book.save()
            borrowing = super().create(validated_data)

            borrow_days = (borrowing.expected_return_date - borrowing.borrow_date).days
            if borrow_days <= 0:
                borrow_days = 1

            money_to_pay = borrow_days * book.daily_fee

            payment = Payment.objects.create(
                borrowing=borrowing,
                type=Payment.TypeChoices.PAYMENT,
                money_to_pay=money_to_pay,
            )

        request = self.context.get("request")
        if request:
            base_url = request.build_absolute_uri("/")[:-1]
        else:
            base_url = "http://127.0.0.1:8000"

        success_url = (
            f"{base_url}/api/payment/success/?session_id={{CHECKOUT_SESSION_ID}}"
        )
        cancel_url = f"{base_url}/api/payment/cancel/"

        try:
            create_stripe_session(payment, success_url, cancel_url)
        except Exception as e:
            print(f"Stripe session creation failed: {e}")

        message = (
            f"📚 *New Borrowing Created!*\n\n"
            f"• *Book:* {borrowing.book.title}\n"
            f"• *User:* {borrowing.user.email}\n"
            f"• *Borrow Date:* {borrowing.borrow_date}\n"
            f"• *Expected Return Date:* {borrowing.expected_return_date}"
        )

        send_telegram_message(message)

        return borrowing
