import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [("tenancy", "0001_initial")]
    operations = [
        migrations.CreateModel(
            name="Product",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("sku", models.CharField(max_length=64)),
                ("barcode", models.CharField(blank=True, max_length=64, null=True)),
                ("name", models.CharField(max_length=180)),
                ("description", models.CharField(blank=True, max_length=500)),
                ("unit", models.CharField(choices=[("each", "Each"), ("kg", "Kilogram"), ("g", "Gram"), ("l", "Litre"), ("ml", "Millilitre"), ("m", "Metre"), ("pack", "Pack")], default="each", max_length=8)),
                ("hsn_code", models.CharField(blank=True, max_length=8)),
                ("gst_rate", models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ("selling_price", models.DecimalField(decimal_places=2, max_digits=12)),
                ("purchase_price", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("tenant", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="tenancy.tenant")),
            ],
            options={"ordering": ["name", "id"]},
        ),
        migrations.AddConstraint(model_name="product", constraint=models.UniqueConstraint(fields=("tenant", "sku"), name="uq_product_tenant_sku")),
        migrations.AddConstraint(model_name="product", constraint=models.UniqueConstraint(condition=models.Q(("barcode__isnull", False)), fields=("tenant", "barcode"), name="uq_product_tenant_barcode")),
        migrations.AddConstraint(model_name="product", constraint=models.CheckConstraint(condition=models.Q(("gst_rate__gte", 0), ("gst_rate__lte", 100)), name="ck_product_gst_rate_range")),
        migrations.AddConstraint(model_name="product", constraint=models.CheckConstraint(condition=models.Q(("selling_price__gte", 0)), name="ck_product_selling_price_nonnegative")),
        migrations.AddConstraint(model_name="product", constraint=models.CheckConstraint(condition=models.Q(("purchase_price__gte", 0)), name="ck_product_purchase_price_nonnegative")),
        migrations.AddIndex(model_name="product", index=models.Index(fields=["tenant", "is_active", "name"], name="ix_product_tenant_active_name")),
    ]
