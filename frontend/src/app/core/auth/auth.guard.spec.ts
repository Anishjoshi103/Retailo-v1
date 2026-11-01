import { TestBed } from '@angular/core/testing';
import { provideRouter, Router, UrlTree } from '@angular/router';
import { Observable, of } from 'rxjs';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { SessionContextService } from './session-context.service';
import { SessionService } from './session.service';
import { authGuard } from './auth.guard';

describe('authGuard', () => {
  let session: { accessToken: () => string | null; refreshAccessToken: ReturnType<typeof vi.fn> };
  let context: { load: ReturnType<typeof vi.fn>; loadBranches: ReturnType<typeof vi.fn> };
  let router: Router;

  beforeEach(() => {
    session = { accessToken: () => null, refreshAccessToken: vi.fn(() => of(null)) };
    context = { load: vi.fn(() => of(true)), loadBranches: vi.fn(() => of([])) };
    TestBed.configureTestingModule({
      providers: [
        provideRouter([]),
        { provide: SessionService, useValue: session },
        { provide: SessionContextService, useValue: context },
      ],
    });
    router = TestBed.inject(Router);
  });

  it('loads session context before allowing navigation with an access token', () => {
    session.accessToken = () => 'token';
    const result = TestBed.runInInjectionContext(() => authGuard({} as never, { url: '/pos' } as never));
    expect(result).toBeInstanceOf(Observable);
    if (result instanceof Observable) result.subscribe((value) => expect(value).toBe(true));
    expect(context.load).toHaveBeenCalledOnce();
    expect(context.loadBranches).toHaveBeenCalledOnce();
    expect(session.refreshAccessToken).not.toHaveBeenCalled();
  });

  it('restores the session before loading context when refresh succeeds', () => {
    session.refreshAccessToken.mockReturnValue(of('restored-token'));
    const result = TestBed.runInInjectionContext(() => authGuard({} as never, { url: '/pos' } as never));
    expect(result).toBeInstanceOf(Observable);
    if (result instanceof Observable) result.subscribe((value) => expect(value).toBe(true));
    expect(context.load).toHaveBeenCalledOnce();
    expect(context.loadBranches).toHaveBeenCalledOnce();
  });

  it('redirects to sign-in and preserves the requested URL when refresh fails', () => {
    const result = TestBed.runInInjectionContext(() => authGuard({} as never, { url: '/pos' } as never));
    expect(result).toBeInstanceOf(Observable);
    if (result instanceof Observable) result.subscribe((value) => {
      expect(value).toBeInstanceOf(UrlTree);
      expect(router.serializeUrl(value as UrlTree)).toContain('returnUrl=%2Fpos');
    });
    expect(context.load).not.toHaveBeenCalled();
  });

  it('redirects to sign-in when the access token exists but context cannot load', () => {
    session.accessToken = () => 'token';
    context.load.mockReturnValue(of(false));
    const result = TestBed.runInInjectionContext(() => authGuard({} as never, { url: '/pos' } as never));
    expect(result).toBeInstanceOf(Observable);
    if (result instanceof Observable) result.subscribe((value) => {
      expect(value).toBeInstanceOf(UrlTree);
      expect(router.serializeUrl(value as UrlTree)).toContain('returnUrl=%2Fpos');
    });
    expect(context.loadBranches).not.toHaveBeenCalled();
  });
});
