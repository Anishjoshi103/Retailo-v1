"""Read access to posted goods receipts (cost data, so owners, admins, managers and accountants only)."""

from decimal import ROUND_HALF_UP, Decimal

from rest_framework import permissions
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.tenancy.access import authorized_branches
from apps.tenancy.listing import filter_documents, page_bounds, uuid_param
from apps.tenancy.permissions import require_membership_role

from .models import PurchaseReceipt, PurchaseReceiptLine
from .purchase_views import PurchaseReceiptCreateView

RECEIPT_READERS = {"owner", "admin", "manager", "accountant"}
PAISE = Decimal("0.01")


def _line_total(quantity: Decimal, unit_cost: Decimal) -> Decimal:
    """Cost of one line, rounded half-up to paise (the same rule the Receive goods screen shows)."""
    return (quantity * unit_cost).quantize(PAISE, rounding=ROUND_HALF_UP)


def _summary(receipt: PurchaseReceipt, line_count: int, total: Decimal) -> dict:
    return {
        "id": str(receipt.id), "branch_id": str(receipt.branch_id),
        "supplier_id": str(receipt.supplier_id) if receipt.supplier_id else None,
        "supplier_name": receipt.supplier_name,
        "supplier_invoice_number": receipt.supplier_invoice_number,
        "received_at": receipt.received_at.isoformat(), "line_count": line_count, "total_cost": str(total),
    }


class PurchaseReceiptListCreateView(PurchaseReceiptCreateView):
    """``POST`` records a delivery (see PurchaseReceiptCreateView); ``GET`` lists them, newest first."""

    def get(self, request):
        membership = require_membership_role(request, RECEIPT_READERS, "Purchase records are not available to your role.")
        queryset = PurchaseReceipt.objects.for_tenant(membership.tenant_id).filter(
            branch__in=authorized_branches(membership)
        )
        queryset = filter_documents(
            queryset, request.query_params, membership, date_field="received_at__date", number_field=None
        )
        supplier_id = uuid_param(request.query_params, "supplier_id")
        if supplier_id is not None:
            queryset = queryset.filter(supplier_id=supplier_id)
        invoice = request.query_params.get("invoice_number", "").strip()
        if invoice:
            queryset = queryset.filter(supplier_invoice_number__icontains=invoice)
        start, stop = page_bounds(request.query_params)
        receipts = list(queryset[start:stop])
        totals: dict = {receipt.id: [0, Decimal("0.00")] for receipt in receipts}
        for row in (
            PurchaseReceiptLine.objects.for_tenant(membership.tenant_id)
            .filter(receipt_id__in=list(totals)).order_by().values("receipt_id", "quantity", "unit_cost")
        ):
            totals[row["receipt_id"]][0] += 1
            totals[row["receipt_id"]][1] += _line_total(row["quantity"], row["unit_cost"])
        return Response([_summary(receipt, *totals[receipt.id]) for receipt in receipts])


class PurchaseReceiptDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, receipt_id):
        membership = require_membership_role(request, RECEIPT_READERS, "Purchase records are not available to your role.")
        receipt = PurchaseReceipt.objects.for_tenant(membership.tenant_id).filter(
            pk=receipt_id, branch__in=authorized_branches(membership)
        ).first()
        # Unknown, foreign-store and ungranted-branch receipts are indistinguishable.
        if receipt is None:
            raise NotFound("Receipt not found.")
        lines = (
            PurchaseReceiptLine.objects.for_tenant(membership.tenant_id).filter(receipt=receipt)
            .select_related("product").order_by("product__name", "id")
        )
        rows = [
            {
                "id": str(line.id), "product_id": str(line.product_id), "sku": line.product.sku,
                "name": line.product.name, "unit": line.product.unit, "quantity": str(line.quantity),
                "unit_cost": str(line.unit_cost), "line_total": str(_line_total(line.quantity, line.unit_cost)),
            }
            for line in lines
        ]
        total = sum((Decimal(row["line_total"]) for row in rows), Decimal("0.00"))
        return Response({**_summary(receipt, len(rows), total), "lines": rows})
