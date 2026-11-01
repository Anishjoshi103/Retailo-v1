from django.db import IntegrityError, transaction
from django.db.models import F
from rest_framework import generics, permissions, status
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.tenancy.access import authorized_branches
from apps.tenancy.permissions import active_tenant_membership, require_membership_role

from .models import InventoryBalance, StockMovement
from .serializers import InventoryBalanceSerializer, StockAdjustmentSerializer


class InventoryBalanceListView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = InventoryBalanceSerializer

    def get_queryset(self):
        membership = active_tenant_membership(self.request)
        tenant_id = membership.tenant_id
        queryset = InventoryBalance.objects.for_tenant(tenant_id).filter(
            branch__in=authorized_branches(membership),
            branch__tenant_id=tenant_id,
        ).select_related("product", "branch")
        branch_id = self.request.query_params.get("branch_id")
        product_id = self.request.query_params.get("product_id")
        if branch_id:
            queryset = queryset.filter(branch_id=branch_id)
        if product_id:
            queryset = queryset.filter(product_id=product_id)
        return queryset


class StockAdjustmentView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        membership = require_membership_role(
            request, {"owner", "admin", "manager"},
            "Store manager permissions are required to adjust stock.",
        )
        tenant_id = membership.tenant_id
        membership_id = str(membership.pk)
        key = request.headers.get("Idempotency-Key", "").strip()
        if not key or len(key) > 128:
            return Response({"detail": "A valid Idempotency-Key header is required."}, status=status.HTTP_400_BAD_REQUEST)
        serializer = StockAdjustmentSerializer(data=request.data, context={"tenant_id": tenant_id, "membership_id": membership_id})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            with transaction.atomic():
                prior = StockMovement.objects.for_tenant(tenant_id).filter(idempotency_key=key).first()
                if prior:
                    if prior.branch_id != data["branch"].id or prior.product_id != data["product"].id or prior.quantity_delta != data["quantity_delta"]:
                        return Response({"detail": "Idempotency-Key was already used for a different adjustment."}, status=status.HTTP_409_CONFLICT)
                    balance = InventoryBalance.objects.for_tenant(tenant_id).get(branch=prior.branch, product=prior.product)
                    return Response({"movement_id": str(prior.id), "quantity_on_hand": str(balance.quantity_on_hand), "replayed": True}, status=status.HTTP_200_OK)
                balance, _ = InventoryBalance.objects.get_or_create(tenant_id=tenant_id, branch=data["branch"], product=data["product"])
                InventoryBalance.objects.filter(pk=balance.pk).update(quantity_on_hand=F("quantity_on_hand") + data["quantity_delta"])
                balance.refresh_from_db(fields=["quantity_on_hand", "updated_at"])
                movement = StockMovement.objects.create(
                    tenant_id=tenant_id, branch=data["branch"], product=data["product"], quantity_delta=data["quantity_delta"],
                    reason=StockMovement.Reason.ADJUSTMENT, reference=data.get("reference", ""), idempotency_key=key,
                    note=data.get("note", ""), created_by=request.user,
                )
        except IntegrityError as exc:
            raise APIException("The stock adjustment conflicted with another update. Retry with the same Idempotency-Key.") from exc
        return Response({"movement_id": str(movement.id), "quantity_on_hand": str(balance.quantity_on_hand), "replayed": False}, status=status.HTTP_201_CREATED)
