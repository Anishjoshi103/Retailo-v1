import { HttpInterceptorFn } from '@angular/common/http';
export const correlationIdInterceptor: HttpInterceptorFn = (request, next) => {
  const id = globalThis.crypto?.randomUUID?.() ?? `retailo-${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
  return next(request.clone({ setHeaders: { 'X-Correlation-ID': id } }));
};