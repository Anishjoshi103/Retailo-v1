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


class PurchaseReceipt(TenantOwnedModel):
    """Posted goods receipt; corrections are represented by compensating movements."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    branch = models.ForeignKey("tenancy.Branch", on_delete=models.PROTECT, related_name="purchase_receipts")
    supplier = models.ForeignKey("Supplier", on_delete=models.PROTECT, null=True, blank=True, related_name="receipts")
    supplier_name = models.CharField(max_length=180)
    supplier_invoice_number = models.CharField(max_length=80, blank=True)
    idempotency_key = models.CharField(max_length=128)
    request_hash = models.CharField(max_length=64)
    received_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)

    class Meta:
        ordering = ["-received_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "idempotency_key"], name="uq_receipt_tenant_idem"),
        ]
        indexes = [models.Index(fields=["tenant", "branch", "received_at"], name="ix_receipt_tenant_branch_date")]

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise TypeError("Posted purchase receipts are immutable.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise TypeError("Posted purchase receipts are immutable; use compensating movements.")


class PurchaseReceiptLine(TenantOwnedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    receipt = models.ForeignKey(PurchaseReceipt, on_delete=models.PROTECT, related_name="lines")
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT, related_name="purchase_receipt_lines")
    quantity = models.DecimalField(max_digits=14, decimal_places=3)
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="ck_receipt_line_qty_positive"),
            models.CheckConstraint(condition=models.Q(unit_cost__gte=0), name="ck_receipt_line_cost_nonnegative"),
        ]

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise TypeError("Posted purchase receipt lines are immutable.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise TypeError("Posted purchase receipt lines are immutable.")


class Supplier(TenantOwnedModel):
    """Tenant-owned supplier master; receipts retain supplier snapshots for audit."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=180)
    gstin = models.CharField(max_length=15, blank=True)
    phone = models.CharField(max_length=32, blank=True)
    email = models.EmailField(max_length=254, blank=True)
    address = models.CharField(max_length=500, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "gstin"],
                condition=~models.Q(gstin=""),
                name="uq_supplier_tenant_gstin",
            ),
        ]
        indexes = [models.Index(fields=["tenant", "is_active", "name"], name="ix_supplier_tenant_active_name")]

    def __str__(self):
        return f"{self.name} ({self.gstin})" if self.gstin else self.name
