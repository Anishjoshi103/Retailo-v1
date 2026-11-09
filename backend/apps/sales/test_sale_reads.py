import uuid
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.catalog.models import Product
from apps.inventory.models import InventoryBalance
from apps.sales.models import Sale
from apps.tenancy.models import Branch, BranchAccess, Membership, Tenant


@override_settings(
    SIMPLE_JWT={"ACCESS_TOKEN_LIFETIME": timedelta(minutes=5), "REFRESH_TOKEN_LIFETIME": timedelta(days=1), "ROTATE_REFRESH_TOKENS": False, "BLACKLIST_AFTER_ROTATION": True, "ALGORITHM": "HS256", "SIGNING_KEY": "sale-reads-test-key-only", "AUTH_HEADER_TYPES": ("Bearer",), "USER_ID_FIELD": "id", "USER_ID_CLAIM": "user_id"},
    REST_FRAMEWORK={"DEFAULT_AUTHENTICATION_CLASSES": ("rest_framework_simplejwt.authentication.JWTAuthentication",), "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema", "EXCEPTION_HANDLER": "config.api_errors.api_exception_handler"},
    IS_TEST_ENV=True,
)
class SaleReadTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Store A", slug="store-a")
        self.other_tenant = Tenant.objects.create(name="Store B", slug="store-b")
        self.main = Branch.objects.create(tenant=self.tenant, name="Main", code="MAIN", state_code="27")
        self.north = Branch.objects.create(tenant=self.tenant, name="North", code="NORTH", state_code="27")
        self.other_branch = Branch.objects.create(tenant=self.other_tenant, name="Main", code="MAIN", state_code="27")
        self.product = Product.objects.create(tenant=self.tenant, sku="RICE-1", name="Rice", gst_rate=Decimal("18.00"), selling_price=Decimal("100.00"))
        for branch in (self.main, self.north):
            InventoryBalance.objects.create(tenant=self.tenant, branch=branch, product=self.product, quantity_on_hand=Decimal("100.000"))
        self.cashier = self.client_for("cashier", [self.main])
        self.owner = self.client_for("owner", [self.main, self.north])

    def client_for(self, role, branches):
        user = get_user_model().objects.create_user(username=f"{role}-{uuid.uuid4().hex[:6]}@example.test", email=f"{role}-{uuid.uuid4().hex[:6]}@example.test", password="Test-password-123")
        membership = Membership.objects.create(tenant=self.tenant, user=user, role=role)
        for branch in branches:
            BranchAccess.objects.create(membership=membership, branch=branch)
        refresh = RefreshToken.for_user(user)
        refresh["tenant_id"] = str(self.tenant.id)
        refresh["membership_id"] = str(membership.id)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
        return client

    def sell(self, client, branch, key):
        response = client.post("/api/v1/sales", {
            "branch_id": str(branch.id),
            "lines": [{"product_id": str(self.product.id), "quantity": "1"}],
            "payments": [{"method": "cash", "amount": "118.00"}],
        }, format="json", HTTP_IDEMPOTENCY_KEY=key)
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()

    def old_sale(self, tenant, branch, number, invoice_date):
        return Sale.objects.create(
            tenant=tenant, branch=branch, invoice_number=number, invoice_date=invoice_date,
            seller_state_code="27", place_of_supply_state_code="27",
            taxable_total=Decimal("10.00"), cgst_total=Decimal("0.00"), sgst_total=Decimal("0.00"),
            igst_total=Decimal("0.00"), total_tax=Decimal("0.00"), round_off=Decimal("0.00"),
            grand_total=Decimal("10.00"), idempotency_key=f"old-{number}", request_hash="h" * 64,
            created_by=get_user_model().objects.first(),
        )

    def test_list_is_newest_first_and_limited_to_granted_branches(self):
        first = self.sell(self.owner, self.main, "s1")
        second = self.sell(self.owner, self.north, "s2")
        third = self.sell(self.owner, self.main, "s3")
        owner_rows = self.owner.get("/api/v1/sales").json()
        self.assertEqual([r["id"] for r in owner_rows], [third["id"], second["id"], first["id"]])
        cashier_rows = self.cashier.get("/api/v1/sales").json()
        self.assertEqual({r["id"] for r in cashier_rows}, {first["id"], third["id"]})
        self.assertNotIn("lines", cashier_rows[0])
        self.assertEqual(cashier_rows[0]["grand_total"], "118.00")

    def test_other_stores_sales_are_never_listed_or_fetched(self):
        foreign = self.old_sale(self.other_tenant, self.other_branch, "INV-MAIN-000001", date(2026, 1, 1))
        self.sell(self.owner, self.main, "s1")
        self.assertEqual(len(self.owner.get("/api/v1/sales").json()), 1)
        self.assertEqual(self.owner.get(f"/api/v1/sales/{foreign.id}").status_code, 404)

    def test_branch_filter_and_access_check(self):
        self.sell(self.owner, self.main, "s1")
        north = self.sell(self.owner, self.north, "s2")
        rows = self.owner.get(f"/api/v1/sales?branch_id={self.north.id}").json()
        self.assertEqual([r["id"] for r in rows], [north["id"]])
        self.assertEqual(self.cashier.get(f"/api/v1/sales?branch_id={self.north.id}").status_code, 403)
        self.assertEqual(self.owner.get("/api/v1/sales?branch_id=not-a-uuid").status_code, 400)

    def test_date_and_invoice_number_filters(self):
        today = self.sell(self.owner, self.main, "s1")
        self.old_sale(self.tenant, self.main, "INV-MAIN-900001", date(2026, 1, 15))
        self.assertEqual(len(self.owner.get("/api/v1/sales").json()), 2)
        recent = self.owner.get("/api/v1/sales?date_from=2026-06-01").json()
        self.assertEqual([r["id"] for r in recent], [today["id"]])
        old = self.owner.get("/api/v1/sales?date_to=2026-02-01").json()
        self.assertEqual([r["invoice_number"] for r in old], ["INV-MAIN-900001"])
        found = self.owner.get("/api/v1/sales?invoice_number=inv-main-000001").json()
        self.assertEqual([r["id"] for r in found], [today["id"]])
        self.assertEqual(self.owner.get("/api/v1/sales?date_from=yesterday").status_code, 400)

    def test_limit_and_offset_page_through_results(self):
        ids = [self.sell(self.owner, self.main, f"s{i}")["id"] for i in range(3)]
        newest_first = list(reversed(ids))
        self.assertEqual([r["id"] for r in self.owner.get("/api/v1/sales?limit=2").json()], newest_first[:2])
        self.assertEqual([r["id"] for r in self.owner.get("/api/v1/sales?limit=2&offset=2").json()], newest_first[2:])
        for query in ("limit=0", "limit=201", "limit=abc", "offset=-1"):
            self.assertEqual(self.owner.get(f"/api/v1/sales?{query}").status_code, 400, query)

    def test_detail_returns_full_invoice_with_lines_and_payments(self):
        sale = self.sell(self.cashier, self.main, "s1")
        body = self.cashier.get(f"/api/v1/sales/{sale['id']}").json()
        self.assertEqual(body["invoice_number"], "INV-MAIN-000001")
        self.assertEqual(body["lines"][0]["sku"], "RICE-1")
        self.assertEqual(body["payments"], [{"method": "cash", "amount": "118.00", "reference": ""}])
        self.assertEqual((body["cgst_total"], body["sgst_total"], body["seller_state_code"]), ("9.00", "9.00", "27"))
        self.assertNotIn("replayed", body)

    def test_detail_is_not_found_for_ungranted_branch_and_unknown_id(self):
        north = self.sell(self.owner, self.north, "s1")
        self.assertEqual(self.cashier.get(f"/api/v1/sales/{north['id']}").status_code, 404)
        self.assertEqual(self.cashier.get(f"/api/v1/sales/{uuid.uuid4()}").status_code, 404)

    def test_accountant_can_read_but_not_sell(self):
        sale = self.sell(self.owner, self.main, "s1")
        accountant = self.client_for("accountant", [self.main])
        self.assertEqual(len(accountant.get("/api/v1/sales").json()), 1)
        self.assertEqual(accountant.get(f"/api/v1/sales/{sale['id']}").status_code, 200)
        denied = accountant.post("/api/v1/sales", {}, format="json", HTTP_IDEMPOTENCY_KEY="x")
        self.assertEqual(denied.status_code, 403)

    def test_reads_require_authentication_and_a_store_membership(self):
        self.assertEqual(APIClient().get("/api/v1/sales").status_code, 401)
        self.assertEqual(APIClient().get(f"/api/v1/sales/{uuid.uuid4()}").status_code, 401)
