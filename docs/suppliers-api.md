# Supplier master API

Base path: `/api/v1/inventory/`.

## List and create

- `GET /api/v1/inventory/suppliers` — list suppliers for the authenticated active tenant.
- `POST /api/v1/inventory/suppliers` — create a supplier; restricted to owner, admin, or manager memberships.
- Optional `search` matches supplier name, GSTIN, or phone. `active=true` / `active=false` filters by active status.
- GSTIN is trimmed, uppercased, and checked against the expected 15-character format. This is format validation only; it does not prove GST registration or status against GSTN.
- Non-empty GSTIN is unique per tenant. Supplier records are never shared across tenants.

## Purchase receipt integration

`POST /api/v1/inventory/receipts` now accepts either:
- `supplier_id` for an active supplier in the same tenant, or
- `supplier_name` for an ad-hoc supplier snapshot during transition.

When `supplier_id` is supplied, the API uses the supplier master name and rejects a conflicting caller-supplied name. The receipt stores the supplier FK and a name snapshot so a later supplier rename does not rewrite posted history. A supplier from another tenant is rejected.

## Outstanding before production

This slice does not verify GSTIN against GSTN, maintain supplier balances, match purchase orders, parse supplier invoices, calculate input tax credit, calculate purchase invoice taxes/discounts, or support purchase returns/reversals. Those require explicit tax/accounting rules and should be implemented before purchase accounting is relied upon. No local test or migration check is claimed while the Codespace is unavailable; CI must pass before merge.
