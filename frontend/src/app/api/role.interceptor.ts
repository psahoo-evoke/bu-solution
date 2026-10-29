import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { catchError, from, switchMap, throwError } from 'rxjs';
import { AuthService } from './auth.service';
import { RoleService } from './role.service';

/**
 * Adds the active role (X-Demo-Role) to every /api call, and in portal / entra mode the bearer token as well
 * (openapi: securitySchemes). /api/health and /api/auth/* are public and never need a token.
 * Portal mode: a 401 means the session expired, so the user is signed out and sent to the home page.
 */
export const roleInterceptor: HttpInterceptorFn = (req, next) => {
  if (!req.url.startsWith('/api')) return next(req);
  const auth = inject(AuthService);
  const router = inject(Router);
  const withRole = req.clone({ setHeaders: { 'X-Demo-Role': inject(RoleService).role() } });
  if (!auth.secured() || req.url === '/api/health' || req.url.startsWith('/api/auth/')) return next(withRole);
  return from(auth.accessToken()).pipe(
    switchMap((token) => next(token ? withRole.clone({ setHeaders: { Authorization: `Bearer ${token}` } }) : withRole)),
    catchError((err: unknown) => {
      if (err instanceof HttpErrorResponse && err.status === 401 && auth.portal()) {
        auth.endPortalSession();
        void router.navigateByUrl('/');
      }
      return throwError(() => err);
    }),
  );
};
