import { HttpParams } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiClient } from '../../core/api/api-client.service';
import { SalesSummary, SalesSummaryQuery } from './reports.models';

@Injectable({ providedIn: 'root' })
export class ReportsApi {
  private readonly api = inject(ApiClient);

  /** Owner, admin, manager and accountant only. */
  salesSummary(query: SalesSummaryQuery = {}): Observable<SalesSummary> {
    let params = new HttpParams();
    if (query.dateFrom) params = params.set('date_from', query.dateFrom);
    if (query.dateTo) params = params.set('date_to', query.dateTo);
    if (query.branchId) params = params.set('branch_id', query.branchId);
    return this.api.get<SalesSummary>('reports/sales-summary', { params });
  }
}
