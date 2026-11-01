import type { AppEnvironment } from '../app/core/config/app-environment.token';

export interface RetailoEnvironment extends AppEnvironment {
  readonly apiBaseUrl: string;
}
