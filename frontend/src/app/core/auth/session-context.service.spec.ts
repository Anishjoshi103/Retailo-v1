import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { afterEach, describe, expect, it } from 'vitest';
import { APP_CONFIG } from '../config/app-config.token';
import { SessionService } from './session.service';
import { SessionContextService } from './session-context.service';

describe('SessionContextService', () => {
  let http: HttpTestingController;
  let context: SessionContextService;
  afterEach(() => http.verify());
  it('loads role, tenant, and only branches allowed by /auth/me', () => {
    TestBed.configureTestingModule({ providers: [
      provideHttpClient(), provideHttpClientTesting(),
      { provide: APP_CONFIG, useValue: { apiBaseUrl: '/api/v1' } },
      { provide: SessionService, useValue: { accessToken: () => 'access' } },
    ] });
    http = TestBed.inject(HttpTestingController);
    context = TestBed.inject(SessionContextService);
    context.load().subscribe((loaded) => expect(loaded).toBe(true));
    http.expectOne('/api/v1/auth/me').flush({
      id: 'u1', email: 'owner@example.test', display_name: 'Owner',
      tenant: { id: 't1', name: 'Shop' }, role: 'owner', allowed_branch_ids: ['b1'],
    });
    context.loadBranches().subscribe();
    http.expectOne('/api/v1/branches').flush([
      { id: 'b1', name: 'Main', code: 'MAIN' },
      { id: 'b2', name: 'Other', code: 'OTHER' },
    ]);
    expect(context.roles()).toEqual(['owner']);
    expect(context.tenantId()).toBe('t1');
    expect(context.branches().map((branch) => branch.id)).toEqual(['b1']);
    expect(context.selectedBranchId()).toBe('b1');
  });
});
