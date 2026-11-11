# Credit notes (sales returns)

A credit note reverses part or all of one posted sale. This document records the policy
and the data model; the posting API and screens follow in later PRs.

## Policy (decided with the store owner)

- **Returned items always go back into sellable stock.** There is no write-off option.
- **Refunds are cash only.** The credit note's `grand_total` is the cash handed back.
- Posted credit notes, like invoices, are immutable. Mistakes are corrected with a new document.

## Models (`apps/sales`)

| Model | Purpose |
|---|---|
| `CreditNote` | The document: links to its `Sale`, snapshots seller/supply/customer details, tax and totals (same shape as `Sale`), a required `reason`, idempotency key. |
| `CreditNoteLine` | One returned line, linked to the original `SaleLine` (`sale_line`) so returns can be capped at what was sold. Snapshots product, MRP, GST rate and amounts. |
| `CreditNoteSequence` | Gapless per-branch counter, independent of the invoice counter. |

All three are tenant-owned (see `tenant-model-classification.md`).

## Integrity

- Immutable through every path (save, delete, `update`, `bulk_update`, queryset `delete`).
- A credit note must belong to the same tenant **and branch** as its sale. A line must
  return a line of its own credit note's sale, for the same product.
- Check constraints: tax components sum, `grand_total = taxable + tax + round_off`, line
  total sum, positive quantity, GST rate 0-100 (compared at paise precision, as for sales).
- Unique credit note number per tenant/branch and idempotency key per tenant.

## Numbering

`CN-<BRANCHCODE>-<6 digit serial>`, for example `CN-MAIN-000001`, allocated the same way
as invoice numbers: gapless, inside the document's own transaction, under a row lock, never
resetting each year, and validated against GST's 16-character limit. Invoice and credit
note counters are separate.

## Posting a return — `POST /api/v1/sales/{id}/returns`

Requires an `Idempotency-Key` header. Owner, admin, manager and cashier may call it for a sale
in a branch they hold a grant on; accountants cannot. Unknown, foreign-store and ungranted-branch
sales return 404.

```json
{"reason": "Damaged", "lines": [{"sale_line_id": "<uuid>", "quantity": "1"}]}
```

- `sale_line_id` is the line's `id` from `GET /api/v1/sales/{id}`; each line may appear once.
- Amounts are never client-supplied; they are reversed from the sale.
- **Cap:** the quantity returned across all credit notes for a line can never exceed the
  quantity sold. The sale row is locked while this is checked, and the branch's credit note
  counter serialises concurrent returns.
- **Tax reversal:** for each of taxable value, CGST, SGST and IGST, the amount returned so far
  is the original amount x (cumulative quantity returned / quantity sold), rounded half-up to
  paise; a return takes the difference between the running totals after and before it. Repeated
  partial returns therefore add up to the original line exactly, never go negative, and keep
  CGST equal to SGST. An individual partial return can differ from the MRP by a paisa; the
  refund is rounded to the rupee like the invoice.
- **Refund:** the credit note's `grand_total` (`refund_amount`), always cash. Returning every
  line of a sale refunds exactly the invoice's grand total.
- **Stock:** each returned line is added back to the branch's inventory and recorded as a
  `return` stock movement referencing the credit note number.
- **Idempotency:** the same key and request replays the original credit note (200,
  `replayed: true`) with no second restock; the same key with a different request is 409.
  Everything is atomic, so a rejected return consumes no number and changes no stock.

`GET /api/v1/sales/{id}` lines now include their `id` for this purpose.

## Planned next

- Credit note list/detail reads, then the "Return items" screen and a printable credit note.
