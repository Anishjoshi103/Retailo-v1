import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { catchError, map, of, switchMap } from 'rxjs';
import { SessionService } from './session.service';
import { SessionContextService } from './session-context.service';

export const authGuard: CanActivateFn = (_route, state) => {
  const session = inject(SessionService);
  const router = inject(Router);
  const context = inject(SessionContextService);
  const loadContext = () => context.load().pipe(map((loaded) => loaded ? true : router.createUrlTree(['/auth/login'], { queryParams: { returnUrl: state.url } })));
  if (session.accessToken()) return loadContext();
  return session.refreshAccessToken().pipe(
    switchMap((token) => token ? loadContext() : of(router.createUrlTree(['/auth/login'], { queryParams: { returnUrl: state.url } }))),
    catchError(() => of(router.createUrlTree(['/auth/login'], { queryParams: { returnUrl: state.url } }))),
  );
};
