import re

from rest_framework import serializers

from .models import Supplier


class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = ["id", "name", "gstin", "phone", "email", "address", "is_active", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Supplier name is required.")
        return value

    def validate_gstin(self, value):
        value = value.strip().upper()
        if value and not re.fullmatch(r"[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]", value):
            raise serializers.ValidationError("Enter a GSTIN in the expected 15-character format.")
        others = Supplier.objects.for_tenant(self.context["tenant_id"]).filter(gstin=value)
        if self.instance is not None:
            others = others.exclude(pk=self.instance.pk)  # editing a supplier must not collide with itself
        if value and others.exists():
            raise serializers.ValidationError("A supplier with this GSTIN already exists in this store.")
        return value
