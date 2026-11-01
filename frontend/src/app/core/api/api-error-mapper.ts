import { HttpErrorResponse } from '@angular/common/http';
import { ApiError, ApiErrorEnvelope } from './api-error.model';

export function mapApiError(error: unknown): ApiError {
  if (error instanceof ApiError) return error;
  if (error instanceof HttpErrorResponse) {
    const body: unknown = error.error;
    if (isEnvelope(body)) {
      const payload = body.error;
      return new ApiError(payload.code, payload.message, payload.field_errors ?? {}, payload.request_id ?? null, error.status);
    }
    return new ApiError(
      'HTTP_ERROR',
      error.status === 401 ? 'Authentication is required.' : error.statusText || 'The request could not be completed.',
      {},
      error.headers.get('X-Request-ID'),
      error.status,
    );
  }
  return new ApiError('UNEXPECTED_ERROR', 'An unexpected error occurred.');
}

function isEnvelope(value: unknown): value is ApiErrorEnvelope {
  if (typeof value !== 'object' || value === null) return false;
  const item = value as Record<string, unknown>;
  const payload = item['error'];
  if (typeof payload !== 'object' || payload === null) return false;
  const envelope = payload as Record<string, unknown>;
  return typeof envelope['code'] === 'string' && typeof envelope['message'] === 'string';
}
