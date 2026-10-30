import { HttpErrorResponse } from '@angular/common/http';
import { ApiError, ApiErrorEnvelope } from './api-error.model';
export function mapApiError(error: unknown): ApiError {
  if (error instanceof ApiError) return error;
  if (error instanceof HttpErrorResponse) {
    const body: unknown = error.error;
    if (isEnvelope(body)) return new ApiError(body.code, body.message, body.field_errors ?? {}, body.correlation_id ?? null, error.status);
    return new ApiError('HTTP_ERROR', error.statusText || 'The request could not be completed.', {}, error.headers.get('X-Correlation-ID'), error.status);
  }
  return new ApiError('UNEXPECTED_ERROR', 'An unexpected error occurred.');
}
function isEnvelope(value: unknown): value is ApiErrorEnvelope {
  if (typeof value !== 'object' || value === null) return false;
  const item = value as Record<string, unknown>;
  return typeof item['code'] === 'string' && typeof item['message'] === 'string';
}