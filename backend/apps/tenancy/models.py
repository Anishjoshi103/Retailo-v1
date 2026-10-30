import uuid

from django.conf import settings
from django.db import models
from django.db.models import QuerySet


class TenantQuerySet(QuerySet):
    def for_tenant(self, tenant_id):
        if tenant_id is None:
            return self.none()
        return self.filter(tenant_id=tenant_id)


class TenantOwnedModel(models.Model):
    """Base for tenant-owned records; callers must use for_tenant(tenant_id)."""

    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT)
    objects = TenantQuerySet.as_manager()

    class Meta:
        abstract = True


class Tenant(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=160)
    slug = models.SlugField(max_length=80, unique=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "id"]

    def __str__(self):
        return self.name


class Membership(models.Model):
    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        ADMIN = "admin", "Administrator"
        MANAGER = "manager", "Manager"
        CASHIER = "cashier", "Cashier"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, related_name="memberships")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="tenant_memberships")
    role = models.CharField(max_length=16, choices=Role.choices)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["tenant", "user"], name="uq_membership_tenant_user")]
        indexes = [models.Index(fields=["user", "is_active"], name="ix_membership_user_active")]

    def __str__(self):
        return f"{self.user_id}@{self.tenant_id}:{self.role}"


class Branch(TenantOwnedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120)
    code = models.CharField(max_length=32)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "id"]
        constraints = [models.UniqueConstraint(fields=["tenant", "code"], name="uq_branch_tenant_code")]
        indexes = [models.Index(fields=["tenant", "is_active"], name="ix_branch_tenant_active")]

    def __str__(self):
        return f"{self.tenant_id}:{self.code} {self.name}"
