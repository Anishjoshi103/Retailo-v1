from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.test import TestCase

from apps.catalog.models import Product
from apps.inventory.models import InventoryBalance, StockMovement, Supplier
from apps.tenancy.models import Branch, BranchAccess, Membership, Tenant


class SeedDemoCommandTests(TestCase):
    def setUp(self):
        self.email = "demo-owner@example.test"
        self.password = "demo-password-123"

    def run_seed(self):
        with patch.dict("os.environ", {"RETAILO_DEMO_PASSWORD": self.password}):
            call_command("seed_demo", email=self.email, state_code="27", verbosity=0)

    def test_seed_creates_store_branches_owner_products_supplier_and_opening_stock(self):
        self.run_seed()

        tenant = Tenant.objects.get(slug="retailo-demo")
        user = get_user_model().objects.get(username=self.email)
        membership = Membership.objects.get(tenant=tenant, user=user)
        branches = Branch.objects.for_tenant(tenant.id)
        products = Product.objects.for_tenant(tenant.id)

        self.assertEqual(tenant.name, "Retailo Demo Store")
        self.assertEqual(membership.role, Membership.Role.OWNER)
        self.assertEqual(set(branches.values_list("code", flat=True)), {"MAIN", "WH"})
        self.assertEqual(set(branches.values_list("state_code", flat=True)), {"27"})
        self.assertEqual(BranchAccess.objects.filter(membership=membership).count(), 2)
        self.assertEqual(products.count(), 5)
        self.assertEqual(Supplier.objects.for_tenant(tenant.id).count(), 1)
        self.assertEqual(StockMovement.objects.for_tenant(tenant.id).count(), 10)
        total_stock = sum(
            InventoryBalance.objects.for_tenant(tenant.id).values_list(
                "quantity_on_hand", flat=True
            ),
            Decimal("0.000"),
        )
        self.assertEqual(total_stock, Decimal("500.000"))

    def test_rerun_does_not_duplicate_or_reset_password_or_stock(self):
        self.run_seed()
        tenant = Tenant.objects.get(slug="retailo-demo")
        user = get_user_model().objects.get(username=self.email)
        user.set_password("a-different-password-456")
        user.save(update_fields=["password"])
        balance = InventoryBalance.objects.for_tenant(tenant.id).first()
        balance.quantity_on_hand = Decimal("77.000")
        balance.save(update_fields=["quantity_on_hand", "updated_at"])

        self.run_seed()

        user.refresh_from_db()
        balance.refresh_from_db()
        self.assertTrue(user.check_password("a-different-password-456"))
        self.assertEqual(balance.quantity_on_hand, Decimal("77.000"))
        self.assertEqual(Tenant.objects.filter(slug="retailo-demo").count(), 1)
        self.assertEqual(StockMovement.objects.for_tenant(tenant.id).count(), 10)
        self.assertEqual(Product.objects.for_tenant(tenant.id).count(), 5)

    def test_nonzero_balance_without_demo_movement_is_not_increased(self):
        self.run_seed()
        tenant = Tenant.objects.get(slug="retailo-demo")
        balance = InventoryBalance.objects.for_tenant(tenant.id).first()
        balance.quantity_on_hand = Decimal("77.000")
        balance.save(update_fields=["quantity_on_hand", "updated_at"])

        empty_movements = StockMovement.objects.for_tenant(tenant.id).filter(pk__isnull=True)
        with patch.object(StockMovement.objects, "for_tenant", return_value=empty_movements):
            with self.assertRaisesRegex(CommandError, "without the demo opening movement"):
                self.run_seed()

        balance.refresh_from_db()
        self.assertEqual(balance.quantity_on_hand, Decimal("77.000"))

    def test_existing_unrelated_user_is_not_taken_over(self):
        user_model = get_user_model()
        user_model.objects.create_user(
            username=self.email,
            email=self.email,
            password="existing-user-password",
        )

        with patch.dict("os.environ", {"RETAILO_DEMO_PASSWORD": self.password}):
            with self.assertRaisesRegex(CommandError, "outside the demo store"):
                call_command("seed_demo", email=self.email, state_code="27", verbosity=0)

        self.assertFalse(Tenant.objects.filter(slug="retailo-demo").exists())
        existing_user = user_model.objects.get(username=self.email)
        self.assertTrue(existing_user.check_password("existing-user-password"))

    def test_existing_user_with_another_active_store_is_not_reused(self):
        user_model = get_user_model()
        user = user_model.objects.create_user(
            username=self.email,
            email=self.email,
            password="existing-user-password",
        )
        other_tenant = Tenant.objects.create(name="Existing Store", slug="existing-store")
        Membership.objects.create(
            tenant=other_tenant,
            user=user,
            role=Membership.Role.OWNER,
            is_active=True,
        )
        demo_tenant = Tenant.objects.create(name="Retailo Demo Store", slug="retailo-demo")
        Membership.objects.create(
            tenant=demo_tenant,
            user=user,
            role=Membership.Role.OWNER,
            is_active=True,
        )

        with patch.dict("os.environ", {"RETAILO_DEMO_PASSWORD": self.password}):
            with self.assertRaisesRegex(CommandError, "another active store"):
                call_command("seed_demo", email=self.email, state_code="27", verbosity=0)

        self.assertEqual(Tenant.objects.count(), 2)
        existing_user = user_model.objects.get(username=self.email)
        self.assertTrue(existing_user.check_password("existing-user-password"))

    def test_existing_non_demo_store_using_reserved_slug_is_not_modified(self):
        tenant = Tenant.objects.create(name="A real store", slug="retailo-demo")

        with patch.dict("os.environ", {"RETAILO_DEMO_PASSWORD": self.password}):
            with self.assertRaisesRegex(CommandError, "non-demo store"):
                call_command("seed_demo", email=self.email, state_code="27", verbosity=0)

        tenant.refresh_from_db()
        self.assertEqual(tenant.name, "A real store")
        self.assertFalse(get_user_model().objects.filter(username=self.email).exists())
