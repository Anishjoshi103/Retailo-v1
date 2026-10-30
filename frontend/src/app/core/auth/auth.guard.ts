import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { SessionService } from './session.service';
export const authGuard: CanActivateFn = (_route, state) => inject(SessionService).accessToken()
  ? true : inject(Router).createUrlTree(['/auth/login'], { queryParams: { returnUrl: state.url } });