# Tenant model classification

This classification is the source of truth for the tenant-scope manager and
`scripts/check_tenant_scope.py`. If a new model is added, classify it here and
make the manager/checker behavior match before merging.

## Global identity models — plain manager, identity lookups only

| Model | Classification / permitted use |
|---|---|
| Django configured `User` model | Global identity. Look up by primary key, username, or authentication identity; do not use as a route to fetch tenant-owned records. |
| `tenancy.Tenant` | Global tenant identity. Resolve the tenant itself by identity (e.g. slug or ID); all data belonging to it must then use tenant-scoped querysets. |

## Tenant-owned models — always scope by tenant and, where relevant, user/branch access

| Model | Required scope |
|---|---|
| `tenancy.Branch` | `for_tenant(tenant_id)`; branch-specific access must additionally be validated server-side. |
| `catalog.Product` | `for_tenant(tenant_id)`; validate branch/user authorization where the operation is branch-scoped. |
| `inventory.StockMovement` | `for_tenant(tenant_id)`; append-only. |
| `inventory.InventoryBalance` | `for_tenant(tenant_id)`; validate branch access. |
| `inventory.PurchaseReceipt` | `for_tenant(tenant_id)`. |
| `inventory.PurchaseReceiptLine` | `for_tenant(tenant_id)`; preserve parent receipt tenant consistency. |
| `inventory.Supplier` | `for_tenant(tenant_id)`. |
| `inventory.PurchaseReturn` | `for_tenant(tenant_id)`. |
| `inventory.PurchaseReturnLine` | `for_tenant(tenant_id)`; preserve parent return tenant consistency. |
| `inventory.PurchaseInvoice` | `for_tenant(tenant_id)`; posted records are immutable. |
| `inventory.PurchaseInvoiceLine` | `for_tenant(tenant_id)`; parent invoice status must be checked for every write path. |
| `inventory.PurchaseInvoiceAllocation` | `for_tenant(tenant_id)`; parent invoice status must be checked for every write path. |
| `sales.Sale` | `for_tenant(tenant_id)`; validate branch access; posted sales are immutable. |
| `sales.SaleLine` | `for_tenant(tenant_id)`; preserve parent sale tenant consistency; immutable. |
| `sales.SalePayment` | `for_tenant(tenant_id)`; preserve parent sale tenant consistency; immutable. |
| `sales.InvoiceSequence` | `for_tenant(tenant_id)`; advanced only by `allocate_invoice_number()` under a row lock. |
| `sales.CreditNote` | `for_tenant(tenant_id)`; validate branch access; same tenant and branch as its sale; immutable. |
| `sales.CreditNoteLine` | `for_tenant(tenant_id)`; must return a line of its own credit note's sale; immutable. |
| `sales.CreditNoteSequence` | `for_tenant(tenant_id)`; advanced only by `allocate_credit_note_number()` under a row lock. |
| `tenancy.Membership` | Tenant-owned relationship/security data. Scope by `tenant_id` and additionally by user identity when resolving a member. Never treat it as a global identity table. |
| `tenancy.BranchAccess` | Tenant-owned access grant through membership and branch. Resolve using the validated tenant, membership/user, and branch. |

Every non-identity model in `backend/apps/*/models.py` that inherits
`TenantOwnedModel` is tenant-owned even if it is not listed above. This list
must be updated alongside the model when the model set changes.

## Historical migration models — plain historical managers

Django migration state models accessed through `apps.get_model()` inside
`backend/apps/*/migrations/*.py` are historical migration models. They use
Django's historical managers and must not import runtime managers or call
`for_tenant()`. Migration files are immutable once applied; add a new migration
if schema changes are required. The AST checker excludes migration directories.

## Enforcement rules

1. Request and instance `tenant_id` is the source of scope; never query globally
   and filter the results in Python afterward.
2. Queryset chains that read or mutate tenant-owned data start with
   `Model.objects.for_tenant(tenant_id)`, including `get_or_create`,
   `update_or_create`, `select_for_update`, `update`, and `delete`.
3. `.unscoped(reason="...")` is only for reviewed trusted access and requires a
   specific rationale. It is not a substitute for tenant scoping in normal
   request paths.
4. Relationship managers, `refresh_from_db`, `select_related`,
   `prefetch_related`, cascades, and bulk operations need explicit regression
   tests where they can cross tenant boundaries or bypass immutability.
5. User and Tenant are global identity exceptions; Membership and BranchAccess
   are not exceptions.
