from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.catalog.models import Product
from apps.inventory.models import InventoryBalance, StockMovement
from apps.sales.models import CreditNote
from apps.tenancy.models import Branch, BranchAccess, Membership, Tenant


@override_settings(
    SIMPLE_JWT={"ACCESS_TOKEN_LIFETIME": timedelta(minutes=5), "REFRESH_TOKEN_LIFETIME": timedelta(days=1), "ROTATE_REFRESH_TOKENS": False, "BLACKLIST_AFTER_ROTATION": True, "ALGORITHM": "HS256", "SIGNING_KEY": "sale-returns-test-key-only", "AUTH_HEADER_TYPES": ("Bearer",), "USER_ID_FIELD": "id", "USER_ID_CLAIM": "user_id"},
    REST_FRAMEWORK={"DEFAULT_AUTHENTICATION_CLASSES": ("rest_framework_simplejwt.authentication.JWTAuthentication",), "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema", "EXCEPTION_HANDLER": "config.api_errors.api_exception_handler"},
    IS_TEST_ENV=True,
)
class SaleReturnTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Store A", slug="store-a")
        self.other_tenant = Tenant.objects.create(name="Store B", slug="store-b")
        self.branch = Branch.objects.create(tenant=self.tenant, name="Main", code="MAIN", state_code="27", gstin="27AAPFU0939F1ZV")
        self.rice = Product.objects.create(tenant=self.tenant, sku="RICE-1", name="Rice", hsn_code="1006", unit=Product.Unit.KG, gst_rate=Decimal("18.00"), selling_price=Decimal("100.00"))
        self.soap = Product.objects.create(tenant=self.tenant, sku="SOAP-1", name="Soap", unit=Product.Unit.EACH, gst_rate=Decimal("5.00"), selling_price=Decimal("33.33"))
        for product in (self.rice, self.soap):
            InventoryBalance.objects.create(tenant=self.tenant, branch=self.branch, product=product, quantity_on_hand=Decimal("10.000"))
        self.cashier = self.client_for("cashier")
        self.sale = self.sell()

    def client_for(self, role, grant=True, tenant=None):
        tenant = tenant or self.tenant
        user = get_user_model().objects.create_user(username=f"{role}-{tenant.slug}@example.test", email=f"{role}-{tenant.slug}@example.test", password="Test-password-123")
        membership = Membership.objects.create(tenant=tenant, user=user, role=role)
        if grant:
            BranchAccess.objects.create(membership=membership, branch=self.branch if tenant == self.tenant else Branch.objects.create(tenant=tenant, name="B", code="B"))
        refresh = RefreshToken.for_user(user)
        refresh["tenant_id"] = str(tenant.id)
        refresh["membership_id"] = str(membership.id)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
        return client

    def sell(self, rice_qty="2", soap_qty=None, key="sale-1", payment="200.00"):
        lines = [{"product_id": str(self.rice.id), "quantity": rice_qty}]
        if soap_qty:
            lines.append({"product_id": str(self.soap.id), "quantity": soap_qty})
        response = self.cashier.post("/api/v1/sales", {"branch_id": str(self.branch.id), "lines": lines, "payments": [{"method": "cash", "amount": payment}]}, format="json", HTTP_IDEMPOTENCY_KEY=key)
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()

    def line_id(self, sale, sku):
        return next(line["id"] for line in sale["lines"] if line["sku"] == sku)

    def give_back(self, client, sale, items, reason="Damaged", key="ret-1"):
        body = {"reason": reason, "lines": [{"sale_line_id": self.line_id(sale, sku), "quantity": qty} for sku, qty in items]}
        return client.post(f"/api/v1/sales/{sale['id']}/returns", body, format="json", HTTP_IDEMPOTENCY_KEY=key)

    def on_hand(self, product):
        return InventoryBalance.objects.for_tenant(self.tenant.id).get(branch=self.branch, product=product).quantity_on_hand

    def note_count(self):
        return CreditNote.objects.for_tenant(self.tenant.id).count()

    def test_partial_return_reverses_tax_restocks_and_refunds_cash(self):
        response = self.give_back(self.cashier, self.sale, [("RICE-1", "1")])
        self.assertEqual(response.status_code, 201, response.content)
        body = response.json()
        self.assertEqual(body["credit_note_number"], "CN-MAIN-000001")
        self.assertEqual(body["invoice_number"], "INV-MAIN-000001")
        self.assertEqual((body["taxable_total"], body["cgst_total"], body["sgst_total"], body["igst_total"]), ("84.75", "7.63", "7.63", "0.00"))
        self.assertEqual((body["grand_total"], body["round_off"], body["refund_amount"], body["refund_method"]), ("100.00", "-0.01", "100.00", "cash"))
        self.assertEqual((body["lines"][0]["sku"], body["lines"][0]["quantity"], body["lines"][0]["unit_price"]), ("RICE-1", "1.000", "100.00"))
        self.assertFalse(body["replayed"])
        self.assertEqual(self.on_hand(self.rice), Decimal("9.000"))
        movement = StockMovement.objects.for_tenant(self.tenant.id).get(reason="return")
        self.assertEqual((movement.quantity_delta, movement.reference), (Decimal("1.000"), "CN-MAIN-000001"))

    def test_returns_never_exceed_what_was_sold_across_several_credit_notes(self):
        self.assertEqual(self.give_back(self.cashier, self.sale, [("RICE-1", "1.5")], key="r1").status_code, 201)
        over = self.give_back(self.cashier, self.sale, [("RICE-1", "1")], key="r2")
        self.assertEqual(over.status_code, 400)
        self.assertIn("only 0.500", str(over.json()))
        self.assertEqual(self.give_back(self.cashier, self.sale, [("RICE-1", "0.5")], key="r3").status_code, 201)
        self.assertEqual(self.give_back(self.cashier, self.sale, [("RICE-1", "0.001")], key="r4").status_code, 400)
        self.assertEqual(self.note_count(), 2)
        self.assertEqual(self.on_hand(self.rice), Decimal("10.000"))

    def test_returning_a_whole_sale_refunds_exactly_its_grand_total(self):
        sale = self.sell(rice_qty="2", soap_qty="3", key="sale-2", payment="300.00")
        response = self.give_back(self.cashier, sale, [("RICE-1", "2"), ("SOAP-1", "3")], key="ret-all")
        self.assertEqual(response.status_code, 201, response.content)
        body = response.json()
        for field in ("taxable_total", "cgst_total", "sgst_total", "igst_total", "total_tax", "round_off", "grand_total"):
            self.assertEqual(body[field], sale[field], field)

    def test_rejected_return_changes_nothing_and_consumes_no_number(self):
        before = self.on_hand(self.rice)
        self.assertEqual(self.give_back(self.cashier, self.sale, [("RICE-1", "3")], key="too-many").status_code, 400)
        self.assertEqual(self.note_count(), 0)
        self.assertEqual(self.on_hand(self.rice), before)
        ok = self.give_back(self.cashier, self.sale, [("RICE-1", "1")], key="fine")
        self.assertEqual(ok.json()["credit_note_number"], "CN-MAIN-000001")

    def test_replay_returns_the_same_credit_note_without_a_second_restock(self):
        first = self.give_back(self.cashier, self.sale, [("RICE-1", "1")])
        replay = self.give_back(self.cashier, self.sale, [("RICE-1", "1")])
        self.assertEqual(replay.status_code, 200)
        self.assertTrue(replay.json()["replayed"])
        self.assertEqual(replay.json()["credit_note_number"], first.json()["credit_note_number"])
        self.assertEqual(self.note_count(), 1)
        self.assertEqual(self.on_hand(self.rice), Decimal("9.000"))

    def test_same_key_with_a_different_return_conflicts(self):
        self.give_back(self.cashier, self.sale, [("RICE-1", "1")])
        self.assertEqual(self.give_back(self.cashier, self.sale, [("RICE-1", "0.5")]).status_code, 409)
        self.assertEqual(self.note_count(), 1)

    def test_idempotency_key_header_is_required(self):
        body = {"reason": "x", "lines": [{"sale_line_id": self.line_id(self.sale, "RICE-1"), "quantity": "1"}]}
        self.assertEqual(self.cashier.post(f"/api/v1/sales/{self.sale['id']}/returns", body, format="json").status_code, 400)

    def test_accountant_cannot_take_returns_but_manager_can(self):
        self.assertEqual(self.give_back(self.client_for("accountant"), self.sale, [("RICE-1", "1")]).status_code, 403)
        self.assertEqual(self.note_count(), 0)
        self.assertEqual(self.give_back(self.client_for("manager"), self.sale, [("RICE-1", "1")]).status_code, 201)

    def test_unknown_foreign_and_ungranted_sales_are_not_found(self):
        ungranted = self.client_for("manager", grant=False)
        self.assertEqual(self.give_back(ungranted, self.sale, [("RICE-1", "1")], key="a").status_code, 404)
        foreign = self.client_for("owner", tenant=self.other_tenant)
        self.assertEqual(self.give_back(foreign, self.sale, [("RICE-1", "1")], key="b").status_code, 404)
        body = {"reason": "x", "lines": [{"sale_line_id": self.line_id(self.sale, "RICE-1"), "quantity": "1"}]}
        self.assertEqual(self.cashier.post("/api/v1/sales/00000000-0000-4000-8000-000000000000/returns", body, format="json", HTTP_IDEMPOTENCY_KEY="c").status_code, 404)
        self.assertEqual(self.note_count(), 0)

    def test_invalid_requests_are_rejected(self):
        line = self.line_id(self.sale, "RICE-1")
        url = f"/api/v1/sales/{self.sale['id']}/returns"
        post = lambda body, key: self.cashier.post(url, body, format="json", HTTP_IDEMPOTENCY_KEY=key)  # noqa: E731
        self.assertEqual(post({"reason": "", "lines": [{"sale_line_id": line, "quantity": "1"}]}, "k1").status_code, 400)
        self.assertEqual(post({"lines": [{"sale_line_id": line, "quantity": "1"}]}, "k2").status_code, 400)
        self.assertEqual(post({"reason": "x", "lines": []}, "k3").status_code, 400)
        self.assertEqual(post({"reason": "x", "lines": [{"sale_line_id": line, "quantity": "0"}]}, "k4").status_code, 400)
        duplicate = {"reason": "x", "lines": [{"sale_line_id": line, "quantity": "1"}, {"sale_line_id": line, "quantity": "1"}]}
        self.assertEqual(post(duplicate, "k5").status_code, 400)
        other_sale = self.sell(key="sale-9")
        foreign_line = {"reason": "x", "lines": [{"sale_line_id": self.line_id(other_sale, "RICE-1"), "quantity": "1"}]}
        self.assertEqual(post(foreign_line, "k6").status_code, 400)
        self.assertEqual(self.note_count(), 0)

    def test_credit_note_numbers_are_sequential_and_separate_from_invoices(self):
        self.give_back(self.cashier, self.sale, [("RICE-1", "0.5")], key="r1")
        second = self.give_back(self.cashier, self.sale, [("RICE-1", "0.5")], key="r2")
        self.assertEqual(second.json()["credit_note_number"], "CN-MAIN-000002")
        self.assertEqual(self.sell(key="sale-2")["invoice_number"], "INV-MAIN-000002")

    def test_credit_note_keeps_the_sale_snapshot_after_a_catalogue_edit(self):
        Product.objects.for_tenant(self.tenant.id).filter(pk=self.rice.pk).update(name="Renamed", selling_price=Decimal("999.00"))
        body = self.give_back(self.cashier, self.sale, [("RICE-1", "1")]).json()
        self.assertEqual((body["lines"][0]["name"], body["lines"][0]["unit_price"]), ("Rice", "100.00"))
        self.assertEqual((body["seller_gstin"], body["place_of_supply_state_code"]), ("27AAPFU0939F1ZV", "27"))
