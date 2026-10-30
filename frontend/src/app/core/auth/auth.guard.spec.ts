import { TestBed } from '@angular/core/testing';
import { provideRouter, Router, UrlTree } from '@angular/router';
import { of } from 'rxjs';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { SessionService } from './session.service';
import { authGuard } from './auth.guard';

describe('authGuard', () => {
  let session: { accessToken: () => string | null; refreshAccessToken: ReturnType<typeof vi.fn> };
  let router: Router;

  beforeEach(() => {
    session = { accessToken: () => null, refreshAccessToken: vi.fn(() => of(null)) };
    TestBed.configureTestingModule({ providers: [provideRouter([]), { provide: SessionService, useValue: session }] });
    router = TestBed.inject(Router);
  });

  it('allows navigation when an access token is already in memory', () => {
    session.accessToken = () => 'token';
    const result = TestBed.runInInjectionContext(() => authGuard({} as never, { url: '/pos' } as never));
    expect(result).toBe(true);
    expect(session.refreshAccessToken).not.toHaveBeenCalled();
  });

  it('restores the session from the refresh cookie before allowing navigation', () => {
    session.refreshAccessToken.mockReturnValue(of('restored-token'));
    const result = TestBed.runInInjectionContext(() => authGuard({} as never, { url: '/pos' } as never));
    expect(result).toBeInstanceOf(Object);
    if (result && typeof result !== 'boolean') result.subscribe((value) => expect(value).toBe(true));
  });

  it('redirects to sign-in and preserves the requested URL when refresh fails', () => {
    const result = TestBed.runInInjectionContext(() => authGuard({} as never, { url: '/pos' } as never));
    if (result && typeof result !== 'boolean') result.subscribe((value) => {
      expect(value).toBeInstanceOf(UrlTree);
      expect(router.serializeUrl(value as UrlTree)).toContain('returnUrl=%2Fpos');
    });
  });
});
