import { HttpHeaders, HttpParams } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiClient } from '../../core/api/api-client.service';
import { CreateSupplierRequest, PurchaseReceipt, ReceiveGoodsRequest, Supplier, SupplierListQuery } from './purchases.models';

@Injectable({ providedIn: 'root' })
export class PurchasesApi {
  private readonly api = inject(ApiClient);

  suppliers(query: SupplierListQuery = {}): Observable<readonly Supplier[]> {
    let params = new HttpParams();
    if (query.search) params = params.set('search', query.search);
    if (query.active !== undefined) params = params.set('active', String(query.active));
    return this.api.get<readonly Supplier[]>('inventory/suppliers', { params });
  }

  /** Owner, admin or manager only. */
  createSupplier(request: CreateSupplierRequest): Observable<Supplier> {
    return this.api.post<Supplier, CreateSupplierRequest>('inventory/suppliers', request);
  }

  /**
   * Record goods received into a branch's stock. Reuse the same idempotency key when retrying the same
   * delivery so a lost response can never add the stock twice.
   */
  receiveGoods(request: ReceiveGoodsRequest, idempotencyKey: string): Observable<PurchaseReceipt> {
    const headers = new HttpHeaders({ 'Idempotency-Key': idempotencyKey });
    return this.api.post<PurchaseReceipt, ReceiveGoodsRequest>('inventory/receipts', request, { headers });
  }
}
