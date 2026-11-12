import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { APP_CONFIG } from '../../core/config/app-config.token';
import { BranchesApi } from './branches.api';

describe('BranchesApi', () => {
  let api: BranchesApi;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting(), { provide: APP_CONFIG, useValue: { apiBaseUrl: '/api/v1' } }],
    });
    api = TestBed.inject(BranchesApi);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('lists branches', () => {
    api.list().subscribe();
    const request = http.expectOne('/api/v1/branches');
    expect(request.request.method).toBe('GET');
    request.flush([]);
  });

  it('updates a branch GST identity with PATCH', () => {
    api.updateGst('b-1', { gstin: '27AAPFU0939F1ZV', state_code: '27' }).subscribe();
    const request = http.expectOne('/api/v1/branches/b-1');
    expect(request.request.method).toBe('PATCH');
    expect(request.request.body).toEqual({ gstin: '27AAPFU0939F1ZV', state_code: '27' });
    request.flush({});
  });
});
