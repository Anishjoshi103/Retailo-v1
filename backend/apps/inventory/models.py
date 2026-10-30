import uuid

from django.conf import settings
from django.db import models
from apps.tenancy.models import TenantOwnedModel, TenantQuerySet


class ImmutableQuerySet(TenantQuerySet):
    def update(self, **kwargs):
        raise TypeError("Stock movements are append-only.")

    def delete(self):
        raise TypeError("Stock movements are append-only.")


class StockMovement(TenantOwnedModel):
    class Reason(models.TextChoices):
        OPENING = "opening", "Opening stock"
        RECEIPT = "receipt", "Goods received"
        SALE = "sale", "Sale"
        RETURN = "return", "Return"
        ADJUSTMENT = "adjustment", "Manual adjustment"
        REVERSAL = "reversal", "Reversal"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    branch = models.ForeignKey("tenancy.Branch", on_delete=models.PROTECT, related_name="stock_movements")
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT, related_name="stock_movements")
    quantity_delta = models.DecimalField(max_digits=14, decimal_places=3)
    reason = models.CharField(max_length=16, choices=Reason.choices)
    reference = models.CharField(max_length=120, blank=True)
    idempotency_key = models.CharField(max_length=128, blank=True)
    note = models.CharField(max_length=500, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    objects = ImmutableQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.CheckConstraint(condition=~models.Q(quantity_delta=0), name="ck_stock_movement_nonzero"),
            models.UniqueConstraint(fields=["tenant", "idempotency_key"], condition=~models.Q(idempotency_key=""), name="uq_stock_move_tenant_idem"),
        ]
        indexes = [models.Index(fields=["tenant", "branch", "product", "created_at"], name="ix_stock_move_lookup")]

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise TypeError("Stock movements are append-only; create a reversal instead.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise TypeError("Stock movements are append-only; create a reversal instead.")


class InventoryBalance(TenantOwnedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    branch = models.ForeignKey("tenancy.Branch", on_delete=models.PROTECT, related_name="inventory_balances")
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT, related_name="inventory_balances")
    quantity_on_hand = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["tenant", "branch", "product"], name="uq_inventory_tenant_branch_product"),
        ]
        indexes = [models.Index(fields=["tenant", "branch", "product"], name="ix_inventory_lookup")]
