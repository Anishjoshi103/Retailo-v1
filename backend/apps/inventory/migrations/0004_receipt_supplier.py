import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("inventory", "0003_supplier_master")]

    operations = [
        migrations.AddField(
            model_name="purchasereceipt",
            name="supplier",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="receipts", to="inventory.supplier"),
        ),
    ]
