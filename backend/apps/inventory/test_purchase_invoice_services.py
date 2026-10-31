from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.catalog.models import Product
from apps.inventory.models import (
    PurchaseInvoice,
    PurchaseInvoiceAllocation,
    PurchaseInvoiceLine,
    PurchaseReceipt,
    PurchaseReceiptLine,
    Supplier,
)
from apps.inventory.purchase_invoice_services import (
    PurchaseInvoicePostingError,
    post_purchase_invoice,
)
from apps.tenancy.models import Branch, Tenant


class PurchaseInvoicePostingTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Invoice Store", slug="invoice-store")
        self.branch = Branch.objects.create(tenant=self.tenant, name="Main", code="MAIN")
        self.user = get_user_model().objects.create_user(
            username="invoice-owner@example.test",
            email="invoice-owner@example.test",
            password="test-only-password",
        )
        self.supplier = Supplier.objects.create(
            tenant=self.tenant,
            name="Supplier One",
            gstin="27AABCU9603R1ZM",
        )
        self.product = Product.objects.create(
            tenant=self.tenant,
            sku="INV-001",
            name="Rice",
            unit=Product.Unit.KG,
            gst_rate=Decimal("5.00"),
            selling_price=Decimal("60.00"),
            purchase_price=Decimal("45.00"),
        )
        self.receipt = PurchaseReceipt.objects.create(
            tenant=self.tenant,
            branch=self.branch,
            supplier=self.supplier,
            supplier_name=self.supplier.name,
            idempotency_key="grn-1",
            request_hash="a" * 64,
            created_by=self.user,
        )
        self.receipt_line = PurchaseReceiptLine.objects.create(
            tenant=self.tenant,
            receipt=self.receipt,
            product=self.product,
            quantity=Decimal("10.000"),
            unit_cost=Decimal("10.00"),
        )
        self.invoice = PurchaseInvoice.objects.create(
            tenant=self.tenant,
            supplier=self.supplier,
            branch=self.branch,
            supplier_name=self.supplier.name,
            supplier_gstin=self.supplier.gstin,
            supplier_state_code="27",
            place_of_supply_state_code="27",
            invoice_number="SUP-INV-1",
            invoice_date=date(2026, 10, 31),
            taxable_total=Decimal("100.00"),
            tax_total=Decimal("18.00"),
            total_amount=Decimal("118.00"),
            idempotency_key="invoice-1",
            request_hash="b" * 64,
            created_by=self.user,
        )
        self.line = PurchaseInvoiceLine.objects.create(
            tenant=self.tenant,
            invoice=self.invoice,
            product=self.product,
            description_snapshot="Rice",
            hsn_code="1006",
            quantity=Decimal("10.000"),
            unit_price=Decimal("10.0000"),
            discount_amount=Decimal("0.00"),
            taxable_value=Decimal("100.00"),
            gst_rate=Decimal("18.00"),
            cgst_amount=Decimal("9.00"),
            sgst_amount=Decimal("9.00"),
            igst_amount=Decimal("0.00"),
            total_tax=Decimal("18.00"),
            total_amount=Decimal("118.00"),
        )
        self.allocation = PurchaseInvoiceAllocation.objects.create(
            tenant=self.tenant,
            invoice_line=self.line,
            receipt_line=self.receipt_line,
            quantity=Decimal("10.000"),
            taxable_value=Decimal("100.00"),
        )

    def test_valid_invoice_posts_without_changing_grn_quantity(self):
        invoice = post_purchase_invoice(tenant_id=self.tenant.id, invoice_id=self.invoice.id)

        self.assertEqual(invoice.status, PurchaseInvoice.Status.POSTED)
        self.assertIsNotNone(invoice.posted_at)
        self.receipt_line.refresh_from_db()
        self.assertEqual(self.receipt_line.quantity, Decimal("10.000"))

    def test_posting_is_idempotent_for_already_posted_invoice(self):
        first = post_purchase_invoice(tenant_id=self.tenant.id, invoice_id=self.invoice.id)
        first_posted_at = first.posted_at
        second = post_purchase_invoice(tenant_id=self.tenant.id, invoice_id=self.invoice.id)

        self.assertEqual(second.status, PurchaseInvoice.Status.POSTED)
        self.assertEqual(second.posted_at, first_posted_at)

    def test_invoice_cannot_be_posted_without_grn_allocations(self):
        self.allocation.delete()

        with self.assertRaisesMessage(PurchaseInvoicePostingError, "Every invoice line must be allocated"):
            post_purchase_invoice(tenant_id=self.tenant.id, invoice_id=self.invoice.id)

    def test_allocation_quantity_must_match_invoice_line(self):
        self.allocation.quantity = Decimal("9.000")
        self.allocation.save()

        with self.assertRaisesMessage(PurchaseInvoicePostingError, "allocation quantities must equal"):
            post_purchase_invoice(tenant_id=self.tenant.id, invoice_id=self.invoice.id)

    def test_line_tax_components_must_reconcile(self):
        self.line.igst_amount = Decimal("1.00")
        self.line.save()

        with self.assertRaisesMessage(PurchaseInvoicePostingError, "tax components do not reconcile"):
            post_purchase_invoice(tenant_id=self.tenant.id, invoice_id=self.invoice.id)

    def test_foreign_tenant_invoice_is_not_found(self):
        other_tenant = Tenant.objects.create(name="Other Store", slug="invoice-store-other")

        with self.assertRaisesMessage(PurchaseInvoicePostingError, "not found in this store"):
            post_purchase_invoice(tenant_id=other_tenant.id, invoice_id=self.invoice.id)
