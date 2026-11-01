import uuid

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase

from .models import Branch, Membership, Tenant


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
