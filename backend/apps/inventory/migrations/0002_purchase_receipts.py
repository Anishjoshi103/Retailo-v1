import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0001_initial"),
        ("tenancy", "0001_initial"),
        ("catalog", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PurchaseReceipt",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("supplier_name", models.CharField(max_length=180)),
                ("supplier_invoice_number", models.CharField(blank=True, max_length=80)),
                ("idempotency_key", models.CharField(max_length=128)),
                ("request_hash", models.CharField(max_length=64)),
                ("received_at", models.DateTimeField(auto_now_add=True)),
                ("branch", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="purchase_receipts", to="tenancy.branch")),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ("tenant", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="tenancy.tenant")),
            ],
            options={"ordering": ["-received_at", "-id"]},
        ),
        migrations.CreateModel(
            name="PurchaseReceiptLine",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("quantity", models.DecimalField(decimal_places=3, max_digits=14)),
                ("unit_cost", models.DecimalField(decimal_places=2, max_digits=12)),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="purchase_receipt_lines", to="catalog.product")),
                ("receipt", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="lines", to="inventory.purchasereceipt")),
                ("tenant", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="tenancy.tenant")),
            ],
        ),
        migrations.AddConstraint(
            model_name="purchasereceipt",
            constraint=models.UniqueConstraint(fields=("tenant", "idempotency_key"), name="uq_receipt_tenant_idem"),
        ),
        migrations.AddIndex(
            model_name="purchasereceipt",
            index=models.Index(fields=["tenant", "branch", "received_at"], name="ix_receipt_tenant_branch_date"),
        ),
        migrations.AddConstraint(
            model_name="purchasereceiptline",
            constraint=models.CheckConstraint(condition=models.Q(("quantity__gt", 0)), name="ck_receipt_line_qty_positive"),
        ),
        migrations.AddConstraint(
            model_name="purchasereceiptline",
            constraint=models.CheckConstraint(condition=models.Q(("unit_cost__gte", 0)), name="ck_receipt_line_cost_nonnegative"),
        ),
    ]
