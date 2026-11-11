"""Shared filtering and paging for the sales and credit note list endpoints."""

import uuid
from datetime import date

from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.tenancy.access import membership_can_access_branch

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200


def _int_param(params, name, default, minimum, maximum):
    raw = params.get(name)
    if raw in (None, ""):
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValidationError({name: "Enter a whole number."}) from exc
    if value < minimum or (maximum is not None and value > maximum):
        bound = f"between {minimum} and {maximum}" if maximum is not None else f"at least {minimum}"
        raise ValidationError({name: f"Must be {bound}."})
    return value


def uuid_param(params, name):
    raw = params.get(name)
    if not raw:
        return None
    try:
        return uuid.UUID(raw)
    except ValueError as exc:
        raise ValidationError({name: "Enter a valid id."}) from exc


def filter_documents(queryset, params, membership, *, date_field, number_field):
    """Apply ``branch_id``, ``date_from``/``date_to`` and number filters from query parameters.

    ``queryset`` must already be limited to the tenant and the caller's granted branches.
    A ``branch_id`` the caller cannot access is refused rather than silently empty.
    """
    branch_id = uuid_param(params, "branch_id")
    if branch_id is not None:
        if not membership_can_access_branch(membership, branch_id):
            raise PermissionDenied("You do not have access to the requested branch.")
        queryset = queryset.filter(branch_id=branch_id)
    for name, lookup in (("date_from", f"{date_field}__gte"), ("date_to", f"{date_field}__lte")):
        if params.get(name):
            try:
                queryset = queryset.filter(**{lookup: date.fromisoformat(params[name])})
            except ValueError as exc:
                raise ValidationError({name: "Use the format YYYY-MM-DD."}) from exc
    if params.get("invoice_number") and number_field:
        queryset = queryset.filter(**{number_field: params["invoice_number"].strip().upper()})
    return queryset


def page_bounds(params) -> tuple[int, int]:
    """Return ``(offset, offset + limit)`` from ``limit`` and ``offset`` query parameters."""
    limit = _int_param(params, "limit", DEFAULT_PAGE_SIZE, 1, MAX_PAGE_SIZE)
    offset = _int_param(params, "offset", 0, 0, None)
    return offset, offset + limit
