import { TestBed } from '@angular/core/testing';
import { ActivatedRouteSnapshot, Router, convertToParamMap, provideRouter } from '@angular/router';
import { vi } from 'vitest';
import { authGuard } from '../api/auth.guard';
import { AuthService, PortalUser } from '../api/auth.service';
import { RoleService } from '../api/role.service';
import { HomePage } from './home';
import { LoginPage } from './login';

const MAYA: PortalUser = { email: 'maya.delgado@bu.edu', name: 'Maya R. Delgado', role: 'Student', student_id: 'SYN-24001', department: null };
const BIO: PortalUser = { email: 'biology.dept@bu.edu', name: 'Biology Department', role: 'Department', student_id: null, department: 'Biology' };
// Unsigned token with a far-future exp (the SPA only reads exp; the API verifies the signature).
const TOKEN = `x.${btoa(JSON.stringify({ exp: 4102444800 }))}.y`;
const OPTIONS = { mode: 'portal', departments: ['Biology', 'Psychology'], majors: ['Biology', 'Psychology'], terms: ['Fall 2026'] };

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
}

/** Fake /api/auth: options, then the given login/register reply. */
function mockFetch(reply: Response) {
  return vi.spyOn(globalThis, 'fetch').mockImplementation(async (url) =>
    String(url).endsWith('/api/auth/options') ? json(200, OPTIONS) : reply,
  );
}

