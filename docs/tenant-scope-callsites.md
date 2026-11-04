# Tenant scope call-site migration

## Baseline CI checklist

| Group | Commit | CI result |
|---|---|---|
| Existing call-site changes baseline | `c132b9fb36bc2986cd66d8979657daebbe74f320` | **FAIL** — [run #41815069201](https://github.com/Anishjoshi103/Retailo-v1/actions/runs/41815069201): Ruff, mypy, Django checks, discovery guard and frontend passed; backend suite ran 120 tests with 20 failures and 1 error; coverage gate was not reached. |
| AST checker, classification and bulk-create regression | `9040df765c26c37ed02fe26e1c9ca032f9683c49` | **FAIL** — [run #41817138410](https://github.com/Anishjoshi103/Retailo-v1/actions/runs/41817138410): Ruff, mypy, Django checks and discovery guard passed; checker unit tests had 1 failure (`test_finds_unscoped_manager_calls`, assertion assumed AST traversal order); scope scan and full suite were skipped. Frontend checks passed. Fix: make the unit test order-independent. |
| InventoryBalance call sites | Pending | Not run yet |
| Immutability guards | Pending | Not run yet |
| Serializer validators | Pending | Not run yet |
| Services and remaining query patterns | Pending | Not run yet |

## Failure-driven migration groups

### Group A — InventoryBalance writes
- `backend/apps/inventory/views.py`: scope `get_or_create` and `F()` update with the request's validated `tenant_id`.
- `backend/apps/inventory/purchase_views.py`: scope receipt balance `get_or_create` and stock `F()` update with the receipt/request tenant.
- `backend/apps/inventory/return_views.py`: scope stock decrement with the return tenant.
- Tests exercising inventory adjustment, receipt posting/retry, and supplier return are part of this group.

### Group B — immutability guards and bulk operations
- `backend/apps/inventory/models.py`: scope posted invoice/line/allocation existence checks by each candidate object's `tenant_id`.
- Preserve checks for posted invoice creation and posted invoice-line/allocation creation, including bulk operations.
- Regression test must prove a new line with a new primary key cannot be bulk-created against a posted invoice. A check keyed only to the candidate line's own primary key is unsafe: the line does not exist yet, so its key says nothing about the parent invoice's posted status.

### Group C — serializer uniqueness validators
- Product SKU and Supplier GSTIN uniqueness validators must use `for_tenant(tenant_id)` and must not search across tenants.

### Group D — services and request paths
- Scope each tenant-owned queryset before evaluation or mutation. Use the request/instance tenant ID, not a global fetch followed by Python filtering.
- Audit `select_for_update` inside `atomic`, `F()` updates, `get_or_create`, `update_or_create`, `bulk_create`, related managers, `select_related`/`prefetch_related`, `refresh_from_db`, cascade deletes, queryset `update`/`delete`.

### Group E — tests and fixtures
- Convert tenant-owned assertions to `for_tenant(known_tenant_id)`; do not weaken enforcement to make tests pass.
- User and Tenant lookups are global identity operations. Membership and BranchAccess remain tenant-owned access data and must be scoped appropriately.

## Checker coverage and remaining limitations
- The AST checker discovers direct `TenantOwnedModel` subclasses in app `models.py` files and checks manager/queryset calls on those named classes in non-test, non-migration Python under `apps/` and `config/`.
- It cannot prove dynamic aliases, raw SQL, dynamically selected models, related-manager tenant safety, or semantic correctness of an allow-list. Those require focused tests and review.
- The CI test-discovery guard is not the same as running the AST checker's unit tests; CI runs both explicitly.

## Actual CI tracebacks
The baseline failure output included receipt/return/stock-adjustment API tests returning HTTP 500 where 201 was expected, and a same-idempotency-key/different-payload test returning 500 instead of 409. Full first-failure locations are retained in Actions run #41815069201. Add each new run's exact failing test names here before fixing its cause.
