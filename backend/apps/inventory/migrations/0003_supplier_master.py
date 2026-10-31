import uuid

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("inventory", "0002_purchase_receipts"), ("tenancy", "0001_initial")]

    operations = [
        migrations.CreateModel(
            name="Supplier",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=180)),
                ("gstin", models.CharField(blank=True, max_length=15)),
                ("phone", models.CharField(blank=True, max_length=32)),
                ("email", models.EmailField(blank=True, max_length=254)),
                ("address", models.CharField(blank=True, max_length=500)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("tenant", models.ForeignKey(on_delete=models.PROTECT, to="tenancy.tenant")),
            ],
            options={"ordering": ["name", "id"]},
        ),
        migrations.AddConstraint(
            model_name="supplier",
            constraint=models.UniqueConstraint(condition=~models.Q(("gstin", "")), fields=("tenant", "gstin"), name="uq_supplier_tenant_gstin"),
        ),
        migrations.AddIndex(
            model_name="supplier",
            index=models.Index(fields=["tenant", "is_active", "name"], name="ix_supplier_tenant_active_name"),
        ),
    ]
