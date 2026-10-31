import { Injectable, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { AuthService } from './auth.service';
import { DEMO_ROLES, DemoRole } from './models';

const STORAGE_KEY = 'transferiq.demoRole';

/**
 * The active role, sent as X-Demo-Role. Demo mode: any role from the switcher. Portal / entra mode: only the
 * role(s) of the signed-in user (the API takes the role from the session and rejects any other with 403).
 */
@Injectable({ providedIn: 'root' })
export class RoleService {
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly selected = signal<DemoRole>(RoleService.load());

  readonly available = computed<readonly DemoRole[]>(() => (this.auth.secured() ? this.auth.roles() : DEMO_ROLES));
  readonly role = computed<DemoRole>(() => {
    const available = this.available();
    const selected = this.selected();
    return available.includes(selected) ? selected : (available[0] ?? 'Student');
  });

  /** A role this user can take on now: any in demo mode, their own when signed in. Portal accounts have one role
   * each, so another role means signing in as that account. Entra roles come from the directory. */
  canSwitchTo(role: DemoRole): boolean {
    return this.available().includes(role) || this.auth.portal();
  }

  switchLabel(role: DemoRole): string {
    return this.available().includes(role) ? `Switch to ${role}` : `Sign in as ${role}`;
  }

  /** Take the role, or (portal mode) sign out and open the sign-in page where that role signs in. */
  async switchTo(role: DemoRole): Promise<void> {
    if (this.available().includes(role)) {
      this.set(role);
    } else if (this.auth.portal()) {
      await this.auth.logout();
      await this.router.navigateByUrl(`/login/${portalFor(role)}`);
    }
  }

  set(role: DemoRole): void {
    this.selected.set(role);
    try {
      localStorage.setItem(STORAGE_KEY, role);
    } catch {
      /* storage may be unavailable; the in-memory role still works */
    }
  }

  private static load(): DemoRole {
    try {
      const stored = localStorage.getItem(STORAGE_KEY) as DemoRole | null;
      if (stored && DEMO_ROLES.includes(stored)) return stored;
    } catch {
      /* ignore */
    }
    return 'Student';
  }
}

/** Which sign-in page an account of this role uses (student | department | staff). */
export function portalFor(role: DemoRole): 'student' | 'department' | 'staff' {
  return role === 'Student' ? 'student' : role === 'Department' ? 'department' : 'staff';
}
