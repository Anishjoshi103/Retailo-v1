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

## Not built yet

A GST sales register / GSTR-1 style export (by rate and place of supply, and HSN summary), stock valuation,
purchase reports and a per-product sales report.
