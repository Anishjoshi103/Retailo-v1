import { HttpErrorResponse } from '@angular/common/http';
import { describe, expect, it } from 'vitest';
import { mapApiError } from './api-error-mapper';
describe('mapApiError', () => {
  it('maps API envelope fields', () => { const error=mapApiError(new HttpErrorResponse({status:400,error:{code:'VALIDATION_ERROR',message:'Invalid',field_errors:{name:['Required']},correlation_id:'id-1'}})); expect(error.code).toBe('VALIDATION_ERROR'); expect(error.fieldErrors['name']).toEqual(['Required']); expect(error.correlationId).toBe('id-1'); });
  it('maps a safe fallback for unknown bodies', () => { expect(mapApiError(new HttpErrorResponse({status:503,statusText:'Unavailable'})).message).toBe('Unavailable'); });
});