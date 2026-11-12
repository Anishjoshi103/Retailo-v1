import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { APP_CONFIG } from '../../core/config/app-config.token';
import { StaffApi } from './staff.api';

describe('StaffApi', () => {
  let api: StaffApi;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting(), { provide: APP_CONFIG, useValue: { apiBaseUrl: '/api/v1' } }],
    });
    api = TestBed.inject(StaffApi);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('lists staff', () => {
    api.list().subscribe();
    const request = http.expectOne('/api/v1/staff');
    expect(request.request.method).toBe('GET');
    request.flush([]);
  });

  it('invites a person with a role and branches', () => {
    const body = { email: 'a@example.test', role: 'cashier' as const, branch_ids: ['b-1'] };
    api.invite(body).subscribe();
    const request = http.expectOne('/api/v1/staff');
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual(body);
    request.flush({});
  });

  it('updates a member with PATCH', () => {
    api.update('m-1', { is_active: false }).subscribe();
    const request = http.expectOne('/api/v1/staff/m-1');
    expect(request.request.method).toBe('PATCH');
    expect(request.request.body).toEqual({ is_active: false });
    request.flush({});
  });

  it('resends an invitation', () => {
    api.resendInvite('m-1').subscribe();
    const request = http.expectOne('/api/v1/staff/m-1/resend-invite');
    expect(request.request.method).toBe('POST');
    request.flush({ invite_sent: true });
  });
});
