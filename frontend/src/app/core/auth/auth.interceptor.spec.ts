import { HttpClient, HttpErrorResponse, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { catchError, of, throwError } from 'rxjs';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api/api-error.model';
import { APP_CONFIG } from '../config/app-config.token';
import { authInterceptor } from './auth.interceptor';
import { SessionService } from './session.service';

describe('authInterceptor', () => {
  let http: HttpClient;
  let controller: HttpTestingController;
  let session: { accessToken: ReturnType<typeof vi.fn>; refreshAccessToken: ReturnType<typeof vi.fn>; clearSession: ReturnType<typeof vi.fn> };

  beforeEach(() => {
    session = {
      accessToken: vi.fn().mockReturnValue('expired-access'),
      refreshAccessToken: vi.fn().mockReturnValue(of('fresh-access')),
      clearSession: vi.fn(),
    };
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([authInterceptor, (request, next) => next(request).pipe(catchError((error: unknown) => {
          if (error instanceof HttpErrorResponse) return throwError(() => new ApiError('UNAUTHENTICATED', 'Expired', {}, null, error.status));
          return throwError(() => error);
        }))])),
        provideHttpClientTesting(),
        { provide: APP_CONFIG, useValue: { apiBaseUrl: '/api/v1' } },
        { provide: SessionService, useValue: session },
      ],
    });
    http = TestBed.inject(HttpClient);
    controller = TestBed.inject(HttpTestingController);
  });

  afterEach(() => controller.verify());

  it('refreshes after mapped 401 and retries with the fresh access token', () => {
    let response = '';
    http.get<{ value: string }>('/api/v1/products').subscribe((value) => response = value.value);
    const first = controller.expectOne('/api/v1/products');
    first.flush({ detail: 'expired' }, { status: 401, statusText: 'Unauthorized' });
    const retry = controller.expectOne('/api/v1/products');
    expect(retry.request.headers.get('Authorization')).toBe('Bearer fresh-access');
    retry.flush({ value: 'ok' });
    expect(response).toBe('ok');
    expect(session.refreshAccessToken).toHaveBeenCalledTimes(1);
  });

  it('clears the session when refresh fails', () => {
    session.refreshAccessToken.mockReturnValue(of(null));
    let error: unknown;
    http.get('/api/v1/products').subscribe({ error: (value: unknown) => error = value });
    controller.expectOne('/api/v1/products').flush({}, { status: 401, statusText: 'Unauthorized' });
    expect(session.clearSession).toHaveBeenCalledOnce();
    expect(error).toBeInstanceOf(ApiError);
  });

  it('does not attempt refresh for auth endpoints including verify-email', () => {
    http.post('/api/v1/auth/verify-email', {}).subscribe({ error: () => undefined });
    controller.expectOne('/api/v1/auth/verify-email').flush({}, { status: 401, statusText: 'Unauthorized' });
    expect(session.refreshAccessToken).not.toHaveBeenCalled();
  });
});
