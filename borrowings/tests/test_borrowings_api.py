from datetime import date, timedelta
from unittest.mock import patch

from book.models import Book
from borrowings.models import Borrowing
from borrowings.serializers import BorrowingReadSerializer
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase


class UnauthenticatedBorrowingApiTests(APITestCase):
    def setUp(self):
        self.borrowing_url = reverse("borrowings:borrowing-list")

    def test_auth_required(self):
        """Test that unauthenticated users cannot access borrowings"""
        res = self.client.get(self.borrowing_url)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


class AuthenticatedBorrowingApiTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email="user@example.com", password="password123"
        )
        self.admin_user = get_user_model().objects.create_superuser(
            email="admin@example.com", password="password123"
        )
        self.client.force_authenticate(user=self.user)

        self.book = Book.objects.create(
            title="Test Book",
            author="Test Author",
            cover=Book.CoverChoices.HARD,
            inventory=5,
            daily_fee="2.00",
        )
        self.borrowing_url = reverse("borrowings:borrowing-list")

    @patch("borrowings.serializers.send_telegram_message")
    @patch("borrowings.serializers.create_stripe_session")
    def test_create_borrowing_success(self, mock_stripe, mock_telegram):
        """Test that authenticated user can create a borrowing and inventory decreases"""
        expected_return = date.today() + timedelta(days=5)
        payload = {
            "book": self.book.id,
            "expected_return_date": str(expected_return),
        }
        res = self.client.post(self.borrowing_url, payload)

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        # Перевіряємо зменшення інвентарю книги
        self.book.refresh_from_db()
        self.assertEqual(self.book.inventory, 4)

        # Перевіряємо створення оренди в базі
        borrowing = Borrowing.objects.get(id=res.data["id"])
        self.assertEqual(borrowing.user, self.user)
        self.assertEqual(borrowing.book, self.book)

        # Перевіряємо, що моки викликалися
        mock_stripe.assert_called_once()
        mock_telegram.assert_called_once()

    def test_create_borrowing_out_of_inventory(self):
        """Test that borrowing fails if book inventory is 0"""
        self.book.inventory = 0
        self.book.save()

        expected_return = date.today() + timedelta(days=5)
        payload = {
            "book": self.book.id,
            "expected_return_date": str(expected_return),
        }
        res = self.client.post(self.borrowing_url, payload)

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("book", res.data)

    def test_list_borrowings_user(self):
        """Test user can list borrowings"""
        Borrowing.objects.create(
            user=self.user,
            book=self.book,
            expected_return_date=date.today() + timedelta(days=3),
        )
        res = self.client.get(self.borrowing_url)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        borrowings = Borrowing.objects.filter(user=self.user)
        serializer = BorrowingReadSerializer(borrowings, many=True)
        self.assertEqual(res.data, serializer.data)
