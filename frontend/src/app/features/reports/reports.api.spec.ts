import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { APP_CONFIG } from '../../core/config/app-config.token';
import { ReportsApi } from './reports.api';

describe('ReportsApi', () => {
  let api: ReportsApi;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting(), { provide: APP_CONFIG, useValue: { apiBaseUrl: '/api/v1' } }],
    });
    api = TestBed.inject(ReportsApi);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('requests the sales summary sending only what was provided', () => {
    api.salesSummary({ dateFrom: '2026-11-01', dateTo: '2026-11-16', branchId: 'b-1' }).subscribe();
    const request = http.expectOne((req) => req.url === '/api/v1/reports/sales-summary');
    expect(request.request.method).toBe('GET');
    expect(request.request.params.get('date_from')).toBe('2026-11-01');
    expect(request.request.params.get('date_to')).toBe('2026-11-16');
    expect(request.request.params.get('branch_id')).toBe('b-1');
    request.flush({});
  });

  it('sends no parameters for today across all branches', () => {
    api.salesSummary().subscribe();
    const request = http.expectOne((req) => req.url === '/api/v1/reports/sales-summary');
    expect(request.request.params.keys()).toEqual([]);
    request.flush({});
  });
});
