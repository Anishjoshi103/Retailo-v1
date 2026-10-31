"""Transactional validation and posting for supplier purchase invoices.

Posting records the accounting document state only. GRNs remain the source of
stock movements; this service never changes inventory balances or stock ledger.
"""
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from .models import (
    PurchaseInvoice,
    PurchaseInvoiceAllocation,
    PurchaseInvoiceLine,
    PurchaseReceiptLine,
    PurchaseReturnLine,
)


class PurchaseInvoicePostingError(ValueError):
    """Raised when an invoice is not safe to post."""


@transaction.atomic
def post_purchase_invoice(*, tenant_id, invoice_id):
    """Validate the complete invoice/GRN allocation graph and post atomically.

    All related records are tenant-scoped and locked before aggregate checks so
    concurrent invoice posts cannot over-allocate the same received quantity.
    """
    invoice = (
        PurchaseInvoice.objects.for_tenant(tenant_id)
        .select_for_update()
        .select_related("supplier", "branch")
        .filter(pk=invoice_id)
        .first()
    )
    if invoice is None:
        raise PurchaseInvoicePostingError("Purchase invoice was not found in this store.")

    if invoice.status == PurchaseInvoice.Status.POSTED:
        return invoice
    if invoice.supplier.tenant_id != invoice.tenant_id or invoice.branch.tenant_id != invoice.tenant_id:
        raise PurchaseInvoicePostingError("Invoice supplier and branch must belong to the same store.")

    lines = list(
        PurchaseInvoiceLine.objects.for_tenant(tenant_id)
        .select_for_update()
        .select_related("product")
        .filter(invoice=invoice)
        .order_by("id")
    )
    if not lines:
        raise PurchaseInvoicePostingError("An invoice must contain at least one line.")

    taxable_total = Decimal("0.00")
    tax_total = Decimal("0.00")
    invoice_total = Decimal("0.00")
    for line in lines:
        if line.invoice_id != invoice.id or line.product.tenant_id != tenant_id:
            raise PurchaseInvoicePostingError("Invoice lines and products must belong to this store.")
        if line.total_tax != line.cgst_amount + line.sgst_amount + line.igst_amount:
            raise PurchaseInvoicePostingError("Line tax components do not reconcile to total tax.")
        if line.total_amount != line.taxable_value + line.total_tax:
            raise PurchaseInvoicePostingError("Line total does not reconcile to taxable value plus tax.")

        allocations = list(
            PurchaseInvoiceAllocation.objects.for_tenant(tenant_id)
            .select_for_update()
            .select_related("receipt_line__receipt", "receipt_line__product")
            .filter(invoice_line=line)
        )
        if not allocations:
            raise PurchaseInvoicePostingError("Every invoice line must be allocated to a received GRN line.")

        allocated_quantity = Decimal("0")
        allocated_taxable = Decimal("0.00")
        for allocation in allocations:
            receipt_line = allocation.receipt_line
            receipt = receipt_line.receipt
            if (
                allocation.invoice_line_id != line.id
                or receipt_line.tenant_id != tenant_id
                or receipt.tenant_id != tenant_id
                or receipt_line.product_id != line.product_id
                or receipt.branch_id != invoice.branch_id
            ):
                raise PurchaseInvoicePostingError("GRN allocations must match the invoice tenant, branch, and product.")

            allocated_quantity += allocation.quantity
            allocated_taxable += allocation.taxable_value

        if allocated_quantity != line.quantity:
            raise PurchaseInvoicePostingError("GRN allocation quantities must equal the invoice line quantity.")
        if allocated_taxable != line.taxable_value:
            raise PurchaseInvoicePostingError("GRN allocation taxable values must equal the invoice line taxable value.")

        # Lock every receipt line touched by this invoice, then enforce the
        # aggregate billed quantity across already-posted invoices.
        receipt_line_ids = [allocation.receipt_line_id for allocation in allocations]
        locked_receipt_lines = list(
            PurchaseReceiptLine.objects.for_tenant(tenant_id)
            .select_for_update()
            .filter(pk__in=receipt_line_ids)
            .order_by("id")
        )
        for receipt_line in locked_receipt_lines:
            billed = (
                PurchaseInvoiceAllocation.objects.for_tenant(tenant_id)
                .filter(
                    receipt_line=receipt_line,
                    invoice_line__invoice__status=PurchaseInvoice.Status.POSTED,
                )
                .exclude(invoice_line__invoice=invoice)
            )
            billed_quantity = sum((row.quantity for row in billed), Decimal("0"))
            returned_quantity = sum(
                PurchaseReturnLine.objects.for_tenant(tenant_id)
                .filter(receipt_line=receipt_line, purchase_return__tenant_id=tenant_id)
                .values_list("quantity", flat=True),
                Decimal("0"),
            )
            if billed_quantity + allocated_quantity_for_receipt_line(allocations, receipt_line.id) > receipt_line.quantity - returned_quantity:
                raise PurchaseInvoicePostingError("Invoice allocation exceeds the unreturned, unbilled GRN quantity.")

        taxable_total += line.taxable_value
        tax_total += line.total_tax
        invoice_total += line.total_amount

    if (invoice.taxable_total, invoice.tax_total, invoice.total_amount) != (taxable_total, tax_total, invoice_total):
        raise PurchaseInvoicePostingError("Invoice totals do not reconcile to its line snapshots.")

    invoice.status = PurchaseInvoice.Status.POSTED
    invoice.posted_at = timezone.now()
    invoice.save(update_fields=["status", "posted_at"])
    return invoice


def allocated_quantity_for_receipt_line(allocations, receipt_line_id):
    return sum(
        (allocation.quantity for allocation in allocations if allocation.receipt_line_id == receipt_line_id),
        Decimal("0"),
    )
