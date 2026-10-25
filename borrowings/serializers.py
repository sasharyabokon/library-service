from django.db import transaction
from rest_framework import serializers

from borrowings.models import Borrowing


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

    def validate(self, artts):
        book = artts.get("book")

        if book.inventory <= 0:
            raise serializers.ValidationError({"book": "this book is out of inventory"})
        return artts

    def create(self, validated_data):
        with transaction.atomic():
            book = validated_data.get("book")
            book.inventory = book.inventory - 1
            book.save()
            return super().create(validated_data)
