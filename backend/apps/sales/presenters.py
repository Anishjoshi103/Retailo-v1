from decimal import Decimal

from django.db.models import Sum

from apps.sales.models import CreditNote, CreditNoteLine, Sale, SaleLine, SalePayment

QUANTITY_PLACES = Decimal("0.001")


def serialize_sale_summary(sale: Sale) -> dict:
    """Compact row for lists: no lines or payments."""
    return {
        "id": str(sale.id), "invoice_number": sale.invoice_number,
        "invoice_date": sale.invoice_date.isoformat(), "branch_id": str(sale.branch_id),
        "customer_name": sale.customer_name, "taxable_total": str(sale.taxable_total),
        "total_tax": str(sale.total_tax), "round_off": str(sale.round_off),
        "grand_total": str(sale.grand_total), "created_at": sale.created_at.isoformat(),
    }


def serialize_sale(sale: Sale) -> dict:
    """Full invoice body shared by POST (create/replay) and GET (detail)."""
    tenant_id = sale.tenant_id
    lines = SaleLine.objects.for_tenant(tenant_id).filter(sale=sale).order_by("id")
    returned = {
        row["sale_line_id"]: row["total"]
        for row in CreditNoteLine.objects.for_tenant(tenant_id)
        .filter(sale_line__sale=sale).values("sale_line_id").annotate(total=Sum("quantity"))
    }
    payments = SalePayment.objects.for_tenant(tenant_id).filter(sale=sale).order_by("id")
    return {
        **serialize_sale_summary(sale),
        "seller_gstin": sale.seller_gstin,
        "seller_state_code": sale.seller_state_code,
        "place_of_supply_state_code": sale.place_of_supply_state_code,
        "cgst_total": str(sale.cgst_total), "sgst_total": str(sale.sgst_total),
        "igst_total": str(sale.igst_total),
        "lines": [
            {
                "id": str(line.id), "product_id": str(line.product_id), "sku": line.sku, "name": line.name,
                "hsn_code": line.hsn_code, "unit": line.unit, "quantity": str(line.quantity),
                # Quantity already returned through credit notes; the rest can still be returned.
                "returned_quantity": str(Decimal(returned.get(line.id) or 0).quantize(QUANTITY_PLACES)),
                "unit_price": str(line.unit_price), "gst_rate": str(line.gst_rate),
                "taxable_value": str(line.taxable_value), "cgst_amount": str(line.cgst_amount),
                "sgst_amount": str(line.sgst_amount), "igst_amount": str(line.igst_amount),
                "line_total": str(line.line_total),
            }
            for line in lines
        ],
        "payments": [
            {"method": p.method, "amount": str(p.amount), "reference": p.reference}
            for p in payments
        ],
    }


def serialize_credit_note_summary(note: CreditNote) -> dict:
    """Compact row for lists: no lines."""
    return {
        "id": str(note.id), "credit_note_number": note.credit_note_number,
        "credit_note_date": note.credit_note_date.isoformat(), "sale_id": str(note.sale_id),
        "invoice_number": note.sale.invoice_number, "branch_id": str(note.branch_id),
        "reason": note.reason, "customer_name": note.customer_name,
        "grand_total": str(note.grand_total), "created_at": note.created_at.isoformat(),
    }


def serialize_credit_note(note: CreditNote) -> dict:
    """Full credit note body. The refund is always cash; ``refund_amount`` equals the total."""
    lines = CreditNoteLine.objects.for_tenant(note.tenant_id).filter(credit_note=note).order_by("id")
    return {
        "id": str(note.id), "credit_note_number": note.credit_note_number,
        "credit_note_date": note.credit_note_date.isoformat(), "sale_id": str(note.sale_id),
        "invoice_number": note.sale.invoice_number, "branch_id": str(note.branch_id),
        "reason": note.reason, "customer_name": note.customer_name,
        "seller_gstin": note.seller_gstin, "seller_state_code": note.seller_state_code,
        "place_of_supply_state_code": note.place_of_supply_state_code,
        "taxable_total": str(note.taxable_total), "cgst_total": str(note.cgst_total),
        "sgst_total": str(note.sgst_total), "igst_total": str(note.igst_total),
        "total_tax": str(note.total_tax), "round_off": str(note.round_off),
        "grand_total": str(note.grand_total), "refund_method": "cash",
        "refund_amount": str(note.grand_total), "created_at": note.created_at.isoformat(),
        "lines": [
            {
                "sale_line_id": str(line.sale_line_id), "product_id": str(line.product_id),
                "sku": line.sku, "name": line.name, "hsn_code": line.hsn_code, "unit": line.unit,
                "quantity": str(line.quantity), "unit_price": str(line.unit_price),
                "gst_rate": str(line.gst_rate), "taxable_value": str(line.taxable_value),
                "cgst_amount": str(line.cgst_amount), "sgst_amount": str(line.sgst_amount),
                "igst_amount": str(line.igst_amount), "line_total": str(line.line_total),
            }
            for line in lines
        ],
    }
