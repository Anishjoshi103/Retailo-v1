import { HttpHeaders, HttpParams } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiClient } from '../../core/api/api-client.service';
import {
  CreateSupplierRequest,
  PurchaseReceipt,
  ReceiptDetail,
  ReceiptListQuery,
  ReceiptSummary,
  ReceiveGoodsRequest,
  Supplier,
  SupplierListQuery,
  UpdateSupplierRequest,
} from './purchases.models';

@Injectable({ providedIn: 'root' })
export class PurchasesApi {
  private readonly api = inject(ApiClient);

  suppliers(query: SupplierListQuery = {}): Observable<readonly Supplier[]> {
    let params = new HttpParams();
    if (query.search) params = params.set('search', query.search);
    if (query.active !== undefined) params = params.set('active', String(query.active));
    if (query.limit !== undefined) params = params.set('limit', String(query.limit));
    if (query.offset !== undefined) params = params.set('offset', String(query.offset));
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

  /** Owner, admin or manager only. Send just the fields that changed; `is_active: false` deactivates. */
  updateSupplier(id: string, request: UpdateSupplierRequest): Observable<Supplier> {
    return this.api.patch<Supplier, UpdateSupplierRequest>(`inventory/suppliers/${encodeURIComponent(id)}`, request);
  }

  /** Past deliveries (cost data: owner, admin, manager and accountant only), newest first. */
  receipts(query: ReceiptListQuery = {}): Observable<readonly ReceiptSummary[]> {
    let params = new HttpParams();
    if (query.branchId) params = params.set('branch_id', query.branchId);
    if (query.supplierId) params = params.set('supplier_id', query.supplierId);
    if (query.invoiceNumber) params = params.set('invoice_number', query.invoiceNumber);
    if (query.dateFrom) params = params.set('date_from', query.dateFrom);
    if (query.dateTo) params = params.set('date_to', query.dateTo);
    if (query.limit !== undefined) params = params.set('limit', String(query.limit));
    if (query.offset !== undefined) params = params.set('offset', String(query.offset));
    return this.api.get<readonly ReceiptSummary[]>('inventory/receipts', { params });
  }

  receipt(id: string): Observable<ReceiptDetail> {
    return this.api.get<ReceiptDetail>(`inventory/receipts/${encodeURIComponent(id)}`);
  }
}
