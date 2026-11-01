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
    objects: models.Manager[StockMovement] = ImmutableQuerySet.as_manager()

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


class PurchaseReturn(TenantOwnedModel):
    """Posted supplier return; stock corrections are represented by immutable return records."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    receipt = models.ForeignKey(PurchaseReceipt, on_delete=models.PROTECT, related_name="returns")
    branch = models.ForeignKey("tenancy.Branch", on_delete=models.PROTECT, related_name="purchase_returns")
    supplier_name = models.CharField(max_length=180)
    reason = models.CharField(max_length=500)
    idempotency_key = models.CharField(max_length=128)
    request_hash = models.CharField(max_length=64)
    returned_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)

    class Meta:
        ordering = ["-returned_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "idempotency_key"], name="uq_purchase_return_tenant_idem"),
        ]
        indexes = [models.Index(fields=["tenant", "receipt", "returned_at"], name="ix_return_tenant_receipt_date")]

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise TypeError("Posted purchase returns are immutable.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise TypeError("Posted purchase returns are immutable.")


class PurchaseReturnLine(TenantOwnedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    purchase_return = models.ForeignKey(PurchaseReturn, on_delete=models.PROTECT, related_name="lines")
    receipt_line = models.ForeignKey(PurchaseReceiptLine, on_delete=models.PROTECT, related_name="return_lines")
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT, related_name="purchase_return_lines")
    quantity = models.DecimalField(max_digits=14, decimal_places=3)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(quantity__gt=0), name="ck_purchase_return_qty_positive")]

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise TypeError("Posted purchase return lines are immutable.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise TypeError("Posted purchase return lines are immutable.")



class PurchaseInvoice(TenantOwnedModel):
    """Supplier tax invoice snapshot; stock is not changed by invoice recording."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        POSTED = "posted", "Posted"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name="purchase_invoices")
    branch = models.ForeignKey("tenancy.Branch", on_delete=models.PROTECT, related_name="purchase_invoices")
    supplier_name = models.CharField(max_length=180)
    supplier_gstin = models.CharField(max_length=15, blank=True)
    supplier_state_code = models.CharField(max_length=2)
    place_of_supply_state_code = models.CharField(max_length=2)
    invoice_number = models.CharField(max_length=80, blank=True)
    invoice_date = models.DateField()
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.DRAFT)
    taxable_total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    tax_total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    idempotency_key = models.CharField(max_length=128)
    request_hash = models.CharField(max_length=64)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    posted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-invoice_date", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "idempotency_key"], name="uq_purchase_invoice_tenant_idem"),
            models.UniqueConstraint(
                fields=["tenant", "supplier", "invoice_number"],
                condition=~models.Q(invoice_number=""),
                name="uq_purchase_invoice_supplier_number",
            ),
            models.CheckConstraint(
                condition=models.Q(taxable_total__gte=0) & models.Q(tax_total__gte=0) & models.Q(total_amount__gte=0),
                name="ck_purchase_invoice_totals_nonnegative",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "supplier", "invoice_date"], name="ix_pi_supplier_date"),
            models.Index(fields=["tenant", "branch", "status"], name="ix_pi_branch_status"),
        ]

    def save(self, *args, **kwargs):
        if self.pk:
            existing = type(self).objects.filter(pk=self.pk).first()
            if existing and existing.status == self.Status.POSTED:
                raise TypeError("Posted purchase invoices are immutable; use a reversal or credit note.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.status == self.Status.POSTED:
            raise TypeError("Posted purchase invoices are immutable; use a reversal or credit note.")
        super().delete(*args, **kwargs)


class PurchaseInvoiceLine(TenantOwnedModel):
    """Billed line with a persisted, auditable GST calculation snapshot."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice = models.ForeignKey(PurchaseInvoice, on_delete=models.PROTECT, related_name="lines")
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT, related_name="purchase_invoice_lines")
    description_snapshot = models.CharField(max_length=240)
    hsn_code = models.CharField(max_length=16, blank=True)
    quantity = models.DecimalField(max_digits=14, decimal_places=3)
    unit_price = models.DecimalField(max_digits=14, decimal_places=4)
    discount_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    taxable_value = models.DecimalField(max_digits=14, decimal_places=2)
    gst_rate = models.DecimalField(max_digits=5, decimal_places=2)
    cgst_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    sgst_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    igst_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_tax = models.DecimalField(max_digits=14, decimal_places=2)
    total_amount = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="ck_purchase_invoice_line_qty_positive"),
            models.CheckConstraint(condition=models.Q(unit_price__gte=0), name="ck_purchase_invoice_line_price_nonnegative"),
            models.CheckConstraint(condition=models.Q(discount_amount__gte=0), name="ck_purchase_invoice_line_discount_nonnegative"),
            models.CheckConstraint(condition=models.Q(taxable_value__gte=0), name="ck_purchase_invoice_line_taxable_nonnegative"),
            models.CheckConstraint(condition=models.Q(gst_rate__gte=0) & models.Q(gst_rate__lte=100), name="ck_purchase_invoice_line_rate_bounds"),
            models.CheckConstraint(
                condition=models.Q(cgst_amount__gte=0) & models.Q(sgst_amount__gte=0) & models.Q(igst_amount__gte=0)
                & models.Q(total_tax__gte=0) & models.Q(total_amount__gte=0),
                name="ck_purchase_invoice_line_tax_nonnegative",
            ),
        ]

    def save(self, *args, **kwargs):
        if self.invoice.status == PurchaseInvoice.Status.POSTED:
            raise TypeError("Lines on posted purchase invoices are immutable.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.invoice.status == PurchaseInvoice.Status.POSTED:
            raise TypeError("Lines on posted purchase invoices are immutable.")
        super().delete(*args, **kwargs)


class PurchaseInvoiceAllocation(TenantOwnedModel):
    """Allocation of a billed line to a received GRN line."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice_line = models.ForeignKey(PurchaseInvoiceLine, on_delete=models.PROTECT, related_name="grn_allocations")
    receipt_line = models.ForeignKey(PurchaseReceiptLine, on_delete=models.PROTECT, related_name="invoice_allocations")
    quantity = models.DecimalField(max_digits=14, decimal_places=3)
    taxable_value = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="ck_invoice_allocation_qty_positive"),
            models.CheckConstraint(condition=models.Q(taxable_value__gte=0), name="ck_invoice_allocation_value_nonnegative"),
            models.UniqueConstraint(fields=["invoice_line", "receipt_line"], name="uq_invoice_line_grn_line"),
        ]
        indexes = [
            models.Index(fields=["tenant", "receipt_line"], name="ix_ia_tenant_grn_line"),
        ]

    def save(self, *args, **kwargs):
        if self.invoice_line.invoice.status == PurchaseInvoice.Status.POSTED:
            raise TypeError("Allocations on posted purchase invoices are immutable.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.invoice_line.invoice.status == PurchaseInvoice.Status.POSTED:
            raise TypeError("Allocations on posted purchase invoices are immutable.")
        super().delete(*args, **kwargs)
