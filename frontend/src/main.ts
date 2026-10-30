import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { bootstrapApplication } from '@angular/platform-browser';
import { provideRouter } from '@angular/router';
import { authInterceptor } from './app/core/auth/auth.interceptor';
import { APP_CONFIG } from './app/core/config/app-config.token';
import { APP_ENVIRONMENT } from './app/core/config/app-environment.token';
import { correlationIdInterceptor } from './app/core/http/correlation-id.interceptor';
import { errorInterceptor } from './app/core/http/error.interceptor';
import { loadingInterceptor } from './app/core/http/loading.interceptor';
import { AppComponent } from './app/app.component';
import { routes } from './app/app.routes';
import { environment } from './environments/environment';
bootstrapApplication(AppComponent, { providers: [
  provideRouter(routes),
  provideHttpClient(withInterceptors([correlationIdInterceptor, authInterceptor, loadingInterceptor, errorInterceptor])),
  { provide: APP_CONFIG, useValue: { apiBaseUrl: environment.apiBaseUrl } },
  { provide: APP_ENVIRONMENT, useValue: environment }
] }).catch((error: unknown) => console.error(error));