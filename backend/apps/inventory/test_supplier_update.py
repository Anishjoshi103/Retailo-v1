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

GSTIN_A = "27AAPFU0939F1ZV"
GSTIN_B = "29AAGCB7383J1Z4"


@override_settings(
    SIMPLE_JWT={"ACCESS_TOKEN_LIFETIME": timedelta(minutes=5), "REFRESH_TOKEN_LIFETIME": timedelta(days=1), "ROTATE_REFRESH_TOKENS": False, "BLACKLIST_AFTER_ROTATION": True, "ALGORITHM": "HS256", "SIGNING_KEY": "supplier-update-test-key-only", "AUTH_HEADER_TYPES": ("Bearer",), "USER_ID_FIELD": "id", "USER_ID_CLAIM": "user_id"},
    REST_FRAMEWORK={"DEFAULT_AUTHENTICATION_CLASSES": ("rest_framework_simplejwt.authentication.JWTAuthentication",), "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema", "EXCEPTION_HANDLER": "config.api_errors.api_exception_handler"},
    IS_TEST_ENV=True,
)
class SupplierUpdateTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Store A", slug="store-a")
        self.other_tenant = Tenant.objects.create(name="Store B", slug="store-b")
        self.branch = Branch.objects.create(tenant=self.tenant, name="Main", code="MAIN", state_code="27")
        self.agro = Supplier.objects.create(tenant=self.tenant, name="Agro Foods", gstin=GSTIN_A, phone="111")
        self.other = Supplier.objects.create(tenant=self.tenant, name="Other Co", gstin=GSTIN_B)
        self.foreign = Supplier.objects.create(tenant=self.other_tenant, name="Foreign Ltd")
        self.rice = Product.objects.create(tenant=self.tenant, sku="RICE-1", name="Rice", gst_rate=Decimal("5.00"), selling_price=Decimal("50.00"))
        self.manager = self.client_for("manager")

    def client_for(self, role):
        email = f"{role}-{uuid.uuid4().hex[:6]}@example.test"
        user = get_user_model().objects.create_user(username=email, email=email, password="Test-password-123")
        member = Membership.objects.create(tenant=self.tenant, user=user, role=role)
        BranchAccess.objects.create(membership=member, branch=self.branch)
        refresh = RefreshToken.for_user(user)
        refresh["tenant_id"] = str(self.tenant.id)
        refresh["membership_id"] = str(member.id)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
        return client

    def url(self, supplier=None):
        return f"/api/v1/inventory/suppliers/{(supplier or self.agro).id}"

    def test_managers_admins_and_owners_can_edit_a_supplier(self):
        for role in ("manager", "admin", "owner"):
            response = self.client_for(role).patch(self.url(), {"phone": f"9{role}"[:32], "address": f"Edited by {role}"}, format="json")
            self.assertEqual(response.status_code, 200, role)
            self.assertEqual(response.json()["address"], f"Edited by {role}")
        self.agro.refresh_from_db()
        self.assertEqual(self.agro.name, "Agro Foods")

    def test_cashiers_and_accountants_can_read_but_not_edit(self):
        for role in ("cashier", "accountant"):
            client = self.client_for(role)
            self.assertEqual(client.get(self.url()).status_code, 200, role)
            self.assertEqual(client.patch(self.url(), {"name": "Hacked"}, format="json").status_code, 403, role)
        self.agro.refresh_from_db()
        self.assertEqual(self.agro.name, "Agro Foods")

    def test_other_stores_and_unknown_suppliers_are_not_found(self):
        self.assertEqual(self.manager.get(self.url(self.foreign)).status_code, 404)
        self.assertEqual(self.manager.patch(self.url(self.foreign), {"name": "x"}, format="json").status_code, 404)
        self.assertEqual(self.manager.get(f"/api/v1/inventory/suppliers/{uuid.uuid4()}").status_code, 404)
        self.foreign.refresh_from_db()
        self.assertEqual(self.foreign.name, "Foreign Ltd")

    def test_unauthenticated_requests_are_rejected(self):
        self.assertEqual(APIClient().get(self.url()).status_code, 401)
        self.assertEqual(APIClient().patch(self.url(), {}, format="json").status_code, 401)

    def test_a_supplier_can_be_saved_again_with_its_own_gstin(self):
        # The uniqueness check must not treat the supplier being edited as a duplicate of itself.
        response = self.manager.patch(self.url(), {"gstin": GSTIN_A.lower(), "name": "Agro Foods Ltd"}, format="json")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual((response.json()["gstin"], response.json()["name"]), (GSTIN_A, "Agro Foods Ltd"))

    def test_a_gstin_used_by_another_supplier_is_refused(self):
        response = self.manager.patch(self.url(), {"gstin": GSTIN_B}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("already exists", str(response.json()))
        self.agro.refresh_from_db()
        self.assertEqual(self.agro.gstin, GSTIN_A)

    def test_gstin_format_and_blank_name_are_validated_and_a_gstin_can_be_cleared(self):
        self.assertEqual(self.manager.patch(self.url(), {"gstin": "NOT-A-GSTIN"}, format="json").status_code, 400)
        self.assertEqual(self.manager.patch(self.url(), {"name": "   "}, format="json").status_code, 400)
        cleared = self.manager.patch(self.url(), {"gstin": ""}, format="json")
        self.assertEqual((cleared.status_code, cleared.json()["gstin"]), (200, ""))
        self.assertEqual(self.manager.patch(self.url(self.other), {"gstin": GSTIN_A}, format="json").status_code, 200)

    def test_the_same_gstin_is_allowed_in_another_store(self):
        Supplier.objects.create(tenant=self.other_tenant, name="Twin", gstin="07AAACN1234A1Z5")
        response = self.manager.patch(self.url(), {"gstin": "07AAACN1234A1Z5"}, format="json")
        self.assertEqual(response.status_code, 200, response.content)

    def test_only_patch_is_allowed_for_changes(self):
        self.assertEqual(self.manager.put(self.url(), {"name": "x"}, format="json").status_code, 405)
        self.assertEqual(self.manager.delete(self.url()).status_code, 405)

    def test_deactivating_hides_a_supplier_from_new_deliveries_and_reactivating_restores_it(self):
        def receive(key):
            return self.manager.post("/api/v1/inventory/receipts", {
                "branch_id": str(self.branch.id), "supplier_id": str(self.agro.id),
                "lines": [{"product_id": str(self.rice.id), "quantity": "1", "unit_cost": "10.00"}],
            }, format="json", HTTP_IDEMPOTENCY_KEY=key)

        self.assertEqual(receive("r1").status_code, 201)
        self.assertEqual(self.manager.patch(self.url(), {"is_active": False}, format="json").json()["is_active"], False)
        self.assertEqual(receive("r2").status_code, 400)
        active_names = [row["name"] for row in self.manager.get("/api/v1/inventory/suppliers?active=true").json()]
        self.assertNotIn("Agro Foods", active_names)
        self.assertIn("Agro Foods", [row["name"] for row in self.manager.get("/api/v1/inventory/suppliers").json()])
        self.manager.patch(self.url(), {"is_active": True}, format="json")
        self.assertEqual(receive("r3").status_code, 201)

    def test_renaming_a_supplier_does_not_rewrite_past_receipts(self):
        created = self.manager.post("/api/v1/inventory/receipts", {
            "branch_id": str(self.branch.id), "supplier_id": str(self.agro.id),
            "lines": [{"product_id": str(self.rice.id), "quantity": "1", "unit_cost": "10.00"}],
        }, format="json", HTTP_IDEMPOTENCY_KEY="r1").json()
        self.manager.patch(self.url(), {"name": "Renamed Co"}, format="json")
        from apps.inventory.models import PurchaseReceipt

        receipt = PurchaseReceipt.objects.for_tenant(self.tenant.id).get(pk=created["id"])
        self.assertEqual(receipt.supplier_name, "Agro Foods")
