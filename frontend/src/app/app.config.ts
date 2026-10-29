import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { ApplicationConfig, inject, provideAppInitializer, provideBrowserGlobalErrorListeners } from '@angular/core';
import { provideRouter, withComponentInputBinding } from '@angular/router';
import { AuthService } from './api/auth.service';
import { roleInterceptor } from './api/role.interceptor';
import { routes } from './app.routes';

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    // Before the first route: read /auth-config.json and finish an Entra sign-in redirect if there is one.
    provideAppInitializer(() => inject(AuthService).init()),
    provideRouter(routes, withComponentInputBinding()),
    provideHttpClient(withInterceptors([roleInterceptor])),
  ],
};
