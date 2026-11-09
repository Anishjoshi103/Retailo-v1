from apps.sales.models import Sale, SaleLine, SalePayment


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
                "product_id": str(line.product_id), "sku": line.sku, "name": line.name,
                "hsn_code": line.hsn_code, "unit": line.unit, "quantity": str(line.quantity),
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
