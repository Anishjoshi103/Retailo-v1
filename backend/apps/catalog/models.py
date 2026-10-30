import uuid

from django.db import models

from apps.tenancy.models import TenantOwnedModel


class Product(TenantOwnedModel):
    class Unit(models.TextChoices):
        EACH = "each", "Each"
        KG = "kg", "Kilogram"
        G = "g", "Gram"
        L = "l", "Litre"
        ML = "ml", "Millilitre"
        M = "m", "Metre"
        PACK = "pack", "Pack"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sku = models.CharField(max_length=64)
    barcode = models.CharField(max_length=64, blank=True, null=True)
    name = models.CharField(max_length=180)
    description = models.CharField(max_length=500, blank=True)
    unit = models.CharField(max_length=8, choices=Unit.choices, default=Unit.EACH)
    hsn_code = models.CharField(max_length=8, blank=True)
    gst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    selling_price = models.DecimalField(max_digits=12, decimal_places=2)
    purchase_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "id"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "sku"], name="uq_product_tenant_sku"),
            models.CheckConstraint(condition=models.Q(gst_rate__gte=0, gst_rate__lte=100), name="ck_product_gst_rate_range"),
            models.CheckConstraint(condition=models.Q(selling_price__gte=0), name="ck_product_selling_price_nonnegative"),
            models.CheckConstraint(condition=models.Q(purchase_price__gte=0), name="ck_product_purchase_price_nonnegative"),
        ]
        indexes = [models.Index(fields=["tenant", "is_active", "name"], name="ix_product_tenant_active_name")]

    def __str__(self):
        return f"{self.tenant_id}:{self.sku} {self.name}"
