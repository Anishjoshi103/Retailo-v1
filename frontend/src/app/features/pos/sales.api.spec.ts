import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { APP_CONFIG } from '../../core/config/app-config.token';
import { SalesApi } from './sales.api';
import { CreateSaleRequest } from './sales.models';

describe('SalesApi', () => {
  let api: SalesApi;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: APP_CONFIG, useValue: { apiBaseUrl: '/api/v1' } },
      ],
    });
    api = TestBed.inject(SalesApi);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('posts a sale with the idempotency key header and decimal strings', () => {
    const body: CreateSaleRequest = {
      branch_id: 'b-1',
      lines: [{ product_id: 'p-1', quantity: '2.000' }],
      payments: [{ method: 'cash', amount: '200.00' }],
    };
    api.create(body, 'key-123').subscribe();
    const request = http.expectOne('/api/v1/sales');
    expect(request.request.method).toBe('POST');
    expect(request.request.headers.get('Idempotency-Key')).toBe('key-123');
    expect(request.request.body).toEqual(body);
    request.flush({});
  });

  it('lists sales sending only the filters that were provided', () => {
    api.list({ branchId: 'b-1', invoiceNumber: 'INV-MAIN-000001', limit: 20, offset: 0 }).subscribe();
    const request = http.expectOne((req) => req.url === '/api/v1/sales');
    expect(request.request.method).toBe('GET');
    expect(request.request.params.get('branch_id')).toBe('b-1');
    expect(request.request.params.get('invoice_number')).toBe('INV-MAIN-000001');
    expect(request.request.params.get('limit')).toBe('20');
    expect(request.request.params.get('offset')).toBe('0');
    expect(request.request.params.has('date_from')).toBe(false);
    request.flush([]);
  });

  it('lists with no filters when none are given', () => {
    api.list().subscribe();
    const request = http.expectOne((req) => req.url === '/api/v1/sales');
    expect(request.request.params.keys()).toEqual([]);
    request.flush([]);
  });

  it('fetches one sale by id', () => {
    api.get('abc-123').subscribe();
    const request = http.expectOne('/api/v1/sales/abc-123');
    expect(request.request.method).toBe('GET');
    request.flush({});
  });
});
