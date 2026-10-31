from datetime import date, timedelta
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from book.models import Book
from borrowings.models import Borrowing
from payment.models import Payment
from payment.serializers import PaymentSerializer


class UnauthenticatedPaymentApiTests(APITestCase):
    def setUp(self):
        self.payment_url = reverse("payment:payment-list")

    def test_auth_required(self):
        """Test that unauthenticated users cannot access payments"""
        res = self.client.get(self.payment_url)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


class AuthenticatedPaymentApiTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email="user@example.com", password="password123"
        )
        self.admin_user = get_user_model().objects.create_superuser(
            email="admin@example.com", password="password123"
        )

        self.book = Book.objects.create(
            title="Test Book",
            author="Author",
            cover=Book.CoverChoices.HARD,
            inventory=5,
            daily_fee="2.00",
        )

        self.borrowing = Borrowing.objects.create(
            user=self.user,
            book=self.book,
            expected_return_date=date.today() + timedelta(days=5),
        )

        self.payment = Payment.objects.create(
            borrowing=self.borrowing,
            type=Payment.TypeChoices.PAYMENT,
            status=Payment.StatusChoices.PENDING,
            money_to_pay="10.00",
            session_id="test_session_id_123",
            session_url="https://stripe.com/test",
        )

        self.payment_url = reverse("payment:payment-list")

    def test_list_payments_user(self):
        """Test that regular user can only see their own payments"""
        other_user = get_user_model().objects.create_user(
            email="other@example.com", password="password123"
        )
        other_borrowing = Borrowing.objects.create(
            user=other_user,
            book=self.book,
            expected_return_date=date.today() + timedelta(days=3),
        )
        Payment.objects.create(
            borrowing=other_borrowing,
            type=Payment.TypeChoices.PAYMENT,
            money_to_pay="5.00",
        )

        self.client.force_authenticate(user=self.user)
        res = self.client.get(self.payment_url)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        payments = Payment.objects.filter(borrowing__user=self.user)
        serializer = PaymentSerializer(payments, many=True)
        self.assertEqual(res.data, serializer.data)

    def test_list_payments_admin(self):
        """Test that admin can see all payments"""
        self.client.force_authenticate(user=self.admin_user)
        res = self.client.get(self.payment_url)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        payments = Payment.objects.all()
        serializer = PaymentSerializer(payments, many=True)
        self.assertEqual(res.data, serializer.data)

    def test_retrieve_payment(self):
        """Test retrieving payment details"""
        self.client.force_authenticate(user=self.user)
        url = reverse("payment:payment-detail", args=[self.payment.id])
        res = self.client.get(url)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        serializer = PaymentSerializer(self.payment)
        self.assertEqual(res.data, serializer.data)

    def test_payment_success_endpoint(self):
        """Test success endpoint returns correct message"""
        self.client.force_authenticate(user=self.user)
        url = (
            reverse("payment:payment-success")
            + f"?session_id={self.payment.session_id}"
        )
        res = self.client.get(url)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("Payment successful", res.data["message"])

    def test_payment_cancel_action(self):
        """Test cancel endpoint returns correct message"""
        self.client.force_authenticate(user=self.user)
        url = reverse("payment:payment-cancel")
        res = self.client.get(url)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("Payment was cancelled", res.data["message"])

    def test_stripe_webhook_updates_status(self):
        """Test that Stripe webhook updates payment status to PAID"""
        url = reverse("payment:stripe-webhook")
        payload = {
            "type": "checkout.session.completed",
            "data": {"object": {"id": self.payment.session_id}},
        }
        res = self.client.post(url, payload, format="json")

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.StatusChoices.PAID)
