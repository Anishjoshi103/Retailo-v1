# Purchase receipts API

## Endpoint

`POST /api/v1/inventory/receipts`

Requires an authenticated owner, admin, or manager membership in an active tenant and an `Idempotency-Key` header (1–128 characters).

Example request:

```json
{
  "branch_id": "branch-uuid",
  "supplier_name": "Supplier Pvt Ltd",
  "supplier_invoice_number": "INV-2026-001",
  "lines": [
    { "product_id": "product-uuid", "quantity": "12.500", "unit_cost": "45.00" }
  ]
}
```

- The branch and every product must be active and belong to the authenticated tenant.
- Quantity and unit cost use decimal strings; quantity must be positive and unit cost non-negative.
- A product may appear only once in a receipt. Combine quantities before submitting duplicate product lines.
- One database transaction creates the immutable receipt and lines, appends receipt stock movements, and updates the branch balance.
- Replaying the same idempotency key with the same normalized payload returns the original receipt with `replayed: true` and does not increase stock again.
- Reusing the key with a different payload returns HTTP 409.
- Posted receipts and receipt lines are immutable at the ORM layer. Corrections should use compensating stock movements, not edit the receipt.

## Current limitations

This first slice records supplier name and invoice reference as text; it does not yet provide a supplier master, purchase-order matching, invoice attachment, supplier GSTIN validation, input-tax-credit accounting, purchase returns, or receipt reversal API. Receipt totals are intentionally not calculated here because tax treatment and invoice-level discounts need a dedicated purchase-tax model. Concurrency-sensitive receipt posting must be validated on the production SQL Server engine before release. Public endpoint rate limits and audit-event integration are also outstanding.

Run backend tests and migration checks in CI before merging. The developer Codespace was unavailable during implementation, so no local test/build result is claimed.
