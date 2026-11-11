import hashlib
import json
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.db.models import F, Sum
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.exceptions import APIException, NotFound, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.inventory.models import InventoryBalance, StockMovement
from apps.sales.models import CreditNote, CreditNoteLine, Sale, SaleLine
from apps.sales.numbering import InvoiceNumberError, allocate_credit_note_number
from apps.sales.presenters import serialize_credit_note
from apps.sales.returns import price_return
from apps.sales.serializers import ReturnInputSerializer
from apps.tenancy.access import authorized_branches
from apps.tenancy.permissions import require_membership_role

RETURNING_ROLES = {"owner", "admin", "manager", "cashier"}


class SaleReturnView(APIView):
    """Issue a credit note for part or all of a sale: stock goes back, the refund is cash."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, sale_id):
        membership = require_membership_role(
            request, RETURNING_ROLES, "Cashier, manager or administrator permissions are required to take returns."
        )
        tenant_id = membership.tenant_id
        key = request.headers.get("Idempotency-Key", "").strip()
        if not key or len(key) > 128:
            return Response({"detail": "A valid Idempotency-Key header is required."}, status=status.HTTP_400_BAD_REQUEST)
        sale = Sale.objects.for_tenant(tenant_id).filter(
            pk=sale_id, branch__in=authorized_branches(membership)
        ).select_related("branch").first()
        # Unknown, foreign-store and ungranted-branch sales are indistinguishable.
        if sale is None:
            raise NotFound("Sale not found.")
        serializer = ReturnInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        request_hash = self._request_hash(sale, data)

        try:
            with transaction.atomic():
                prior = CreditNote.objects.for_tenant(tenant_id).filter(idempotency_key=key).first()
                if prior:
                    return self._replay(prior, request_hash)
                # Serialise concurrent returns of the same sale before reading what was returned.
                Sale.objects.for_tenant(tenant_id).select_for_update().filter(pk=sale.pk).first()
                try:
                    number = allocate_credit_note_number(tenant_id=tenant_id, branch=sale.branch)
                except InvoiceNumberError as exc:
                    raise ValidationError({"branch_id": str(exc)}) from exc
                items = self._validated_items(tenant_id, sale, data["lines"])
                priced = price_return(items)
                note = CreditNote.objects.create(
                    tenant_id=tenant_id, branch=sale.branch, sale=sale, credit_note_number=number,
                    credit_note_date=timezone.localdate(), seller_gstin=sale.seller_gstin,
                    seller_state_code=sale.seller_state_code,
                    place_of_supply_state_code=sale.place_of_supply_state_code,
                    customer_name=sale.customer_name, customer_gstin=sale.customer_gstin,
                    taxable_total=priced.taxable_total, cgst_total=priced.cgst_total,
                    sgst_total=priced.sgst_total, igst_total=priced.igst_total,
                    total_tax=priced.total_tax, round_off=priced.round_off, grand_total=priced.grand_total,
                    reason=data["reason"], idempotency_key=key, request_hash=request_hash,
                    created_by=request.user,
                )
                for line in priced.lines:
                    sale_line = line.sale_line
                    CreditNoteLine.objects.create(
                        tenant_id=tenant_id, credit_note=note, sale_line=sale_line,
                        product_id=sale_line.product_id, sku=sale_line.sku, name=sale_line.name,
                        hsn_code=sale_line.hsn_code, unit=sale_line.unit, quantity=line.quantity,
                        unit_price=sale_line.unit_price, gst_rate=sale_line.gst_rate,
                        taxable_value=line.taxable_value, cgst_amount=line.cgst_amount,
                        sgst_amount=line.sgst_amount, igst_amount=line.igst_amount,
                        line_total=line.line_total,
                    )
                    self._restock(tenant_id, sale, note, sale_line, line.quantity, request.user)
        except IntegrityError as exc:
            # A competing request may have committed the same key after our lookup.
            prior = CreditNote.objects.for_tenant(tenant_id).filter(idempotency_key=key).first()
            if prior is not None:
                return self._replay(prior, request_hash)
            raise APIException("The return conflicted with another request. Retry with the same Idempotency-Key.") from exc
        return Response({**serialize_credit_note(note), "replayed": False}, status=status.HTTP_201_CREATED)

    @staticmethod
    def _request_hash(sale, data) -> str:
        canonical = {
            "sale_id": str(sale.id),
            "reason": data["reason"],
            "lines": sorted(
                ({"sale_line_id": str(line["sale_line_id"]), "quantity": str(line["quantity"])} for line in data["lines"]),
                key=lambda item: item["sale_line_id"],
            ),
        }
        return hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    @staticmethod
    def _validated_items(tenant_id, sale, requested):
        """Check every line belongs to the sale and the total returned never exceeds what was sold."""
        sale_lines = {
            line.id: line for line in SaleLine.objects.for_tenant(tenant_id).filter(sale=sale)
        }
        if any(item["sale_line_id"] not in sale_lines for item in requested):
            raise ValidationError({"lines": "Select items from this sale."})
        returned = {
            row["sale_line_id"]: row["total"]
            for row in CreditNoteLine.objects.for_tenant(tenant_id)
            .filter(sale_line_id__in=[item["sale_line_id"] for item in requested])
            .values("sale_line_id").annotate(total=Sum("quantity"))
        }
        items = []
        for item in requested:
            sale_line = sale_lines[item["sale_line_id"]]
            before = returned.get(sale_line.id) or Decimal("0")
            remaining = sale_line.quantity - before
            if item["quantity"] > remaining:
                raise ValidationError({"lines": (
                    f"Cannot return {item['quantity']} of {sale_line.sku}: "
                    f"only {remaining} of {sale_line.quantity} sold can still be returned."
                )})
            items.append((sale_line, before, item["quantity"]))
        return items

    @staticmethod
    def _restock(tenant_id, sale, note, sale_line, quantity, user):
        balances = InventoryBalance.objects.for_tenant(tenant_id)
        balance = balances.select_for_update().filter(branch=sale.branch, product_id=sale_line.product_id).first()
        if balance is None:
            balance, _ = balances.get_or_create(
                tenant_id=tenant_id, branch=sale.branch, product_id=sale_line.product_id
            )
        balances.filter(pk=balance.pk).update(quantity_on_hand=F("quantity_on_hand") + quantity)
        StockMovement.objects.create(
            tenant_id=tenant_id, branch=sale.branch, product_id=sale_line.product_id,
            quantity_delta=quantity, reason=StockMovement.Reason.RETURN,
            reference=note.credit_note_number, idempotency_key=f"credit-note:{note.id}:{sale_line.product_id}",
            note=f"Customer return against {sale.invoice_number}", created_by=user,
        )

    @staticmethod
    def _replay(prior, request_hash):
        if prior.request_hash != request_hash:
            return Response({"detail": "Idempotency-Key was already used for a different return."}, status=status.HTTP_409_CONFLICT)
        return Response({**serialize_credit_note(prior), "replayed": True}, status=status.HTTP_200_OK)
