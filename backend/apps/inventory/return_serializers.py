from decimal import Decimal

from rest_framework import serializers

from apps.tenancy.access import membership_can_access_branch
from apps.tenancy.models import Membership

from .models import PurchaseReceipt, PurchaseReceiptLine


class PurchaseReturnLineInputSerializer(serializers.Serializer):
    receipt_line_id = serializers.UUIDField()
    quantity = serializers.DecimalField(max_digits=14, decimal_places=3, min_value=Decimal("0.001"))


class PurchaseReturnInputSerializer(serializers.Serializer):
    receipt_id = serializers.UUIDField()
    reason = serializers.CharField(max_length=500, trim_whitespace=True)
    lines = PurchaseReturnLineInputSerializer(many=True, allow_empty=False, max_length=500)

    def validate(self, attrs):
        tenant_id = self.context["tenant_id"]
        receipt = PurchaseReceipt.objects.for_tenant(tenant_id).filter(pk=attrs["receipt_id"]).first()
        membership = Membership.objects.filter(pk=self.context["membership_id"], tenant_id=tenant_id, is_active=True, tenant__status="active").first()
        if receipt is None or membership is None or not membership_can_access_branch(membership, receipt.branch_id):
            raise serializers.ValidationError({"receipt_id": "Select a purchase receipt from an assigned branch in your store."})
        if not attrs["reason"].strip():
            raise serializers.ValidationError({"reason": "A return reason is required."})
        line_ids = [line["receipt_line_id"] for line in attrs["lines"]]
        if len(set(line_ids)) != len(line_ids):
            raise serializers.ValidationError({"lines": "Each receipt line may appear only once per return."})
        receipt_lines = PurchaseReceiptLine.objects.for_tenant(tenant_id).filter(receipt=receipt, pk__in=line_ids).select_related("product")
        by_id = {line.id: line for line in receipt_lines}
        if set(by_id) != set(line_ids):
            raise serializers.ValidationError({"lines": "Every line must belong to the selected receipt and tenant."})
        for line in attrs["lines"]:
            line["receipt_line"] = by_id[line["receipt_line_id"]]
        attrs["receipt"] = receipt
        return attrs
