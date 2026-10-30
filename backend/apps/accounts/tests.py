from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.tenancy.models import Membership, Tenant
from .views import REFRESH_COOKIE


@override_settings(
    SIMPLE_JWT={
        "ACCESS_TOKEN_LIFETIME": __import__("datetime").timedelta(minutes=5),
        "REFRESH_TOKEN_LIFETIME": __import__("datetime").timedelta(days=1),
        "ROTATE_REFRESH_TOKENS": True,
        "BLACKLIST_AFTER_ROTATION": True,
        "ALGORITHM": "HS256",
        "SIGNING_KEY": "test-signing-key-only",
        "AUTH_HEADER_TYPES": ("Bearer",),
        "USER_ID_FIELD": "id",
        "USER_ID_CLAIM": "user_id",
    },
    REST_FRAMEWORK={
        "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
        "EXCEPTION_HANDLER": "config.api_errors.api_exception_handler",
        "DEFAULT_AUTHENTICATION_CLASSES": (
            "rest_framework_simplejwt.authentication.JWTAuthentication",
        ),
    },
    IS_TEST_ENV=True,
)
class AuthenticationApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.tenant = Tenant.objects.create(name="Test Store", slug="test-store")
        self.user = get_user_model().objects.create_user(
            username="owner@example.test", email="owner@example.test", password="Strong-test-password-123"
        )
        Membership.objects.create(tenant=self.tenant, user=self.user, role=Membership.Role.OWNER)

    def test_login_returns_access_and_http_only_refresh_cookie(self):
        response = self.client.post(
            "/api/v1/auth/login",
            {"email": "OWNER@example.test", "password": "Strong-test-password-123"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.json())
        cookie = response.cookies[REFRESH_COOKIE]
        self.assertTrue(cookie["httponly"])
        self.assertNotIn(REFRESH_COOKIE, response.json())

    def test_invalid_login_has_generic_error(self):
        response = self.client.post(
            "/api/v1/auth/login", {"email": "owner@example.test", "password": "wrong-password"}, format="json"
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "Email or password is incorrect.")

    def test_unknown_user_has_same_login_error(self):
        response = self.client.post(
            "/api/v1/auth/login", {"email": "unknown@example.test", "password": "wrong-password"}, format="json"
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "Email or password is incorrect.")

    def test_login_rejects_user_without_membership(self):
        orphan = get_user_model().objects.create_user(
            username="orphan@example.test", email="orphan@example.test", password="Strong-test-password-123"
        )
        response = self.client.post(
            "/api/v1/auth/login", {"email": orphan.email, "password": "Strong-test-password-123"}, format="json"
        )
        self.assertEqual(response.status_code, 403)

    def test_refresh_rejects_missing_cookie(self):
        response = self.client.post("/api/v1/auth/refresh", {}, format="json")
        self.assertEqual(response.status_code, 401)
