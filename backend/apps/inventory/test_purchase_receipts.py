from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.catalog.models import Product
from apps.inventory.models import InventoryBalance, PurchaseReceipt, StockMovement, Supplier
from apps.tenancy.models import Branch, Membership, Tenant


@override_settings(
    SIMPLE_JWT={"ACCESS_TOKEN_LIFETIME": timedelta(minutes=5), "REFRESH_TOKEN_LIFETIME": timedelta(days=1), "ROTATE_REFRESH_TOKENS": False, "BLACKLIST_AFTER_ROTATION": True, "ALGORITHM": "HS256", "SIGNING_KEY": "receipt-test-key-only", "AUTH_HEADER_TYPES": ("Bearer",), "USER_ID_FIELD": "id", "USER_ID_CLAIM": "user_id"},
    REST_FRAMEWORK={"DEFAULT_AUTHENTICATION_CLASSES": ("rest_framework_simplejwt.authentication.JWTAuthentication",), "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema", "EXCEPTION_HANDLER": "config.api_errors.api_exception_handler"},
)
class PurchaseReceiptApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.tenant = Tenant.objects.create(name="Store A", slug="receipt-store-a")
        self.other_tenant = Tenant.objects.create(name="Store B", slug="receipt-store-b")
        self.branch = Branch.objects.create(tenant=self.tenant, name="Main", code="MAIN")
        self.other_branch = Branch.objects.create(tenant=self.other_tenant, name="Main", code="MAIN")
        self.user = get_user_model().objects.create_user(username="receipt-owner@example.test", email="receipt-owner@example.test", password="Test-password-123")
        self.membership = Membership.objects.create(tenant=self.tenant, user=self.user, role=Membership.Role.OWNER)
        from rest_framework_simplejwt.tokens import RefreshToken
        refresh = RefreshToken.for_user(self.user)
        refresh["tenant_id"] = str(self.tenant.id)
        refresh["membership_id"] = str(self.membership.id)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
        self.product = Product.objects.create(tenant=self.tenant, sku="RICE-1", name="Rice", unit=Product.Unit.KG, gst_rate=Decimal("5.00"), selling_price=Decimal("60.00"), purchase_price=Decimal("45.00"))

    def payload(self):
        return {
            "branch_id": str(self.branch.id),
            "supplier_name": "Example Supplier",
            "supplier_invoice_number": "SUP-INV-100",
            "lines": [{"product_id": str(self.product.id), "quantity": "12.500", "unit_cost": "45.00"}],
        }

    def test_receipt_posts_lines_movements_and_balance_atomically(self):
        response = self.client.post("/api/v1/inventory/receipts", self.payload(), format="json", HTTP_IDEMPOTENCY_KEY="receipt-1")
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()["lines"][0]["quantity"], "12.500")
        self.assertEqual(InventoryBalance.objects.for_tenant(self.tenant.id).get().quantity_on_hand, Decimal("12.500"))
        movement = StockMovement.objects.for_tenant(self.tenant.id).get()
        self.assertEqual(movement.reason, StockMovement.Reason.RECEIPT)
        self.assertEqual(movement.quantity_delta, Decimal("12.500"))
        self.assertEqual(PurchaseReceipt.objects.for_tenant(self.tenant.id).count(), 1)

    def test_identical_retry_does_not_double_receive_stock(self):
        first = self.client.post("/api/v1/inventory/receipts", self.payload(), format="json", HTTP_IDEMPOTENCY_KEY="receipt-retry")
        second = self.client.post("/api/v1/inventory/receipts", self.payload(), format="json", HTTP_IDEMPOTENCY_KEY="receipt-retry")
        self.assertEqual(first.status_code, 201, first.content)
        self.assertEqual(second.status_code, 200, second.content)
        self.assertTrue(second.json()["replayed"])
        self.assertEqual(InventoryBalance.objects.for_tenant(self.tenant.id).get().quantity_on_hand, Decimal("12.500"))
        self.assertEqual(StockMovement.objects.for_tenant(self.tenant.id).count(), 1)

    def test_same_key_with_different_payload_returns_conflict(self):
        self.client.post("/api/v1/inventory/receipts", self.payload(), format="json", HTTP_IDEMPOTENCY_KEY="receipt-conflict")
        payload = self.payload()
        payload["lines"][0]["quantity"] = "13.000"
        response = self.client.post("/api/v1/inventory/receipts", payload, format="json", HTTP_IDEMPOTENCY_KEY="receipt-conflict")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(InventoryBalance.objects.for_tenant(self.tenant.id).get().quantity_on_hand, Decimal("12.500"))

    def test_foreign_tenant_branch_and_product_are_rejected(self):
        payload = self.payload()
        payload["branch_id"] = str(self.other_branch.id)
        response = self.client.post("/api/v1/inventory/receipts", payload, format="json", HTTP_IDEMPOTENCY_KEY="receipt-foreign")
        self.assertEqual(response.status_code, 400)
        payload = self.payload()
        foreign_product = Product.objects.create(tenant=self.other_tenant, sku="OTHER-RICE", name="Other rice", unit=Product.Unit.KG, gst_rate=Decimal("5.00"), selling_price=Decimal("60.00"), purchase_price=Decimal("45.00"))
        payload["lines"][0]["product_id"] = str(foreign_product.id)
        response = self.client.post("/api/v1/inventory/receipts", payload, format="json", HTTP_IDEMPOTENCY_KEY="receipt-foreign-product")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(PurchaseReceipt.objects.count(), 0)

    def test_duplicate_product_lines_are_rejected(self):
        payload = self.payload()
        payload["lines"].append(payload["lines"][0].copy())
        response = self.client.post("/api/v1/inventory/receipts", payload, format="json", HTTP_IDEMPOTENCY_KEY="receipt-duplicate-line")
        self.assertEqual(response.status_code, 400)

    def test_receipt_can_reference_supplier_master(self):
        supplier = Supplier.objects.create(tenant=self.tenant, name="Supplier Master One", gstin="27AABCU9603R1ZM")
        payload = self.payload()
        payload.pop("supplier_name")
        payload["supplier_id"] = str(supplier.id)
        response = self.client.post("/api/v1/inventory/receipts", payload, format="json", HTTP_IDEMPOTENCY_KEY="receipt-supplier-master")
        self.assertEqual(response.status_code, 201, response.content)
        receipt = PurchaseReceipt.objects.for_tenant(self.tenant.id).get()
        self.assertEqual(receipt.supplier_id, supplier.id)
        self.assertEqual(receipt.supplier_name, supplier.name)

    def test_receipt_rejects_supplier_from_another_tenant(self):
        supplier = Supplier.objects.create(tenant=self.other_tenant, name="Foreign Supplier")
        payload = self.payload()
        payload.pop("supplier_name")
        payload["supplier_id"] = str(supplier.id)
        response = self.client.post("/api/v1/inventory/receipts", payload, format="json", HTTP_IDEMPOTENCY_KEY="receipt-foreign-supplier")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(PurchaseReceipt.objects.count(), 0)

    def test_cashier_cannot_post_receipt(self):
        self.membership.role = Membership.Role.CASHIER
        self.membership.save(update_fields=["role"])
        response = self.client.post("/api/v1/inventory/receipts", self.payload(), format="json", HTTP_IDEMPOTENCY_KEY="receipt-cashier")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(PurchaseReceipt.objects.count(), 0)
