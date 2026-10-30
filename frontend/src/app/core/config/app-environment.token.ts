import { InjectionToken } from '@angular/core';

export interface AppEnvironment {
  readonly production: boolean;
  readonly environmentLabel: string;
  readonly showEnvironmentLabel: boolean;
}

export const APP_ENVIRONMENT = new InjectionToken<AppEnvironment>('APP_ENVIRONMENT');
