import uuid
import warnings

from django.conf import settings
from django.db import models
from django.db.models import QuerySet


class TenantQuerySet(QuerySet):
    _tenant_scope_explicit = False
    _tenant_scope_escape_reason = None

    def _clone(self):
        clone = super()._clone()
        clone._tenant_scope_explicit = self._tenant_scope_explicit
        clone._tenant_scope_escape_reason = self._tenant_scope_escape_reason
        return clone

    def for_tenant(self, tenant_id):
        queryset = self.none() if tenant_id is None else self.filter(tenant_id=tenant_id)
        queryset._tenant_scope_explicit = True
        return queryset

    def unscoped(self, *, reason):
        """Explicitly opt into an unscoped query for trusted code; require rationale."""
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("An explicit reason is required for an unscoped tenant query.")
        queryset = self.all()
        queryset._tenant_scope_explicit = True
        queryset._tenant_scope_escape_reason = reason.strip()
        return queryset

    def _fetch_all(self):
        if not self._tenant_scope_explicit and self._result_cache is None:
            warnings.warn(
                f"Unscoped query on tenant-owned model {self.model.__name__}; "
                "use .for_tenant(tenant_id) or .unscoped(reason=...) for trusted access.",
                RuntimeWarning,
                stacklevel=2,
            )
        return super()._fetch_all()


class TenantOwnedModel(models.Model):
    """Base for tenant-owned records; callers must use for_tenant(tenant_id)."""

    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT)
    objects = TenantQuerySet.as_manager()
    # Django's relation traversal and deletion collector need an unfiltered base manager.
    base_objects = models.Manager()

    class Meta:
        abstract = True
        base_manager_name = "base_objects"


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
        ACCOUNTANT = "accountant", "Accountant"

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


class BranchAccess(models.Model):
    """Explicit access grant connecting a tenant membership to one branch."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    membership = models.ForeignKey(Membership, on_delete=models.CASCADE, related_name="branch_accesses")
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name="membership_accesses")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["membership", "branch"], name="uq_branch_access_membership_branch")]
        indexes = [models.Index(fields=["membership", "is_active"], name="ix_br_access_mem_active")]

    def __str__(self):
        return f"{self.membership_id}:{self.branch_id}"
