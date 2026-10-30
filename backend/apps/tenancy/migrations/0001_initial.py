import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(
            name="Tenant",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=160)),
                ("slug", models.SlugField(max_length=80, unique=True)),
                ("status", models.CharField(choices=[("active", "Active"), ("suspended", "Suspended")], default="active", max_length=16)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["name", "id"]},
        ),
        migrations.CreateModel(
            name="Membership",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("role", models.CharField(choices=[("owner", "Owner"), ("admin", "Administrator"), ("manager", "Manager"), ("cashier", "Cashier")], max_length=16)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("tenant", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="memberships", to="tenancy.tenant")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="tenant_memberships", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="Branch",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=120)),
                ("code", models.CharField(max_length=32)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("tenant", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="tenancy.tenant")),
            ],
            options={"ordering": ["name", "id"]},
        ),
        migrations.AddConstraint(model_name="membership", constraint=models.UniqueConstraint(fields=("tenant", "user"), name="uq_membership_tenant_user")),
        migrations.AddIndex(model_name="membership", index=models.Index(fields=["user", "is_active"], name="ix_membership_user_active")),
        migrations.AddConstraint(model_name="branch", constraint=models.UniqueConstraint(fields=("tenant", "code"), name="uq_branch_tenant_code")),
        migrations.AddIndex(model_name="branch", index=models.Index(fields=["tenant", "is_active"], name="ix_branch_tenant_active")),
    ]
