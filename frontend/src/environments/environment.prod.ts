import type { RetailoEnvironment } from './retailo-environment';

export const productionEnvironment: RetailoEnvironment = {
  production: true,
  environmentLabel: 'Production',
  showEnvironmentLabel: false,
  apiBaseUrl: '/api/v1',
};

export const environment = productionEnvironment;
