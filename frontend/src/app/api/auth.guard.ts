import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AuthService } from './auth.service';
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
