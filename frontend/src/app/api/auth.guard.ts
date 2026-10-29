import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AuthService } from './auth.service';
import { RoleService } from './role.service';

/** Entra mode: app pages need a signed-in user with at least one TransferIQ role; otherwise go to the
 * home page (sign-in). Demo mode: always allowed. The API enforces the same rule on every call. */
export const authGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  if (!auth.entra()) return true;
  if (auth.signedIn() && inject(RoleService).available().length > 0) return true;
  return inject(Router).createUrlTree(['/']);
};
