import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { catchError, map, of } from 'rxjs';
import { SessionService } from './session.service';

export const authGuard: CanActivateFn = (_route, state) => {
  const session = inject(SessionService);
  const router = inject(Router);
  if (session.accessToken()) return true;
  return session.refreshAccessToken().pipe(
    map((token) => token ? true : router.createUrlTree(['/auth/login'], { queryParams: { returnUrl: state.url } })),
    catchError(() => of(router.createUrlTree(['/auth/login'], { queryParams: { returnUrl: state.url } }))),
  );
};
