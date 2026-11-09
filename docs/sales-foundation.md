# Sales foundation

Data model and invoice numbering for retail sales. The posting API (`POST /api/v1/sales`)
is a separate follow-up PR; nothing here is exposed over HTTP yet.

## Models (`apps/sales`)

| Model | Purpose |
|---|---|
| `Sale` | A posted tax invoice. No draft state: every row is final. Snapshots seller GSTIN, seller state and place of supply. |
| `SaleLine` | Product snapshot (SKU, name, HSN, unit, GST rate) with quantity, price and CGST/SGST/IGST amounts. |
| `SalePayment` | One tender per row (`cash`, `upi`, `card`, `other`); a sale may be split across several. |
| `InvoiceSequence` | Gapless counter, one row per tenant and branch. |

All four are tenant-owned (see `tenant-model-classification.md`).

## Immutability

Sales, lines and payments cannot be saved again, deleted, or changed through
`update()`, `bulk_update()` or `delete()` on their querysets. Corrections will be new
documents (credit notes), not edits. Children must share their sale's tenant.

## Database integrity

Check constraints keep stored money consistent even if application code is bypassed:

- sale: `total_tax = cgst + sgst + igst`; `grand_total = taxable + total_tax + round_off`
- line: `line_total = taxable_value + cgst + sgst + igst`; quantity > 0; GST rate 0-100
- payment: amount > 0
- uniqueness: invoice number per tenant/branch; idempotency key per tenant

## Invoice numbers

Format `INV-<BRANCHCODE>-<6 digit serial>`, for example `INV-MAIN-000001`.

- GST allows at most 16 characters (letters, digits, hyphen, slash), so a branch code
  can be at most 5 characters. `allocate_invoice_number()` rejects longer codes, invalid
  characters, and serial overflow without consuming a number.
- The serial does not reset each financial year, so numbers stay unique across years.
- Numbers are allocated inside the sale's own transaction, under a row lock on the
  branch's sequence. A failed sale rolls the counter back, so numbers are never skipped.
- Allocation outside a transaction raises.

## Posting

See `sales-posting.md` for `POST /api/v1/sales`.

## Note on stored money checks

The sum check constraints compare against `ROUND(sum, 2)`. SQLite stores decimals as
floats, so an exact sum such as 84.74 + 7.63 + 7.63 can differ in the last bit; rounding to
paise makes the checks behave identically on SQLite and SQL Server.
