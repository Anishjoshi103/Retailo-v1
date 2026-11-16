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

  it('updates a supplier with PATCH', () => {
    api.updateSupplier('s-1', { is_active: false }).subscribe();
    const request = http.expectOne('/api/v1/inventory/suppliers/s-1');
    expect(request.request.method).toBe('PATCH');
    expect(request.request.body).toEqual({ is_active: false });
    request.flush({});
  });

  it('lists past deliveries sending only the filters provided', () => {
    api.receipts({ branchId: 'b-1', supplierId: 's-1', invoiceNumber: 'AF-1', dateFrom: '2026-11-01', limit: 20, offset: 40 }).subscribe();
    const request = http.expectOne((req) => req.url === '/api/v1/inventory/receipts');
    expect(request.request.method).toBe('GET');
    expect(request.request.params.get('branch_id')).toBe('b-1');
    expect(request.request.params.get('supplier_id')).toBe('s-1');
    expect(request.request.params.get('invoice_number')).toBe('AF-1');
    expect(request.request.params.get('date_from')).toBe('2026-11-01');
    expect(request.request.params.has('date_to')).toBe(false);
    expect(request.request.params.get('limit')).toBe('20');
    expect(request.request.params.get('offset')).toBe('40');
    request.flush([]);
  });

  it('lists with no filters and fetches one delivery by id', () => {
    api.receipts().subscribe();
    const list = http.expectOne((req) => req.url === '/api/v1/inventory/receipts');
    expect(list.request.params.keys()).toEqual([]);
    list.flush([]);
    api.receipt('r-1').subscribe();
    const one = http.expectOne('/api/v1/inventory/receipts/r-1');
    expect(one.request.method).toBe('GET');
    one.flush({});
  });
});
