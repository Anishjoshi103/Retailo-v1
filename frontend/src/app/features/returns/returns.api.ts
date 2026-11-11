import { HttpHeaders, HttpParams } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiClient } from '../../core/api/api-client.service';
import { CreateReturnRequest, CreditNote, CreditNoteListQuery, CreditNoteSummary } from './returns.models';

@Injectable({ providedIn: 'root' })
export class ReturnsApi {
  private readonly api = inject(ApiClient);

  /**
   * Issue a credit note for items returned from a sale. Reuse the same idempotency key when
   * retrying the same return so a lost response can never refund or restock twice.
   */
  create(saleId: string, request: CreateReturnRequest, idempotencyKey: string): Observable<CreditNote> {
    const headers = new HttpHeaders({ 'Idempotency-Key': idempotencyKey });
    return this.api.post<CreditNote, CreateReturnRequest>(`sales/${encodeURIComponent(saleId)}/returns`, request, { headers });
  }

  list(query: CreditNoteListQuery = {}): Observable<readonly CreditNoteSummary[]> {
    let params = new HttpParams();
    if (query.branchId) params = params.set('branch_id', query.branchId);
    if (query.saleId) params = params.set('sale_id', query.saleId);
    if (query.creditNoteNumber) params = params.set('credit_note_number', query.creditNoteNumber);
    if (query.dateFrom) params = params.set('date_from', query.dateFrom);
    if (query.dateTo) params = params.set('date_to', query.dateTo);
    if (query.limit !== undefined) params = params.set('limit', String(query.limit));
    if (query.offset !== undefined) params = params.set('offset', String(query.offset));
    return this.api.get<readonly CreditNoteSummary[]>('credit-notes', { params });
  }

  get(id: string): Observable<CreditNote> {
    return this.api.get<CreditNote>(`credit-notes/${encodeURIComponent(id)}`);
  }
}
