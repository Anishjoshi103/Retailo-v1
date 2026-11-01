from rest_framework.exceptions import PermissionDenied

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
