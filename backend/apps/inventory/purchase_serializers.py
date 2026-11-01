from decimal import Decimal

from rest_framework import serializers

from apps.catalog.models import Product
from apps.tenancy.models import Branch

from .models import Supplier


class PurchaseReceiptLineInputSerializer(serializers.Serializer):
    product_id = serializers.UUIDField()
    quantity = serializers.DecimalField(max_digits=14, decimal_places=3, min_value=Decimal("0.001"))
    unit_cost = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0"))


class PurchaseReceiptInputSerializer(serializers.Serializer):
    branch_id = serializers.UUIDField()
    supplier_id = serializers.UUIDField(required=False)
    supplier_name = serializers.CharField(max_length=180, required=False, allow_blank=True, trim_whitespace=True)
    supplier_invoice_number = serializers.CharField(max_length=80, required=False, allow_blank=True, trim_whitespace=True)
    lines = PurchaseReceiptLineInputSerializer(many=True, allow_empty=False, max_length=500)

    def validate(self, attrs):
        tenant_id = self.context["tenant_id"]
        branch = Branch.objects.for_tenant(tenant_id).filter(pk=attrs["branch_id"], is_active=True).first()
        if branch is None:
            raise serializers.ValidationError({"branch_id": "Select an active branch in your store."})
        product_ids = [line["product_id"] for line in attrs["lines"]]
        if len(set(product_ids)) != len(product_ids):
            raise serializers.ValidationError({"lines": "Each product may appear only once per receipt; combine quantities for duplicate products."})
        products = Product.objects.for_tenant(tenant_id).filter(pk__in=product_ids, is_active=True)
        by_id = {product.id: product for product in products}
        if set(by_id) != set(product_ids):
            raise serializers.ValidationError({"lines": "Every product must be active and belong to your store."})
        for line in attrs["lines"]:
            line["product"] = by_id[line["product_id"]]
        supplier = None
        supplier_id = attrs.get("supplier_id")
        supplier_name = attrs.get("supplier_name", "").strip()
        if supplier_id:
            supplier = Supplier.objects.for_tenant(tenant_id).filter(pk=supplier_id, is_active=True).first()
            if supplier is None:
                raise serializers.ValidationError({"supplier_id": "Select an active supplier in your store."})
            if supplier_name and supplier_name != supplier.name:
                raise serializers.ValidationError({"supplier_name": "Supplier name is taken from the selected supplier record."})
            supplier_name = supplier.name
        if not supplier_name:
            raise serializers.ValidationError({"supplier_name": "Provide a supplier name or select a supplier record."})
        attrs["supplier"] = supplier
        attrs["supplier_name"] = supplier_name
        attrs["branch"] = branch
        return attrs
