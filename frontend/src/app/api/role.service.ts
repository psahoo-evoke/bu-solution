import { Injectable, signal } from '@angular/core';
import { DEMO_ROLES, DemoRole } from './models';

const STORAGE_KEY = 'transferiq.demoRole';

/** Holds the demo role sent as X-Demo-Role (production would use an Entra ID token instead). */
@Injectable({ providedIn: 'root' })
export class RoleService {
  readonly role = signal<DemoRole>(RoleService.load());

  set(role: DemoRole): void {
    this.role.set(role);
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
