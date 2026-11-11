/** Shapes of the returns API (`/sales/{id}/returns`, `/credit-notes`). Money and quantities are decimal strings. */

export interface CreateReturnLine {
  readonly sale_line_id: string;
  readonly quantity: string;
}

export interface CreateReturnRequest {
  readonly reason: string;
  readonly lines: readonly CreateReturnLine[];
}

export interface CreditNoteSummary {
  readonly id: string;
  readonly credit_note_number: string;
  readonly credit_note_date: string;
  readonly sale_id: string;
  readonly invoice_number: string;
  readonly branch_id: string;
  readonly reason: string;
  readonly customer_name: string;
  /** Cash handed back to the customer. */
  readonly grand_total: string;
  readonly created_at: string;
}

export interface CreditNoteLineView {
  readonly sale_line_id: string;
  readonly product_id: string;
  readonly sku: string;
  readonly name: string;
  readonly hsn_code: string;
  readonly unit: string;
  readonly quantity: string;
  readonly unit_price: string;
  readonly gst_rate: string;
  readonly taxable_value: string;
  readonly cgst_amount: string;
  readonly sgst_amount: string;
  readonly igst_amount: string;
  readonly line_total: string;
}

export interface CreditNote extends CreditNoteSummary {
  readonly seller_gstin: string;
  readonly seller_state_code: string;
  readonly place_of_supply_state_code: string;
  readonly taxable_total: string;
  readonly cgst_total: string;
  readonly sgst_total: string;
  readonly igst_total: string;
  readonly total_tax: string;
  readonly round_off: string;
  readonly refund_method: 'cash';
  readonly refund_amount: string;
  readonly lines: readonly CreditNoteLineView[];
  /** Present on POST responses only: true when an earlier identical request was replayed. */
  readonly replayed?: boolean;
}

export interface CreditNoteListQuery {
  readonly branchId?: string;
  readonly saleId?: string;
  readonly creditNoteNumber?: string;
  readonly dateFrom?: string;
  readonly dateTo?: string;
  readonly limit?: number;
  readonly offset?: number;
}
