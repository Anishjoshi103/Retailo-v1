import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0005_purchase_returns"),
        ("catalog", "0001_initial"),
        ("tenancy", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PurchaseInvoice",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("supplier_name", models.CharField(max_length=180)),
                ("supplier_gstin", models.CharField(blank=True, max_length=15)),
                ("supplier_state_code", models.CharField(max_length=2)),
                ("place_of_supply_state_code", models.CharField(max_length=2)),
                ("invoice_number", models.CharField(blank=True, max_length=80)),
                ("invoice_date", models.DateField()),
                ("status", models.CharField(choices=[("draft", "Draft"), ("posted", "Posted")], default="draft", max_length=8)),
                ("taxable_total", models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ("tax_total", models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ("total_amount", models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ("idempotency_key", models.CharField(max_length=128)),
                ("request_hash", models.CharField(max_length=64)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("posted_at", models.DateTimeField(blank=True, null=True)),
                ("branch", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="purchase_invoices", to="tenancy.branch")),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ("supplier", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="purchase_invoices", to="inventory.supplier")),
                ("tenant", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="tenancy.tenant")),
            ],
            options={"ordering": ["-invoice_date", "-id"]},
        ),
        migrations.CreateModel(
            name="PurchaseInvoiceLine",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("description_snapshot", models.CharField(max_length=240)),
                ("hsn_code", models.CharField(blank=True, max_length=16)),
                ("quantity", models.DecimalField(decimal_places=3, max_digits=14)),
                ("unit_price", models.DecimalField(decimal_places=4, max_digits=14)),
                ("discount_amount", models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ("taxable_value", models.DecimalField(decimal_places=2, max_digits=14)),
                ("gst_rate", models.DecimalField(decimal_places=2, max_digits=5)),
                ("cgst_amount", models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ("sgst_amount", models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ("igst_amount", models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ("total_tax", models.DecimalField(decimal_places=2, max_digits=14)),
                ("total_amount", models.DecimalField(decimal_places=2, max_digits=14)),
                ("invoice", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="lines", to="inventory.purchaseinvoice")),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="purchase_invoice_lines", to="catalog.product")),
                ("tenant", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="tenancy.tenant")),
            ],
        ),
        migrations.CreateModel(
            name="PurchaseInvoiceAllocation",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("quantity", models.DecimalField(decimal_places=3, max_digits=14)),
                ("taxable_value", models.DecimalField(decimal_places=2, max_digits=14)),
                ("invoice_line", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="grn_allocations", to="inventory.purchaseinvoiceline")),
                ("receipt_line", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="invoice_allocations", to="inventory.purchasereceiptline")),
                ("tenant", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="tenancy.tenant")),
            ],
        ),
        migrations.AddConstraint(
            model_name="purchaseinvoice",
            constraint=models.UniqueConstraint(fields=("tenant", "idempotency_key"), name="uq_purchase_invoice_tenant_idem"),
        ),
        migrations.AddConstraint(
            model_name="purchaseinvoice",
            constraint=models.UniqueConstraint(condition=~models.Q(("invoice_number", "")), fields=("tenant", "supplier", "invoice_number"), name="uq_purchase_invoice_supplier_number"),
        ),
        migrations.AddConstraint(
            model_name="purchaseinvoice",
            constraint=models.CheckConstraint(condition=models.Q(("taxable_total__gte", 0), ("tax_total__gte", 0), ("total_amount__gte", 0), _connector="AND"), name="ck_purchase_invoice_totals_nonnegative"),
        ),
        migrations.AddIndex(
            model_name="purchaseinvoice",
            index=models.Index(fields=["tenant", "supplier", "invoice_date"], name="ix_purchase_invoice_supplier_date"),
        ),
        migrations.AddIndex(
            model_name="purchaseinvoice",
            index=models.Index(fields=["tenant", "branch", "status"], name="ix_purchase_invoice_branch_status"),
        ),
        migrations.AddConstraint(
            model_name="purchaseinvoiceline",
            constraint=models.CheckConstraint(condition=models.Q(("quantity__gt", 0)), name="ck_purchase_invoice_line_qty_positive"),
        ),
        migrations.AddConstraint(
            model_name="purchaseinvoiceline",
            constraint=models.CheckConstraint(condition=models.Q(("unit_price__gte", 0)), name="ck_purchase_invoice_line_price_nonnegative"),
        ),
        migrations.AddConstraint(
            model_name="purchaseinvoiceline",
            constraint=models.CheckConstraint(condition=models.Q(("discount_amount__gte", 0)), name="ck_purchase_invoice_line_discount_nonnegative"),
        ),
        migrations.AddConstraint(
            model_name="purchaseinvoiceline",
            constraint=models.CheckConstraint(condition=models.Q(("taxable_value__gte", 0)), name="ck_purchase_invoice_line_taxable_nonnegative"),
        ),
        migrations.AddConstraint(
            model_name="purchaseinvoiceline",
            constraint=models.CheckConstraint(condition=models.Q(("gst_rate__gte", 0), ("gst_rate__lte", 100), _connector="AND"), name="ck_purchase_invoice_line_rate_bounds"),
        ),
        migrations.AddConstraint(
            model_name="purchaseinvoiceline",
            constraint=models.CheckConstraint(condition=models.Q(("cgst_amount__gte", 0), ("sgst_amount__gte", 0), ("igst_amount__gte", 0), ("total_tax__gte", 0), ("total_amount__gte", 0), _connector="AND"), name="ck_purchase_invoice_line_tax_nonnegative"),
        ),
        migrations.AddConstraint(
            model_name="purchaseinvoiceallocation",
            constraint=models.CheckConstraint(condition=models.Q(("quantity__gt", 0)), name="ck_invoice_allocation_qty_positive"),
        ),
        migrations.AddConstraint(
            model_name="purchaseinvoiceallocation",
            constraint=models.CheckConstraint(condition=models.Q(("taxable_value__gte", 0)), name="ck_invoice_allocation_value_nonnegative"),
        ),
        migrations.AddConstraint(
            model_name="purchaseinvoiceallocation",
            constraint=models.UniqueConstraint(fields=("invoice_line", "receipt_line"), name="uq_invoice_line_grn_line"),
        ),
        migrations.AddIndex(
            model_name="purchaseinvoiceallocation",
            index=models.Index(fields=["tenant", "receipt_line"], name="ix_invoice_alloc_tenant_grn_line"),
        ),
    ]
