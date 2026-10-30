from decimal import Decimal

from rest_framework import serializers

from .models import Product


class ProductSerializer(serializers.ModelSerializer):
    selling_price = serializers.DecimalField(max_digits=12, decimal_places=2, coerce_to_string=True)
    purchase_price = serializers.DecimalField(max_digits=12, decimal_places=2, coerce_to_string=True)
    gst_rate = serializers.DecimalField(max_digits=5, decimal_places=2, coerce_to_string=True)

    class Meta:
        model = Product
        fields = ["id", "sku", "barcode", "name", "description", "unit", "hsn_code", "gst_rate", "selling_price", "purchase_price", "is_active", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_sku(self, value):
        value = value.strip().upper()
        tenant_id = self.context["tenant_id"]
        qs = Product.objects.for_tenant(tenant_id).filter(sku=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("This SKU already exists in the store.")
        return value

    def validate_barcode(self, value):
        value = value.strip() or None
        if value:
            qs = Product.objects.for_tenant(self.context["tenant_id"]).filter(barcode=value)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError("This barcode already exists in the store.")
        return value

    def validate_hsn_code(self, value):
        value = value.strip()
        if value and (not value.isdigit() or len(value) not in (4, 6, 8)):
            raise serializers.ValidationError("HSN must contain 4, 6, or 8 digits.")
        return value

    def validate_gst_rate(self, value: Decimal):
        if value not in {Decimal("0"), Decimal("0.25"), Decimal("3"), Decimal("5"), Decimal("12"), Decimal("18"), Decimal("28")}:
            raise serializers.ValidationError("Use a configured GST rate: 0, 0.25, 3, 5, 12, 18, or 28 percent.")
        return value
