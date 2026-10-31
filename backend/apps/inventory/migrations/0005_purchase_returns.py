import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0004_receipt_supplier"),
        ("tenancy", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PurchaseReturn",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("supplier_name", models.CharField(max_length=180)),
                ("reason", models.CharField(max_length=500)),
                ("idempotency_key", models.CharField(max_length=128)),
                ("request_hash", models.CharField(max_length=64)),
                ("returned_at", models.DateTimeField(auto_now_add=True)),
                ("branch", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="purchase_returns", to="tenancy.branch")),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ("receipt", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="returns", to="inventory.purchasereceipt")),
                ("tenant", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="tenancy.tenant")),
            ],
            options={"ordering": ["-returned_at", "-id"]},
        ),
        migrations.CreateModel(
            name="PurchaseReturnLine",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("quantity", models.DecimalField(decimal_places=3, max_digits=14)),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="purchase_return_lines", to="catalog.product")),
                ("purchase_return", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="lines", to="inventory.purchasereturn")),
                ("receipt_line", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="return_lines", to="inventory.purchasereceiptline")),
                ("tenant", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="tenancy.tenant")),
            ],
        ),
        migrations.AddConstraint(
            model_name="purchasereturn",
            constraint=models.UniqueConstraint(fields=("tenant", "idempotency_key"), name="uq_purchase_return_tenant_idem"),
        ),
        migrations.AddIndex(
            model_name="purchasereturn",
            index=models.Index(fields=["tenant", "receipt", "returned_at"], name="ix_return_tenant_receipt_date"),
        ),
        migrations.AddConstraint(
            model_name="purchasereturnline",
            constraint=models.CheckConstraint(condition=models.Q(("quantity__gt", 0)), name="ck_purchase_return_qty_positive"),
        ),
    ]
