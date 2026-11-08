from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.tenancy.models import Branch, BranchAccess, Membership, Tenant

VALID_GSTIN = "27AAPFU0939F1ZV"  # Maharashtra (27)


@override_settings(
    SIMPLE_JWT={"ACCESS_TOKEN_LIFETIME": timedelta(minutes=5), "REFRESH_TOKEN_LIFETIME": timedelta(days=1), "ROTATE_REFRESH_TOKENS": False, "BLACKLIST_AFTER_ROTATION": True, "ALGORITHM": "HS256", "SIGNING_KEY": "branch-gst-test-key-only", "AUTH_HEADER_TYPES": ("Bearer",), "USER_ID_FIELD": "id", "USER_ID_CLAIM": "user_id"},
    REST_FRAMEWORK={"DEFAULT_AUTHENTICATION_CLASSES": ("rest_framework_simplejwt.authentication.JWTAuthentication",), "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema", "EXCEPTION_HANDLER": "config.api_errors.api_exception_handler"},
    IS_TEST_ENV=True,
)
class BranchGstIdentityTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Store A", slug="store-a")
        self.other_tenant = Tenant.objects.create(name="Store B", slug="store-b")
        self.branch = Branch.objects.create(tenant=self.tenant, name="Main", code="MAIN")
        self.other_branch = Branch.objects.create(tenant=self.other_tenant, name="Main", code="MAIN")

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

    def url(self, branch=None):
        return f"/api/v1/branches/{(branch or self.branch).id}"

    def test_owner_and_admin_can_set_gstin_and_state_is_derived(self):
        for role in (Membership.Role.OWNER, Membership.Role.ADMIN):
            client = self.client_for(role)
            response = client.patch(self.url(), {"gstin": VALID_GSTIN.lower()}, format="json")
            self.assertEqual(response.status_code, 200, response.content)
            self.assertEqual(response.json()["gstin"], VALID_GSTIN)
            self.assertEqual(response.json()["state_code"], "27")
            self.branch.refresh_from_db()
            self.assertEqual((self.branch.gstin, self.branch.state_code), (VALID_GSTIN, "27"))

    def test_state_code_alone_can_be_set_for_unregistered_branch(self):
        response = self.client_for(Membership.Role.OWNER).patch(self.url(), {"state_code": "29"}, format="json")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual((response.json()["gstin"], response.json()["state_code"]), ("", "29"))

    def test_other_roles_are_denied_and_nothing_changes(self):
        for role in (Membership.Role.MANAGER, Membership.Role.CASHIER, Membership.Role.ACCOUNTANT):
            response = self.client_for(role).patch(self.url(), {"state_code": "27"}, format="json")
            self.assertEqual(response.status_code, 403, role)
        self.branch.refresh_from_db()
        self.assertEqual(self.branch.state_code, "")

    def test_gstin_must_match_state_code_and_format(self):
        client = self.client_for(Membership.Role.OWNER)
        mismatch = client.patch(self.url(), {"gstin": VALID_GSTIN, "state_code": "29"}, format="json")
        self.assertEqual(mismatch.status_code, 400)
        bad_format = client.patch(self.url(), {"gstin": "NOT-A-GSTIN"}, format="json")
        self.assertEqual(bad_format.status_code, 400)
        bad_state = client.patch(self.url(), {"state_code": "00"}, format="json")
        self.assertEqual(bad_state.status_code, 400)
        empty = client.patch(self.url(), {}, format="json")
        self.assertEqual(empty.status_code, 400)
        self.branch.refresh_from_db()
        self.assertEqual((self.branch.gstin, self.branch.state_code), ("", ""))

    def test_foreign_tenant_and_ungranted_branches_are_not_found(self):
        client = self.client_for(Membership.Role.OWNER)
        self.assertEqual(client.patch(self.url(self.other_branch), {"state_code": "27"}, format="json").status_code, 404)
        ungranted = self.client_for(Membership.Role.ADMIN, grant=False)
        self.assertEqual(ungranted.patch(self.url(), {"state_code": "27"}, format="json").status_code, 404)
        self.other_branch.refresh_from_db()
        self.assertEqual(self.other_branch.state_code, "")

    def test_branch_list_exposes_gst_identity(self):
        client = self.client_for(Membership.Role.CASHIER)
        Branch.objects.for_tenant(self.tenant.id).filter(pk=self.branch.pk).update(gstin=VALID_GSTIN, state_code="27")
        item = client.get("/api/v1/branches").json()[0]
        self.assertEqual((item["gstin"], item["state_code"]), (VALID_GSTIN, "27"))
