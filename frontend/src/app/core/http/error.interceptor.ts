import { HttpInterceptorFn } from '@angular/common/http';
import { catchError, throwError } from 'rxjs';
import { mapApiError } from '../api/api-error-mapper';
export const errorInterceptor: HttpInterceptorFn = (_request, next) => next(_request).pipe(catchError((error: unknown) => throwError(() => mapApiError(error))));