import { HttpParams } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiClient } from '../../core/api/api-client.service';
import { GstRegister, GstTable, SalesSummary, SalesSummaryQuery } from './reports.models';

@Injectable({ providedIn: 'root' })
export class ReportsApi {
  private readonly api = inject(ApiClient);

  /** Owner, admin, manager and accountant only. */
  salesSummary(query: SalesSummaryQuery = {}): Observable<SalesSummary> {
    return this.api.get<SalesSummary>('reports/sales-summary', { params: this.params(query) });
  }

  /** The GST sales register (net of returns). Owner, admin, manager and accountant only. */
  gstRegister(query: SalesSummaryQuery = {}): Observable<GstRegister> {
    return this.api.get<GstRegister>('reports/gst-register', { params: this.params(query) });
  }

  /** One register table as a CSV file. */
  gstRegisterCsv(table: GstTable, query: SalesSummaryQuery = {}): Observable<Blob> {
    return this.api.getBlob('reports/gst-register.csv', { params: this.params(query).set('table', table) });
  }

  private params(query: SalesSummaryQuery): HttpParams {
    let params = new HttpParams();
    if (query.dateFrom) params = params.set('date_from', query.dateFrom);
    if (query.dateTo) params = params.set('date_to', query.dateTo);
    if (query.branchId) params = params.set('branch_id', query.branchId);
    return params;
  }
}
