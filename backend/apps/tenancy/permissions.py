from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission

from apps.tenancy.access import membership_can_access_branch
from apps.tenancy.models import Membership


def active_tenant_membership(request) -> Membership:
    """Return the active JWT-selected membership, cached for this request."""
    cached = getattr(request, "_retailo_active_membership", None)
    if cached is not None:
        return cached

    auth = request.auth
    tenant_id = auth.get("tenant_id") if auth else None
    membership_id = auth.get("membership_id") if auth else None
    if not tenant_id or not membership_id:
        raise PermissionDenied("An active store membership is required.")

    membership = (
        Membership.objects.select_related("tenant")
        .filter(
            pk=membership_id,
            tenant_id=tenant_id,
            user=request.user,
            is_active=True,
            tenant__status="active",
        )
        .first()
    )
    if membership is None:
        raise PermissionDenied("An active store membership is required.")

    setattr(request, "_retailo_active_membership", membership)
    return membership


def require_membership_role(
    request,
    allowed_roles: set[str],
    message: str = "You do not have permission to perform this action.",
) -> Membership:
    """Resolve the active tenant membership and enforce its role allowlist."""
    membership = active_tenant_membership(request)
    if membership.role not in allowed_roles:
        raise PermissionDenied(message)
    return membership


class IsActiveTenantMember(BasePermission):
    """Allow only requests with a valid, active tenant membership."""

    def has_permission(self, request, view) -> bool:
        try:
            active_tenant_membership(request)
        except PermissionDenied:
            return False
        return True


class HasRole(BasePermission):
    """Require one of the configured membership roles.

    Configure as HasRole(allowed_roles={Membership.Role.OWNER, ...}) in a
    permission subclass, or instantiate directly with role values in tests.
    """

    allowed_roles: frozenset[str] = frozenset()

    def __init__(self, *roles, allowed_roles=None):
        if allowed_roles is not None:
            self.allowed_roles = frozenset(allowed_roles)
        elif roles:
            self.allowed_roles = frozenset(roles)
        else:
            self.allowed_roles = frozenset(type(self).allowed_roles)

    def has_permission(self, request, view) -> bool:
        try:
            membership = active_tenant_membership(request)
        except PermissionDenied:
            return False
        return membership.role in self.allowed_roles


class HasBranchAccess(BasePermission):
    """Require an explicit active grant to the branch in X-Branch-ID."""

    branch_header = "X-Branch-ID"

    def has_permission(self, request, view) -> bool:
        try:
            membership = active_tenant_membership(request)
        except PermissionDenied:
            return False

        branch_id = request.headers.get(self.branch_header)
        if not branch_id:
            return False
        return membership_can_access_branch(membership, branch_id)
