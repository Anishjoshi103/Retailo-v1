import uuid
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.catalog.models import Product
from apps.inventory.models import Supplier
from apps.tenancy.models import Branch, BranchAccess, Membership, Tenant


@override_settings(
    SIMPLE_JWT={"ACCESS_TOKEN_LIFETIME": timedelta(minutes=5), "REFRESH_TOKEN_LIFETIME": timedelta(days=1), "ROTATE_REFRESH_TOKENS": False, "BLACKLIST_AFTER_ROTATION": True, "ALGORITHM": "HS256", "SIGNING_KEY": "receipt-reads-test-key-only", "AUTH_HEADER_TYPES": ("Bearer",), "USER_ID_FIELD": "id", "USER_ID_CLAIM": "user_id"},
    REST_FRAMEWORK={"DEFAULT_AUTHENTICATION_CLASSES": ("rest_framework_simplejwt.authentication.JWTAuthentication",), "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema", "EXCEPTION_HANDLER": "config.api_errors.api_exception_handler"},
    IS_TEST_ENV=True,
)
class PurchaseReceiptReadTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Store A", slug="store-a")
        self.other_tenant = Tenant.objects.create(name="Store B", slug="store-b")
        self.main = Branch.objects.create(tenant=self.tenant, name="Main", code="MAIN", state_code="27")
        self.north = Branch.objects.create(tenant=self.tenant, name="North", code="NORTH", state_code="27")
        self.rice = Product.objects.create(tenant=self.tenant, sku="RICE-1", name="Rice", unit=Product.Unit.KG, gst_rate=Decimal("5.00"), selling_price=Decimal("50.00"))
        self.soap = Product.objects.create(tenant=self.tenant, sku="SOAP-1", name="Soap", unit=Product.Unit.EACH, gst_rate=Decimal("18.00"), selling_price=Decimal("40.00"))
        self.agro = Supplier.objects.create(tenant=self.tenant, name="Agro Foods")
        self.owner = self.client_for("owner", [self.main, self.north])
        self.manager = self.client_for("manager", [self.main])

    def client_for(self, role, branches, tenant=None):
        tenant = tenant or self.tenant
        tag = uuid.uuid4().hex[:6]
        user = get_user_model().objects.create_user(username=f"{role}-{tag}@example.test", email=f"{role}-{tag}@example.test", password="Test-password-123")
        member = Membership.objects.create(tenant=tenant, user=user, role=role)
        for branch in branches:
            BranchAccess.objects.create(membership=member, branch=branch)
        refresh = RefreshToken.for_user(user)
        refresh["tenant_id"] = str(tenant.id)
        refresh["membership_id"] = str(member.id)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
        return client

    def receive(self, branch, key, lines=None, **extra):
        body = {"branch_id": str(branch.id), "supplier_name": "Walk-in", "lines": lines or [{"product_id": str(self.rice.id), "quantity": "10", "unit_cost": "42.50"}], **extra}
        response = self.owner.post("/api/v1/inventory/receipts", body, format="json", HTTP_IDEMPOTENCY_KEY=key)
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()

    def test_list_is_newest_first_scoped_to_granted_branches_and_totals_each_receipt(self):
        first = self.receive(self.main, "r1")
        second = self.receive(self.north, "r2", lines=[
            {"product_id": str(self.rice.id), "quantity": "3", "unit_cost": "33.33"},
            {"product_id": str(self.soap.id), "quantity": "0.333", "unit_cost": "45.00"},
        ])
        third = self.receive(self.main, "r3", supplier_id=str(self.agro.id), supplier_name="")
        rows = self.owner.get("/api/v1/inventory/receipts").json()
        self.assertEqual([r["id"] for r in rows], [third["id"], second["id"], first["id"]])
        by_id = {r["id"]: r for r in rows}
        self.assertEqual((by_id[first["id"]]["line_count"], by_id[first["id"]]["total_cost"]), (1, "425.00"))
        # 3 x 33.33 = 99.99 and 0.333 x 45.00 = 14.985 -> 14.99, rounded per line like the screen does.
        self.assertEqual((by_id[second["id"]]["line_count"], by_id[second["id"]]["total_cost"]), (2, "114.98"))
        self.assertEqual(by_id[third["id"]]["supplier_id"], str(self.agro.id))
        self.assertIsNone(by_id[first["id"]]["supplier_id"])
        manager_rows = self.manager.get("/api/v1/inventory/receipts").json()
        self.assertEqual({r["id"] for r in manager_rows}, {first["id"], third["id"]})

    def test_cost_data_is_not_available_to_cashiers(self):
        receipt = self.receive(self.main, "r1")
        cashier = self.client_for("cashier", [self.main])
        self.assertEqual(cashier.get("/api/v1/inventory/receipts").status_code, 403)
        self.assertEqual(cashier.get(f"/api/v1/inventory/receipts/{receipt['id']}").status_code, 403)

    def test_accountants_can_read_receipts(self):
        receipt = self.receive(self.main, "r1")
        accountant = self.client_for("accountant", [self.main])
        self.assertEqual(len(accountant.get("/api/v1/inventory/receipts").json()), 1)
        self.assertEqual(accountant.get(f"/api/v1/inventory/receipts/{receipt['id']}").status_code, 200)

    def test_other_stores_receipts_are_never_listed_or_fetched(self):
        receipt = self.receive(self.main, "r1")
        foreign_branch = Branch.objects.create(tenant=self.other_tenant, name="B", code="B", state_code="27")
        foreign = self.client_for("owner", [foreign_branch], tenant=self.other_tenant)
        self.assertEqual(foreign.get("/api/v1/inventory/receipts").json(), [])
        self.assertEqual(foreign.get(f"/api/v1/inventory/receipts/{receipt['id']}").status_code, 404)

    def test_filters_by_supplier_invoice_branch_and_date(self):
        self.receive(self.main, "r1", supplier_invoice_number="AF-1001")
        with_supplier = self.receive(self.north, "r2", supplier_id=str(self.agro.id), supplier_name="", supplier_invoice_number="XY-7")
        by_supplier = self.owner.get(f"/api/v1/inventory/receipts?supplier_id={self.agro.id}").json()
        self.assertEqual([r["id"] for r in by_supplier], [with_supplier["id"]])
        by_invoice = self.owner.get("/api/v1/inventory/receipts?invoice_number=af-10").json()
        self.assertEqual(len(by_invoice), 1)
        self.assertEqual(by_invoice[0]["supplier_invoice_number"], "AF-1001")
        self.assertEqual(len(self.owner.get(f"/api/v1/inventory/receipts?branch_id={self.north.id}").json()), 1)
        self.assertEqual(self.manager.get(f"/api/v1/inventory/receipts?branch_id={self.north.id}").status_code, 403)
        self.assertEqual(len(self.owner.get("/api/v1/inventory/receipts?date_from=2000-01-01&date_to=2999-01-01").json()), 2)
        self.assertEqual(self.owner.get("/api/v1/inventory/receipts?date_from=2999-01-01").json(), [])
        self.assertEqual(self.owner.get("/api/v1/inventory/receipts?date_to=2000-01-01").json(), [])
        for bad in ("supplier_id=nope", "branch_id=nope", "date_from=yesterday", "limit=0", "limit=201", "offset=-1"):
            self.assertEqual(self.owner.get(f"/api/v1/inventory/receipts?{bad}").status_code, 400, bad)

    def test_limit_and_offset_page_through_results(self):
        ids = [self.receive(self.main, f"r{i}")["id"] for i in range(3)]
        newest_first = list(reversed(ids))
        self.assertEqual([r["id"] for r in self.owner.get("/api/v1/inventory/receipts?limit=2").json()], newest_first[:2])
        self.assertEqual([r["id"] for r in self.owner.get("/api/v1/inventory/receipts?limit=2&offset=2").json()], newest_first[2:])

    def test_detail_returns_named_lines_with_line_totals_in_a_stable_order(self):
        receipt = self.receive(self.main, "r1", supplier_invoice_number="AF-1", lines=[
            {"product_id": str(self.soap.id), "quantity": "0.333", "unit_cost": "45.00"},
            {"product_id": str(self.rice.id), "quantity": "3", "unit_cost": "33.33"},
        ])
        body = self.manager.get(f"/api/v1/inventory/receipts/{receipt['id']}").json()
        self.assertEqual((body["supplier_invoice_number"], body["line_count"], body["total_cost"]), ("AF-1", 2, "114.98"))
        self.assertEqual([line["name"] for line in body["lines"]], ["Rice", "Soap"])
        rice_line, soap_line = body["lines"]
        self.assertEqual((rice_line["sku"], rice_line["unit"], rice_line["quantity"], rice_line["unit_cost"], rice_line["line_total"]), ("RICE-1", "kg", "3.000", "33.33", "99.99"))
        self.assertEqual((soap_line["quantity"], soap_line["line_total"]), ("0.333", "14.99"))

    def test_detail_is_not_found_for_ungranted_branch_and_unknown_id(self):
        north_receipt = self.receive(self.north, "r1")
        self.assertEqual(self.manager.get(f"/api/v1/inventory/receipts/{north_receipt['id']}").status_code, 404)
        self.assertEqual(self.owner.get(f"/api/v1/inventory/receipts/{uuid.uuid4()}").status_code, 404)

    def test_reads_require_authentication_and_posting_still_works(self):
        self.assertEqual(APIClient().get("/api/v1/inventory/receipts").status_code, 401)
        self.assertEqual(APIClient().get(f"/api/v1/inventory/receipts/{uuid.uuid4()}").status_code, 401)
        self.receive(self.main, "r1")
        replay = self.owner.post("/api/v1/inventory/receipts", {"branch_id": str(self.main.id), "supplier_name": "Walk-in", "lines": [{"product_id": str(self.rice.id), "quantity": "10", "unit_cost": "42.50"}]}, format="json", HTTP_IDEMPOTENCY_KEY="r1")
        self.assertEqual((replay.status_code, replay.json()["replayed"]), (200, True))
