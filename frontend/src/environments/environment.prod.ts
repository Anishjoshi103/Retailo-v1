import { AppEnvironment } from '../app/core/config/app-environment.token';

export const productionEnvironment: AppEnvironment = {
  production: true,
  environmentLabel: 'Production',
  showEnvironmentLabel: false
};

export const environment = productionEnvironment;
