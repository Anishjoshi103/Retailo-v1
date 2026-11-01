import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, switchMap, throwError } from 'rxjs';
import { ApiError } from '../api/api-error.model';
import { APP_CONFIG } from '../config/app-config.token';
import { SessionService } from './session.service';

function isAuthEndpoint(url: string): boolean {
  return /\/auth\/(login|register|refresh|logout|password-reset)(?:[/?#]|$)/i.test(url);
}

export const authInterceptor: HttpInterceptorFn = (request, next) => {
  const session = inject(SessionService);
  const base = inject(APP_CONFIG).apiBaseUrl.replace(/\/$/, '');
  if (!request.url.startsWith(base) || isAuthEndpoint(request.url)) return next(request);

  const token = session.accessToken();
  const authorized = token ? request.clone({ setHeaders: { Authorization: `Bearer ${token}` } }) : request;
  return next(authorized).pipe(catchError((error: unknown) => {
    if (!(error instanceof ApiError) || error.status !== 401 || !token) return throwError(() => error);
    return session.refreshAccessToken().pipe(switchMap((refreshed) => {
      if (!refreshed) { session.clearSession(); return throwError(() => error); }
      return next(request.clone({ setHeaders: { Authorization: `Bearer ${refreshed}` } })).pipe(catchError((retryError: unknown) => throwError(() => retryError)));
    }));
  }));
};
