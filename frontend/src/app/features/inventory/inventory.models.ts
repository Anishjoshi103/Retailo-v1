/** Shapes of the inventory API (`/inventory/balances`, `/inventory/adjustments`). Quantities are decimal strings. */

export interface StockBalance {
  readonly id: string;
  readonly branch: string;
  readonly product: string;
  readonly product_sku: string;
  readonly product_name: string;
  /** May be negative when a manager sold below available stock. */
  readonly quantity_on_hand: string;
  readonly updated_at: string;
}

export interface ProductSummary {
  readonly id: string;
  readonly sku: string;
  readonly barcode: string | null;
  readonly name: string;
  readonly unit: string;
  readonly is_active: boolean;
}

export interface AdjustStockRequest {
  readonly branch_id: string;
  readonly product_id: string;
  /** Signed change to apply; never zero. */
  readonly quantity_delta: string;
  readonly note?: string;
  readonly reference?: string;
}

export interface AdjustStockResult {
  readonly movement_id: string;
  readonly quantity_on_hand: string;
  /** True when an earlier identical request was replayed. */
  readonly replayed: boolean;
}
