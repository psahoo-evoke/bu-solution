import { Injectable, computed, inject, signal } from '@angular/core';
import { AuthService } from './auth.service';
import { DEMO_ROLES, DemoRole } from './models';

const STORAGE_KEY = 'transferiq.demoRole';

/**
 * The active role, sent as X-Demo-Role. Demo mode: any role from the switcher. Entra mode: only the roles the
 * signed-in user is assigned (the API rejects any other with 403).
 */
@Injectable({ providedIn: 'root' })
export class RoleService {
  private readonly auth = inject(AuthService);
  private readonly selected = signal<DemoRole>(RoleService.load());

  readonly available = computed<readonly DemoRole[]>(() => (this.auth.entra() ? this.auth.roles() : DEMO_ROLES));
  readonly role = computed<DemoRole>(() => {
    const available = this.available();
    const selected = this.selected();
    return available.includes(selected) ? selected : (available[0] ?? 'Student');
  });

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
