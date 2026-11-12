import uuid
from datetime import timedelta
from unittest import mock
from urllib.parse import parse_qs, urlparse

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.tenancy.models import Branch, BranchAccess, Membership, Tenant

PASSWORD = "Correct-horse-battery-1"


@override_settings(
    SIMPLE_JWT={"ACCESS_TOKEN_LIFETIME": timedelta(minutes=5), "REFRESH_TOKEN_LIFETIME": timedelta(days=1), "ROTATE_REFRESH_TOKENS": False, "BLACKLIST_AFTER_ROTATION": True, "ALGORITHM": "HS256", "SIGNING_KEY": "staff-test-key-only", "AUTH_HEADER_TYPES": ("Bearer",), "USER_ID_FIELD": "id", "USER_ID_CLAIM": "user_id"},
    REST_FRAMEWORK={"DEFAULT_AUTHENTICATION_CLASSES": ("rest_framework_simplejwt.authentication.JWTAuthentication",), "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema", "EXCEPTION_HANDLER": "config.api_errors.api_exception_handler"},
    IS_TEST_ENV=True,
)
class StaffManagementTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Store A", slug="store-a")
        self.other_tenant = Tenant.objects.create(name="Store B", slug="store-b")
        self.main = Branch.objects.create(tenant=self.tenant, name="Main", code="MAIN", state_code="27")
        self.north = Branch.objects.create(tenant=self.tenant, name="North", code="NORTH", state_code="27")
        self.other_branch = Branch.objects.create(tenant=self.other_tenant, name="Main", code="MAIN", state_code="27")
        self.owner, self.owner_member, self.owner_client = self.person("owner", [self.main, self.north])

    def person(self, role, branches, tenant=None, password=PASSWORD):
        tenant = tenant or self.tenant
        email = f"{role}-{uuid.uuid4().hex[:6]}@example.test"
        user = get_user_model().objects.create_user(username=email, email=email, password=password)
        member = Membership.objects.create(tenant=tenant, user=user, role=role)
        for branch in branches:
            BranchAccess.objects.create(membership=member, branch=branch)
        refresh = RefreshToken.for_user(user)
        refresh["tenant_id"] = str(tenant.id)
        refresh["membership_id"] = str(member.id)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
        return user, member, client

    def invite(self, client, email="newbie@example.test", role="cashier", branches=None, **extra):
        body = {"email": email, "role": role, "branch_ids": [str(b.id) for b in (branches or [self.main])], **extra}
        return client.post("/api/v1/staff", body, format="json")

    def grants(self, member):
        return set(BranchAccess.objects.filter(membership=member, is_active=True).values_list("branch_id", flat=True))

    # ---- who may manage staff
    def test_only_owners_and_admins_can_manage_staff(self):
        for role in ("manager", "cashier", "accountant"):
            _, _, client = self.person(role, [self.main])
            self.assertEqual(client.get("/api/v1/staff").status_code, 403, role)
            self.assertEqual(self.invite(client).status_code, 403, role)
        self.assertEqual(APIClient().get("/api/v1/staff").status_code, 401)
        self.assertEqual(get_user_model().objects.filter(email="newbie@example.test").count(), 0)

    def test_list_shows_this_stores_members_with_flags(self):
        _, cashier_member, _ = self.person("cashier", [self.main])
        self.person("owner", [self.other_branch], tenant=self.other_tenant)
        rows = self.owner_client.get("/api/v1/staff").json()
        self.assertEqual(len(rows), 2)
        by_id = {row["id"]: row for row in rows}
        me = by_id[str(self.owner_member.id)]
        self.assertEqual((me["is_self"], me["can_manage"], me["role"], me["invited"]), (True, False, "owner", False))
        row = by_id[str(cashier_member.id)]
        self.assertEqual((row["is_self"], row["can_manage"], row["is_active"]), (False, True, True))
        self.assertEqual(row["branch_ids"], [str(self.main.id)])
        self.assertNotIn("password", str(row))

    def test_admins_can_list_but_cannot_manage_other_admins_or_the_owner(self):
        _, _, admin_client = self.person("admin", [self.main, self.north])
        self.person("admin", [self.main])
        rows = admin_client.get("/api/v1/staff").json()
        can_manage = {row["role"]: row["can_manage"] for row in rows if not row["is_self"]}
        self.assertEqual(can_manage["owner"], False)
        self.assertEqual(can_manage["admin"], False)

    # ---- inviting
    def test_invite_creates_a_pending_member_and_emails_a_set_password_link(self):
        response = self.invite(self.owner_client, email="  New.Cashier@Example.test ", display_name="Asha", branches=[self.main, self.north])
        self.assertEqual(response.status_code, 201, response.content)
        body = response.json()
        self.assertEqual((body["email"], body["role"], body["display_name"], body["invited"], body["is_active"], body["invite_sent"]), ("new.cashier@example.test", "cashier", "Asha", True, True, True))
        self.assertEqual(set(body["branch_ids"]), {str(self.main.id), str(self.north.id)})
        user = get_user_model().objects.get(email="new.cashier@example.test")
        self.assertFalse(user.has_usable_password())
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["new.cashier@example.test"])
        self.assertIn("Store A", mail.outbox[0].subject)
        self.assertIn("Cashier", mail.outbox[0].body)

    def test_invited_person_can_set_a_password_from_the_email_and_sign_in(self):
        self.invite(self.owner_client, email="newbie@example.test")
        link = next(line for line in mail.outbox[0].body.splitlines() if line.startswith("http"))
        query = parse_qs(urlparse(link).query)
        self.assertEqual(urlparse(link).path, "/auth/password-reset/confirm")
        anonymous = APIClient()
        before = anonymous.post("/api/v1/auth/login", {"email": "newbie@example.test", "password": PASSWORD}, format="json")
        self.assertEqual(before.status_code, 401)
        confirm = anonymous.post("/api/v1/auth/password-reset/confirm", {"uid": query["uid"][0], "token": query["token"][0], "password": PASSWORD}, format="json")
        self.assertEqual(confirm.status_code, 200, confirm.content)
        login = anonymous.post("/api/v1/auth/login", {"email": "newbie@example.test", "password": PASSWORD}, format="json")
        self.assertEqual(login.status_code, 200, login.content)
        me = APIClient()
        me.credentials(HTTP_AUTHORIZATION=f"Bearer {login.json()['access']}")
        profile = me.get("/api/v1/auth/me").json()
        self.assertEqual((profile["role"], profile["tenant"]["name"]), ("cashier", "Store A"))
        self.assertEqual(profile["allowed_branch_ids"], [str(self.main.id)])

    def test_admin_can_invite_lower_roles_but_not_admins(self):
        _, _, admin_client = self.person("admin", [self.main])
        self.assertEqual(self.invite(admin_client, email="m@example.test", role="manager").status_code, 201)
        self.assertEqual(self.invite(admin_client, email="a@example.test", role="admin").status_code, 403)
        self.assertEqual(self.invite(self.owner_client, email="b@example.test", role="admin").status_code, 201)

    def test_nobody_can_create_an_owner(self):
        response = self.invite(self.owner_client, role="owner")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(get_user_model().objects.filter(email="newbie@example.test").count(), 0)

    def test_an_email_that_already_has_an_account_is_refused(self):
        existing, _, _ = self.person("cashier", [self.main])
        self.assertEqual(self.invite(self.owner_client, email=existing.email.upper()).status_code, 409)
        other_user, _, _ = self.person("owner", [self.other_branch], tenant=self.other_tenant)
        self.assertEqual(self.invite(self.owner_client, email=other_user.email).status_code, 409)
        self.assertEqual(len(mail.outbox), 0)

    def test_branch_selection_is_validated_and_limited_to_the_callers_own_branches(self):
        _, _, admin_client = self.person("admin", [self.main])
        self.assertEqual(self.invite(admin_client, branches=[self.north]).status_code, 400)
        foreign = self.owner_client.post("/api/v1/staff", {"email": "x@example.test", "role": "cashier", "branch_ids": [str(self.other_branch.id)]}, format="json")
        self.assertEqual(foreign.status_code, 400)
        none = self.owner_client.post("/api/v1/staff", {"email": "y@example.test", "role": "cashier", "branch_ids": []}, format="json")
        self.assertEqual(none.status_code, 400)
        inactive = Branch.objects.create(tenant=self.tenant, name="Old", code="OLD", is_active=False)
        BranchAccess.objects.create(membership=self.owner_member, branch=inactive)
        self.assertEqual(self.invite(self.owner_client, branches=[inactive]).status_code, 400)
        self.assertEqual(get_user_model().objects.filter(email__in=["newbie@example.test", "x@example.test", "y@example.test"]).count(), 0)

    def test_invalid_invites_are_rejected(self):
        for body in ({"role": "cashier", "branch_ids": [str(self.main.id)]}, {"email": "not-an-email", "role": "cashier", "branch_ids": [str(self.main.id)]}, {"email": "a@example.test", "branch_ids": [str(self.main.id)]}, {"email": "a@example.test", "role": "wizard", "branch_ids": [str(self.main.id)]}, {"email": "a@example.test", "role": "cashier", "branch_ids": ["nope"]}):
            self.assertEqual(self.owner_client.post("/api/v1/staff", body, format="json").status_code, 400, body)

    def test_a_failed_email_still_creates_the_member_and_can_be_resent(self):
        with mock.patch("apps.accounts.staff_views._send_account_email", side_effect=OSError("smtp down")):
            response = self.invite(self.owner_client)
        self.assertEqual(response.status_code, 201)
        self.assertFalse(response.json()["invite_sent"])
        member_id = response.json()["id"]
        resent = self.owner_client.post(f"/api/v1/staff/{member_id}/resend-invite")
        self.assertEqual((resent.status_code, resent.json()["invite_sent"]), (202, True))
        self.assertEqual(len(mail.outbox), 1)

    def test_resend_is_only_for_people_who_have_not_set_a_password(self):
        _, active_member, _ = self.person("cashier", [self.main])
        self.assertEqual(self.owner_client.post(f"/api/v1/staff/{active_member.id}/resend-invite").status_code, 409)
        _, admin_member, _ = self.person("admin", [self.main])
        _, _, admin_client = self.person("admin", [self.main])
        self.assertEqual(admin_client.post(f"/api/v1/staff/{admin_member.id}/resend-invite").status_code, 403)
        self.assertEqual(self.owner_client.post(f"/api/v1/staff/{uuid.uuid4()}/resend-invite").status_code, 404)

    # ---- updating
    def test_owner_changes_a_role_and_branches(self):
        _, member, _ = self.person("cashier", [self.main])
        response = self.owner_client.patch(f"/api/v1/staff/{member.id}", {"role": "manager", "branch_ids": [str(self.north.id)]}, format="json")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual((response.json()["role"], response.json()["branch_ids"]), ("manager", [str(self.north.id)]))
        member.refresh_from_db()
        self.assertEqual(member.role, "manager")
        self.assertEqual(self.grants(member), {self.north.id})
        back = self.owner_client.patch(f"/api/v1/staff/{member.id}", {"branch_ids": [str(self.main.id), str(self.north.id)]}, format="json")
        self.assertEqual(set(back.json()["branch_ids"]), {str(self.main.id), str(self.north.id)})

    def test_deactivating_blocks_access_immediately_and_reactivating_restores_it(self):
        _, member, member_client = self.person("cashier", [self.main])
        self.assertEqual(member_client.get("/api/v1/branches").status_code, 200)
        response = self.owner_client.patch(f"/api/v1/staff/{member.id}", {"is_active": False}, format="json")
        self.assertEqual((response.status_code, response.json()["is_active"]), (200, False))
        self.assertEqual(member_client.get("/api/v1/branches").status_code, 403)
        self.assertEqual(member_client.get("/api/v1/auth/me").status_code, 403)
        user = member.user
        login = APIClient().post("/api/v1/auth/login", {"email": user.email, "password": PASSWORD}, format="json")
        self.assertEqual(login.status_code, 403)
        self.owner_client.patch(f"/api/v1/staff/{member.id}", {"is_active": True}, format="json")
        self.assertEqual(member_client.get("/api/v1/branches").status_code, 200)

    def test_nobody_can_change_their_own_access(self):
        for body in ({"is_active": False}, {"role": "cashier"}, {"branch_ids": [str(self.main.id)]}):
            self.assertEqual(self.owner_client.patch(f"/api/v1/staff/{self.owner_member.id}", body, format="json").status_code, 403)
        self.owner_member.refresh_from_db()
        self.assertEqual((self.owner_member.role, self.owner_member.is_active), ("owner", True))

    def test_admins_cannot_change_admins_or_the_owner_or_promote_to_admin(self):
        _, _, admin_client = self.person("admin", [self.main, self.north])
        _, other_admin, _ = self.person("admin", [self.main])
        _, cashier, _ = self.person("cashier", [self.main])
        self.assertEqual(admin_client.patch(f"/api/v1/staff/{other_admin.id}", {"is_active": False}, format="json").status_code, 403)
        self.assertEqual(admin_client.patch(f"/api/v1/staff/{self.owner_member.id}", {"is_active": False}, format="json").status_code, 403)
        self.assertEqual(admin_client.patch(f"/api/v1/staff/{cashier.id}", {"role": "admin"}, format="json").status_code, 403)
        self.assertEqual(admin_client.patch(f"/api/v1/staff/{cashier.id}", {"role": "manager"}, format="json").status_code, 200)

    def test_a_member_must_keep_at_least_one_branch(self):
        _, member, _ = self.person("cashier", [self.main])
        response = self.owner_client.patch(f"/api/v1/staff/{member.id}", {"branch_ids": []}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.grants(member), {self.main.id})

    def test_branch_changes_leave_grants_the_actor_cannot_see_untouched(self):
        _, admin_member, admin_client = self.person("admin", [self.main])
        _, cashier, _ = self.person("cashier", [self.main, self.north])
        response = admin_client.patch(f"/api/v1/staff/{cashier.id}", {"branch_ids": [str(self.main.id)]}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.grants(cashier), {self.main.id, self.north.id})
        self.assertEqual(admin_client.patch(f"/api/v1/staff/{cashier.id}", {"branch_ids": [str(self.north.id)]}, format="json").status_code, 400)
        _, narrow, _ = self.person("cashier", [self.north])
        stripped = admin_client.patch(f"/api/v1/staff/{narrow.id}", {"branch_ids": [str(self.main.id)]}, format="json")
        self.assertEqual(stripped.status_code, 200)
        self.assertEqual(self.grants(narrow), {self.north.id, self.main.id})

    def test_members_of_other_stores_are_not_found_and_empty_updates_are_rejected(self):
        _, foreign, _ = self.person("cashier", [self.other_branch], tenant=self.other_tenant)
        self.assertEqual(self.owner_client.patch(f"/api/v1/staff/{foreign.id}", {"is_active": False}, format="json").status_code, 404)
        foreign.refresh_from_db()
        self.assertTrue(foreign.is_active)
        _, member, _ = self.person("cashier", [self.main])
        self.assertEqual(self.owner_client.patch(f"/api/v1/staff/{member.id}", {}, format="json").status_code, 400)
        self.assertEqual(self.owner_client.patch(f"/api/v1/staff/{uuid.uuid4()}", {"is_active": False}, format="json").status_code, 404)

    def test_non_managers_cannot_update_staff(self):
        _, member, _ = self.person("cashier", [self.main])
        _, _, manager_client = self.person("manager", [self.main])
        self.assertEqual(manager_client.patch(f"/api/v1/staff/{member.id}", {"is_active": False}, format="json").status_code, 403)
