import uuid
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.catalog.models import Product
from apps.inventory.models import InventoryBalance
from apps.sales.models import Sale
from apps.tenancy.models import Branch, BranchAccess, Membership, Tenant

REPORT = "/api/v1/reports/sales-summary"


@override_settings(
    SIMPLE_JWT={"ACCESS_TOKEN_LIFETIME": timedelta(minutes=5), "REFRESH_TOKEN_LIFETIME": timedelta(days=1), "ROTATE_REFRESH_TOKENS": False, "BLACKLIST_AFTER_ROTATION": True, "ALGORITHM": "HS256", "SIGNING_KEY": "sales-report-test-key-only", "AUTH_HEADER_TYPES": ("Bearer",), "USER_ID_FIELD": "id", "USER_ID_CLAIM": "user_id"},
    REST_FRAMEWORK={"DEFAULT_AUTHENTICATION_CLASSES": ("rest_framework_simplejwt.authentication.JWTAuthentication",), "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema", "EXCEPTION_HANDLER": "config.api_errors.api_exception_handler"},
    IS_TEST_ENV=True,
)
class SalesSummaryReportTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Store A", slug="store-a")
        self.other_tenant = Tenant.objects.create(name="Store B", slug="store-b")
        self.main = Branch.objects.create(tenant=self.tenant, name="Main", code="MAIN", state_code="27")
        self.north = Branch.objects.create(tenant=self.tenant, name="North", code="NORTH", state_code="27")
        self.rice = Product.objects.create(tenant=self.tenant, sku="RICE-1", name="Rice", gst_rate=Decimal("18.00"), selling_price=Decimal("100.00"))
        self.soap = Product.objects.create(tenant=self.tenant, sku="SOAP-1", name="Soap", gst_rate=Decimal("5.00"), selling_price=Decimal("33.33"))
        for branch in (self.main, self.north):
            for product in (self.rice, self.soap):
                InventoryBalance.objects.create(tenant=self.tenant, branch=branch, product=product, quantity_on_hand=Decimal("100.000"))
        self.owner = self.client_for("owner", [self.main, self.north])
        self.today = timezone.localdate()

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

    def sell(self, branch, key, lines, payments):
        response = self.owner.post("/api/v1/sales", {"branch_id": str(branch.id), "lines": lines, "payments": payments}, format="json", HTTP_IDEMPOTENCY_KEY=key)
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()

    def rice_sale(self, branch, key, quantity="2", method="cash"):
        amount = f"{int(quantity) * 100}.00"
        return self.sell(branch, key, [{"product_id": str(self.rice.id), "quantity": quantity}], [{"method": method, "amount": amount}])

    def old_sale(self, branch, number, invoice_date, grand_total="100.00"):
        return Sale.objects.create(
            tenant=self.tenant, branch=branch, invoice_number=number, invoice_date=invoice_date,
            seller_state_code="27", place_of_supply_state_code="27", taxable_total=Decimal(grand_total),
            cgst_total=Decimal("0.00"), sgst_total=Decimal("0.00"), igst_total=Decimal("0.00"), total_tax=Decimal("0.00"),
            round_off=Decimal("0.00"), grand_total=Decimal(grand_total), idempotency_key=f"old-{number}",
            request_hash="h" * 64, created_by=get_user_model().objects.first(),
        )

    def test_summarises_sales_returns_tax_and_tenders_for_today_by_default(self):
        self.rice_sale(self.main, "s1", method="cash")  # 200.00: taxable 169.50, CGST 15.25, SGST 15.25
        soap = self.sell(self.main, "s2", [{"product_id": str(self.soap.id), "quantity": "3"}], [{"method": "upi", "amount": "100.00"}])  # 99.99 -> 100.00
        self.assertEqual(soap["grand_total"], "100.00")
        rice = self.owner.get("/api/v1/sales").json()
        first = next(s for s in rice if s["grand_total"] == "200.00")
        detail = self.owner.get(f"/api/v1/sales/{first['id']}").json()
        self.owner.post(f"/api/v1/sales/{first['id']}/returns", {"reason": "Damaged", "lines": [{"sale_line_id": detail["lines"][0]["id"], "quantity": "1"}]}, format="json", HTTP_IDEMPOTENCY_KEY="r1")

        body = self.owner.get(REPORT).json()
        self.assertEqual((body["date_from"], body["date_to"], body["branch_id"], body["branch_count"]), (self.today.isoformat(), self.today.isoformat(), None, 2))
        self.assertEqual(body["sales"], {"count": 2, "taxable_total": "264.73", "cgst_total": "17.63", "sgst_total": "17.63", "igst_total": "0.00", "total_tax": "35.26", "round_off": "0.01", "grand_total": "300.00"})
        self.assertEqual((body["returns"]["count"], body["returns"]["taxable_total"], body["returns"]["total_tax"], body["returns"]["grand_total"]), (1, "84.75", "15.26", "100.00"))
        self.assertEqual(body["net"], {"taxable_total": "179.98", "total_tax": "20.00", "grand_total": "200.00"})
        self.assertEqual(body["payments"], [{"method": "cash", "amount": "200.00", "count": 1}, {"method": "upi", "amount": "100.00", "count": 1}])
        self.assertEqual(body["by_day"], [{"date": self.today.isoformat(), "sales_count": 2, "sales_total": "300.00", "returns_count": 1, "returns_total": "100.00", "net_total": "200.00"}])

    def test_an_empty_range_reports_zeros(self):
        body = self.owner.get(REPORT).json()
        self.assertEqual(body["sales"], {"count": 0, "taxable_total": "0.00", "cgst_total": "0.00", "sgst_total": "0.00", "igst_total": "0.00", "total_tax": "0.00", "round_off": "0.00", "grand_total": "0.00"})
        self.assertEqual((body["returns"]["count"], body["net"]["grand_total"], body["payments"], body["by_day"]), (0, "0.00", [], []))

    def test_ranges_and_per_day_figures(self):
        self.old_sale(self.main, "INV-MAIN-900001", date(2026, 1, 15), "100.00")
        self.old_sale(self.main, "INV-MAIN-900002", date(2026, 1, 15), "50.00")
        self.old_sale(self.main, "INV-MAIN-900003", date(2026, 1, 17), "25.00")
        self.rice_sale(self.main, "s1")
        january = self.owner.get(f"{REPORT}?date_from=2026-01-01&date_to=2026-01-31").json()
        self.assertEqual((january["sales"]["count"], january["sales"]["grand_total"]), (3, "175.00"))
        self.assertEqual([(d["date"], d["sales_count"], d["sales_total"]) for d in january["by_day"]], [("2026-01-15", 2, "150.00"), ("2026-01-17", 1, "25.00")])
        one_day = self.owner.get(f"{REPORT}?date_from=2026-01-15").json()
        self.assertEqual((one_day["date_to"], one_day["sales"]["grand_total"]), ("2026-01-15", "150.00"))
        today_only = self.owner.get(REPORT).json()
        self.assertEqual(today_only["sales"]["grand_total"], "200.00")

    def test_a_branch_filter_and_branch_scoping(self):
        self.rice_sale(self.main, "s1")
        self.rice_sale(self.north, "s2", quantity="3")
        self.assertEqual(self.owner.get(REPORT).json()["sales"]["grand_total"], "500.00")
        self.assertEqual(self.owner.get(f"{REPORT}?branch_id={self.north.id}").json()["sales"]["grand_total"], "300.00")
        manager = self.client_for("manager", [self.main])
        body = manager.get(REPORT).json()
        self.assertEqual((body["sales"]["grand_total"], body["branch_count"]), ("200.00", 1))
        self.assertEqual(manager.get(f"{REPORT}?branch_id={self.north.id}").status_code, 403)

    def test_only_roles_that_may_see_financial_figures_can_read_it(self):
        for role, expected in (("owner", 200), ("admin", 200), ("manager", 200), ("accountant", 200), ("cashier", 403)):
            self.assertEqual(self.client_for(role, [self.main]).get(REPORT).status_code, expected, role)
        self.assertEqual(APIClient().get(REPORT).status_code, 401)

    def test_other_stores_figures_are_never_included(self):
        foreign_branch = Branch.objects.create(tenant=self.other_tenant, name="B", code="B", state_code="27")
        Sale.objects.create(
            tenant=self.other_tenant, branch=foreign_branch, invoice_number="INV-B-000001", invoice_date=self.today,
            seller_state_code="27", place_of_supply_state_code="27", taxable_total=Decimal("999.00"), cgst_total=Decimal("0.00"),
            sgst_total=Decimal("0.00"), igst_total=Decimal("0.00"), total_tax=Decimal("0.00"), round_off=Decimal("0.00"),
            grand_total=Decimal("999.00"), idempotency_key="x", request_hash="h" * 64, created_by=get_user_model().objects.first(),
        )
        self.rice_sale(self.main, "s1")
        self.assertEqual(self.owner.get(REPORT).json()["sales"]["grand_total"], "200.00")

    def test_invalid_parameters_are_rejected(self):
        for query in ("date_from=yesterday", "date_to=2026-13-40", "date_from=2026-02-01&date_to=2026-01-01", "date_from=2024-01-01&date_to=2026-01-01", "branch_id=nope"):
            self.assertEqual(self.owner.get(f"{REPORT}?{query}").status_code, 400, query)
        # The limit counts both end dates: 366 days is allowed, 367 is not.
        self.assertEqual(self.owner.get(f"{REPORT}?date_from=2024-01-01&date_to=2024-12-31").status_code, 200)
        self.assertEqual(self.owner.get(f"{REPORT}?date_from=2025-01-01&date_to=2026-01-01").status_code, 200)
        self.assertEqual(self.owner.get(f"{REPORT}?date_from=2025-01-01&date_to=2026-01-02").status_code, 400)
