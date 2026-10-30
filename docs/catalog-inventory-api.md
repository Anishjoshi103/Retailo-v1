# Catalog and inventory API foundation

Base path: `/api/v1/`. Authenticated requests use the bearer access token returned by `POST /api/v1/auth/login`. Tenant and membership IDs are read from the signed access token and checked against the current active membership on each request; callers cannot choose a tenant ID in the request body.

## Products

- `GET /api/v1/products` — list products for the active tenant only.
- `POST /api/v1/products` — create a product for the active tenant.
- Optional list filters: `search` searches name, SKU, or barcode; `active=true` limits to active products.
- SKU is normalized to uppercase and unique per tenant. Barcode is optional.
- HSN accepts 4, 6, or 8 digits when provided.
- Monetary values and GST rate are serialized as decimal strings. The backend uses Django `DecimalField`, not binary floats.
- GST rate currently has only a numeric range guard (0–100%). It is not yet an authoritative HSN/rate mapping. Before production billing, replace manual rate entry with an approved, versioned tax-classification catalogue and effective dates; tax must be resolved by backend rules, not trusted from the client.

## Inventory

- `GET /api/v1/inventory/balances` — list balances in the active tenant; optional `branch_id` and `product_id` filters.
- `POST /api/v1/inventory/adjustments` — append a stock adjustment.
- Every adjustment requires an `Idempotency-Key` header (1–128 characters). Repeating the same key and same branch/product/quantity returns a replay response without applying the movement twice. Reusing the key for a different adjustment returns HTTP 409.
- Quantity is a decimal string with three decimal places. A zero movement is rejected.
- Stock movements are append-only at the ORM layer; correct mistakes by adding a compensating movement, not editing history.
- Branch and product IDs are independently checked against the active tenant. A cross-tenant reference is rejected.

## Current scope and rollout cautions

This is the first catalog/inventory API slice, not a complete inventory ledger or billing implementation. The balance table is maintained transactionally alongside each adjustment, but a reconciliation job and concurrency-focused integration tests are still needed. Stock movements from sales, purchase receipts, returns, negative-stock policy, unit conversions, batches/expiry, and branch-level role permissions are not implemented yet. Product create and inventory adjustments are currently available to any active member; role-based write permissions must be added before production use.

Run backend tests with:

```sh
cd backend
DJANGO_SETTINGS_MODULE=config.settings.ci python manage.py test
```