describe('portal sign-in', () => {
  let auth: AuthService;
  let router: Router;

  beforeEach(() => {
    try {
      localStorage.clear();
      sessionStorage.clear();
    } catch {
      /* ignore */
    }
    TestBed.configureTestingModule({ providers: [provideRouter([])] });
    auth = TestBed.inject(AuthService);
    auth.config.set({ mode: 'portal' });
    router = TestBed.inject(Router);
    vi.spyOn(router, 'navigateByUrl').mockResolvedValue(true);
  });

  afterEach(() => vi.restoreAllMocks());

  async function loginPage(portal: string) {
    const fixture = TestBed.createComponent(LoginPage);
    fixture.componentRef.setInput('portal', portal);
    fixture.detectChanges();
    await fixture.whenStable();
    return fixture;
  }

  it('a student signs in and lands on their own status page', async () => {
    const fetchSpy = mockFetch(json(200, { token: TOKEN, user: MAYA, expires_in: 28800 }));
    const fixture = await loginPage('student');
    const page = fixture.componentInstance as unknown as { email: string; password: string; signIn(): Promise<void> };
    page.email = 'maya.delgado@bu.edu';
    page.password = 'admin';
    await page.signIn();
    const [, init] = fetchSpy.mock.calls.find(([u]) => String(u).endsWith('/api/auth/login'))!;
    expect(JSON.parse(String(init!.body))).toEqual({ email: 'maya.delgado@bu.edu', password: 'admin', portal: 'student' });
    expect(router.navigateByUrl).toHaveBeenCalledWith('/student/SYN-24001');
    expect(auth.studentId()).toBe('SYN-24001');
    expect(TestBed.inject(RoleService).role()).toBe('Student');
    expect(await auth.accessToken()).toBe(TOKEN);
  });

  it('a department signs in and lands on the Evaluator workbench', async () => {
    mockFetch(json(200, { token: TOKEN, user: BIO, expires_in: 28800 }));
    const fixture = await loginPage('department');
    const page = fixture.componentInstance as unknown as { email: string; password: string; signIn(): Promise<void> };
    page.email = 'biology.dept@bu.edu';
    page.password = 'admin';
    await page.signIn();
    expect(router.navigateByUrl).toHaveBeenCalledWith('/review');
    expect(auth.department()).toBe('Biology');
  });

  it('an unknown email offers registration', async () => {
    mockFetch(json(404, { detail: 'No account found for this email. Register first.' }));
    const fixture = await loginPage('student');
    const page = fixture.componentInstance as unknown as { email: string; password: string; signIn(): Promise<void> };
    page.email = 'new.person@bu.edu';
    page.password = 'admin';
    await page.signIn();
    fixture.detectChanges();
    const el = fixture.nativeElement as HTMLElement;
    expect(el.textContent).toContain('No account found');
    const register = Array.from(el.querySelectorAll('.banner button')).find((b) => b.textContent?.includes('Register'));
    expect(register).toBeTruthy();
    (register as HTMLButtonElement).click();
    fixture.detectChanges();
    expect(el.querySelector('#r-name')).toBeTruthy();
    expect(router.navigateByUrl).not.toHaveBeenCalled();
  });

  it('a new student registers and is signed in to their new record', async () => {
    const fetchSpy = mockFetch(json(201, { token: TOKEN, user: { ...MAYA, name: 'Sam Patel', student_id: 'SYN-24005' }, expires_in: 1 }));
    const fixture = await loginPage('student');
    const page = fixture.componentInstance as unknown as Record<string, string> & { register(): Promise<void> };
    Object.assign(page, { name: 'Sam Patel', email: 'sam.patel@bu.edu', password: 'secret1', confirm: 'secret1', major: 'Biology' });
    await page.register();
    const [url] = fetchSpy.mock.calls.find(([u]) => String(u).includes('/register/'))!;
    expect(String(url)).toContain('/api/auth/register/student');
    expect(router.navigateByUrl).toHaveBeenCalledWith('/student/SYN-24005');
  });

  it('staff can register: office and staff code are sent, and they land on their own page', async () => {
    const ADV: PortalUser = { email: 'sam@bu.edu', name: 'Sam Staff', role: 'Advisor', student_id: null, department: null };
    const fetchSpy = mockFetch(json(201, { token: TOKEN, user: ADV, expires_in: 1 }));
    const fixture = await loginPage('staff');
    const page = fixture.componentInstance as unknown as Record<string, string> & { register(): Promise<void>; show(t: string): void };
    page.show('register');
    fixture.detectChanges();
    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector('#r-role')).toBeTruthy();
    expect((el.querySelector('#r-code') as HTMLInputElement).type).toBe('password');
    Object.assign(page, { name: 'Sam Staff', email: 'sam@bu.edu', password: 'secret1', confirm: 'secret1', staffRole: 'Advisor', inviteCode: 'bu-staff' });
    await page.register();
    const [url, init] = fetchSpy.mock.calls.find(([u]) => String(u).includes('/register/'))!;
    expect(String(url)).toContain('/api/auth/register/staff');
    expect(JSON.parse(String((init as RequestInit).body))).toMatchObject({ role: 'Advisor', invite_code: 'bu-staff' });
    expect(router.navigateByUrl).toHaveBeenCalledWith('/advisor');
  });

  it('a wrong staff code shows the server message and signs nobody in', async () => {
    mockFetch(json(403, { detail: 'That staff code is not correct. Ask your administrator for it.' }));
    const fixture = await loginPage('staff');
    const page = fixture.componentInstance as unknown as Record<string, string> & { register(): Promise<void> };
    Object.assign(page, { name: 'Sam Staff', email: 'sam@bu.edu', password: 'secret1', confirm: 'secret1', staffRole: 'Advisor', inviteCode: 'nope' });
    await page.register();
    fixture.detectChanges();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('staff code is not correct');
    expect(router.navigateByUrl).not.toHaveBeenCalled();
    expect(auth.signedIn()).toBe(false);
  });

  it('staff registration switched off on the server disables the form', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (url) =>
      String(url).endsWith('/api/auth/options') ? json(200, { ...OPTIONS, staff_roles: ['Advisor'], staff_registration: false }) : json(201, {}),
    );
    const fixture = await loginPage('staff');
    (fixture.componentInstance as unknown as { show(t: string): void }).show('register');
    await vi.waitFor(() => { fixture.detectChanges(); expect(fixture.nativeElement.textContent).toContain('Staff registration is switched off'); });
    const el = fixture.nativeElement as HTMLElement;
    expect(el.textContent).toContain('Staff registration is switched off');
    expect((el.querySelector('button[type="submit"]') as HTMLButtonElement).disabled).toBe(true);
  });

  it('registration checks that the passwords match', async () => {
    const fetchSpy = mockFetch(json(201, {}));
    const fixture = await loginPage('department');
    const page = fixture.componentInstance as unknown as Record<string, string> & { register(): Promise<void> };
    Object.assign(page, { password: 'secret1', confirm: 'other' });
    await page.register();
    expect(fetchSpy.mock.calls.some(([u]) => String(u).includes('/register/'))).toBe(false);
  });

  it('home page: Student View and Department View open their sign-in pages', () => {
    const fixture = TestBed.createComponent(HomePage);
    fixture.detectChanges();
    const buttons = Array.from((fixture.nativeElement as HTMLElement).querySelectorAll('button'));
    buttons.find((b) => b.textContent?.includes('Student sign in'))!.click();
    expect(router.navigateByUrl).toHaveBeenCalledWith('/login/student');
    buttons.find((b) => b.textContent?.includes('Department sign in'))!.click();
    expect(router.navigateByUrl).toHaveBeenCalledWith('/login/department');
  });

  it('guard: a signed-in student is sent to their own record', () => {
    auth.portalUser.set(MAYA);
    const run = (id: string) =>
      TestBed.runInInjectionContext(() => authGuard({ paramMap: convertToParamMap({ id }) } as ActivatedRouteSnapshot, {} as never));
    expect(run('SYN-24001')).toBe(true);
    expect(String(run('SYN-24002'))).toBe('/student/SYN-24001');
  });

  it('an expired session signs out and leaves a notice for the home page', async () => {
    auth.portalUser.set(MAYA);
    expect(await auth.handleUnauthorized()).toBe(false);
    expect(auth.signedIn()).toBe(false);
    expect(auth.notice()).toContain('session has expired');
  });

  it('a demo-mode tab does not reload while the site is still in demo mode', async () => {
    auth.config.set({ mode: 'demo' });
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(json(200, { mode: 'demo' }));
    expect(await auth.handleUnauthorized()).toBe(false);
  });

  it('guard: signed-out users go to the home page', () => {
    expect(String(TestBed.runInInjectionContext(() => authGuard({} as never, {} as never)))).toBe('/');
  });
});
