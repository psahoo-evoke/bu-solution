import { HttpErrorResponse, HttpEvent, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { Observable, catchError, from, switchMap, throwError } from 'rxjs';
import { AuthService } from './auth.service';
import { RoleService } from './role.service';

/** Public course-credit check and chat: exactly the routes in guard.py PUBLIC (ADR 0006). */
const PUBLIC_CREDIT = new Set(['/api/credit-check', '/api/credit-check/schools', '/api/credit-check/courses', '/api/credit-chat']);

/**
 * Adds the active role (X-Demo-Role) to every /api call, and in portal / entra mode the bearer token as well
 * (openapi: securitySchemes). /api/health, /api/auth/* and the credit check and chat are public and never need a
 * token.
 * A 401 is handed to AuthService.handleUnauthorized(): portal mode signs out and goes home with a notice; a tab
 * still in demo mode after the site switched to sign-in reloads itself.
 */
export const roleInterceptor: HttpInterceptorFn = (req, next) => {
  if (!req.url.startsWith('/api')) return next(req);
  const auth = inject(AuthService);
  const router = inject(Router);
  const withRole = req.clone({ setHeaders: { 'X-Demo-Role': inject(RoleService).role() } });
  if (req.url === '/api/health' || req.url.startsWith('/api/auth/') || PUBLIC_CREDIT.has(req.url)) return next(withRole);
  const onError = (source: Observable<HttpEvent<unknown>>) =>
    source.pipe(
      catchError((err: unknown) => {
        if (err instanceof HttpErrorResponse && err.status === 401) {
          void auth.handleUnauthorized().then((reloading) => {
            if (!reloading && auth.portal()) void router.navigateByUrl('/');
          });
        }
        return throwError(() => err);
      }),
    );
  if (!auth.secured()) return onError(next(withRole));
  return onError(
    from(auth.accessToken()).pipe(
      switchMap((token) => next(token ? withRole.clone({ setHeaders: { Authorization: `Bearer ${token}` } }) : withRole)),
    ),
  );
};
