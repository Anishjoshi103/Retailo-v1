from apps.tenancy.models import Branch, BranchAccess, Membership


def authorized_branches(membership: Membership):
    """Return active branches explicitly granted to an active membership."""
    return Branch.objects.for_tenant(membership.tenant_id).filter(
        is_active=True,
        membership_accesses__membership=membership,
        membership_accesses__is_active=True,
    ).distinct()


def membership_can_access_branch(membership: Membership, branch_id) -> bool:
    """Check branch access without trusting a client-supplied tenant identifier."""
    if not membership.is_active or membership.tenant.status != "active":
        return False
    return BranchAccess.objects.filter(
        membership=membership,
        membership__tenant_id=membership.tenant_id,
        membership__is_active=True,
        branch_id=branch_id,
        branch__tenant_id=membership.tenant_id,
        branch__is_active=True,
        is_active=True,
    ).exists()
