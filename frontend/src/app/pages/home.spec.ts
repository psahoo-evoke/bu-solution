import { TestBed } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';
import type { AccountInfo } from '@azure/msal-browser';
import { vi } from 'vitest';
import { authGuard } from '../api/auth.guard';
import { AuthService } from '../api/auth.service';
import { RoleService } from '../api/role.service';
import { HomePage } from './home';

function entra(auth: AuthService, roles?: string[]): void {
  auth.config.set({ mode: 'entra', clientId: 'c', tenantId: 't' });
  if (roles) auth.account.set({ name: 'Pat Lee', username: 'pat@x', idTokenClaims: { roles } } as unknown as AccountInfo);
}

function buttons(el: HTMLElement): string[] {
  return Array.from(el.querySelectorAll('button')).map((b) => b.textContent?.trim() ?? '');
}

describe('HomePage', () => {
  let auth: AuthService;
  let roles: RoleService;
  let router: Router;

  beforeEach(() => {
    try {
      localStorage.clear();
    } catch {
      /* ignore */
    }
    TestBed.configureTestingModule({ imports: [HomePage], providers: [provideRouter([])] });
    auth = TestBed.inject(AuthService);
    roles = TestBed.inject(RoleService);
    router = TestBed.inject(Router);
    vi.spyOn(router, 'navigateByUrl').mockResolvedValue(true);
  });

  function render(): HTMLElement {
    const fixture = TestBed.createComponent(HomePage);
    fixture.detectChanges();
    return fixture.nativeElement as HTMLElement;
  }

  function click(el: HTMLElement, label: string): void {
    const btn = Array.from(el.querySelectorAll('button')).find((b) => b.textContent?.trim().startsWith(label));
    expect(btn, label).toBeTruthy();
    btn!.click();
  }

  it('shows My view, Student View and Department View', () => {
    const el = render();
    const headings = Array.from(el.querySelectorAll('h2')).map((h) => h.textContent?.trim());
    expect(headings).toEqual(expect.arrayContaining(['My view', 'Student View', 'Department View']));
  });

  it('demo mode: Student View opens the student page as Student', () => {
    click(render(), 'Continue as Student');
    expect(roles.role()).toBe('Student');
    expect(router.navigateByUrl).toHaveBeenCalledWith('/student/SYN-24001');
  });

  it('demo mode: Department View opens the workbench as Department', () => {
    click(render(), 'Continue as Department');
    expect(roles.role()).toBe('Department');
    expect(router.navigateByUrl).toHaveBeenCalledWith('/review');
  });

  it('lists every staff view as its own sign-in tile', () => {
    const el = render();
    const names = Array.from(el.querySelectorAll('.staff__name')).map((h) => h.textContent?.trim());
    expect(names).toEqual(['Advisor', 'Financial aid', 'Evaluator', 'Credit staff', 'Registrar']);
    expect(Array.from(el.querySelectorAll('h2')).map((h) => h.textContent?.trim())).toContain('Staff views');
  });

  it('demo mode: the Advisor and Financial aid tiles open their own pages', () => {
    click(render(), 'Continue as Advisor');
    expect(roles.role()).toBe('Advisor');
    expect(router.navigateByUrl).toHaveBeenLastCalledWith('/advisor');
    click(render(), 'Continue as Financial aid');
    expect(roles.role()).toBe('FinancialAid');
    expect(router.navigateByUrl).toHaveBeenLastCalledWith('/financial-aid');
  });

  it('portal mode, signed out: a staff tile goes to the staff sign-in, and says there is no registration', () => {
    auth.config.set({ mode: 'portal' });
    const el = render();
    click(el, 'Financial aid sign in');
    expect(router.navigateByUrl).toHaveBeenCalledWith('/login/staff');
    expect(el.querySelector('.staff')?.textContent).toContain('no registration');
  });

  it('entra mode, signed out: views start Microsoft sign-in with the chosen view', () => {
    entra(auth);
    const login = vi.spyOn(auth, 'login').mockResolvedValue();
    const el = render();
    expect(buttons(el).filter((b) => b.includes('Sign in with Microsoft'))).toHaveLength(7);   // Student, Department and 5 staff views
    // Signed out: no empty "My view" card; the hero offers the public check and a hint points at the sign-in cards.
    expect(Array.from(el.querySelectorAll('h2')).map((h) => h.textContent?.trim())).not.toContain('My view');
    expect(el.querySelector('.hero a[href="/credit-check"]')).not.toBeNull();
    expect(el.textContent).toContain('Sign in below with your university Microsoft account.');
    click(el, 'Sign in with Microsoft');
    expect(login).toHaveBeenCalledWith('Student');
    expect(router.navigateByUrl).not.toHaveBeenCalled();
  });

  it('entra mode: a Student cannot open the Department view', () => {
    entra(auth, ['Student']);
    const fixture = TestBed.createComponent(HomePage);
    fixture.detectChanges();
    click(fixture.nativeElement, 'Open Department view');
    fixture.detectChanges();
    expect(router.navigateByUrl).not.toHaveBeenCalled();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('not a Department account');
  });

  it('entra mode: after sign-in the chosen view opens', () => {
    entra(auth, ['Department']);
    auth.intent.set('Department');
    render();
    expect(router.navigateByUrl).toHaveBeenCalledWith('/review');
    expect(auth.intent()).toBeNull();
  });

  it('entra mode: signed in without a role shows the no-role message', () => {
    entra(auth, []);
    expect(render().textContent).toContain('no TransferIQ role yet');
  });
});

describe('authGuard', () => {
  const run = () => TestBed.runInInjectionContext(() => authGuard({} as never, {} as never));

  beforeEach(() => TestBed.configureTestingModule({ providers: [provideRouter([])] }));

  it('allows everything in demo mode', () => {
    expect(run()).toBe(true);
  });

  it('sends signed-out users home in entra mode', () => {
    entra(TestBed.inject(AuthService));
    expect(String(run())).toBe('/');
  });

  it('allows a signed-in user with a role', () => {
    entra(TestBed.inject(AuthService), ['Student']);
    expect(run()).toBe(true);
  });
});
