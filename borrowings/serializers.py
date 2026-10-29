from django.db import transaction
from rest_framework import serializers

from borrowings.models import Borrowing
from borrowings.telegram import send_telegram_message


class BorrowingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Borrowing
        fields = (
            "id",
            "user",
            "book",
            "borrow_date",
            "expected_return_date",
            "actual_return_date",
        )
        read_only_fields = ("id", "user", "borrow_date", "actual_return_date")

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

        message = (
            f"📚 *New Borrowing Created!*\n\n"
            f"• *Book:* {borrowing.book.title}\n"
            f"• *User:* {borrowing.user.email}\n"
            f"• *Borrow Date:* {borrowing.borrow_date}\n"
            f"• *Expected Return Date:* {borrowing.expected_return_date}"
        )

        send_telegram_message(message)

        return borrowing
