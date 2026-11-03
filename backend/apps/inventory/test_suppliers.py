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


    def test_duplicate_gstin_in_same_tenant_returns_validation_error(self):
        first = self.client.post(
            "/api/v1/inventory/suppliers",
            {"name": "Supplier One", "gstin": "27AABCU9603R1ZM"},
            format="json",
        )
        self.assertEqual(first.status_code, 201, first.content)

        duplicate = self.client.post(
            "/api/v1/inventory/suppliers",
            {"name": "Supplier Duplicate", "gstin": "27aabcu9603r1zm"},
            format="json",
        )
        self.assertEqual(duplicate.status_code, 400, duplicate.content)
        self.assertEqual(Supplier.objects.for_tenant(self.tenant.id).count(), 1)


    def test_gstin_unique_constraint_race_returns_validation_error(self):
        from unittest.mock import patch

        from django.db import IntegrityError

        existing = Supplier.objects.create(
            tenant=self.tenant, name="Existing Supplier", gstin="27AABCU9603R1ZM"
        )
        with (
            patch("apps.inventory.supplier_serializers.SupplierSerializer.validate_gstin", return_value=existing.gstin),
            patch("apps.inventory.supplier_serializers.SupplierSerializer.save", side_effect=IntegrityError("unique race")),
        ):
            response = self.client.post(
                "/api/v1/inventory/suppliers",
                {"name": "Concurrent Supplier", "gstin": existing.gstin},
                format="json",
            )
        self.assertEqual(response.status_code, 400, response.content)

    def test_supplier_create_role_matrix(self):
        expected = {
            Membership.Role.OWNER: 201,
            Membership.Role.ADMIN: 201,
            Membership.Role.MANAGER: 201,
            Membership.Role.CASHIER: 403,
            Membership.Role.ACCOUNTANT: 403,
        }
        for role, status_code in expected.items():
            with self.subTest(role=role):
                self.membership.role = role
                self.membership.save(update_fields=["role"])
                response = self.client.post(
                    "/api/v1/inventory/suppliers",
                    {"name": f"Supplier {role}"},
                    format="json",
                )
                self.assertEqual(response.status_code, status_code, response.content)

    def test_supplier_list_role_matrix(self):
        expected_roles = {
            Membership.Role.OWNER,
            Membership.Role.ADMIN,
            Membership.Role.MANAGER,
            Membership.Role.CASHIER,
            Membership.Role.ACCOUNTANT,
        }
        for role in expected_roles:
            with self.subTest(role=role):
                self.membership.role = role
                self.membership.save(update_fields=["role"])
                response = self.client.get("/api/v1/inventory/suppliers")
                self.assertEqual(response.status_code, 200, response.content)
