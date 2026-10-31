# Supplier purchase returns API

## Endpoint

`POST /api/v1/inventory/returns`

Requires an authenticated owner, admin, or manager membership in the active tenant and an `Idempotency-Key` header of 1–128 characters.

Example:

```json
{
  "receipt_id": "receipt-uuid",
  "reason": "Damaged packaging",
  "lines": [
    { "receipt_line_id": "receipt-line-uuid", "quantity": "2.500" }
  ]
}
```

- The receipt and each receipt line must belong to the authenticated tenant; each requested line must belong to the selected receipt.
- Each receipt line may appear once per return. Quantity must be a positive decimal string.
- Returns cannot exceed the originally received quantity after previous posted returns, and cannot reduce branch stock below zero.
- The transaction creates an immutable return and return lines, reduces the branch balance, and appends negative stock movements.
- Replaying the same idempotency key and payload returns the original return without reducing stock again. Reusing the key with a different payload returns HTTP 409.
- Posted returns are append-only; a mistaken return needs a separately authorized compensating workflow.

## Important accounting boundary

This API is an inventory movement only. It does **not** create supplier credit notes, reverse purchase tax or input tax credit, calculate GST, adjust supplier balances, or account for landed cost. Those financial actions must be implemented with a dedicated purchase-tax/accounting model and must not be inferred from stock quantities. A return does not establish that a supplier has accepted the goods or issued a credit note.

## Verification

Automated tests cover return posting, stock reduction, retry safety, and quantity-limit rejection. The Codespace terminal was unavailable during implementation, so tests and migrations have not been executed locally. Verify CI, migration consistency, and locking behavior on SQL Server before merging.
