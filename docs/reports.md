# Reports

Financial reports are for **owners, admins, managers and accountants**. Cashiers are refused (403). Only
branches the membership is granted are included, and other stores are never visible.

## Sales summary: `GET /api/v1/reports/sales-summary`

Sales, returns, tax and tenders for a date range.

| Parameter | Meaning |
|---|---|
| `date_from` | `YYYY-MM-DD`. Defaults to today (Indian time). |
| `date_to` | `YYYY-MM-DD`. Defaults to `date_from`, so no dates means a one-day report for today. |
| `branch_id` | One branch. Omit for all branches the caller may see. A branch outside the caller's grants returns 403. |

The range is at most 366 days, counting both end dates; a reversed range or a malformed date returns 400.

Response (money as two-decimal strings):

- `sales`: `count`, `taxable_total`, `cgst_total`, `sgst_total`, `igst_total`, `total_tax`, `round_off`, `grand_total`,
  for invoices dated in the range (the invoice date).
- `returns`: the same fields for credit notes dated in the range. Their `grand_total` is the **cash refunded**.
- `net`: `taxable_total`, `total_tax` and `grand_total` after returns (sales minus returns).
- `payments`: sales by tender (`method`, `amount`, `count`), for example cash and UPI. Refunds are always cash, so
  cash in hand is cash sales less `returns.grand_total`.
- `by_day`: one entry per day that had activity, oldest first, with sales and returns counts and totals and the net.
- `branch_id` and `branch_count` say what was included.

Totals are summed in the database. Sales and returns are counted by their own dates, so a return taken today
for an earlier sale reduces today's net, not the day of the sale.

## GST sales register: `GET /api/v1/reports/gst-register`

The tables an accountant files a GSTR-1 style return from. Same access, dates (`date_from`, `date_to`) and
`branch_id` rules as the sales summary. **All figures are net of returns** for the period and come from the
posted invoice and credit note lines, so they always agree with the sales summary (tested).

- `rates`: by place of supply (state code) and tax rate: taxable value, IGST, CGST, SGST/UTGST, cess, plus the
  sales and returns taxable values it was netted from.
- `hsn`: by HSN code, unit and rate: description, unit quantity code (UQC), net quantity, total value, taxable
  value and tax. Units map to `NOS` (each), `KGS`, `GMS`, `LTR`, `MLT`, `MTR`, `PAC`; anything else is `OTH`.
- `documents`: per branch, the first and last invoice number and credit note number issued in the period and
  how many. `cancelled` is always 0 because posted documents are never cancelled (corrections are credit notes).
- `totals` and `missing_hsn_lines`: the number of sold lines whose product has no HSN code, so they can be fixed.

`GET /api/v1/reports/gst-register.csv?table=rates|hsn|documents` returns one table as a CSV download with
the same filters. Text cells that start with `=`, `+`, `-` or `@` are prefixed with an apostrophe so a
spreadsheet cannot run them as formulas.

### What this is, and is not

- It covers **B2C supplies by place of supply and rate** (the small-supply table) and the HSN and document
  summaries. Customer GSTIN and inter-state business sales are not recorded yet, so there is no B2B table.
- Cess is not modelled and is always `0.00`.
- Branch series are numbered per branch, so documents are listed per branch.
- It is a working aid: have an accountant review the figures before filing. The column headers follow the
  return's table names but the files are not the government offline tool's import format.

## Not built yet

Stock valuation, purchase reports, a per-product sales report, and a B2B / inter-state table.
