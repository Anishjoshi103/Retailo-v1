"""SQL Server integration tests for concurrent sales, returns and invoice numbering.

These tests use independent database connections and overlapping transactions. SQLite does not
implement the row-locking semantics under test, so the suite is deliberately skipped there.
"""
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from threading import Barrier

from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection
from django.test import TransactionTestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.catalog.models import Product
from apps.inventory.models import InventoryBalance
from apps.sales.models import CreditNote, Sale
from apps.tenancy.models import Branch, BranchAccess, Membership, Tenant


@override_settings(
    SIMPLE_JWT={
        "ACCESS_TOKEN_LIFETIME": timedelta(minutes=5),
        "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
        "ROTATE_REFRESH_TOKENS": False,
        "BLACKLIST_AFTER_ROTATION": True,
        "ALGORITHM": "HS256",
        "SIGNING_KEY": "sales-concurrency-test-key-only",
        "AUTH_HEADER_TYPES": ("Bearer",),
        "USER_ID_FIELD": "id",
        "USER_ID_CLAIM": "user_id",
    },
    REST_FRAMEWORK={
        "DEFAULT_AUTHENTICATION_CLASSES": ("rest_framework_simplejwt.authentication.JWTAuthentication",),
        "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
        "EXCEPTION_HANDLER": "config.api_errors.api_exception_handler",
    },
    IS_TEST_ENV=True,
)
class SalesConcurrencyTests(TransactionTestCase):
    """Exercise the real API with overlapping requests on independent connections."""

    reset_sequences = True

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if connection.vendor != "microsoft":
            raise unittest.SkipTest("Requires SQL Server row-level transaction locking.")

    def setUp(self):
        self.tenant = Tenant.objects.create(name="Concurrency Store", slug="concurrency-store")
        self.branch = Branch.objects.create(
            tenant=self.tenant, name="Main", code="MAIN", state_code="27", gstin="27AAPFU0939F1ZV"
        )
        self.product = Product.objects.create(
            tenant=self.tenant, sku="RACE-1", name="Race product", hsn_code="1006",
            unit=Product.Unit.EACH, gst_rate=Decimal("0.00"), selling_price=Decimal("100.00"),
        )
        InventoryBalance.objects.create(
            tenant=self.tenant, branch=self.branch, product=self.product,
            quantity_on_hand=Decimal("10.000"),
        )
        user = get_user_model().objects.create_user(
            username="concurrency-cashier@example.test",
            email="concurrency-cashier@example.test",
            password="Test-password-123",
        )
        membership = Membership.objects.create(tenant=self.tenant, user=user, role="cashier")
        BranchAccess.objects.create(membership=membership, branch=self.branch)
        refresh = RefreshToken.for_user(user)
        refresh["tenant_id"] = str(self.tenant.id)
        refresh["membership_id"] = str(membership.id)
        self.access_token = str(refresh.access_token)

    def api_client(self):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")
        return client

    def concurrent_posts(self, requests):
        """Start requests together; each worker owns its DB connection and API client."""
        barrier = Barrier(len(requests))

        def post(request):
            close_old_connections()
            try:
                client = self.api_client()
                barrier.wait(timeout=10)
                response = client.post(
                    request["path"], request["body"], format="json",
                    HTTP_IDEMPOTENCY_KEY=request["key"],
                )
                return response.status_code, response.json()
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=len(requests)) as pool:
            return list(pool.map(post, requests))

    def sale_request(self, key, quantity="1"):
        return {
            "path": "/api/v1/sales",
            "key": key,
            "body": {
                "branch_id": str(self.branch.id),
                "lines": [{"product_id": str(self.product.id), "quantity": quantity}],
                "payments": [{"method": "cash", "amount": str(Decimal(quantity) * Decimal("100.00"))}],
            },
        }

    def on_hand(self):
        return InventoryBalance.objects.for_tenant(self.tenant.id).get(
            branch=self.branch, product=self.product
        ).quantity_on_hand

    def test_two_sales_cannot_both_consume_the_same_available_stock(self):
        # Each request needs 7 units; only 10 are available.
        results = self.concurrent_posts([
            self.sale_request("race-sale-a", "7"),
            self.sale_request("race-sale-b", "7"),
        ])

        self.assertEqual(sorted(status for status, _ in results), [201, 400], results)
        self.assertEqual(Sale.objects.for_tenant(self.tenant.id).count(), 1)
        self.assertEqual(self.on_hand(), Decimal("3.000"))

    def test_two_returns_cannot_return_the_same_sold_quantity_twice(self):
        seed = self.sale_request("seed-sale", "2")
        sale_response = self.api_client().post(
            seed["path"], seed["body"], format="json", HTTP_IDEMPOTENCY_KEY=seed["key"],
        )
        self.assertEqual(sale_response.status_code, 201, sale_response.content)
        sale = sale_response.json()
        body = {
            "reason": "Damaged",
            "lines": [{"sale_line_id": sale["lines"][0]["id"], "quantity": "2"}],
        }
        path = f"/api/v1/sales/{sale['id']}/returns"
        results = self.concurrent_posts([
            {"path": path, "key": "race-return-a", "body": body},
            {"path": path, "key": "race-return-b", "body": body},
        ])

        self.assertEqual(sorted(status for status, _ in results), [201, 400], results)
        self.assertEqual(CreditNote.objects.for_tenant(self.tenant.id).count(), 1)
        self.assertEqual(self.on_hand(), Decimal("10.000"))

    def test_concurrent_invoices_receive_distinct_sequential_numbers(self):
        results = self.concurrent_posts([
            self.sale_request("number-sale-a", "1"),
            self.sale_request("number-sale-b", "1"),
        ])

        self.assertEqual([status for status, _ in results], [201, 201], results)
        numbers = sorted(body["invoice_number"] for _, body in results)
        self.assertEqual(numbers, ["INV-MAIN-000001", "INV-MAIN-000002"])
        self.assertEqual(Sale.objects.for_tenant(self.tenant.id).count(), 2)
        self.assertEqual(self.on_hand(), Decimal("8.000"))
