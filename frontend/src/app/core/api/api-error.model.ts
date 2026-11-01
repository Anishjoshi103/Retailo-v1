export interface ApiErrorPayload {
  readonly code: string;
  readonly message: string;
  readonly field_errors?: Readonly<Record<string, readonly string[]>>;
  readonly request_id?: string;
}
export interface ApiErrorEnvelope {
  readonly error: ApiErrorPayload;
}
export class ApiError extends Error {
  constructor(readonly code: string, message: string, readonly fieldErrors: Readonly<Record<string, readonly string[]>> = {}, readonly correlationId: string | null = null, readonly status = 0) {
    super(message); this.name = 'ApiError';
  }
}
