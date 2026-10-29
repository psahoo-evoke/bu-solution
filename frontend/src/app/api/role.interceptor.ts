import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { from, switchMap } from 'rxjs';
import { AuthService } from './auth.service';
import { RoleService } from './role.service';

/**
 * Adds the active role (X-Demo-Role) to every /api call, and in entra mode the Entra access token as well
 * (openapi: securitySchemes). /api/health is public and never needs a token.
 */
export const roleInterceptor: HttpInterceptorFn = (req, next) => {
  if (!req.url.startsWith('/api')) return next(req);
  const auth = inject(AuthService);
  const withRole = req.clone({ setHeaders: { 'X-Demo-Role': inject(RoleService).role() } });
  if (!auth.entra() || req.url === '/api/health') return next(withRole);
  return from(auth.accessToken()).pipe(
    switchMap((token) => next(token ? withRole.clone({ setHeaders: { Authorization: `Bearer ${token}` } }) : withRole)),
  );
};
