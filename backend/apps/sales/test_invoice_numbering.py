from django.db import transaction
from django.test import TestCase, TransactionTestCase

from apps.sales.models import InvoiceSequence
from apps.sales.numbering import (
    InvoiceNumberError,
    allocate_invoice_number,
    format_invoice_number,
)
from apps.tenancy.models import Branch, Tenant


class InvoiceNumberingTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Store A", slug="store-a")
        self.other_tenant = Tenant.objects.create(name="Store B", slug="store-b")
        self.main = Branch.objects.create(tenant=self.tenant, name="Main", code="MAIN")
        self.north = Branch.objects.create(tenant=self.tenant, name="North", code="NORTH")

    def allocate(self, branch):
        return allocate_invoice_number(tenant_id=branch.tenant_id, branch=branch)

    def test_numbers_are_sequential_per_branch(self):
        self.assertEqual(self.allocate(self.main), "INV-MAIN-000001")
        self.assertEqual(self.allocate(self.main), "INV-MAIN-000002")
        self.assertEqual(self.allocate(self.north), "INV-NORTH-000001")
        self.assertEqual(self.allocate(self.main), "INV-MAIN-000003")

    def test_same_branch_code_in_another_tenant_has_its_own_sequence(self):
        other = Branch.objects.create(tenant=self.other_tenant, name="Main", code="MAIN")
        self.allocate(self.main)
        self.assertEqual(self.allocate(other), "INV-MAIN-000001")

    def test_branch_code_is_upper_cased(self):
        branch = Branch.objects.create(tenant=self.tenant, name="Lower", code="ab1")
        self.assertEqual(self.allocate(branch), "INV-AB1-000001")

    def test_rolled_back_allocation_does_not_skip_a_number(self):
        with self.assertRaises(RuntimeError):
            with transaction.atomic():
                self.assertEqual(self.allocate(self.main), "INV-MAIN-000001")
                raise RuntimeError("sale failed after numbering")
        self.assertEqual(self.allocate(self.main), "INV-MAIN-000001")

    def test_branch_code_longer_than_five_characters_is_rejected_without_consuming(self):
        branch = Branch.objects.create(tenant=self.tenant, name="Long", code="LONGER")
        with self.assertRaises(InvoiceNumberError):
            self.allocate(branch)
        self.assertFalse(InvoiceSequence.objects.for_tenant(self.tenant.id).filter(branch=branch).exists())

    def test_branch_code_with_invalid_characters_is_rejected(self):
        branch = Branch.objects.create(tenant=self.tenant, name="Spaced", code="A B")
        with self.assertRaises(InvoiceNumberError):
            self.allocate(branch)

    def test_serial_overflow_past_sixteen_characters_is_rejected(self):
        branch = Branch.objects.create(tenant=self.tenant, name="Five", code="FIVE5")
        InvoiceSequence.objects.create(tenant=self.tenant, branch=branch, last_number=999999)
        with self.assertRaises(InvoiceNumberError):
            self.allocate(branch)
        sequence = InvoiceSequence.objects.for_tenant(self.tenant.id).get(branch=branch)
        self.assertEqual(sequence.last_number, 999999)

    def test_foreign_tenant_branch_is_rejected(self):
        with self.assertRaises(InvoiceNumberError):
            allocate_invoice_number(tenant_id=self.other_tenant.id, branch=self.main)

    def test_format_fits_gst_limit_for_five_character_codes(self):
        self.assertEqual(len(format_invoice_number("ABCDE", 999999)), 16)


class InvoiceNumberingTransactionTests(TransactionTestCase):
    def test_allocation_outside_a_transaction_is_refused(self):
        tenant = Tenant.objects.create(name="Store A", slug="store-a")
        branch = Branch.objects.create(tenant=tenant, name="Main", code="MAIN")
        with self.assertRaises(RuntimeError):
            allocate_invoice_number(tenant_id=tenant.id, branch=branch)
