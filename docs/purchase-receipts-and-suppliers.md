# Goods receipts and suppliers: reads and edits

Completes the purchasing API that the Receive goods and Suppliers screens use.

## Reading goods receipts

Receipts carry cost prices, so reads are limited to **owner, admin, manager and accountant** (cashiers
get 403, matching who may record a delivery). Only branches the membership is granted are visible.

- `GET /api/v1/inventory/receipts`: compact rows, newest first, with `line_count` and `total_cost`.
  Filters: `branch_id` (an inaccessible branch returns 403), `supplier_id`, `invoice_number`
  (the supplier's invoice number, partial and case-insensitive), `date_from` / `date_to`
  (`YYYY-MM-DD`, on the day received), `limit` (1-200, default 50), `offset`.
- `GET /api/v1/inventory/receipts/{id}`: the receipt with its lines (`sku`, `name`, `unit`, `quantity`,
  `unit_cost`, `line_total`) ordered by product name. Unknown, foreign-store and ungranted-branch
  receipts all return 404.
- `POST /api/v1/inventory/receipts` is unchanged (see `purchase-gst-foundation.md`).

`total_cost` is the sum of each line's `quantity x unit_cost` **rounded half-up to paise per line**,
the same rule the Receive goods screen shows, so the two always agree.

## Editing suppliers

- `GET /api/v1/inventory/suppliers/{id}`: any role in the store.
- `PATCH /api/v1/inventory/suppliers/{id}` (owner, admin, manager): `name`, `gstin`, `phone`, `email`,
  `address`, `is_active`. The same validation as creating applies (a name is required; the GSTIN must be
  well formed and unique within the store, and the supplier being edited does not count as a duplicate of
  itself). A GSTIN may be cleared. `PUT` and `DELETE` are not allowed.
- **Renaming never rewrites history:** receipts keep the supplier name as it was when the delivery was
  recorded.
- **Deactivating** (`is_active: false`) hides the supplier from new deliveries (a delivery naming an
  inactive supplier is refused) and from `?active=true` lists. Nothing is deleted, and reactivating restores it.
