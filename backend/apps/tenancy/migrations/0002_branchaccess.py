import uuid

import django.db.models.deletion
from django.db import migrations, models


def grant_existing_memberships_all_tenant_branches(apps, schema_editor):
    Membership = apps.get_model("tenancy", "Membership")
    Branch = apps.get_model("tenancy", "Branch")
    BranchAccess = apps.get_model("tenancy", "BranchAccess")
    alias = schema_editor.connection.alias
    memberships = Membership.objects.using(alias).all().iterator()
    for membership in memberships:
        branch_ids = Branch.objects.using(alias).filter(tenant_id=membership.tenant_id).values_list("id", flat=True)
        BranchAccess.objects.using(alias).bulk_create(
            [
                BranchAccess(membership_id=membership.id, branch_id=branch_id, is_active=True)
                for branch_id in branch_ids
            ],
        )


class Migration(migrations.Migration):
    dependencies = [("tenancy", "0001_initial")]

    operations = [
        migrations.CreateModel(
            name="BranchAccess",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("branch", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="membership_accesses", to="tenancy.branch")),
                ("membership", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="branch_accesses", to="tenancy.membership")),
            ],
        ),
        migrations.AddConstraint(
            model_name="branchaccess",
            constraint=models.UniqueConstraint(fields=("membership", "branch"), name="uq_branch_access_membership_branch"),
        ),
        migrations.AddIndex(
            model_name="branchaccess",
            index=models.Index(fields=["membership", "is_active"], name="ix_branch_access_membership_active"),
        ),
        migrations.RunPython(grant_existing_memberships_all_tenant_branches, migrations.RunPython.noop),
    ]
