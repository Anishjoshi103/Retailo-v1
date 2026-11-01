from rest_framework import serializers

from apps.catalog.models import Product
from apps.tenancy.access import membership_can_access_branch
from apps.tenancy.models import Branch, Membership

from .models import InventoryBalance


class InventoryBalanceSerializer(serializers.ModelSerializer):
    product_sku = serializers.CharField(source="product.sku", read_only=True)
    product_name = serializers.CharField(source="product.name", read_only=True)
    quantity_on_hand = serializers.DecimalField(max_digits=14, decimal_places=3, coerce_to_string=True)

    class Meta:
        model = InventoryBalance
        fields = ["id", "branch", "product", "product_sku", "product_name", "quantity_on_hand", "updated_at"]
        read_only_fields = fields


class StockAdjustmentSerializer(serializers.Serializer):
    branch_id = serializers.UUIDField()
    product_id = serializers.UUIDField()
    quantity_delta = serializers.DecimalField(max_digits=14, decimal_places=3, coerce_to_string=True)
    note = serializers.CharField(max_length=500, required=False, allow_blank=True)
    reference = serializers.CharField(max_length=120, required=False, allow_blank=True)

    def validate_quantity_delta(self, value):
        if value == 0:
            raise serializers.ValidationError("Quantity adjustment must not be zero.")
        return value

    def validate(self, attrs):
        tenant_id = self.context["tenant_id"]
        membership = Membership.objects.filter(pk=self.context["membership_id"], tenant_id=tenant_id, is_active=True, tenant__status="active").first()
        branch = Branch.objects.for_tenant(tenant_id).filter(pk=attrs["branch_id"], is_active=True).first()
        if membership is None or not membership_can_access_branch(membership, attrs["branch_id"]):
            raise serializers.ValidationError({"branch_id": "Select a branch assigned to your membership."})
        product = Product.objects.for_tenant(tenant_id).filter(pk=attrs["product_id"], is_active=True).first()
        if branch is None or product is None:
            raise serializers.ValidationError("Select an active branch and product in your store.")
        attrs["branch"] = branch
        attrs["product"] = product
        return attrs
