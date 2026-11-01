from rest_framework import serializers

from apps.catalog.models import Product
from apps.tenancy.models import Branch
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
        branch = Branch.objects.for_tenant(tenant_id).filter(pk=attrs["branch_id"], is_active=True).first()
        product = Product.objects.for_tenant(tenant_id).filter(pk=attrs["product_id"], is_active=True).first()
        if branch is None or product is None:
            raise serializers.ValidationError("Select an active branch and product in your store.")
        attrs["branch"] = branch
        attrs["product"] = product
        return attrs
