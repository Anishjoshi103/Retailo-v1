import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { APP_CONFIG } from '../../core/config/app-config.token';
import { InventoryApi } from './inventory.api';

describe('InventoryApi', () => {
  let api: InventoryApi;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting(), { provide: APP_CONFIG, useValue: { apiBaseUrl: '/api/v1' } }],
    });
    api = TestBed.inject(InventoryApi);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('loads stock balances for one branch', () => {
    api.balances('b-1').subscribe();
    const request = http.expectOne((req) => req.url === '/api/v1/inventory/balances');
    expect(request.request.method).toBe('GET');
    expect(request.request.params.get('branch_id')).toBe('b-1');
    request.flush([]);
  });

  it('searches active products', () => {
    api.searchProducts('rice').subscribe();
    const request = http.expectOne((req) => req.url === '/api/v1/products');
    expect(request.request.params.get('search')).toBe('rice');
    expect(request.request.params.get('active')).toBe('true');
    request.flush([]);
  });

  it('posts an adjustment with the idempotency key header', () => {
    const body = { branch_id: 'b-1', product_id: 'p-1', quantity_delta: '-2.000', note: 'Damaged' };
    api.adjust(body, 'key-7').subscribe();
    const request = http.expectOne('/api/v1/inventory/adjustments');
    expect(request.request.method).toBe('POST');
    expect(request.request.headers.get('Idempotency-Key')).toBe('key-7');
    expect(request.request.body).toEqual(body);
    request.flush({});
  });
});
