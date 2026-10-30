import { AppEnvironment } from '../app/core/config/app-environment.token';
export interface RetailoEnvironment extends AppEnvironment { readonly apiBaseUrl: string; }
export const environment: RetailoEnvironment = { production: false, environmentLabel: 'Development workspace', showEnvironmentLabel: true, apiBaseUrl: '/api/v1' };