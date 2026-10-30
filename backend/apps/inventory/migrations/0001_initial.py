import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [("catalog", "0001_initial"), ("tenancy", "0001_initial"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(
            name="InventoryBalance",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("quantity_on_hand", models.DecimalField(decimal_places=3, default=0, max_digits=14)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("tenant", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="tenancy.tenant")),
                ("branch", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="inventory_balances", to="tenancy.branch")),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="inventory_balances", to="catalog.product")),
            ],
        ),
        migrations.CreateModel(
            name="StockMovement",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("quantity_delta", models.DecimalField(decimal_places=3, max_digits=14)),
                ("reason", models.CharField(choices=[("opening", "Opening stock"), ("receipt", "Goods received"), ("sale", "Sale"), ("return", "Return"), ("adjustment", "Manual adjustment"), ("reversal", "Reversal")], max_length=16)),
                ("reference", models.CharField(blank=True, max_length=120)),
                ("idempotency_key", models.CharField(blank=True, max_length=128)),
                ("note", models.CharField(blank=True, max_length=500)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("branch", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="stock_movements", to="tenancy.branch")),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="stock_movements", to="catalog.product")),
                ("tenant", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="tenancy.tenant")),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
        migrations.AddConstraint(model_name="inventorybalance", constraint=models.UniqueConstraint(fields=("tenant", "branch", "product"), name="uq_inventory_tenant_branch_product")),
        migrations.AddIndex(model_name="inventorybalance", index=models.Index(fields=["tenant", "branch", "product"], name="ix_inventory_lookup")),
        migrations.AddConstraint(model_name="stockmovement", constraint=models.CheckConstraint(condition=~models.Q(("quantity_delta", 0)), name="ck_stock_movement_nonzero")),
        migrations.AddConstraint(model_name="stockmovement", constraint=models.UniqueConstraint(condition=~models.Q(("idempotency_key", "")), fields=("tenant", "idempotency_key"), name="uq_stock_move_tenant_idem")),
        migrations.AddIndex(model_name="stockmovement", index=models.Index(fields=["tenant", "branch", "product", "created_at"], name="ix_stock_move_lookup")),
    ]
