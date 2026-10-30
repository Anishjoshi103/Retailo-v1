import { bootstrapApplication } from '@angular/platform-browser';
import { provideRouter } from '@angular/router';
import { APP_ENVIRONMENT } from './app/core/config/app-environment.token';
import { AppComponent } from './app/app.component';
import { routes } from './app/app.routes';
import { environment } from './environments/environment';

bootstrapApplication(AppComponent, {
  providers: [
    provideRouter(routes),
    { provide: APP_ENVIRONMENT, useValue: environment }
  ]
}).catch((error: unknown) => console.error(error));
