import { HttpHeaders, HttpParams } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiClient } from '../../core/api/api-client.service';
import { CreateSaleRequest, Sale, SaleListQuery, SaleSummary } from './sales.models';

@Injectable({ providedIn: 'root' })
export class SalesApi {
  private readonly api = inject(ApiClient);

  /**
   * Post a sale. Reuse the same idempotency key when retrying the same sale so a lost
   * response can never produce a second invoice or a second stock deduction.
   */
  create(request: CreateSaleRequest, idempotencyKey: string): Observable<Sale> {
    const headers = new HttpHeaders({ 'Idempotency-Key': idempotencyKey });
    return this.api.post<Sale, CreateSaleRequest>('sales', request, { headers });
  }

  list(query: SaleListQuery = {}): Observable<readonly SaleSummary[]> {
    let params = new HttpParams();
    if (query.branchId) params = params.set('branch_id', query.branchId);
    if (query.dateFrom) params = params.set('date_from', query.dateFrom);
    if (query.dateTo) params = params.set('date_to', query.dateTo);
    if (query.invoiceNumber) params = params.set('invoice_number', query.invoiceNumber);
    if (query.limit !== undefined) params = params.set('limit', String(query.limit));
    if (query.offset !== undefined) params = params.set('offset', String(query.offset));
    return this.api.get<readonly SaleSummary[]>('sales', { params });
  }

  get(id: string): Observable<Sale> {
    return this.api.get<Sale>(`sales/${encodeURIComponent(id)}`);
  }
}
