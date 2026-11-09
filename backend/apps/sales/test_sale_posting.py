from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.catalog.models import Product
from apps.inventory.models import InventoryBalance, StockMovement
from apps.sales.models import Sale
from apps.tenancy.models import Branch, BranchAccess, Membership, Tenant


@override_settings(
    SIMPLE_JWT={"ACCESS_TOKEN_LIFETIME": timedelta(minutes=5), "REFRESH_TOKEN_LIFETIME": timedelta(days=1), "ROTATE_REFRESH_TOKENS": False, "BLACKLIST_AFTER_ROTATION": True, "ALGORITHM": "HS256", "SIGNING_KEY": "sale-posting-test-key-only", "AUTH_HEADER_TYPES": ("Bearer",), "USER_ID_FIELD": "id", "USER_ID_CLAIM": "user_id"},
    REST_FRAMEWORK={"DEFAULT_AUTHENTICATION_CLASSES": ("rest_framework_simplejwt.authentication.JWTAuthentication",), "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema", "EXCEPTION_HANDLER": "config.api_errors.api_exception_handler"},
    IS_TEST_ENV=True,
)
class SalePostingTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Store A", slug="store-a")
        self.other_tenant = Tenant.objects.create(name="Store B", slug="store-b")
        self.branch = Branch.objects.create(tenant=self.tenant, name="Main", code="MAIN", state_code="27", gstin="27AAPFU0939F1ZV")
        self.rice = Product.objects.create(tenant=self.tenant, sku="RICE-1", name="Rice", hsn_code="1006", unit=Product.Unit.KG, gst_rate=Decimal("18.00"), selling_price=Decimal("100.00"))
        self.soap = Product.objects.create(tenant=self.tenant, sku="SOAP-1", name="Soap", unit=Product.Unit.EACH, gst_rate=Decimal("5.00"), selling_price=Decimal("33.33"))
        self.stock(self.rice, "10.000")
        self.stock(self.soap, "10.000")

    def stock(self, product, quantity):
        InventoryBalance.objects.create(tenant=self.tenant, branch=self.branch, product=product, quantity_on_hand=Decimal(quantity))

    def on_hand(self, product):
        return InventoryBalance.objects.for_tenant(self.tenant.id).get(branch=self.branch, product=product).quantity_on_hand

    def sale_count(self):
        return Sale.objects.for_tenant(self.tenant.id).count()

    def client_for(self, role, grant=True):
        user = get_user_model().objects.create_user(username=f"{role}@example.test", email=f"{role}@example.test", password="Test-password-123")
        membership = Membership.objects.create(tenant=self.tenant, user=user, role=role)
        if grant:
            BranchAccess.objects.create(membership=membership, branch=self.branch)
        refresh = RefreshToken.for_user(user)
        refresh["tenant_id"] = str(self.tenant.id)
        refresh["membership_id"] = str(membership.id)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
        return client

    def payload(self, **overrides):
        body = {
            "branch_id": str(self.branch.id),
            "lines": [{"product_id": str(self.rice.id), "quantity": "2"}],
            "payments": [{"method": "cash", "amount": "236.00"}],
        }
        body.update(overrides)
        return body

    def post(self, client, body=None, key="sale-1"):
        return client.post("/api/v1/sales", body if body is not None else self.payload(), format="json", HTTP_IDEMPOTENCY_KEY=key)

    def test_cashier_posts_sale_with_gst_snapshot_and_stock_deduction(self):
        response = self.post(self.client_for("cashier"))
        self.assertEqual(response.status_code, 201, response.content)
        body = response.json()
        self.assertEqual(body["invoice_number"], "INV-MAIN-000001")
        self.assertEqual((body["taxable_total"], body["cgst_total"], body["sgst_total"], body["igst_total"], body["grand_total"], body["round_off"]), ("200.00", "18.00", "18.00", "0.00", "236.00", "0.00"))
        self.assertEqual(body["lines"][0]["sku"], "RICE-1")
        self.assertEqual(body["lines"][0]["hsn_code"], "1006")
        self.assertEqual(body["payments"], [{"method": "cash", "amount": "236.00", "reference": ""}])
        self.assertFalse(body["replayed"])
        self.assertEqual(self.on_hand(self.rice), Decimal("8.000"))
        movement = StockMovement.objects.for_tenant(self.tenant.id).get(reason="sale")
        self.assertEqual((movement.quantity_delta, movement.reference), (Decimal("-2.000"), "INV-MAIN-000001"))

    def test_multi_line_sale_rounds_to_the_rupee_and_numbers_increase(self):
        client = self.client_for("manager")
        body = self.payload(
            lines=[{"product_id": str(self.rice.id), "quantity": "2"}, {"product_id": str(self.soap.id), "quantity": "3"}],
            payments=[{"method": "cash", "amount": "300.00"}, {"method": "upi", "amount": "41.00", "reference": "UPI-9"}],
        )
        first = self.post(client, body, key="sale-a")
        self.assertEqual(first.status_code, 201, first.content)
        self.assertEqual((first.json()["grand_total"], first.json()["round_off"]), ("341.00", "0.01"))
        second = self.post(client, key="sale-b")
        self.assertEqual(second.json()["invoice_number"], "INV-MAIN-000002")

    def test_client_cannot_set_prices(self):
        body = self.payload(lines=[{"product_id": str(self.rice.id), "quantity": "1", "unit_price": "1.00"}], payments=[{"method": "cash", "amount": "118.00"}])
        response = self.post(self.client_for("cashier"), body)
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()["lines"][0]["unit_price"], "100.00")

    def test_replay_returns_same_invoice_without_second_deduction(self):
        client = self.client_for("cashier")
        first = self.post(client)
        replay = self.post(client)
        self.assertEqual(replay.status_code, 200)
        self.assertTrue(replay.json()["replayed"])
        self.assertEqual(replay.json()["invoice_number"], first.json()["invoice_number"])
        self.assertEqual(self.sale_count(), 1)
        self.assertEqual(self.on_hand(self.rice), Decimal("8.000"))

    def test_same_key_with_different_sale_conflicts(self):
        client = self.client_for("cashier")
        self.post(client)
        other = self.payload(lines=[{"product_id": str(self.rice.id), "quantity": "1"}], payments=[{"method": "cash", "amount": "118.00"}])
        self.assertEqual(self.post(client, other).status_code, 409)
        self.assertEqual(self.sale_count(), 1)

    def test_idempotency_key_header_is_required(self):
        response = self.client_for("cashier").post("/api/v1/sales", self.payload(), format="json")
        self.assertEqual(response.status_code, 400)

    def test_accountant_cannot_sell(self):
        self.assertEqual(self.post(self.client_for("accountant")).status_code, 403)
        self.assertEqual(self.sale_count(), 0)

    def test_insufficient_stock_blocks_sale_and_changes_nothing(self):
        body = self.payload(lines=[{"product_id": str(self.rice.id), "quantity": "11"}], payments=[{"method": "cash", "amount": "1298.00"}])
        client = self.client_for("cashier")
        response = self.post(client, body)
        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(self.sale_count(), 0)
        self.assertEqual(self.on_hand(self.rice), Decimal("10.000"))
        self.assertEqual(StockMovement.objects.for_tenant(self.tenant.id).filter(reason="sale").count(), 0)
        self.assertEqual(self.post(client, key="sale-2").json()["invoice_number"], "INV-MAIN-000001")

    def test_cashier_cannot_use_the_stock_override(self):
        body = self.payload(allow_negative_stock=True)
        self.assertEqual(self.post(self.client_for("cashier"), body).status_code, 403)
        self.assertEqual(self.sale_count(), 0)

    def test_manager_override_sells_below_stock_and_notes_it(self):
        body = self.payload(lines=[{"product_id": str(self.rice.id), "quantity": "11"}], payments=[{"method": "cash", "amount": "1298.00"}], allow_negative_stock=True)
        response = self.post(self.client_for("manager"), body)
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(self.on_hand(self.rice), Decimal("-1.000"))
        movement = StockMovement.objects.for_tenant(self.tenant.id).get(reason="sale")
        self.assertIn("override", movement.note)

    def test_override_creates_a_balance_for_a_product_never_stocked(self):
        fresh = Product.objects.create(tenant=self.tenant, sku="NEW-1", name="New", gst_rate=Decimal("0.00"), selling_price=Decimal("10.00"))
        body = self.payload(lines=[{"product_id": str(fresh.id), "quantity": "1"}], payments=[{"method": "cash", "amount": "10.00"}], allow_negative_stock=True)
        self.assertEqual(self.post(self.client_for("owner"), body).status_code, 201)
        self.assertEqual(self.on_hand(fresh), Decimal("-1.000"))

    def test_branch_without_state_code_cannot_issue_invoices(self):
        Branch.objects.for_tenant(self.tenant.id).filter(pk=self.branch.pk).update(state_code="")
        response = self.post(self.client_for("cashier"))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.sale_count(), 0)

    def test_branch_code_too_long_for_gst_invoice_number_is_rejected(self):
        Branch.objects.for_tenant(self.tenant.id).filter(pk=self.branch.pk).update(code="TOOLONG")
        response = self.post(self.client_for("cashier"))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.sale_count(), 0)
        self.assertEqual(self.on_hand(self.rice), Decimal("10.000"))

    def test_payments_must_total_the_invoice(self):
        client = self.client_for("cashier")
        for amount in ("235.00", "237.00"):
            response = self.post(client, self.payload(payments=[{"method": "cash", "amount": amount}]), key=f"pay-{amount}")
            self.assertEqual(response.status_code, 400, amount)
        self.assertEqual(self.sale_count(), 0)
        self.assertEqual(self.on_hand(self.rice), Decimal("10.000"))

    def test_invalid_requests_are_rejected(self):
        client = self.client_for("cashier")
        dup = self.payload(lines=[{"product_id": str(self.rice.id), "quantity": "1"}, {"product_id": str(self.rice.id), "quantity": "1"}])
        self.assertEqual(self.post(client, dup, key="k1").status_code, 400)
        self.assertEqual(self.post(client, self.payload(lines=[]), key="k2").status_code, 400)
        self.assertEqual(self.post(client, self.payload(payments=[]), key="k3").status_code, 400)
        zero = self.payload(lines=[{"product_id": str(self.rice.id), "quantity": "0"}])
        self.assertEqual(self.post(client, zero, key="k4").status_code, 400)
        self.assertEqual(self.sale_count(), 0)

    def test_foreign_product_inactive_product_and_ungranted_branch_are_rejected(self):
        other_branch = Branch.objects.create(tenant=self.other_tenant, name="Main", code="MAIN", state_code="27")
        foreign = Product.objects.create(tenant=self.other_tenant, sku="X", name="X", selling_price=Decimal("1.00"))
        client = self.client_for("cashier")
        self.assertEqual(self.post(client, self.payload(lines=[{"product_id": str(foreign.id), "quantity": "1"}]), key="a").status_code, 400)
        self.assertEqual(self.post(client, self.payload(branch_id=str(other_branch.id)), key="b").status_code, 400)
        Product.objects.for_tenant(self.tenant.id).filter(pk=self.rice.pk).update(is_active=False)
        self.assertEqual(self.post(client, key="c").status_code, 400)
        ungranted = self.client_for("manager", grant=False)
        self.assertEqual(self.post(ungranted, key="d").status_code, 400)
        self.assertEqual(self.sale_count(), 0)

    def test_posted_sale_keeps_product_snapshot_after_catalogue_edit(self):
        client = self.client_for("cashier")
        sale_id = self.post(client).json()["id"]
        Product.objects.for_tenant(self.tenant.id).filter(pk=self.rice.pk).update(name="Renamed", selling_price=Decimal("999.00"))
        replay = self.post(client).json()
        self.assertEqual(replay["id"], sale_id)
        self.assertEqual((replay["lines"][0]["name"], replay["lines"][0]["unit_price"]), ("Rice", "100.00"))
