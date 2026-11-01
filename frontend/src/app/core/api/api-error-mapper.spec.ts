import { HttpErrorResponse } from '@angular/common/http';
import { describe, expect, it } from 'vitest';
import { mapApiError } from './api-error-mapper';

describe('mapApiError', () => {
  it('maps the standard nested error envelope', () => {
    const error = mapApiError(new HttpErrorResponse({ status: 400, error: { error: { code: 'VALIDATION_ERROR', message: 'Invalid', field_errors: { name: ['Required'] }, request_id: 'id-1' } } }));
    expect(error.code).toBe('VALIDATION_ERROR');
    expect(error.fieldErrors['name']).toEqual(['Required']);
    expect(error.correlationId).toBe('id-1');
  });
  it('maps a safe fallback for unknown bodies', () => {
    expect(mapApiError(new HttpErrorResponse({ status: 503, statusText: 'Unavailable' })).message).toBe('Unavailable');
  });
});
