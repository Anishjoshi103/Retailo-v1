from django.db import transaction
from django.test import TestCase

from apps.sales.models import CreditNoteSequence
from apps.sales.numbering import (
    InvoiceNumberError,
    allocate_credit_note_number,
    allocate_invoice_number,
    format_credit_note_number,
)
from apps.tenancy.models import Branch, Tenant


class CreditNoteNumberingTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Store A", slug="store-a")
        self.other_tenant = Tenant.objects.create(name="Store B", slug="store-b")
        self.main = Branch.objects.create(tenant=self.tenant, name="Main", code="MAIN")
        self.north = Branch.objects.create(tenant=self.tenant, name="North", code="NORTH")

    def allocate(self, branch):
        return allocate_credit_note_number(tenant_id=branch.tenant_id, branch=branch)

    def test_numbers_are_sequential_per_branch_with_cn_prefix(self):
        self.assertEqual(self.allocate(self.main), "CN-MAIN-000001")
        self.assertEqual(self.allocate(self.main), "CN-MAIN-000002")
        self.assertEqual(self.allocate(self.north), "CN-NORTH-000001")

    def test_credit_note_and_invoice_counters_are_independent(self):
        allocate_invoice_number(tenant_id=self.tenant.id, branch=self.main)
        allocate_invoice_number(tenant_id=self.tenant.id, branch=self.main)
        self.assertEqual(self.allocate(self.main), "CN-MAIN-000001")
        self.assertEqual(allocate_invoice_number(tenant_id=self.tenant.id, branch=self.main), "INV-MAIN-000003")

    def test_same_branch_code_in_another_tenant_has_its_own_sequence(self):
        other = Branch.objects.create(tenant=self.other_tenant, name="Main", code="MAIN")
        self.allocate(self.main)
        self.assertEqual(self.allocate(other), "CN-MAIN-000001")

    def test_rolled_back_allocation_does_not_skip_a_number(self):
        with self.assertRaises(RuntimeError):
            with transaction.atomic():
                self.assertEqual(self.allocate(self.main), "CN-MAIN-000001")
                raise RuntimeError("credit note failed after numbering")
        self.assertEqual(self.allocate(self.main), "CN-MAIN-000001")

    def test_invalid_branch_codes_are_rejected_without_consuming_a_number(self):
        spaced = Branch.objects.create(tenant=self.tenant, name="Spaced", code="A B")
        with self.assertRaises(InvoiceNumberError):
            self.allocate(spaced)
        long_code = Branch.objects.create(tenant=self.tenant, name="Long", code="TOOLONGCODE")
        with self.assertRaises(InvoiceNumberError):
            self.allocate(long_code)
        self.assertEqual(CreditNoteSequence.objects.for_tenant(self.tenant.id).count(), 0)

    def test_serial_overflow_past_sixteen_characters_is_rejected(self):
        with self.assertRaises(InvoiceNumberError):
            format_credit_note_number("ABCDEFG", 1)  # CN- + 7 + - + 6 = 17
        self.assertEqual(len(format_credit_note_number("ABCDEF", 999999)), 16)

    def test_foreign_tenant_branch_is_rejected(self):
        with self.assertRaises(InvoiceNumberError):
            allocate_credit_note_number(tenant_id=self.other_tenant.id, branch=self.main)
