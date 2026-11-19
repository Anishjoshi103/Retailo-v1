import csv
import io
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

REGISTER = "/api/v1/reports/gst-register"
CSV = "/api/v1/reports/gst-register.csv"


@override_settings(
    SIMPLE_JWT={"ACCESS_TOKEN_LIFETIME": timedelta(minutes=5), "REFRESH_TOKEN_LIFETIME": timedelta(days=1), "ROTATE_REFRESH_TOKENS": False, "BLACKLIST_AFTER_ROTATION": True, "ALGORITHM": "HS256", "SIGNING_KEY": "gst-register-test-key-only", "AUTH_HEADER_TYPES": ("Bearer",), "USER_ID_FIELD": "id", "USER_ID_CLAIM": "user_id"},
    REST_FRAMEWORK={"DEFAULT_AUTHENTICATION_CLASSES": ("rest_framework_simplejwt.authentication.JWTAuthentication",), "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema", "EXCEPTION_HANDLER": "config.api_errors.api_exception_handler"},
    IS_TEST_ENV=True,
)
class GstRegisterTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Store A", slug="store-a")
        self.other_tenant = Tenant.objects.create(name="Store B", slug="store-b")
        self.main = Branch.objects.create(tenant=self.tenant, name="Main", code="MAIN", state_code="27")
        self.north = Branch.objects.create(tenant=self.tenant, name="North", code="NORTH", state_code="27")
        self.rice = Product.objects.create(tenant=self.tenant, sku="RICE-1", name="Rice", hsn_code="1006", unit=Product.Unit.KG, gst_rate=Decimal("18.00"), selling_price=Decimal("100.00"))
        self.soap = Product.objects.create(tenant=self.tenant, sku="SOAP-1", name="Soap", hsn_code="3401", unit=Product.Unit.EACH, gst_rate=Decimal("5.00"), selling_price=Decimal("33.33"))
        self.misc = Product.objects.create(tenant=self.tenant, sku="MISC-1", name="=Mystery item", hsn_code="", unit=Product.Unit.EACH, gst_rate=Decimal("0.00"), selling_price=Decimal("10.00"))
        for branch in (self.main, self.north):
            for product in (self.rice, self.soap, self.misc):
                InventoryBalance.objects.create(tenant=self.tenant, branch=branch, product=product, quantity_on_hand=Decimal("100.000"))
        self.owner = self.client_for("owner", [self.main, self.north])
        self.build_scenario()

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

    def sell(self, branch, key, lines, total):
        body = {"branch_id": str(branch.id), "lines": lines, "payments": [{"method": "cash", "amount": total}]}
        response = self.owner.post("/api/v1/sales", body, format="json", HTTP_IDEMPOTENCY_KEY=key)
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()

    def build_scenario(self):
        # Sale A: rice x2 (200.00) + soap x3 (99.99) -> 300.00.  Sale B: rice x1 (100.00).  Sale C (north): misc x2 (20.00).
        sale_a = self.sell(self.main, "a", [{"product_id": str(self.rice.id), "quantity": "2"}, {"product_id": str(self.soap.id), "quantity": "3"}], "300.00")
        self.sell(self.main, "b", [{"product_id": str(self.rice.id), "quantity": "1"}], "100.00")
        self.sell(self.north, "c", [{"product_id": str(self.misc.id), "quantity": "2"}], "20.00")
        rice_line = next(line for line in sale_a["lines"] if line["sku"] == "RICE-1")
        response = self.owner.post(f"/api/v1/sales/{sale_a['id']}/returns", {"reason": "Damaged", "lines": [{"sale_line_id": rice_line["id"], "quantity": "1"}]}, format="json", HTTP_IDEMPOTENCY_KEY="ret")
        self.assertEqual(response.status_code, 201, response.content)

    def test_rates_table_is_net_of_returns_by_place_of_supply_and_rate(self):
        body = self.owner.get(REGISTER).json()
        by_rate = {row["gst_rate"]: row for row in body["rates"]}
        self.assertEqual([row["gst_rate"] for row in body["rates"]], ["0.00", "5.00", "18.00"])
        self.assertEqual({row["place_of_supply"] for row in body["rates"]}, {"27"})
        zero, five, eighteen = by_rate["0.00"], by_rate["5.00"], by_rate["18.00"]
        self.assertEqual((zero["taxable_value"], zero["cgst"], zero["sgst"], zero["igst"], zero["cess"]), ("20.00", "0.00", "0.00", "0.00", "0.00"))
        self.assertEqual((five["taxable_value"], five["cgst"], five["sgst"]), ("95.23", "2.38", "2.38"))
        # Sales 169.50 + 84.74 = 254.24 taxable, less the returned 84.75 -> 169.49; tax likewise.
        self.assertEqual((eighteen["sales_taxable_value"], eighteen["returns_taxable_value"], eighteen["taxable_value"]), ("254.24", "84.75", "169.49"))
        self.assertEqual((eighteen["cgst"], eighteen["sgst"]), ("15.25", "15.25"))
        self.assertEqual(body["totals"], {"taxable_value": "284.72", "cgst": "17.63", "sgst": "17.63", "igst": "0.00", "total_tax": "35.26"})

    def test_hsn_table_nets_quantities_and_values_and_uses_official_unit_codes(self):
        rows = {(row["hsn_code"], row["gst_rate"]): row for row in self.owner.get(REGISTER).json()["hsn"]}
        rice = rows[("1006", "18.00")]
        self.assertEqual((rice["description"], rice["uqc"], rice["quantity"]), ("Rice", "KGS", "2.000"))  # 3 sold, 1 returned
        self.assertEqual((rice["taxable_value"], rice["cgst"], rice["sgst"], rice["total_value"]), ("169.49", "15.25", "15.25", "199.99"))
        soap = rows[("3401", "5.00")]
        self.assertEqual((soap["uqc"], soap["quantity"], soap["total_value"]), ("NOS", "3.000", "99.99"))
        self.assertEqual(len(rows), 3)

    def test_lines_without_an_hsn_code_are_counted_so_they_can_be_fixed(self):
        body = self.owner.get(REGISTER).json()
        self.assertEqual(body["missing_hsn_lines"], 1)
        self.assertIn(("", "0.00"), {(row["hsn_code"], row["gst_rate"]) for row in body["hsn"]})

    def test_documents_table_gives_number_ranges_per_branch(self):
        documents = self.owner.get(REGISTER).json()["documents"]
        by_key = {(row["document_type"], row["series"]): row for row in documents}
        self.assertEqual(by_key[("Invoices for outward supply", "MAIN")]["from"], "INV-MAIN-000001")
        self.assertEqual(by_key[("Invoices for outward supply", "MAIN")]["to"], "INV-MAIN-000002")
        self.assertEqual(by_key[("Invoices for outward supply", "MAIN")]["total"], 2)
        self.assertEqual((by_key[("Invoices for outward supply", "NORTH")]["from"], by_key[("Invoices for outward supply", "NORTH")]["total"]), ("INV-NORTH-000001", 1))
        credit = by_key[("Credit notes", "MAIN")]
        self.assertEqual((credit["from"], credit["to"], credit["total"], credit["cancelled"]), ("CN-MAIN-000001", "CN-MAIN-000001", 1, 0))
        self.assertEqual(len(documents), 3)

    def test_the_register_agrees_with_the_sales_summary(self):
        register = self.owner.get(REGISTER).json()
        summary = self.owner.get("/api/v1/reports/sales-summary").json()
        self.assertEqual(register["totals"]["taxable_value"], summary["net"]["taxable_total"])
        self.assertEqual(register["totals"]["total_tax"], summary["net"]["total_tax"])

    def test_branch_filter_and_scoping(self):
        north_only = self.owner.get(f"{REGISTER}?branch_id={self.north.id}").json()
        self.assertEqual([row["gst_rate"] for row in north_only["rates"]], ["0.00"])
        self.assertEqual({row["series"] for row in north_only["documents"]}, {"NORTH"})
        manager = self.client_for("manager", [self.main])
        scoped = manager.get(REGISTER).json()
        self.assertEqual({row["gst_rate"] for row in scoped["rates"]}, {"5.00", "18.00"})
        self.assertEqual(manager.get(f"{REGISTER}?branch_id={self.north.id}").status_code, 403)

    def test_date_ranges_and_empty_periods(self):
        empty = self.owner.get(f"{REGISTER}?date_from=2000-01-01&date_to=2000-01-31").json()
        self.assertEqual((empty["rates"], empty["hsn"], empty["documents"], empty["missing_hsn_lines"]), ([], [], [], 0))
        self.assertEqual(empty["totals"]["total_tax"], "0.00")
        for bad in ("date_from=yesterday", "date_from=2026-02-01&date_to=2026-01-01", "branch_id=nope"):
            self.assertEqual(self.owner.get(f"{REGISTER}?{bad}").status_code, 400, bad)

    def test_only_roles_that_may_see_financial_data_can_read_it(self):
        for role, expected in (("owner", 200), ("admin", 200), ("manager", 200), ("accountant", 200), ("cashier", 403)):
            client = self.client_for(role, [self.main])
            self.assertEqual(client.get(REGISTER).status_code, expected, role)
            self.assertEqual(client.get(f"{CSV}?table=rates").status_code, expected, role)
        self.assertEqual(APIClient().get(REGISTER).status_code, 401)
        self.assertEqual(APIClient().get(f"{CSV}?table=rates").status_code, 401)

    def test_other_stores_data_is_never_included(self):
        foreign_branch = Branch.objects.create(tenant=self.other_tenant, name="B", code="B", state_code="29")
        foreign_owner = self.client_for("owner", [foreign_branch], tenant=self.other_tenant)
        body = foreign_owner.get(REGISTER).json()
        self.assertEqual((body["rates"], body["hsn"], body["documents"]), ([], [], []))

    def rows(self, table, query=""):
        response = self.owner.get(f"{CSV}?table={table}{query}")
        self.assertEqual(response.status_code, 200, response.content)
        return response, list(csv.reader(io.StringIO(response.content.decode())))

    def test_csv_downloads_match_the_json_tables(self):
        response, rows = self.rows("rates")
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn("attachment; filename=\"gst-rates-", response["Content-Disposition"])
        self.assertEqual(rows[0], ["Place of supply (state code)", "Tax rate %", "Taxable value", "IGST", "CGST", "SGST/UTGST", "Cess"])
        self.assertEqual(rows[1:], [["27", "0.00", "20.00", "0.00", "0.00", "0.00", "0.00"], ["27", "5.00", "95.23", "0.00", "2.38", "2.38", "0.00"], ["27", "18.00", "169.49", "0.00", "15.25", "15.25", "0.00"]])
        _, hsn = self.rows("hsn")
        self.assertEqual(hsn[0][:4], ["HSN", "Description", "UQC", "Total quantity"])
        self.assertEqual(len(hsn), 4)
        _, documents = self.rows("documents")
        self.assertEqual(documents[0], ["Document type", "Series (branch)", "From", "To", "Total number", "Cancelled"])
        self.assertIn(["Credit notes", "MAIN", "CN-MAIN-000001", "CN-MAIN-000001", "1", "0"], documents)

    def test_csv_text_cannot_be_read_as_a_spreadsheet_formula(self):
        _, hsn = self.rows("hsn")
        descriptions = [row[1] for row in hsn[1:]]
        self.assertIn("'=Mystery item", descriptions)
        self.assertNotIn("=Mystery item", descriptions)

    def test_csv_needs_a_valid_table_and_respects_the_filters(self):
        self.assertEqual(self.owner.get(CSV).status_code, 400)
        self.assertEqual(self.owner.get(f"{CSV}?table=everything").status_code, 400)
        _, rows = self.rows("rates", f"&branch_id={self.north.id}")
        self.assertEqual(len(rows), 2)
        response = self.owner.get(f"{CSV}?table=rates&date_from=2000-01-01&date_to=2000-01-31")
        self.assertEqual(len(list(csv.reader(io.StringIO(response.content.decode())))), 1)
        self.assertIn("2000-01-01-to-2000-01-31", response["Content-Disposition"])
