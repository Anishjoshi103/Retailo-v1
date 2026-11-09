import uuid
from typing import ClassVar

from django.conf import settings
from django.db import models
from django.db.models.functions import Round

from apps.tenancy.models import TenantOwnedModel, TenantQuerySet


class AppendOnlyQuerySet(TenantQuerySet):
    """Posted sales documents are never edited or removed; corrections are new documents."""

    def update(self, **kwargs):
        raise TypeError("Posted sales records are immutable.")

    def bulk_update(self, objs, fields, batch_size=None):
        raise TypeError("Posted sales records are immutable.")

    def delete(self):
        raise TypeError("Posted sales records are immutable.")


class InvoiceSequence(TenantOwnedModel):
    """Gapless invoice counter for one branch; advanced only by allocate_invoice_number()."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    branch = models.ForeignKey(
        "tenancy.Branch", on_delete=models.PROTECT, related_name="invoice_sequences"
    )
    last_number = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "branch"], name="uq_invoice_sequence_tenant_branch"
            ),
        ]


class Sale(TenantOwnedModel):
    """A posted retail tax invoice. Every row is final; there is no draft state."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    branch = models.ForeignKey("tenancy.Branch", on_delete=models.PROTECT, related_name="sales")
    invoice_number = models.CharField(max_length=16)
    invoice_date = models.DateField()
    # Seller and supply snapshots so later branch edits never change a posted invoice.
    seller_gstin = models.CharField(max_length=15, blank=True)
    seller_state_code = models.CharField(max_length=2)
    place_of_supply_state_code = models.CharField(max_length=2)
    customer_name = models.CharField(max_length=180, blank=True)
    customer_gstin = models.CharField(max_length=15, blank=True)
    taxable_total = models.DecimalField(max_digits=14, decimal_places=2)
    cgst_total = models.DecimalField(max_digits=14, decimal_places=2)
    sgst_total = models.DecimalField(max_digits=14, decimal_places=2)
    igst_total = models.DecimalField(max_digits=14, decimal_places=2)
    total_tax = models.DecimalField(max_digits=14, decimal_places=2)
    round_off = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    grand_total = models.DecimalField(max_digits=14, decimal_places=2)
    idempotency_key = models.CharField(max_length=128)
    request_hash = models.CharField(max_length=64)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    objects: ClassVar[models.Manager["Sale"]] = AppendOnlyQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "branch", "invoice_number"], name="uq_sale_tenant_branch_invoice"
            ),
            models.UniqueConstraint(
                fields=["tenant", "idempotency_key"], name="uq_sale_tenant_idempotency_key"
            ),
            models.CheckConstraint(
                condition=models.Q(
                    taxable_total__gte=0, cgst_total__gte=0, sgst_total__gte=0,
                    igst_total__gte=0, total_tax__gte=0, grand_total__gte=0,
                ),
                name="ck_sale_amounts_nonnegative",
            ),
            models.CheckConstraint(
                # Round(.., 2): SQLite stores decimals as floats, so an exact sum can differ in
                # the last bit; rounding to paise makes the check behave the same as on SQL Server.
                condition=models.Q(
                    total_tax=Round(models.F("cgst_total") + models.F("sgst_total") + models.F("igst_total"), 2)
                ),
                name="ck_sale_tax_components_sum",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    grand_total=Round(
                        models.F("taxable_total") + models.F("total_tax") + models.F("round_off"), 2
                    )
                ),
                name="ck_sale_grand_total_sum",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "branch", "created_at"], name="ix_sale_tenant_branch_created"),
        ]

    def __str__(self):
        return self.invoice_number

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise TypeError("Posted sales are immutable; issue a credit note instead.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise TypeError("Posted sales are immutable; issue a credit note instead.")


class _SaleChildGuard:
    """Immutability and tenant-consistency rules for records hanging off a sale.

    A plain mixin (not an abstract model) so each child inherits TenantOwnedModel
    directly, which is how scripts/check_tenant_scope.py recognises tenant-owned models.
    """

    sale: "Sale"
    tenant_id: uuid.UUID
    _state: models.base.ModelState

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise TypeError("Posted sales records are immutable.")
        if self.sale.tenant_id != self.tenant_id:
            raise ValueError("A sale record must belong to the same tenant as its sale.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise TypeError("Posted sales records are immutable.")


class SaleLine(_SaleChildGuard, TenantOwnedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sale = models.ForeignKey(Sale, on_delete=models.PROTECT, related_name="lines")
    product = models.ForeignKey(
        "catalog.Product", on_delete=models.PROTECT, related_name="sale_lines"
    )
    # Product snapshots: catalogue edits never rewrite a posted invoice.
    sku = models.CharField(max_length=64)
    name = models.CharField(max_length=180)
    hsn_code = models.CharField(max_length=8, blank=True)
    unit = models.CharField(max_length=8)
    quantity = models.DecimalField(max_digits=14, decimal_places=3)
    # Tax-inclusive (MRP-style) unit price as sold; taxable_value is the tax-exclusive part.
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    gst_rate = models.DecimalField(max_digits=5, decimal_places=2)
    taxable_value = models.DecimalField(max_digits=14, decimal_places=2)
    cgst_amount = models.DecimalField(max_digits=14, decimal_places=2)
    sgst_amount = models.DecimalField(max_digits=14, decimal_places=2)
    igst_amount = models.DecimalField(max_digits=14, decimal_places=2)
    line_total = models.DecimalField(max_digits=14, decimal_places=2)
    objects: ClassVar[models.Manager["SaleLine"]] = AppendOnlyQuerySet.as_manager()

    class Meta:
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="ck_sale_line_qty_positive"),
            models.CheckConstraint(
                condition=models.Q(unit_price__gte=0), name="ck_sale_line_price_nonnegative"
            ),
            models.CheckConstraint(
                condition=models.Q(
                    taxable_value__gte=0, cgst_amount__gte=0, sgst_amount__gte=0,
                    igst_amount__gte=0, gst_rate__gte=0, gst_rate__lte=100,
                ),
                name="ck_sale_line_amounts_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    line_total=Round(
                        models.F("taxable_value") + models.F("cgst_amount")
                        + models.F("sgst_amount") + models.F("igst_amount"), 2
                    )
                ),
                name="ck_sale_line_total_sum",
            ),
        ]


class SalePayment(_SaleChildGuard, TenantOwnedModel):
    class Method(models.TextChoices):
        CASH = "cash", "Cash"
        UPI = "upi", "UPI"
        CARD = "card", "Card"
        OTHER = "other", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sale = models.ForeignKey(Sale, on_delete=models.PROTECT, related_name="payments")
    method = models.CharField(max_length=8, choices=Method.choices)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    reference = models.CharField(max_length=120, blank=True)
    objects: ClassVar[models.Manager["SalePayment"]] = AppendOnlyQuerySet.as_manager()

    class Meta:
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(condition=models.Q(amount__gt=0), name="ck_sale_payment_positive"),
        ]
