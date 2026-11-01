from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.catalog.models import Product
from apps.inventory.models import InventoryBalance, StockMovement
from apps.tenancy.models import Branch, BranchAccess, Membership, Tenant


@override_settings(
    SIMPLE_JWT={"ACCESS_TOKEN_LIFETIME": timedelta(minutes=5), "REFRESH_TOKEN_LIFETIME": timedelta(days=1), "ROTATE_REFRESH_TOKENS": False, "BLACKLIST_AFTER_ROTATION": True, "ALGORITHM": "HS256", "SIGNING_KEY": "catalog-test-key-only", "AUTH_HEADER_TYPES": ("Bearer",), "USER_ID_FIELD": "id", "USER_ID_CLAIM": "user_id"},
    REST_FRAMEWORK={"DEFAULT_AUTHENTICATION_CLASSES": ("rest_framework_simplejwt.authentication.JWTAuthentication",), "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema", "EXCEPTION_HANDLER": "config.api_errors.api_exception_handler"},
    IS_TEST_ENV=True,
)
class CatalogApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.tenant = Tenant.objects.create(name="Store A", slug="store-a")
        self.other_tenant = Tenant.objects.create(name="Store B", slug="store-b")
        self.branch = Branch.objects.create(tenant=self.tenant, name="Main", code="MAIN")
        self.other_branch = Branch.objects.create(tenant=self.other_tenant, name="Main", code="MAIN")
        self.user = get_user_model().objects.create_user(username="owner@example.test", email="owner@example.test", password="Test-password-123")
        self.membership = Membership.objects.create(tenant=self.tenant, user=self.user, role=Membership.Role.OWNER)
        BranchAccess.objects.create(membership=self.membership, branch=self.branch)
        from rest_framework_simplejwt.tokens import RefreshToken
        refresh = RefreshToken.for_user(self.user)
        refresh["tenant_id"] = str(self.tenant.id)
        refresh["membership_id"] = str(self.membership.id)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")

    def product(self, tenant=None, sku="MILK-1"):
        return Product.objects.create(tenant=tenant or self.tenant, sku=sku, name="Milk", unit=Product.Unit.EACH, gst_rate=Decimal("5.00"), selling_price=Decimal("35.00"), purchase_price=Decimal("28.00"))

    def test_product_create_serializes_money_as_strings(self):
        response = self.client.post("/api/v1/products", {"sku": " milk-1 ", "name": "Milk", "unit": "each", "gst_rate": "5.00", "selling_price": "35.00", "purchase_price": "28.00"}, format="json")
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()["sku"], "MILK-1")
        self.assertEqual(response.json()["selling_price"], "35.00")
        self.assertEqual(response.json()["gst_rate"], "5.00")

    def test_product_list_never_returns_other_tenants_products(self):
        own = self.product(sku="OWN-1")
        self.product(tenant=self.other_tenant, sku="OTHER-1")
        response = self.client.get("/api/v1/products")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["id"] for item in response.json()["results"]] if isinstance(response.json(), dict) and "results" in response.json() else [item["id"] for item in response.json()], [str(own.id)])

    def test_duplicate_sku_is_rejected_within_tenant_but_allowed_between_tenants(self):
        self.product(sku="DUP-1")
        self.product(tenant=self.other_tenant, sku="DUP-1")
        response = self.client.post("/api/v1/products", {"sku": "dup-1", "name": "Another", "unit": "each", "gst_rate": "0", "selling_price": "1.00", "purchase_price": "0.00"}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_stock_adjustment_requires_idempotency_and_is_tenant_scoped(self):
        product = self.product()
        payload = {"branch_id": str(self.branch.id), "product_id": str(product.id), "quantity_delta": "2.500", "note": "Opening count"}
        missing_key = self.client.post("/api/v1/inventory/adjustments", payload, format="json")
        self.assertEqual(missing_key.status_code, 400)
        first = self.client.post("/api/v1/inventory/adjustments", payload, format="json", HTTP_IDEMPOTENCY_KEY="stock-adjust-1")
        self.assertEqual(first.status_code, 201, first.content)
        replay = self.client.post("/api/v1/inventory/adjustments", payload, format="json", HTTP_IDEMPOTENCY_KEY="stock-adjust-1")
        self.assertEqual(replay.status_code, 200)
        self.assertTrue(replay.json()["replayed"])
        self.assertEqual(replay.json()["quantity_on_hand"], "2.500")
        self.assertEqual(StockMovement.objects.for_tenant(self.tenant.id).count(), 1)
        self.assertEqual(InventoryBalance.objects.for_tenant(self.tenant.id).get().quantity_on_hand, Decimal("2.500"))

    def test_stock_adjustment_rejects_foreign_tenant_branch_or_product(self):
        foreign_product = self.product(tenant=self.other_tenant, sku="FOREIGN")
        payload = {"branch_id": str(self.other_branch.id), "product_id": str(foreign_product.id), "quantity_delta": "1.000"}
        response = self.client.post("/api/v1/inventory/adjustments", payload, format="json", HTTP_IDEMPOTENCY_KEY="foreign-1")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(StockMovement.objects.count(), 0)


    def test_cashier_cannot_create_products_or_adjust_stock(self):
        self.membership.role = Membership.Role.CASHIER
        self.membership.save(update_fields=["role"])
        product_payload = {"sku": "CASHIER-1", "name": "Milk", "unit": "each", "gst_rate": "5.00", "selling_price": "35.00", "purchase_price": "28.00"}
        product_response = self.client.post("/api/v1/products", product_payload, format="json")
        self.assertEqual(product_response.status_code, 403)
        product = self.product()
        adjustment_response = self.client.post(
            "/api/v1/inventory/adjustments",
            {"branch_id": str(self.branch.id), "product_id": str(product.id), "quantity_delta": "1.000"},
            format="json",
            HTTP_IDEMPOTENCY_KEY="cashier-adjust-1",
        )
        self.assertEqual(adjustment_response.status_code, 403)

    def test_stock_movements_are_append_only(self):
        product = self.product()
        movement = StockMovement.objects.create(tenant=self.tenant, branch=self.branch, product=product, quantity_delta=Decimal("1.000"), reason=StockMovement.Reason.OPENING, created_by=self.user)
        with self.assertRaises(TypeError):
            movement.delete()
        with self.assertRaises(TypeError):
            StockMovement.objects.filter(pk=movement.pk).update(note="edited")


    def test_stock_adjustment_rejects_unassigned_branch_in_same_tenant(self):
        unassigned = Branch.objects.create(tenant=self.tenant, name="Back Room", code="BACK")
        product = self.product()
        response = self.client.post(
            "/api/v1/inventory/adjustments",
            {"branch_id": str(unassigned.id), "product_id": str(product.id), "quantity_delta": "1.000"},
            format="json", HTTP_IDEMPOTENCY_KEY="unassigned-branch-adjustment",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(StockMovement.objects.count(), 0)
