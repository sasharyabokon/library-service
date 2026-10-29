from book.models import Book
from book.serializers import BookSerializer
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase


class UnauthenticatedBookApiTests(APITestCase):
    def setUp(self):
        self.book_list_url = reverse("book:book-list")
        self.book = Book.objects.create(
            title="Test Book",
            author="Test Author",
            cover=Book.CoverChoices.HARD,
            inventory=10,
            daily_fee="1.50",
        )

    def test_auth_required_for_admin_actions(self):
        """Test that unauthenticated users cannot create, update or delete books"""
        payload = {
            "title": "New Book",
            "author": "New Author",
            "cover": Book.CoverChoices.SOFT,
            "inventory": 5,
            "daily_fee": "2.00",
        }
        res = self.client.post(self.book_list_url, payload)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_books_public(self):
        """Test that anyone can list books"""
        res = self.client.get(self.book_list_url)
        books = Book.objects.all()
        serializer = BookSerializer(books, many=True)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, serializer.data)

    def test_retrieve_book_public(self):
        """Test that anyone can retrieve book details"""
        url = reverse("book:book-detail", args=[self.book.id])
        res = self.client.get(url)
        serializer = BookSerializer(self.book)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, serializer.data)


class AdminBookApiTests(APITestCase):
    def setUp(self):
        self.book_list_url = reverse("book:book-list")
        self.admin_user = get_user_model().objects.create_superuser(
            email="admin@example.com", password="adminpassword123"
        )
        self.client.force_authenticate(user=self.admin_user)

    def test_create_book_admin(self):
        """Test that admin can create a book"""
        payload = {
            "title": "Admin Book",
            "author": "Admin Author",
            "cover": Book.CoverChoices.HARD,
            "inventory": 5,
            "daily_fee": "2.00",
        }
        res = self.client.post(self.book_list_url, payload)

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        exists = Book.objects.filter(title=payload["title"]).exists()
        self.assertTrue(exists)

    def test_update_book_admin(self):
        """Test that admin can update a book"""
        book = Book.objects.create(
            title="Old Title",
            author="Author",
            cover=Book.CoverChoices.SOFT,
            inventory=2,
            daily_fee="1.00",
        )
        url = reverse("book:book-detail", args=[book.id])
        payload = {"title": "Updated Title"}
        res = self.client.patch(url, payload)

        book.refresh_from_db()
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(book.title, payload["title"])
