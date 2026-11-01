from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0006_purchase_invoice_snapshots"),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name="purchaseinvoice",
            name="ix_purchase_invoice_supplier_date",
        ),
        migrations.RemoveIndex(
            model_name="purchaseinvoice",
            name="ix_purchase_invoice_branch_status",
        ),
        migrations.RemoveIndex(
            model_name="purchaseinvoiceallocation",
            name="ix_invoice_alloc_tenant_grn_line",
        ),
        migrations.AddIndex(
            model_name="purchaseinvoice",
            index=models.Index(
                fields=["tenant", "supplier", "invoice_date"],
                name="ix_pi_supplier_date",
            ),
        ),
        migrations.AddIndex(
            model_name="purchaseinvoice",
            index=models.Index(
                fields=["tenant", "branch", "status"],
                name="ix_pi_branch_status",
            ),
        ),
        migrations.AddIndex(
            model_name="purchaseinvoiceallocation",
            index=models.Index(
                fields=["tenant", "receipt_line"],
                name="ix_ia_tenant_grn_line",
            ),
        ),
    ]
