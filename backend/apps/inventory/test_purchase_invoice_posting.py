from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.catalog.models import Product
from apps.inventory.models import (
    InventoryBalance,
    PurchaseInvoice,
    PurchaseInvoiceAllocation,
    PurchaseInvoiceLine,
    PurchaseReceipt,
    PurchaseReceiptLine,
    PurchaseInvoice,
    Supplier,
    StockMovement,
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
        self.user = get_user_model().objects.create_user(username="invoice-owner@example.test", password="Test-password-123")
        self.supplier = Supplier.objects.create(tenant=self.tenant, name="Supplier One", gstin="27AABCU9603R1ZM")
        self.product = Product.objects.create(
            tenant=self.tenant, sku="INV-RICE-1", name="Rice", unit=Product.Unit.KG,
            gst_rate=Decimal("5.00"), selling_price=Decimal("60.00"), purchase_price=Decimal("45.00"),
        )
        self.receipt = PurchaseReceipt.objects.create(
            tenant=self.tenant, branch=self.branch, supplier=self.supplier,
            supplier_name=self.supplier.name, supplier_invoice_number="GRN-SOURCE-1",
            idempotency_key="receipt-key-1", request_hash="a" * 64, created_by=self.user,
        )
        self.receipt_line = PurchaseReceiptLine.objects.create(
            tenant=self.tenant, receipt=self.receipt, product=self.product,
            quantity=Decimal("10.000"), unit_cost=Decimal("45.00"),
        )

    def create_invoice(self, *, quantity=Decimal("3.000"), allocation_quantity=None):
        allocation_quantity = quantity if allocation_quantity is None else allocation_quantity
        invoice = PurchaseInvoice.objects.create(
            tenant=self.tenant, supplier=self.supplier, branch=self.branch,
            supplier_name=self.supplier.name, supplier_gstin=self.supplier.gstin,
            supplier_state_code="27", place_of_supply_state_code="27",
            invoice_number=f"SUP-{PurchaseInvoice.objects.count() + 1}", invoice_date=date(2026, 10, 31),
            taxable_total=Decimal("135.00"), tax_total=Decimal("6.76"), total_amount=Decimal("141.76"),
            idempotency_key=f"invoice-key-{PurchaseInvoice.objects.count() + 1}",
            request_hash="b" * 64, created_by=self.user,
        )
        line = PurchaseInvoiceLine.objects.create(
            tenant=self.tenant, invoice=invoice, product=self.product,
            description_snapshot=self.product.name, hsn_code="1006",
            quantity=quantity, unit_price=Decimal("45.0000"), discount_amount=Decimal("0.00"),
            taxable_value=Decimal("135.00"), gst_rate=Decimal("5.00"),
            cgst_amount=Decimal("3.38"), sgst_amount=Decimal("3.38"), igst_amount=Decimal("0.00"),
            total_tax=Decimal("6.76"), total_amount=Decimal("141.76"),
        )
        PurchaseInvoiceAllocation.objects.create(
            tenant=self.tenant, invoice_line=line, receipt_line=self.receipt_line,
            quantity=allocation_quantity, taxable_value=Decimal("135.00"),
        )
        return invoice

    def test_posting_validates_and_posts_without_touching_stock(self):
        invoice = self.create_invoice()
        before_balance = InventoryBalance.objects.for_tenant(self.tenant.id).count()
        before_movements = StockMovement.objects.for_tenant(self.tenant.id).count()

        posted = post_purchase_invoice(tenant_id=self.tenant.id, invoice_id=invoice.id)

        self.assertEqual(posted.status, PurchaseInvoice.Status.POSTED)
        self.assertIsNotNone(posted.posted_at)
        self.assertEqual(InventoryBalance.objects.for_tenant(self.tenant.id).count(), before_balance)
        self.assertEqual(StockMovement.objects.for_tenant(self.tenant.id).count(), before_movements)

    def test_posting_rejects_allocation_quantity_that_does_not_match_line(self):
        invoice = self.create_invoice(quantity=Decimal("3.000"), allocation_quantity=Decimal("2.000"))

        with self.assertRaisesMessage(PurchaseInvoicePostingError, "allocation quantities must equal"):
            post_purchase_invoice(tenant_id=self.tenant.id, invoice_id=invoice.id)

        invoice.refresh_from_db()
        self.assertEqual(invoice.status, PurchaseInvoice.Status.DRAFT)
        self.assertIsNone(invoice.posted_at)

    def test_posting_rejects_invoice_from_another_tenant(self):
        other_tenant = Tenant.objects.create(name="Other Store", slug="invoice-other-store")

        with self.assertRaisesMessage(PurchaseInvoicePostingError, "not found in this store"):
            post_purchase_invoice(tenant_id=other_tenant.id, invoice_id="00000000-0000-0000-0000-000000000001")
