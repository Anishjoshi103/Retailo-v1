import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { finalize } from 'rxjs';
import { LoadingService } from './loading.service';
export const loadingInterceptor: HttpInterceptorFn = (_request, next) => {
  const loading = inject(LoadingService); loading.begin();
  return next(_request).pipe(finalize(() => loading.end()));
};