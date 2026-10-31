from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.inventory.models import Supplier
from apps.tenancy.models import Membership, Tenant


@override_settings(
    SIMPLE_JWT={"ACCESS_TOKEN_LIFETIME": timedelta(minutes=5), "REFRESH_TOKEN_LIFETIME": timedelta(days=1), "ROTATE_REFRESH_TOKENS": False, "BLACKLIST_AFTER_ROTATION": True, "ALGORITHM": "HS256", "SIGNING_KEY": "supplier-test-key-only", "AUTH_HEADER_TYPES": ("Bearer",), "USER_ID_FIELD": "id", "USER_ID_CLAIM": "user_id"},
    REST_FRAMEWORK={"DEFAULT_AUTHENTICATION_CLASSES": ("rest_framework_simplejwt.authentication.JWTAuthentication",), "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema", "EXCEPTION_HANDLER": "config.api_errors.api_exception_handler"},
)
class SupplierApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.tenant = Tenant.objects.create(name="Supplier Store", slug="supplier-store")
        self.other_tenant = Tenant.objects.create(name="Other Store", slug="supplier-other-store")
        self.user = get_user_model().objects.create_user(username="supplier-owner@example.test", email="supplier-owner@example.test", password="Test-password-123")
        self.membership = Membership.objects.create(tenant=self.tenant, user=self.user, role=Membership.Role.OWNER)
        from rest_framework_simplejwt.tokens import RefreshToken
        refresh = RefreshToken.for_user(self.user)
        refresh["tenant_id"] = str(self.tenant.id)
        refresh["membership_id"] = str(self.membership.id)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")

    def test_create_supplier_normalizes_gstin_and_lists_only_current_tenant(self):
        response = self.client.post("/api/v1/inventory/suppliers", {"name": "Supplier One", "gstin": "27aabcu9603r1zm", "phone": "123"}, format="json")
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()["gstin"], "27AABCU9603R1ZM")
        Supplier.objects.create(tenant=self.other_tenant, name="Other supplier")
        listed = self.client.get("/api/v1/inventory/suppliers")
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(len(listed.json()), 1)

    def test_invalid_gstin_is_rejected(self):
        response = self.client.post("/api/v1/inventory/suppliers", {"name": "Bad Supplier", "gstin": "NOT-A-GSTIN"}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_cashier_cannot_create_supplier(self):
        self.membership.role = Membership.Role.CASHIER
        self.membership.save(update_fields=["role"])
        response = self.client.post("/api/v1/inventory/suppliers", {"name": "Blocked Supplier"}, format="json")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Supplier.objects.count(), 0)
