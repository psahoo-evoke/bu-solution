import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AuthService } from './auth.service';
import { Page, canOpenPage } from './permissions';
import { homeHidden, homeRoute } from './role-home';
import { RoleService } from './role.service';

/** Portal / entra mode: app pages need a signed-in user with a TransferIQ role, otherwise go to the home page
 * (sign-in). A signed-in student only ever opens their own status page. Demo mode: always allowed.
 * The API enforces the same rules on every call; this only avoids showing pages that would fail. */
export const authGuard: CanActivateFn = (route) => {
  const auth = inject(AuthService);
  if (!auth.secured()) return true;
  const router = inject(Router);
  if (!auth.signedIn() || inject(RoleService).available().length === 0) return router.createUrlTree(['/']);
  const own = auth.studentId();
  const id = route.paramMap?.get('id') ?? null;
  if (own && auth.roles().includes('Student') && id !== null && id !== own) {
    return router.createUrlTree(['/student', own]);
  }
  return true;
};

/** The home page: a signed-in student or department user has no Home and goes to their own page instead (their
 * status page, or the workbench). Staff, signed-out visitors and demo mode see the home page. */
export const homeGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  const roles = inject(RoleService);
  // No role yet: stay here, the home page explains it (authGuard sends such users here, so never bounce back).
  if (!auth.secured() || roles.available().length === 0 || !homeHidden(roles.role(), auth.signedIn())) return true;
  return inject(Router).parseUrl(homeRoute(roles.role(), auth.studentId()));
};

/** A page that belongs to certain roles (permissions.PAGE_ROLES): anyone else who is signed in is sent to their own
 * page. Signed-out visitors go to the home page like authGuard; demo mode shows every page. */
export const pageGuard = (page: Page): CanActivateFn => () => {
  const auth = inject(AuthService);
  if (!auth.secured()) return true;
  const router = inject(Router);
  const roles = inject(RoleService);
  if (!auth.signedIn() || roles.available().length === 0) return router.createUrlTree(['/']);
  if (canOpenPage(roles.role(), page)) return true;
  return router.parseUrl(homeRoute(roles.role(), auth.studentId()));
};
