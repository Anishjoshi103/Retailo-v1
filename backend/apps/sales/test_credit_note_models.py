from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.catalog.models import Product
from apps.sales.models import CreditNote, CreditNoteLine, Sale, SaleLine
from apps.tenancy.models import Branch, Tenant


class CreditNoteModelTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Store A", slug="store-a")
        self.other_tenant = Tenant.objects.create(name="Store B", slug="store-b")
        self.branch = Branch.objects.create(tenant=self.tenant, name="Main", code="MAIN", state_code="27")
        self.user = get_user_model().objects.create_user(
            username="cashier@example.test", email="cashier@example.test", password="Test-password-123"
        )
        self.rice = Product.objects.create(tenant=self.tenant, sku="RICE-1", name="Rice", unit=Product.Unit.KG, gst_rate=Decimal("18.00"), selling_price=Decimal("100.00"))
        self.soap = Product.objects.create(tenant=self.tenant, sku="SOAP-1", name="Soap", unit=Product.Unit.EACH, gst_rate=Decimal("5.00"), selling_price=Decimal("20.00"))
        self.sale = self.make_sale()
        self.sale_line = self.make_sale_line(self.sale, self.rice)

    def make_sale(self, number="INV-MAIN-000001", key="sale-1"):
        return Sale.objects.create(
            tenant=self.tenant, branch=self.branch, invoice_number=number, invoice_date=date(2026, 11, 9),
            seller_gstin="27AAPFU0939F1ZV", seller_state_code="27", place_of_supply_state_code="27",
            taxable_total=Decimal("84.74"), cgst_total=Decimal("7.63"), sgst_total=Decimal("7.63"),
            igst_total=Decimal("0.00"), total_tax=Decimal("15.26"), round_off=Decimal("0.00"),
            grand_total=Decimal("100.00"), idempotency_key=key, request_hash="h" * 64, created_by=self.user,
        )

    def make_sale_line(self, sale, product):
        return SaleLine.objects.create(
            tenant=self.tenant, sale=sale, product=product, sku=product.sku, name=product.name, hsn_code="1006",
            unit="kg", quantity=Decimal("1.000"), unit_price=Decimal("100.00"), gst_rate=Decimal("18.00"),
            taxable_value=Decimal("84.74"), cgst_amount=Decimal("7.63"), sgst_amount=Decimal("7.63"),
            igst_amount=Decimal("0.00"), line_total=Decimal("100.00"),
        )

    def note_fields(self, **overrides):
        fields = dict(
            tenant=self.tenant, branch=self.branch, sale=self.sale, credit_note_number="CN-MAIN-000001",
            credit_note_date=date(2026, 11, 10), seller_gstin="27AAPFU0939F1ZV", seller_state_code="27",
            place_of_supply_state_code="27", taxable_total=Decimal("84.74"), cgst_total=Decimal("7.63"),
            sgst_total=Decimal("7.63"), igst_total=Decimal("0.00"), total_tax=Decimal("15.26"),
            round_off=Decimal("0.00"), grand_total=Decimal("100.00"), reason="Damaged", idempotency_key="cn-1",
            request_hash="h" * 64, created_by=self.user,
        )
        fields.update(overrides)
        return fields

    def make_note(self, **overrides):
        return CreditNote.objects.create(**self.note_fields(**overrides))

    def line_fields(self, note, **overrides):
        fields = dict(
            tenant=self.tenant, credit_note=note, sale_line=self.sale_line, product=self.rice, sku="RICE-1",
            name="Rice", hsn_code="1006", unit="kg", quantity=Decimal("1.000"), unit_price=Decimal("100.00"),
            gst_rate=Decimal("18.00"), taxable_value=Decimal("84.74"), cgst_amount=Decimal("7.63"),
            sgst_amount=Decimal("7.63"), igst_amount=Decimal("0.00"), line_total=Decimal("100.00"),
        )
        fields.update(overrides)
        return fields

    def make_line(self, note, **overrides):
        return CreditNoteLine.objects.create(**self.line_fields(note, **overrides))

    def test_credit_note_with_line_is_stored_and_linked_to_its_sale(self):
        note = self.make_note()
        line = self.make_line(note)
        self.assertEqual(note.sale_id, self.sale.id)
        self.assertEqual(line.sale_line_id, self.sale_line.id)
        self.assertEqual(note.lines.for_tenant(self.tenant.id).count(), 1)
        self.assertEqual(self.sale.credit_notes.for_tenant(self.tenant.id).get().credit_note_number, "CN-MAIN-000001")
        self.assertEqual(self.sale_line.credit_lines.for_tenant(self.tenant.id).count(), 1)

    def test_credit_notes_and_lines_are_immutable_through_every_path(self):
        note = self.make_note()
        line = self.make_line(note)
        for record in (note, line):
            with self.assertRaises(TypeError):
                record.save()
            with self.assertRaises(TypeError):
                record.delete()
        with self.assertRaises(TypeError):
            CreditNote.objects.for_tenant(self.tenant.id).filter(pk=note.pk).update(reason="x")
        with self.assertRaises(TypeError):
            CreditNote.objects.for_tenant(self.tenant.id).filter(pk=note.pk).delete()
        with self.assertRaises(TypeError):
            CreditNoteLine.objects.for_tenant(self.tenant.id).filter(pk=line.pk).update(quantity=Decimal("2.000"))
        with self.assertRaises(TypeError):
            CreditNoteLine.objects.for_tenant(self.tenant.id).bulk_update([line], ["quantity"])

    def test_number_unique_per_branch_and_idempotency_key_per_tenant(self):
        self.make_note()
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.make_note(idempotency_key="cn-2")
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.make_note(credit_note_number="CN-MAIN-000002")
        north = Branch.objects.create(tenant=self.tenant, name="North", code="NORTH", state_code="27")
        north_sale = Sale.objects.create(
            tenant=self.tenant, branch=north, invoice_number="INV-NORTH-000001", invoice_date=date(2026, 11, 9),
            seller_state_code="27", place_of_supply_state_code="27", taxable_total=Decimal("0.00"),
            cgst_total=Decimal("0.00"), sgst_total=Decimal("0.00"), igst_total=Decimal("0.00"),
            total_tax=Decimal("0.00"), grand_total=Decimal("0.00"), idempotency_key="sale-n",
            request_hash="h" * 64, created_by=self.user,
        )
        self.make_note(branch=north, sale=north_sale, idempotency_key="cn-3")

    def test_database_rejects_inconsistent_totals_but_accepts_float_prone_amounts(self):
        # 84.74 + 7.63 + 7.63 is 99.99999999999999 as a float; the rounded check accepts it.
        note = self.make_note()
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.make_note(credit_note_number="CN-MAIN-000002", idempotency_key="cn-2", grand_total=Decimal("100.01"))
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.make_note(credit_note_number="CN-MAIN-000003", idempotency_key="cn-3", total_tax=Decimal("15.25"), grand_total=Decimal("99.99"))
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.make_line(note, line_total=Decimal("100.01"))
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.make_line(note, quantity=Decimal("0.000"))

    def test_credit_note_must_share_the_sales_tenant_and_branch(self):
        with self.assertRaises(ValueError):
            self.make_note(tenant=self.other_tenant)
        other_branch = Branch.objects.create(tenant=self.tenant, name="North", code="NORTH", state_code="27")
        with self.assertRaises(ValueError):
            self.make_note(branch=other_branch)

    def test_line_must_return_a_line_of_the_credit_notes_own_sale(self):
        note = self.make_note()
        other_sale = self.make_sale(number="INV-MAIN-000002", key="sale-2")
        foreign_line = self.make_sale_line(other_sale, self.rice)
        with self.assertRaises(ValueError):
            self.make_line(note, sale_line=foreign_line)
        with self.assertRaises(ValueError):
            self.make_line(note, product=self.soap)
        with self.assertRaises(ValueError):
            self.make_line(note, tenant=self.other_tenant)

    def test_unscoped_credit_note_queries_are_refused(self):
        self.make_note()
        with self.assertRaises(RuntimeError):
            CreditNote.objects.count()
