from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase


class UnauthenticatedUserTests(APITestCase):
    def setUp(self):
        self.create_user_url = reverse("user:create")
        self.token_url = reverse("user:token_obtain_pair")
        self.manage_user_url = reverse("user:manage")

    def test_create_user_success(self):
        """Test that creating a user with valid credentials is successful"""
        payload = {
            "email": "test@example.com",
            "password": "testpassword123",
            "first_name": "Test",
            "last_name": "User",
        }
        res = self.client.post(self.create_user_url, payload)

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        user = get_user_model().objects.get(id=res.data["id"])
        self.assertTrue(user.check_password(payload["password"]))
        self.assertNotIn("password", res.data)

    def test_user_email_exists(self):
        """Test that error is returned if user with email already exists"""
        payload = {
            "email": "test@example.com",
            "password": "testpassword123",
        }
        get_user_model().objects.create_user(**payload)
        res = self.client.post(self.create_user_url, payload)

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_user_password_too_short(self):
        """Test that password with less than 5 characters fails"""
        payload = {
            "email": "test@example.com",
            "password": "123",
        }
        res = self.client.post(self.create_user_url, payload)

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        user_exists = get_user_model().objects.filter(email="test@example.com").exists()
        self.assertFalse(user_exists)

    def test_create_token_success(self):
        """Test that token is generated for valid credentials"""
        payload = {
            "email": "test@example.com",
            "password": "testpassword123",
        }
        get_user_model().objects.create_user(**payload)
        res = self.client.post(self.token_url, payload)

        self.assertIn("access", res.data)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_create_token_invalid_credentials(self):
        """Test that invalid credentials return 401 error"""
        payload = {
            "email": "wrong@example.com",
            "password": "wrongpassword",
        }
        res = self.client.post(self.token_url, payload)

        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertNotIn("access", res.data)

    def test_manage_user_unauthorized(self):
        """Test that unauthenticated user cannot access profile"""
        res = self.client.get(self.manage_user_url)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


class AuthenticatedUserTests(APITestCase):
    def setUp(self):
        self.manage_user_url = reverse("user:manage")
        self.user = get_user_model().objects.create_user(
            email="test@example.com",
            password="testpassword123",
            first_name="Original",
        )
        self.client.force_authenticate(user=self.user)

    def test_retrieve_user_profile(self):
        """Test retrieving authenticated user profile"""
        res = self.client.get(self.manage_user_url)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["email"], self.user.email)
        self.assertEqual(res.data["first_name"], self.user.first_name)

    def test_update_user_profile(self):
        """Test updating authenticated user profile"""
        payload = {
            "first_name": "Updated",
            "password": "newpassword123",
        }
        res = self.client.patch(self.manage_user_url, payload)

        self.user.refresh_from_db()
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(self.user.first_name, "Updated")
        self.assertTrue(self.user.check_password("newpassword123"))
