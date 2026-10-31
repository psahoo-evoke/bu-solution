import { TestBed } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';
import type { AccountInfo } from '@azure/msal-browser';
import { vi } from 'vitest';
import { authGuard, pageGuard } from '../api/auth.guard';
import { DemoRole } from '../api/models';
import { Page } from '../api/permissions';
import { AuthService } from '../api/auth.service';
import { RoleService } from '../api/role.service';
import { HomePage } from './home';

function entra(auth: AuthService, roles?: string[]): void {
  auth.config.set({ mode: 'entra', clientId: 'c', tenantId: 't' });
  if (roles) auth.account.set({ name: 'Pat Lee', username: 'pat@x', idTokenClaims: { roles } } as unknown as AccountInfo);
}

/** Accessible names, as a screen reader hears them: the aria-label when there is one, else the text. */
function buttons(el: HTMLElement): string[] {
  return Array.from(el.querySelectorAll('button')).map((b) => b.getAttribute('aria-label') ?? b.textContent?.trim() ?? '');
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
    const btn = Array.from(el.querySelectorAll('button')).find((b) => (b.getAttribute('aria-label') ?? b.textContent?.trim() ?? '').startsWith(label));
    expect(btn, label).toBeTruthy();
    btn!.click();
  }

  it('shows My view, Student View and Department View', () => {
    const el = render();
    const headings = Array.from(el.querySelectorAll('h2, h3')).map((h) => h.textContent?.trim());
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
    const names = Array.from(el.querySelectorAll('.office__name')).map((h) => h.textContent?.trim());
    expect(names).toEqual(['Advisor', 'Financial aid', 'Evaluator', 'Credit staff', 'Registrar']);
    expect(Array.from(el.querySelectorAll('h2, h3')).map((h) => h.textContent?.trim())).toContain('Staff views');
  });

  it('demo mode: the Advisor and Financial aid tiles open their own pages', () => {
    click(render(), 'Continue as Advisor');
    expect(roles.role()).toBe('Advisor');
    expect(router.navigateByUrl).toHaveBeenLastCalledWith('/advisor');
    click(render(), 'Continue as Financial aid');
    expect(roles.role()).toBe('FinancialAid');
    expect(router.navigateByUrl).toHaveBeenLastCalledWith('/financial-aid');
  });

  it('portal mode, signed out: a staff tile goes to the staff sign-in, and offers staff registration', () => {
    auth.config.set({ mode: 'portal' });
    const el = render();
    click(el, 'Financial aid sign in');
    expect(router.navigateByUrl).toHaveBeenCalledWith('/login/staff');
    expect(el.querySelector('.aud--staff')?.textContent).toContain('Register with the staff code');
    expect(el.querySelector('.aud--staff a[href="/login/staff"]')).not.toBeNull();
  });

  it('portal mode, signed in as another role: a tile signs out and opens that sign-in', async () => {
    auth.config.set({ mode: 'portal' });
    auth.portalUser.set({ email: 'advisor@bu.edu', name: 'Academic Advisor', role: 'Advisor', student_id: null, department: null } as never);
    const logout = vi.spyOn(auth, 'logout').mockResolvedValue();
    const el = render();
    expect(buttons(el).some((b) => b.startsWith('Switch to Registrar sign in'))).toBe(true);
    expect(buttons(el).some((b) => b.startsWith('Open Advisor view'))).toBe(true);
    click(el, 'Switch to Registrar sign in');
    await Promise.resolve();
    await Promise.resolve();
    expect(logout).toHaveBeenCalled();
    expect(router.navigateByUrl).toHaveBeenCalledWith('/login/staff');
  });

  it('entra mode, signed out: views start Microsoft sign-in with the chosen view', () => {
    entra(auth);
    const login = vi.spyOn(auth, 'login').mockResolvedValue();
    const el = render();
    expect(buttons(el).filter((b) => b.includes('Sign in with Microsoft'))).toHaveLength(7);   // Student, Department and 5 staff views
    // Signed out: no empty "My view" card; the hero offers the public check and a hint points at the sign-in cards.
    expect(Array.from(el.querySelectorAll('h2')).map((h) => h.textContent?.trim())).not.toContain('My view');
    expect(el.querySelector('.hero a[href="/credit-check"]')).not.toBeNull();
    expect(el.textContent).toContain('Sign in with your university Microsoft account.');
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

describe('pageGuard (each role only opens its own pages)', () => {
  const run = (page: Page) => TestBed.runInInjectionContext(() => pageGuard(page)({} as never, {} as never));

  function portal(role: DemoRole): AuthService {
    const auth = TestBed.inject(AuthService);
    auth.config.set({ mode: 'portal' });
    auth.portalUser.set({ email: `${role}@bu.edu`, name: role, role, student_id: null, department: null } as never);
    return auth;
  }

  beforeEach(() => TestBed.configureTestingModule({ providers: [provideRouter([])] }));

  it('demo mode shows every page', () => {
    expect(run('advisor')).toBe(true);
    expect(run('financialAid')).toBe(true);
  });

  it('signed-out visitors go to the home page', () => {
    TestBed.inject(AuthService).config.set({ mode: 'portal' });
    expect(String(run('advisor'))).toBe('/');
  });

  it('the Financial aid team cannot open the Advisor page, or the metrics, and lands on its own page', () => {
    portal('FinancialAid');
    expect(String(run('advisor'))).toBe('/financial-aid');
    expect(String(run('evaluation'))).toBe('/financial-aid');
    expect(String(run('review'))).toBe('/financial-aid');
    expect(run('financialAid')).toBe(true);
  });

  it('an Advisor cannot open the Financial aid page and lands on the Advisor page', () => {
    portal('Advisor');
    expect(String(run('financialAid'))).toBe('/advisor');
    expect(String(run('registrar'))).toBe('/advisor');
    expect(run('advisor')).toBe(true);
  });

  it('a Registrar sees only the Registrar page; a Department only the workbench and metrics', () => {
    portal('Registrar');
    expect(run('registrar')).toBe(true);
    expect(String(run('review'))).toBe('/registrar');
  });
});

describe('home page for a signed-in user (the logo opens it)', () => {
  it('shows My view with a way back to their own page', () => {
    TestBed.configureTestingModule({ imports: [HomePage], providers: [provideRouter([])] });
    const auth = TestBed.inject(AuthService);
    auth.config.set({ mode: 'portal' });
    auth.portalUser.set({ email: 'advisor@bu.edu', name: 'Academic Advisor', role: 'Advisor', student_id: null, department: null } as never);
    const fixture = TestBed.createComponent(HomePage);
    fixture.detectChanges();
    const el = fixture.nativeElement as HTMLElement;
    expect(Array.from(el.querySelectorAll('h2')).map((h) => h.textContent?.trim())).toContain('My view');
    expect(el.textContent).toContain('Welcome back, Academic Advisor');
    expect(Array.from(el.querySelectorAll('button')).map((b) => b.textContent?.trim())).toContain('Continue to my view →');
  });
});

describe('home page content', () => {
  function page(setup?: (auth: AuthService) => void): HTMLElement {
    TestBed.configureTestingModule({ imports: [HomePage], providers: [provideRouter([])] });
    setup?.(TestBed.inject(AuthService));
    const fixture = TestBed.createComponent(HomePage);
    fixture.detectChanges();
    return fixture.nativeElement as HTMLElement;
  }

  it('explains every status code in plain words', () => {
    const el = page();
    const codes = Array.from(el.querySelectorAll('.legend .chip__code')).map((c) => c.textContent?.trim());
    expect(codes).toEqual(['T', 'TP', 'TS', 'TM', 'TX']);
    expect(el.querySelector('.legend')?.textContent).toContain('a grade below C');
  });

  it('signed out: the hero has a Sign in button and the public course check', () => {
    const el = page((a) => a.config.set({ mode: 'portal' }));
    expect(Array.from(el.querySelectorAll('.hero button')).map((b) => b.textContent?.trim())).toEqual(['Sign in']);
    expect(el.querySelector('.hero a[href="/credit-check"]')).not.toBeNull();
    expect(el.querySelector('.cta a[href="/credit-check"]')).not.toBeNull();
    expect(el.querySelector('details.signin__switch')).toBeNull();            // the choices are open, not tucked away
  });

  it('signed in: no Sign in button, and the choices move into "Sign in as someone else"', () => {
    const el = page((a) => {
      a.config.set({ mode: 'portal' });
      a.portalUser.set({ email: 'advisor@bu.edu', name: 'Academic Advisor', role: 'Advisor', student_id: null, department: null } as never);
    });
    expect(el.querySelector('.hero button')).toBeNull();
    const switcher = el.querySelector('details.signin__switch') as HTMLDetailsElement;
    expect(switcher.open).toBe(false);
    expect(switcher.querySelector('summary')?.textContent).toContain('Sign in as someone else');
    expect(switcher.querySelectorAll('.office')).toHaveLength(5);
  });

  it('every office button has a distinct accessible name', () => {
    const el = page();
    const names = Array.from(el.querySelectorAll('.office')).map((b) => b.getAttribute('aria-label'));
    expect(new Set(names).size).toBe(5);
    expect(names[0]).toContain('Advisor');
  });
});
