# Posting a sale — `POST /api/v1/sales`

Creates one final GST tax invoice, deducts stock and records payments in a single
transaction. Requires an `Idempotency-Key` header (max 128 characters).

## Request

```json
{
  "branch_id": "<uuid>",
  "customer_name": "optional",
  "allow_negative_stock": false,
  "lines": [{"product_id": "<uuid>", "quantity": "2"}],
  "payments": [{"method": "cash", "amount": "236.00"}, {"method": "upi", "amount": "10.00", "reference": "UPI-1"}]
}
```

- `quantity` up to 3 decimals, > 0. A product may appear once; 1-200 lines.
- `method` is `cash`, `upi`, `card` or `other`; 1-10 payments.
- **Prices and tax are never accepted from the client.** The unit price and GST rate
  come from the catalogue at posting time and are snapshotted on the invoice lines.

## Who may call it

Owner, admin, manager and cashier, for a branch they hold an active grant on. Accountants
cannot sell. `allow_negative_stock` needs owner, admin or manager (cashiers get 403).

## Calculation

- Prices are **tax-exclusive**: `taxable = quantity × selling_price` (rounded to paise),
  GST is added per line using `apps.gst`.
- Place of supply is the branch's state, so every sale is intra-state (CGST + SGST). The
  branch needs a `state_code` (see `branch-gst-identity.md`), otherwise the request is rejected.
- The grand total is rounded to the nearest rupee; `round_off` records the difference.
- Payments must add up exactly to the grand total. Credit sales and change-giving are
  not modelled yet.

## Stock

Each line deducts from the branch's `InventoryBalance` and writes a `sale` stock movement
referencing the invoice number. If on-hand stock is short the sale is **blocked** (400),
unless a manager/admin/owner sets `allow_negative_stock`, in which case stock may go
negative and the movement note records the override.

## Idempotency

A repeated key with the same request returns 200 with `replayed: true` and the original
invoice, with no second deduction. The same key with a different request returns 409.
Everything is atomic: a rejected sale consumes no invoice number and changes no stock.

## Not included yet

Customer GSTIN / inter-state supply, discounts, credit or partial payments, listing and
fetching sales, credit notes and the billing screen.
