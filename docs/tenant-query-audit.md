# Tenant-owned queryset audit (A1.5 PR 1)

## Scope

This PR records the current tenant-query contract before any manager behavior changes. It is characterization only: no production model, manager, view, serializer, or API behavior is changed.

## Current contract

`TenantOwnedModel` in `backend/apps/tenancy/models.py` provides `TenantQuerySet.for_tenant(tenant_id)`. A null tenant ID returns an empty queryset. The default manager is still a normal `TenantQuerySet` manager, so callers can run unscoped operations such as `Model.objects.all()` and `Model.objects.filter(...)`.

The manager does not currently enforce tenant scoping. This audit does not establish that an unauthenticated or tenant-facing API endpoint exposes cross-tenant data; the API querysets reviewed generally call `for_tenant`. The gap is that the model manager cannot enforce the intended invariant for every caller.

## Call-site findings to carry into PR 2

- Tenant-facing catalogue, supplier, balance, purchase receipt, and purchase return reads use `for_tenant(tenant_id)` in the inspected query paths.
- Inventory balance writes in `backend/apps/inventory/views.py`, `purchase_views.py`, and `return_views.py` include unscoped manager calls after resolving a row or providing `tenant_id` in `get_or_create`. These need explicit scoping or a deliberately named trusted escape hatch before enforcement.
- Some tests use unscoped `.count()`, `.filter()`, and `.objects.create()`. Test fixture creation and administrative/test-only access must be distinguished from production query access.
- Specialized querysets in `backend/apps/inventory/models.py` inherit `TenantQuerySet` and add immutability guards; any manager change must preserve those guards and Django's internal base-manager behavior.

## Characterization tests

`backend/apps/tenancy/tests.py` records that the current default manager can read rows across tenants, while `for_tenant(tenant_id)` returns only the requested tenant and `for_tenant(None)` returns no rows. The cross-tenant default-manager assertion intentionally describes current behavior and must be replaced by the desired contract in the enforcement PR.

## Planned follow-up

- PR 2: add a warning-only default manager, a named explicit escape hatch, and a plain base manager for Django internals. Inventory and migrate production call sites; keep behavior unchanged.
- PR 3: enforce explicit tenant scoping after warning inventory is clean and tests prove expected failure for unscoped application queries. **Status:** implemented. Unscoped evaluation, count, exists, aggregate, iterator, update and delete raise `RuntimeError`; trusted code must use `.for_tenant(tenant_id)` or `.unscoped(reason=...)`. Reverse-relation managers (e.g. `receipt.lines`) are not scoped automatically and must call `for_tenant` too.

## Validation boundary

This PR must pass the repository's existing CI. GitHub Actions is the available verification mechanism here; no local checkout/test runner is available in this session. SQL Server concurrency is outside this characterization PR and remains an outstanding CI gap.
