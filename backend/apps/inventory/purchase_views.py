import hashlib
import json

from django.db import IntegrityError, transaction
from django.db.models import F
from rest_framework import permissions, status
from rest_framework.exceptions import APIException, PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.tenancy.models import Membership
from .models import InventoryBalance, PurchaseReceipt, PurchaseReceiptLine, StockMovement
from .purchase_serializers import PurchaseReceiptInputSerializer
from .views import active_tenant_membership


class PurchaseReceiptCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        tenant_id = active_tenant_membership(request)
        membership_id = request.auth.get("membership_id") if request.auth else None
        membership = Membership.objects.filter(pk=membership_id, tenant_id=tenant_id, user=request.user, is_active=True).first()
        if membership is None or membership.role not in {Membership.Role.OWNER, Membership.Role.ADMIN, Membership.Role.MANAGER}:
            raise PermissionDenied("Store manager permissions are required to receive stock.")
        key = request.headers.get("Idempotency-Key", "").strip()
        if not key or len(key) > 128:
            return Response({"detail": "A valid Idempotency-Key header is required."}, status=status.HTTP_400_BAD_REQUEST)
        serializer = PurchaseReceiptInputSerializer(data=request.data, context={"tenant_id": tenant_id})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        canonical = {
            "branch_id": str(data["branch"].id),
            "supplier_id": str(data["supplier"].id) if data.get("supplier") else None,
            "supplier_name": data["supplier_name"],
            "supplier_invoice_number": data.get("supplier_invoice_number", ""),
            "lines": sorted([
                {"product_id": str(line["product"].id), "quantity": str(line["quantity"]), "unit_cost": str(line["unit_cost"])}
                for line in data["lines"]
            ], key=lambda item: (item["product_id"], item["quantity"], item["unit_cost"])),
        }
        request_hash = hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        try:
            with transaction.atomic():
                prior = PurchaseReceipt.objects.for_tenant(tenant_id).filter(idempotency_key=key).first()
                if prior:
                    if prior.request_hash != request_hash:
                        return Response({"detail": "Idempotency-Key was already used for a different receipt."}, status=status.HTTP_409_CONFLICT)
                    return Response(self._response(prior, replayed=True), status=status.HTTP_200_OK)
                receipt = PurchaseReceipt.objects.create(
                    tenant_id=tenant_id, branch=data["branch"], supplier=data.get("supplier"), supplier_name=data["supplier_name"],
                    supplier_invoice_number=data.get("supplier_invoice_number", ""), idempotency_key=key,
                    request_hash=request_hash, created_by=request.user,
                )
                for line in data["lines"]:
                    PurchaseReceiptLine.objects.create(
                        tenant_id=tenant_id, receipt=receipt, product=line["product"],
                        quantity=line["quantity"], unit_cost=line["unit_cost"],
                    )
                    balance, _ = InventoryBalance.objects.get_or_create(tenant_id=tenant_id, branch=data["branch"], product=line["product"])
                    InventoryBalance.objects.filter(pk=balance.pk).update(quantity_on_hand=F("quantity_on_hand") + line["quantity"])
                    StockMovement.objects.create(
                        tenant_id=tenant_id, branch=data["branch"], product=line["product"], quantity_delta=line["quantity"],
                        reason=StockMovement.Reason.RECEIPT, reference=str(receipt.id),
                        idempotency_key=f"receipt:{receipt.id}:{line['product'].id}", note=f"Goods received from {data['supplier_name']}", created_by=request.user,
                    )
        except IntegrityError as exc:
            raise APIException("The receipt conflicted with another request. Retry with the same Idempotency-Key.") from exc
        return Response(self._response(receipt, replayed=False), status=status.HTTP_201_CREATED)

    @staticmethod
    def _response(receipt, replayed):
        return {
            "id": str(receipt.id), "branch_id": str(receipt.branch_id),
            "supplier_id": str(receipt.supplier_id) if receipt.supplier_id else None,
            "supplier_name": receipt.supplier_name, "supplier_invoice_number": receipt.supplier_invoice_number,
            "received_at": receipt.received_at.isoformat(), "replayed": replayed,
            "lines": [{"product_id": str(line.product_id), "quantity": str(line.quantity), "unit_cost": str(line.unit_cost)} for line in receipt.lines.all().order_by("id")],
        }
