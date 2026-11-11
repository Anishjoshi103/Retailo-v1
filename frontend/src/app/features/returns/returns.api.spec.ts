import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { APP_CONFIG } from '../../core/config/app-config.token';
import { CreateReturnRequest } from './returns.models';
import { ReturnsApi } from './returns.api';

describe('ReturnsApi', () => {
  let api: ReturnsApi;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting(), { provide: APP_CONFIG, useValue: { apiBaseUrl: '/api/v1' } }],
    });
    api = TestBed.inject(ReturnsApi);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('posts a return against a sale with the idempotency key header', () => {
    const body: CreateReturnRequest = { reason: 'Damaged', lines: [{ sale_line_id: 'sl-1', quantity: '1.000' }] };
    api.create('s-1', body, 'key-9').subscribe();
    const request = http.expectOne('/api/v1/sales/s-1/returns');
    expect(request.request.method).toBe('POST');
    expect(request.request.headers.get('Idempotency-Key')).toBe('key-9');
    expect(request.request.body).toEqual(body);
    request.flush({});
  });

  it('lists credit notes sending only the filters that were provided', () => {
    api.list({ saleId: 's-1', creditNoteNumber: 'CN-MAIN-000001', limit: 20, offset: 40 }).subscribe();
    const request = http.expectOne((req) => req.url === '/api/v1/credit-notes');
    expect(request.request.params.get('sale_id')).toBe('s-1');
    expect(request.request.params.get('credit_note_number')).toBe('CN-MAIN-000001');
    expect(request.request.params.get('limit')).toBe('20');
    expect(request.request.params.get('offset')).toBe('40');
    expect(request.request.params.has('branch_id')).toBe(false);
    request.flush([]);
  });

  it('lists with no filters when none are given', () => {
    api.list().subscribe();
    const request = http.expectOne((req) => req.url === '/api/v1/credit-notes');
    expect(request.request.params.keys()).toEqual([]);
    request.flush([]);
  });

  it('fetches one credit note by id', () => {
    api.get('cn-1').subscribe();
    const request = http.expectOne('/api/v1/credit-notes/cn-1');
    expect(request.request.method).toBe('GET');
    request.flush({});
  });
});
