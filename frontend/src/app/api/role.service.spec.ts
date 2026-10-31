import { TestBed } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';
import { vi } from 'vitest';
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

describe('RoleService.switchTo', () => {
  let auth: AuthService;
  let roles: RoleService;
  let router: Router;

  beforeEach(() => {
    try {
      localStorage.clear();
    } catch {
      /* ignore */
    }
    TestBed.configureTestingModule({ providers: [provideRouter([])] });
    auth = TestBed.inject(AuthService);
    roles = TestBed.inject(RoleService);
    router = TestBed.inject(Router);
    vi.spyOn(router, 'navigateByUrl').mockResolvedValue(true);
  });

  it('demo mode: switches the role straight away', async () => {
    await roles.switchTo('Evaluator');
    expect(roles.role()).toBe('Evaluator');
    expect(roles.switchLabel('Evaluator')).toBe('Switch to Evaluator');
  });

  it('portal mode: another role means signing out and opening that sign-in page', async () => {
    auth.config.set({ mode: 'portal' });
    auth.portalUser.set({ email: 'creditstaff@bu.edu', name: 'Credit Staff', role: 'CreditStaff', student_id: null, department: null } as never);
    const logout = vi.spyOn(auth, 'logout').mockResolvedValue();
    expect(roles.role()).toBe('CreditStaff');
    expect(roles.canSwitchTo('Evaluator')).toBe(true);
    expect(roles.switchLabel('Evaluator')).toBe('Sign in as Evaluator');
    await roles.switchTo('Evaluator');
    expect(roles.role()).toBe('CreditStaff');                       // the role itself cannot be changed
    expect(logout).toHaveBeenCalled();
    expect(router.navigateByUrl).toHaveBeenCalledWith('/login/staff');
    await roles.switchTo('Department');
    expect(router.navigateByUrl).toHaveBeenLastCalledWith('/login/department');
  });

  it('portal mode: a role the account has is just selected', async () => {
    auth.config.set({ mode: 'portal' });
    auth.portalUser.set({ email: 'a@bu.edu', name: 'A', role: 'Advisor', student_id: null, department: null } as never);
    const logout = vi.spyOn(auth, 'logout').mockResolvedValue();
    await roles.switchTo('Advisor');
    expect(logout).not.toHaveBeenCalled();
    expect(roles.switchLabel('Advisor')).toBe('Switch to Advisor');
  });

  it('entra mode: no button for a role the token does not grant', () => {
    signIn(auth, ['CreditStaff']);
    expect(roles.canSwitchTo('Evaluator')).toBe(false);
    expect(roles.canSwitchTo('CreditStaff')).toBe(true);
  });
});
