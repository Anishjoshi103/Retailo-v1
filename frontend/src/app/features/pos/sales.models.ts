/** Shapes of the sales API (`/sales`). Money and quantities are decimal strings, never numbers. */

export type PaymentMethod = 'cash' | 'upi' | 'card' | 'other';

export interface CreateSaleLine {
  readonly product_id: string;
  readonly quantity: string;
}

export interface CreateSalePayment {
  readonly method: PaymentMethod;
  readonly amount: string;
  readonly reference?: string;
}

export interface CreateSaleRequest {
  readonly branch_id: string;
  readonly customer_name?: string;
  readonly allow_negative_stock?: boolean;
  readonly lines: readonly CreateSaleLine[];
  readonly payments: readonly CreateSalePayment[];
}

export interface SaleSummary {
  readonly id: string;
  readonly invoice_number: string;
  readonly invoice_date: string;
  readonly branch_id: string;
  readonly customer_name: string;
  readonly taxable_total: string;
  readonly total_tax: string;
  readonly round_off: string;
  readonly grand_total: string;
  readonly created_at: string;
}

export interface SaleLineView {
  readonly product_id: string;
  readonly sku: string;
  readonly name: string;
  readonly hsn_code: string;
  readonly unit: string;
  readonly quantity: string;
  /** Tax-inclusive (MRP-style) unit price as sold. */
  readonly unit_price: string;
  readonly gst_rate: string;
  readonly taxable_value: string;
  readonly cgst_amount: string;
  readonly sgst_amount: string;
  readonly igst_amount: string;
  readonly line_total: string;
}

export interface SalePaymentView {
  readonly method: PaymentMethod;
  readonly amount: string;
  readonly reference: string;
}

export interface Sale extends SaleSummary {
  readonly seller_gstin: string;
  readonly seller_state_code: string;
  readonly place_of_supply_state_code: string;
  readonly cgst_total: string;
  readonly sgst_total: string;
  readonly igst_total: string;
  readonly lines: readonly SaleLineView[];
  readonly payments: readonly SalePaymentView[];
  /** Present on POST responses only: true when an earlier identical request was replayed. */
  readonly replayed?: boolean;
}

export interface SaleListQuery {
  readonly branchId?: string;
  readonly dateFrom?: string;
  readonly dateTo?: string;
  readonly invoiceNumber?: string;
  readonly limit?: number;
  readonly offset?: number;
}
