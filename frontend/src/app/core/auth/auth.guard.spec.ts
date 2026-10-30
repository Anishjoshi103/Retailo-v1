import { TestBed } from '@angular/core/testing';
import { provideRouter, Router, UrlTree } from '@angular/router';
import { of } from 'rxjs';
import { SessionService } from './session.service';
import { authGuard } from './auth.guard';

describe('authGuard', () => {
  let session: jasmine.SpyObj<SessionService>;
  let router: Router;

  beforeEach(() => {
    session = jasmine.createSpyObj<SessionService>('SessionService', ['refreshAccessToken'], { accessToken: () => null });
    TestBed.configureTestingModule({ providers: [provideRouter([]), { provide: SessionService, useValue: session }] });
    router = TestBed.inject(Router);
  });

  it('allows navigation when an access token is already in memory', () => {
    Object.defineProperty(session, 'accessToken', { value: () => 'token' });
    const result = TestBed.runInInjectionContext(() => authGuard({} as never, { url: '/pos' } as never));
    expect(result).toBeTrue();
    expect(session.refreshAccessToken).not.toHaveBeenCalled();
  });

  it('restores the session from the refresh cookie before redirecting', (done) => {
    session.refreshAccessToken.and.returnValue(of('restored-token'));
    const result = TestBed.runInInjectionContext(() => authGuard({} as never, { url: '/pos' } as never));
    (result as ReturnType<typeof of>).subscribe((value) => { expect(value).toBeTrue(); done(); });
  });

  it('redirects to sign-in and preserves the requested URL when refresh fails', (done) => {
    session.refreshAccessToken.and.returnValue(of(null));
    const result = TestBed.runInInjectionContext(() => authGuard({} as never, { url: '/pos' } as never));
    (result as ReturnType<typeof of>).subscribe((value) => {
      expect(value instanceof UrlTree).toBeTrue();
      expect(router.serializeUrl(value as UrlTree)).toContain('returnUrl=%2Fpos');
      done();
    });
  });
});
