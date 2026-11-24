/** Shapes of the purchasing API (`/inventory/suppliers`, `/inventory/receipts`). Money and quantities are decimal strings. */

export interface Supplier {
  readonly id: string;
  readonly name: string;
  readonly gstin: string;
  readonly phone: string;
  readonly email: string;
  readonly address: string;
  readonly is_active: boolean;
  readonly created_at: string;
  readonly updated_at: string;
}

export interface CreateSupplierRequest {
  readonly name: string;
  readonly gstin?: string;
  readonly phone?: string;
  readonly email?: string;
  readonly address?: string;
}

export interface SupplierListQuery {
  readonly search?: string;
  readonly active?: boolean;
  readonly limit?: number;
  readonly offset?: number;
}

export interface ReceiveGoodsLine {
  readonly product_id: string;
  readonly quantity: string;
  readonly unit_cost: string;
}

/** Name the supplier either by `supplier_id` (a saved supplier) or by `supplier_name`, not both. */
export interface ReceiveGoodsRequest {
  readonly branch_id: string;
  readonly supplier_id?: string;
  readonly supplier_name?: string;
  readonly supplier_invoice_number?: string;
  readonly lines: readonly ReceiveGoodsLine[];
}

export interface PurchaseReceipt {
  readonly id: string;
  readonly branch_id: string;
  readonly supplier_id: string | null;
  readonly supplier_name: string;
  readonly supplier_invoice_number: string;
  readonly received_at: string;
  /** True when an earlier identical request was replayed. */
  readonly replayed: boolean;
  readonly lines: readonly ReceiveGoodsLine[];
}

export interface UpdateSupplierRequest {
  readonly name?: string;
  readonly gstin?: string;
  readonly phone?: string;
  readonly email?: string;
  readonly address?: string;
  readonly is_active?: boolean;
}

export interface ReceiptSummary {
  readonly id: string;
  readonly branch_id: string;
  readonly supplier_id: string | null;
  readonly supplier_name: string;
  readonly supplier_invoice_number: string;
  readonly received_at: string;
  readonly line_count: number;
  /** Sum of each line's quantity x cost, rounded to paise per line. */
  readonly total_cost: string;
}

export interface ReceiptLineView {
  readonly id: string;
  readonly product_id: string;
  readonly sku: string;
  readonly name: string;
  readonly unit: string;
  readonly quantity: string;
  readonly unit_cost: string;
  readonly line_total: string;
}

export interface ReceiptDetail extends ReceiptSummary {
  readonly lines: readonly ReceiptLineView[];
}

export interface ReceiptListQuery {
  readonly branchId?: string;
  readonly supplierId?: string;
  readonly invoiceNumber?: string;
  readonly dateFrom?: string;
  readonly dateTo?: string;
  readonly limit?: number;
  readonly offset?: number;
}
