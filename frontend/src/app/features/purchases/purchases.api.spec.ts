import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { APP_CONFIG } from '../../core/config/app-config.token';
import { PurchasesApi } from './purchases.api';

describe('PurchasesApi', () => {
  let api: PurchasesApi;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting(), { provide: APP_CONFIG, useValue: { apiBaseUrl: '/api/v1' } }],
    });
    api = TestBed.inject(PurchasesApi);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('lists suppliers sending only the filters provided', () => {
    api.suppliers({ search: 'agro', active: true }).subscribe();
    const request = http.expectOne((req) => req.url === '/api/v1/inventory/suppliers');
    expect(request.request.method).toBe('GET');
    expect(request.request.params.get('search')).toBe('agro');
    expect(request.request.params.get('active')).toBe('true');
    request.flush([]);
  });

  it('lists all suppliers when no filter is given', () => {
    api.suppliers().subscribe();
    const request = http.expectOne((req) => req.url === '/api/v1/inventory/suppliers');
    expect(request.request.params.keys()).toEqual([]);
    request.flush([]);
  });

  it('creates a supplier', () => {
    api.createSupplier({ name: 'Agro Foods', gstin: '27AAPFU0939F1ZV' }).subscribe();
    const request = http.expectOne('/api/v1/inventory/suppliers');
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual({ name: 'Agro Foods', gstin: '27AAPFU0939F1ZV' });
    request.flush({});
  });

  it('receives goods with the idempotency key header', () => {
    const body = { branch_id: 'b-1', supplier_name: 'Agro Foods', lines: [{ product_id: 'p-1', quantity: '10.000', unit_cost: '42.50' }] };
    api.receiveGoods(body, 'key-3').subscribe();
    const request = http.expectOne('/api/v1/inventory/receipts');
    expect(request.request.method).toBe('POST');
    expect(request.request.headers.get('Idempotency-Key')).toBe('key-3');
    expect(request.request.body).toEqual(body);
    request.flush({});
  });
});
