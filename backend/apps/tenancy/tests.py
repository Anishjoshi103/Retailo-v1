import uuid
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase

from .models import Branch, BranchAccess, Membership, Tenant


class ActiveTenantMembershipTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Store Cache", slug="store-cache")
        self.user = get_user_model().objects.create_user(
            username="cache@example.test", email="cache@example.test", password="not-a-real-password"
        )
        self.membership = Membership.objects.create(
            tenant=self.tenant, user=self.user, role=Membership.Role.OWNER
        )
        self.request = SimpleNamespace(
            user=self.user,
            auth={"tenant_id": str(self.tenant.id), "membership_id": str(self.membership.id)},
        )

    def test_active_membership_is_resolved_once_per_request(self):
        from apps.tenancy.permissions import active_tenant_membership

        with self.assertNumQueries(1):
            first = active_tenant_membership(self.request)
            second = active_tenant_membership(self.request)

        self.assertEqual(first.pk, self.membership.pk)
        self.assertIs(first, second)

    def test_inactive_membership_is_denied(self):
        from rest_framework.exceptions import PermissionDenied

        from apps.tenancy.permissions import active_tenant_membership

        self.membership.is_active = False
        self.membership.save(update_fields=["is_active"])
        with self.assertRaises(PermissionDenied):
            active_tenant_membership(self.request)


class TenantIdentityTests(TestCase):
    def setUp(self):
        self.tenant_a = Tenant.objects.create(name="Store A", slug="store-a")
        self.tenant_b = Tenant.objects.create(name="Store B", slug="store-b")
        self.user = get_user_model().objects.create_user(
            username="owner@example.test", email="owner@example.test", password="not-a-real-password"
        )
        Membership.objects.create(tenant=self.tenant_a, user=self.user, role=Membership.Role.OWNER)

    def test_branch_queryset_can_be_explicitly_scoped_to_tenant(self):
        branch_a = Branch.objects.create(tenant=self.tenant_a, name="Main", code="MAIN")
        Branch.objects.create(tenant=self.tenant_b, name="Main", code="MAIN")
        self.assertEqual(list(Branch.objects.for_tenant(self.tenant_a.id)), [branch_a])
        self.assertEqual(Branch.objects.for_tenant(None).count(), 0)

    def test_branch_code_is_unique_only_within_tenant(self):
        Branch.objects.create(tenant=self.tenant_a, name="Main", code="MAIN")
        Branch.objects.create(tenant=self.tenant_b, name="Main", code="MAIN")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Branch.objects.create(tenant=self.tenant_a, name="Second", code="MAIN")

    def test_membership_is_unique_per_tenant_and_user(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Membership.objects.create(tenant=self.tenant_a, user=self.user, role=Membership.Role.CASHIER)

    def test_membership_does_not_grant_access_to_another_tenant(self):
        self.assertTrue(Membership.objects.filter(tenant=self.tenant_a, user=self.user).exists())
        self.assertFalse(Membership.objects.filter(tenant=self.tenant_b, user=self.user).exists())

    def test_tenant_ids_are_uuid_values(self):
        self.assertNotEqual(self.tenant_a.id, self.tenant_b.id)
        self.assertIsInstance(self.tenant_a.id, uuid.UUID)


class MembershipRoleAuthorizationTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Role Store", slug="role-store")
        self.user = get_user_model().objects.create_user(
            username="roles@example.test", email="roles@example.test", password="not-a-real-password"
        )
        self.membership = Membership.objects.create(
            tenant=self.tenant, user=self.user, role=Membership.Role.OWNER
        )
        self.request = SimpleNamespace(
            user=self.user,
            auth={"tenant_id": str(self.tenant.id), "membership_id": str(self.membership.id)},
        )

    def test_role_guard_returns_membership_for_allowed_role(self):
        from apps.tenancy.permissions import require_membership_role

        result = require_membership_role(
            self.request, {Membership.Role.OWNER, Membership.Role.ADMIN}
        )

        self.assertEqual(result.pk, self.membership.pk)

    def test_role_guard_denies_role_not_in_allowlist(self):
        from rest_framework.exceptions import PermissionDenied

        from apps.tenancy.permissions import require_membership_role

        self.membership.role = Membership.Role.CASHIER
        self.membership.save(update_fields=["role"])

        with self.assertRaises(PermissionDenied):
            require_membership_role(
                self.request, {Membership.Role.OWNER, Membership.Role.ADMIN, Membership.Role.MANAGER}
            )

    def test_role_guard_uses_active_membership_resolver(self):
        from apps.tenancy.permissions import require_membership_role

        with self.assertNumQueries(1):
            require_membership_role(self.request, {Membership.Role.OWNER})
            require_membership_role(self.request, {Membership.Role.OWNER})



class DRFPermissionClassTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Permission Store", slug="permission-store")
        self.user = get_user_model().objects.create_user(
            username="permission@example.test",
            email="permission@example.test",
            password="not-a-real-password",
        )
        self.membership = Membership.objects.create(
            tenant=self.tenant, user=self.user, role=Membership.Role.MANAGER
        )
        self.branch = Branch.objects.create(
            tenant=self.tenant, name="Main", code="MAIN"
        )
        BranchAccess.objects.create(membership=self.membership, branch=self.branch)
        self.request = SimpleNamespace(
            user=self.user,
            auth={
                "tenant_id": str(self.tenant.id),
                "membership_id": str(self.membership.id),
            },
            headers={"X-Branch-ID": str(self.branch.id)},
        )

    def test_is_active_tenant_member_accepts_resolved_membership(self):
        from apps.tenancy.permissions import IsActiveTenantMember

        self.assertTrue(IsActiveTenantMember().has_permission(self.request, None))

    def test_is_active_tenant_member_rejects_missing_membership_context(self):
        from apps.tenancy.permissions import IsActiveTenantMember

        self.request.auth = None
        self.assertFalse(IsActiveTenantMember().has_permission(self.request, None))

    def test_has_role_accepts_allowed_role_and_rejects_other_role(self):
        from apps.tenancy.permissions import HasRole

        self.assertTrue(HasRole(Membership.Role.MANAGER).has_permission(self.request, None))
        self.assertFalse(HasRole(Membership.Role.OWNER).has_permission(self.request, None))

    def test_has_branch_access_requires_active_grant(self):
        from apps.tenancy.permissions import HasBranchAccess

        self.assertTrue(HasBranchAccess().has_permission(self.request, None))
        BranchAccess.objects.filter(membership=self.membership, branch=self.branch).update(
            is_active=False
        )
        self.assertFalse(HasBranchAccess().has_permission(self.request, None))

    def test_has_branch_access_rejects_missing_or_unrecognized_branch(self):
        from apps.tenancy.permissions import HasBranchAccess

        self.request.headers = {}
        self.assertFalse(HasBranchAccess().has_permission(self.request, None))
        self.request.headers = {"X-Branch-ID": str(uuid.uuid4())}
        self.assertFalse(HasBranchAccess().has_permission(self.request, None))
