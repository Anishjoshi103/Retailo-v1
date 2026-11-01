import hashlib
import json

from django.db import IntegrityError, transaction
from django.db.models import F, Sum
from rest_framework import permissions, status
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.tenancy.permissions import require_membership_role

from .models import (
    InventoryBalance,
    PurchaseReceiptLine,
    PurchaseReturn,
    PurchaseReturnLine,
    StockMovement,
)
from .models import PurchaseReturnLine as ReturnLine
from .return_serializers import PurchaseReturnInputSerializer


class PurchaseReturnCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        membership = require_membership_role(
            request, {"owner", "admin", "manager"},
            "Store manager permissions are required to return goods to a supplier.",
        )
        tenant_id = membership.tenant_id
        membership_id = str(membership.pk)
        key = request.headers.get("Idempotency-Key", "").strip()
        if not key or len(key) > 128:
            return Response({"detail": "A valid Idempotency-Key header is required."}, status=status.HTTP_400_BAD_REQUEST)
        serializer = PurchaseReturnInputSerializer(data=request.data, context={"tenant_id": tenant_id, "membership_id": membership_id})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        canonical = {
            "receipt_id": str(data["receipt"].id),
            "reason": data["reason"].strip(),
            "lines": sorted([
                {"receipt_line_id": str(line["receipt_line"].id), "quantity": str(line["quantity"])}
                for line in data["lines"]
            ], key=lambda item: item["receipt_line_id"]),
        }
        request_hash = hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        try:
            with transaction.atomic():
                prior = PurchaseReturn.objects.for_tenant(tenant_id).filter(idempotency_key=key).first()
                if prior:
                    if prior.request_hash != request_hash:
                        return Response({"detail": "Idempotency-Key was already used for a different return."}, status=status.HTTP_409_CONFLICT)
                    return Response(self._response(prior, replayed=True), status=status.HTTP_200_OK)

                receipt = data["receipt"]
                # Lock each balance and receipt line before checking limits so concurrent returns serialize.
                locked_lines = list(PurchaseReceiptLine.objects.for_tenant(tenant_id).filter(
                    receipt=receipt, pk__in=[line["receipt_line"].id for line in data["lines"]]
                ).select_for_update().select_related("product"))
                by_id = {line.id: line for line in locked_lines}
                return_record = PurchaseReturn.objects.create(
                    tenant_id=tenant_id, receipt=receipt, branch=receipt.branch,
                    supplier_name=receipt.supplier_name, reason=data["reason"].strip(),
                    idempotency_key=key, request_hash=request_hash, created_by=request.user,
                )
                for requested in data["lines"]:
                    receipt_line = by_id[requested["receipt_line"].id]
                    already_returned = ReturnLine.objects.for_tenant(tenant_id).filter(
                        receipt_line=receipt_line
                    ).aggregate(total=Sum("quantity"))["total"] or 0
                    quantity = requested["quantity"]
                    if already_returned + quantity > receipt_line.quantity:
                        raise ValidationError({"lines": f"Return quantity exceeds remaining received quantity for product {receipt_line.product_id}."})
                    balance = InventoryBalance.objects.for_tenant(tenant_id).select_for_update().filter(
                        branch=receipt.branch, product=receipt_line.product
                    ).first()
                    if balance is None or balance.quantity_on_hand < quantity:
                        raise ValidationError({"lines": f"Insufficient on-hand stock to return product {receipt_line.product_id}."})
                    PurchaseReturnLine.objects.create(
                        tenant_id=tenant_id, purchase_return=return_record, receipt_line=receipt_line,
                        product=receipt_line.product, quantity=quantity,
                    )
                    InventoryBalance.objects.filter(pk=balance.pk).update(quantity_on_hand=F("quantity_on_hand") - quantity)
                    StockMovement.objects.create(
                        tenant_id=tenant_id, branch=receipt.branch, product=receipt_line.product,
                        quantity_delta=-quantity, reason=StockMovement.Reason.RETURN,
                        reference=str(return_record.id), idempotency_key=f"purchase-return:{return_record.id}:{receipt_line.product_id}",
                        note=f"Supplier return: {data['reason'].strip()}", created_by=request.user,
                    )
        except IntegrityError as exc:
            raise APIException("The return conflicted with another request. Retry with the same Idempotency-Key.") from exc
        return Response(self._response(return_record, replayed=False), status=status.HTTP_201_CREATED)

    @staticmethod
    def _response(return_record, replayed):
        return {
            "id": str(return_record.id), "receipt_id": str(return_record.receipt_id),
            "branch_id": str(return_record.branch_id), "supplier_name": return_record.supplier_name,
            "reason": return_record.reason, "returned_at": return_record.returned_at.isoformat(),
            "replayed": replayed,
            "lines": [
                {"receipt_line_id": str(line.receipt_line_id), "product_id": str(line.product_id), "quantity": str(line.quantity)}
                for line in return_record.lines.all().order_by("id")
            ],
        }
