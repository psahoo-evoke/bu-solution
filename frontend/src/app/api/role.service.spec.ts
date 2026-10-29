import { TestBed } from '@angular/core/testing';
import type { AccountInfo } from '@azure/msal-browser';
import { AuthService } from './auth.service';
import { DEMO_ROLES } from './models';
import { RoleService } from './role.service';

function signIn(auth: AuthService, roles?: string[]): void {
  auth.config.set({ mode: 'entra', clientId: 'c', tenantId: 't' });
  auth.account.set({ name: 'Test User', username: 'u@x', idTokenClaims: roles ? { roles } : {} } as unknown as AccountInfo);
}

describe('RoleService', () => {
  let auth: AuthService;
  let roles: RoleService;

  beforeEach(() => {
    try {
      localStorage.clear();
    } catch {
      /* ignore */
    }
    TestBed.configureTestingModule({});
    auth = TestBed.inject(AuthService);
    roles = TestBed.inject(RoleService);
  });

  it('offers every role in demo mode', () => {
    expect(roles.available()).toEqual(DEMO_ROLES);
    roles.set('Department');
    expect(roles.role()).toBe('Department');
  });

  it('offers only the roles from the Entra token', () => {
    signIn(auth, ['Department', 'Unknown', 'Student']);
    expect(roles.available()).toEqual(['Student', 'Department']);
    expect(roles.role()).toBe('Student');
    roles.set('Department');
    expect(roles.role()).toBe('Department');
  });

  it('never acts as a role the user is not assigned', () => {
    signIn(auth, ['Student']);
    roles.set('Registrar');
    expect(roles.role()).toBe('Student');
  });

  it('has no roles when none are assigned', () => {
    signIn(auth);
    expect(roles.available()).toEqual([]);
  });
});
