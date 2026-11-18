/** Shapes of the reports API (`/reports/sales-summary`). Money is a two-decimal string. */

export interface ReportTotals {
  readonly count: number;
  readonly taxable_total: string;
  readonly cgst_total: string;
  readonly sgst_total: string;
  readonly igst_total: string;
  readonly total_tax: string;
  readonly round_off: string;
  readonly grand_total: string;
}

export interface NetTotals {
  readonly taxable_total: string;
  readonly total_tax: string;
  readonly grand_total: string;
}

export interface PaymentTotal {
  readonly method: string;
  readonly amount: string;
  readonly count: number;
}

export interface DaySummary {
  readonly date: string;
  readonly sales_count: number;
  readonly sales_total: string;
  readonly returns_count: number;
  readonly returns_total: string;
  readonly net_total: string;
}

export interface SalesSummary {
  readonly date_from: string;
  readonly date_to: string;
  readonly branch_id: string | null;
  readonly branch_count: number;
  readonly sales: ReportTotals;
  /** `grand_total` here is the cash refunded to customers. */
  readonly returns: ReportTotals;
  readonly net: NetTotals;
  readonly payments: readonly PaymentTotal[];
  readonly by_day: readonly DaySummary[];
}

export interface SalesSummaryQuery {
  /** Omit both dates for today (the server decides what "today" is). */
  readonly dateFrom?: string;
  readonly dateTo?: string;
  /** Omit for every branch the caller may see. */
  readonly branchId?: string;
}
