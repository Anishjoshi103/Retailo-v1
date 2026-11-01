import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { afterEach, describe, expect, it } from 'vitest';
import { correlationIdInterceptor } from './correlation-id.interceptor';
describe('correlationIdInterceptor', () => {
  afterEach(() => TestBed.inject(HttpTestingController).verify());
  it('adds a request ID header to outgoing requests', () => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(withInterceptors([correlationIdInterceptor])), provideHttpClientTesting()] });
    TestBed.inject(HttpClient).get('/api/v1/health').subscribe();
    const request = TestBed.inject(HttpTestingController).expectOne('/api/v1/health');
    expect(request.request.headers.get('X-Request-ID')).toBeTruthy();
    request.flush({ status: 'ok' });
  });
});