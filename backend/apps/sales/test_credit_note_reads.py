import uuid
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.catalog.models import Product
from apps.inventory.models import InventoryBalance
from apps.tenancy.models import Branch, BranchAccess, Membership, Tenant


@override_settings(
    SIMPLE_JWT={"ACCESS_TOKEN_LIFETIME": timedelta(minutes=5), "REFRESH_TOKEN_LIFETIME": timedelta(days=1), "ROTATE_REFRESH_TOKENS": False, "BLACKLIST_AFTER_ROTATION": True, "ALGORITHM": "HS256", "SIGNING_KEY": "credit-note-reads-test-key-only", "AUTH_HEADER_TYPES": ("Bearer",), "USER_ID_FIELD": "id", "USER_ID_CLAIM": "user_id"},
    REST_FRAMEWORK={"DEFAULT_AUTHENTICATION_CLASSES": ("rest_framework_simplejwt.authentication.JWTAuthentication",), "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema", "EXCEPTION_HANDLER": "config.api_errors.api_exception_handler"},
    IS_TEST_ENV=True,
)
class CreditNoteReadTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Store A", slug="store-a")
        self.other_tenant = Tenant.objects.create(name="Store B", slug="store-b")
        self.main = Branch.objects.create(tenant=self.tenant, name="Main", code="MAIN", state_code="27")
        self.north = Branch.objects.create(tenant=self.tenant, name="North", code="NORTH", state_code="27")
        self.product = Product.objects.create(tenant=self.tenant, sku="RICE-1", name="Rice", hsn_code="1006", gst_rate=Decimal("18.00"), selling_price=Decimal("100.00"))
        for branch in (self.main, self.north):
            InventoryBalance.objects.create(tenant=self.tenant, branch=branch, product=self.product, quantity_on_hand=Decimal("100.000"))
        self.owner = self.client_for("owner", [self.main, self.north])
        self.cashier = self.client_for("cashier", [self.main])

    def client_for(self, role, branches, tenant=None):
        tenant = tenant or self.tenant
        tag = uuid.uuid4().hex[:6]
        user = get_user_model().objects.create_user(username=f"{role}-{tag}@example.test", email=f"{role}-{tag}@example.test", password="Test-password-123")
        membership = Membership.objects.create(tenant=tenant, user=user, role=role)
        for branch in branches:
            BranchAccess.objects.create(membership=membership, branch=branch)
        refresh = RefreshToken.for_user(user)
        refresh["tenant_id"] = str(tenant.id)
        refresh["membership_id"] = str(membership.id)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
        return client

    def sell(self, branch, key, quantity="3"):
        response = self.owner.post("/api/v1/sales", {
            "branch_id": str(branch.id),
            "lines": [{"product_id": str(self.product.id), "quantity": quantity}],
            "payments": [{"method": "cash", "amount": f"{int(quantity) * 100}.00"}],
        }, format="json", HTTP_IDEMPOTENCY_KEY=key)
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()

    def give_back(self, sale, quantity, key, reason="Damaged"):
        body = {"reason": reason, "lines": [{"sale_line_id": sale["lines"][0]["id"], "quantity": quantity}]}
        response = self.owner.post(f"/api/v1/sales/{sale['id']}/returns", body, format="json", HTTP_IDEMPOTENCY_KEY=key)
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()

    def test_list_is_newest_first_limited_to_granted_branches_and_compact(self):
        main_sale = self.sell(self.main, "s1")
        north_sale = self.sell(self.north, "s2")
        first = self.give_back(main_sale, "1", "r1")
        second = self.give_back(north_sale, "1", "r2")
        third = self.give_back(main_sale, "1", "r3")
        owner_rows = self.owner.get("/api/v1/credit-notes").json()
        self.assertEqual([row["id"] for row in owner_rows], [third["id"], second["id"], first["id"]])
        cashier_rows = self.cashier.get("/api/v1/credit-notes").json()
        self.assertEqual({row["id"] for row in cashier_rows}, {first["id"], third["id"]})
        row = cashier_rows[0]
        self.assertNotIn("lines", row)
        self.assertEqual((row["invoice_number"], row["reason"], row["grand_total"]), ("INV-MAIN-000001", "Damaged", "100.00"))

    def test_other_stores_credit_notes_are_never_listed_or_fetched(self):
        note = self.give_back(self.sell(self.main, "s1"), "1", "r1")
        foreign_branch = Branch.objects.create(tenant=self.other_tenant, name="B", code="B", state_code="27")
        foreign = self.client_for("owner", [foreign_branch], tenant=self.other_tenant)
        self.assertEqual(foreign.get("/api/v1/credit-notes").json(), [])
        self.assertEqual(foreign.get(f"/api/v1/credit-notes/{note['id']}").status_code, 404)

    def test_filters_by_sale_number_branch_and_date(self):
        sale_a = self.sell(self.main, "s1")
        sale_b = self.sell(self.north, "s2")
        note_a = self.give_back(sale_a, "1", "r1")
        self.give_back(sale_b, "1", "r2")
        by_sale = self.owner.get(f"/api/v1/credit-notes?sale_id={sale_a['id']}").json()
        self.assertEqual([row["id"] for row in by_sale], [note_a["id"]])
        by_number = self.owner.get("/api/v1/credit-notes?credit_note_number=cn-main-000001").json()
        self.assertEqual([row["id"] for row in by_number], [note_a["id"]])
        by_branch = self.owner.get(f"/api/v1/credit-notes?branch_id={self.north.id}").json()
        self.assertEqual(len(by_branch), 1)
        self.assertEqual(self.cashier.get(f"/api/v1/credit-notes?branch_id={self.north.id}").status_code, 403)
        self.assertEqual(len(self.owner.get("/api/v1/credit-notes?date_from=2000-01-01&date_to=2999-01-01").json()), 2)
        self.assertEqual(self.owner.get("/api/v1/credit-notes?date_from=2999-01-01").json(), [])
        self.assertEqual(self.owner.get("/api/v1/credit-notes?date_to=2000-01-01").json(), [])
        for bad in ("sale_id=nope", "branch_id=nope", "date_from=yesterday", "limit=0", "limit=201", "offset=-1"):
            self.assertEqual(self.owner.get(f"/api/v1/credit-notes?{bad}").status_code, 400, bad)

    def test_limit_and_offset_page_through_results(self):
        sale = self.sell(self.main, "s1", quantity="3")
        ids = [self.give_back(sale, "1", f"r{i}")["id"] for i in range(3)]
        newest_first = list(reversed(ids))
        self.assertEqual([r["id"] for r in self.owner.get("/api/v1/credit-notes?limit=2").json()], newest_first[:2])
        self.assertEqual([r["id"] for r in self.owner.get("/api/v1/credit-notes?limit=2&offset=2").json()], newest_first[2:])

    def test_detail_returns_the_full_credit_note(self):
        sale = self.sell(self.main, "s1")
        note = self.give_back(sale, "1", "r1")
        body = self.cashier.get(f"/api/v1/credit-notes/{note['id']}").json()
        self.assertEqual(body["credit_note_number"], "CN-MAIN-000001")
        self.assertEqual((body["refund_method"], body["refund_amount"]), ("cash", "100.00"))
        self.assertEqual(body["lines"][0]["sale_line_id"], sale["lines"][0]["id"])
        self.assertNotIn("replayed", body)

    def test_detail_is_not_found_for_ungranted_branch_and_unknown_id(self):
        note = self.give_back(self.sell(self.north, "s1"), "1", "r1")
        self.assertEqual(self.cashier.get(f"/api/v1/credit-notes/{note['id']}").status_code, 404)
        self.assertEqual(self.owner.get(f"/api/v1/credit-notes/{uuid.uuid4()}").status_code, 404)

    def test_accountant_can_read_credit_notes(self):
        note = self.give_back(self.sell(self.main, "s1"), "1", "r1")
        accountant = self.client_for("accountant", [self.main])
        self.assertEqual(len(accountant.get("/api/v1/credit-notes").json()), 1)
        self.assertEqual(accountant.get(f"/api/v1/credit-notes/{note['id']}").status_code, 200)

    def test_reads_require_authentication(self):
        self.assertEqual(APIClient().get("/api/v1/credit-notes").status_code, 401)
        self.assertEqual(APIClient().get(f"/api/v1/credit-notes/{uuid.uuid4()}").status_code, 401)

    def test_sale_detail_reports_how_much_of_each_line_has_been_returned(self):
        sale = self.sell(self.main, "s1")
        self.assertEqual(sale["lines"][0]["returned_quantity"], "0.000")
        self.give_back(sale, "1.5", "r1")
        detail = self.owner.get(f"/api/v1/sales/{sale['id']}").json()
        self.assertEqual((detail["lines"][0]["quantity"], detail["lines"][0]["returned_quantity"]), ("3.000", "1.500"))
        self.give_back(sale, "1.5", "r2")
        detail = self.owner.get(f"/api/v1/sales/{sale['id']}").json()
        self.assertEqual(detail["lines"][0]["returned_quantity"], "3.000")
