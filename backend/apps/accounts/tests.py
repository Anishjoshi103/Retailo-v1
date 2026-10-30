from datetime import timedelta
from urllib.parse import parse_qs, urlparse

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.tenancy.models import Branch, Membership, Tenant
from .views import REFRESH_COOKIE


@override_settings(
    SIMPLE_JWT={
        "ACCESS_TOKEN_LIFETIME": timedelta(minutes=5),
        "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
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
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="test@retailo.invalid",
    FRONTEND_BASE_URL="https://retailo.example.test",
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
        response = self.client.post("/api/v1/auth/login", {"email": "OWNER@example.test", "password": "Strong-test-password-123"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.json())
        cookie = response.cookies[REFRESH_COOKIE]
        self.assertTrue(cookie["httponly"])
        self.assertNotIn(REFRESH_COOKIE, response.json())

    def test_invalid_and_unknown_login_use_same_error(self):
        invalid = self.client.post("/api/v1/auth/login", {"email": "owner@example.test", "password": "wrong-password"}, format="json")
        unknown = self.client.post("/api/v1/auth/login", {"email": "unknown@example.test", "password": "wrong-password"}, format="json")
        self.assertEqual(invalid.status_code, 401)
        self.assertEqual(invalid.json(), unknown.json())

    def test_login_rejects_user_without_membership(self):
        orphan = get_user_model().objects.create_user(username="orphan@example.test", email="orphan@example.test", password="Strong-test-password-123")
        response = self.client.post("/api/v1/auth/login", {"email": orphan.email, "password": "Strong-test-password-123"}, format="json")
        self.assertEqual(response.status_code, 403)

    def test_refresh_rejects_missing_cookie(self):
        response = self.client.post("/api/v1/auth/refresh", {}, format="json")
        self.assertEqual(response.status_code, 401)

    def test_registration_creates_inactive_owner_tenant_and_initial_branch(self):
        response = self.client.post("/api/v1/auth/register", {"store_name": "Corner Shop", "email": "new@example.test", "password": "A-strong-password-123"}, format="json")
        self.assertEqual(response.status_code, 202)
        user = get_user_model().objects.get(email="new@example.test")
        self.assertFalse(user.is_active)
        membership = Membership.objects.get(user=user)
        self.assertEqual(membership.role, Membership.Role.OWNER)
        self.assertEqual(Branch.objects.filter(tenant=membership.tenant).count(), 1)
        self.assertEqual(Branch.objects.get(tenant=membership.tenant).code, "MAIN")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/auth/verify-email?token=", mail.outbox[0].body)

    def test_email_verification_activates_user_and_is_single_use(self):
        self.client.post("/api/v1/auth/register", {"store_name": "Corner Shop", "email": "new@example.test", "password": "A-strong-password-123"}, format="json")
        verify_url = next(line for line in mail.outbox[0].body.splitlines() if "/auth/verify-email?token=" in line)
        token = parse_qs(urlparse(verify_url).query)["token"][0]
        response = self.client.post("/api/v1/auth/verify-email", {"token": token}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(get_user_model().objects.get(email="new@example.test").is_active)
        again = self.client.post("/api/v1/auth/verify-email", {"token": token}, format="json")
        self.assertEqual(again.status_code, 400)

    def test_password_reset_request_is_non_enumerating_and_reset_token_is_single_use(self):
        existing = self.client.post("/api/v1/auth/password-reset/request", {"email": self.user.email}, format="json")
        unknown = self.client.post("/api/v1/auth/password-reset/request", {"email": "missing@example.test"}, format="json")
        self.assertEqual(existing.status_code, 202)
        self.assertEqual(existing.json(), unknown.json())
        reset_url = next(line for line in mail.outbox[0].body.splitlines() if "/auth/password-reset/confirm?" in line)
        query = parse_qs(urlparse(reset_url).query)
        response = self.client.post("/api/v1/auth/password-reset/confirm", {"uid": query["uid"][0], "token": query["token"][0], "password": "Another-strong-password-456"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("Another-strong-password-456"))
        reused = self.client.post("/api/v1/auth/password-reset/confirm", {"uid": query["uid"][0], "token": query["token"][0], "password": "Yet-another-password-789"}, format="json")
        self.assertEqual(reused.status_code, 400)
