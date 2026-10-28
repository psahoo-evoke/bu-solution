import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { RoleService } from './role.service';

/** Adds the demo auth header (openapi: securitySchemes.demoRole) to every /api call. */
export const roleInterceptor: HttpInterceptorFn = (req, next) => {
  if (!req.url.startsWith('/api')) return next(req);
  const role = inject(RoleService).role();
  return next(req.clone({ setHeaders: { 'X-Demo-Role': role } }));
};
