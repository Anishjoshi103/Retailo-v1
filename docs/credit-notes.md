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

## Planned next

- `POST /api/v1/sales/{id}/returns`: partial or full returns capped at the quantity sold
  across all earlier credit notes; tax reversed from the original line (the final return of
  a line takes the exact remainder, so repeated partial returns reconcile with the invoice);
  stock restored; cash refund equal to the credit note total.
- Credit note list/detail reads, then the "Return items" screen and printable credit note.
