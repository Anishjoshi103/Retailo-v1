import { HttpHeaders, HttpParams } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiClient } from '../../core/api/api-client.service';
import { AdjustStockRequest, AdjustStockResult, ProductSummary, StockBalance } from './inventory.models';

@Injectable({ providedIn: 'root' })
export class InventoryApi {
  private readonly api = inject(ApiClient);

  balances(branchId: string, limit = 50, offset = 0, search = ''): Observable<readonly StockBalance[]> {
    let params = new HttpParams().set('branch_id', branchId).set('limit', String(limit)).set('offset', String(offset));
    if (search.trim()) params = params.set('search', search.trim());
    return this.api.get<readonly StockBalance[]>('inventory/balances', { params });
  }

  /** Active products matching the text, for choosing something that has no stock record yet. */
  searchProducts(text: string): Observable<readonly ProductSummary[]> {
    return this.api.get<readonly ProductSummary[]>('products', { params: new HttpParams().set('search', text).set('active', 'true') });
  }

  /**
   * Apply a signed stock change. Reuse the same idempotency key when retrying the same adjustment so a
   * lost response can never apply it twice.
   */
  adjust(request: AdjustStockRequest, idempotencyKey: string): Observable<AdjustStockResult> {
    const headers = new HttpHeaders({ 'Idempotency-Key': idempotencyKey });
    return this.api.post<AdjustStockResult, AdjustStockRequest>('inventory/adjustments', request, { headers });
  }
}
