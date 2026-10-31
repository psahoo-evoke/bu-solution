import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter, UrlTree } from '@angular/router';
import { homeGuard } from './api/auth.guard';
import { AuthService, PortalUser } from './api/auth.service';
import { DemoRole } from './api/models';
import { roleInterceptor } from './api/role.interceptor';
import { App } from './app';

describe('App shell', () => {
  beforeEach(async () => {
    localStorage.clear();
    await TestBed.configureTestingModule({
      imports: [App],
      providers: [provideRouter([]), provideHttpClient(withInterceptors([roleInterceptor])), provideHttpClientTesting()],
    }).compileComponents();
  });

  it('shows the role switcher and no synthetic-data wording', async () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    TestBed.inject(HttpTestingController).expectOne('/api/health').flush({ status: 'ok' });
    await fixture.whenStable();
    const el = fixture.nativeElement as HTMLElement;
    expect(el.textContent?.toLowerCase()).not.toContain('synthetic');
    const options = Array.from(el.querySelectorAll('#role-select option')).map((o) => o.textContent?.trim());
    expect(options).toEqual(['Student', 'CreditStaff', 'Evaluator', 'Department', 'Registrar', 'Advisor', 'FinancialAid']);
  });

  it('shows an error banner (not a blank page) when the API is down', async () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    TestBed.inject(HttpTestingController)
      .expectOne('/api/health')
      .error(new ProgressEvent('error'), { status: 0, statusText: 'Unknown Error' });
    await fixture.whenStable();
    const alert = (fixture.nativeElement as HTMLElement).querySelector('[role="alert"]');
    expect(alert?.textContent).toContain('API offline');
  });
});

describe('App shell: no Home for signed-in students and departments', () => {
  const user = (role: DemoRole, student_id: string | null = null, department: string | null = null): PortalUser =>
    ({ email: 'x@bu.edu', name: 'X', role, student_id, department });

  beforeEach(async () => {
    localStorage.clear();
    await TestBed.configureTestingModule({
      imports: [App],
      providers: [provideRouter([]), provideHttpClient(withInterceptors([roleInterceptor])), provideHttpClientTesting()],
    }).compileComponents();
  });

  async function shell(u: PortalUser | null): Promise<HTMLElement> {
    const auth = TestBed.inject(AuthService);
    auth.config.set({ mode: 'portal' });
    auth.portalUser.set(u);
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    TestBed.inject(HttpTestingController).match('/api/health').forEach((r) => r.flush({ status: 'ok' }));
    await fixture.whenStable();
    fixture.detectChanges();
    return fixture.nativeElement as HTMLElement;
  }
  const navTexts = (el: HTMLElement) => Array.from(el.querySelectorAll('.topbar__nav a')).map((a) => a.textContent?.trim());
  const brandHref = (el: HTMLElement) => el.querySelector('.topbar__brand')?.getAttribute('href');

  it('hides Home for a student and the logo opens their own status page', async () => {
    const el = await shell(user('Student', 'SYN-24001'));
    expect(navTexts(el)).not.toContain('Home');
    expect(brandHref(el)).toBe('/student/SYN-24001');
  });

  it('hides Home for a department and the logo opens the workbench', async () => {
    const el = await shell(user('Department', null, 'Biology'));
    expect(navTexts(el)).not.toContain('Home');
    expect(brandHref(el)).toBe('/review');
  });

  it('shows each signed-in role only its own pages, never Home', async () => {
    const expected: Record<string, string[]> = {
      Advisor: ['Student status', 'Advisor caseload'],
      FinancialAid: ['Student status', 'Financial aid'],
      Registrar: ['Student status', 'Registrar'],
      Evaluator: ['Student status', 'Evaluator workbench', 'AI evaluation'],
      CreditStaff: ['Student status', 'Evaluator workbench', 'AI evaluation', 'Registrar'],
    };
    for (const [role, links] of Object.entries(expected)) {
      TestBed.resetTestingModule();
      await TestBed.configureTestingModule({
        imports: [App],
        providers: [provideRouter([]), provideHttpClient(withInterceptors([roleInterceptor])), provideHttpClientTesting()],
      }).compileComponents();
      const el = await shell(user(role as DemoRole));
      expect(navTexts(el), role).toEqual(links);
      expect(brandHref(el), role).not.toBe('/');
    }
  });

  it('a student sees their status and the course check; visitors keep Home', async () => {
    expect(navTexts(await shell(user('Student', 'SYN-24001')))).toEqual(['Check a course', 'My credit status']);
    TestBed.resetTestingModule();
    await TestBed.configureTestingModule({
      imports: [App],
      providers: [provideRouter([]), provideHttpClient(withInterceptors([roleInterceptor])), provideHttpClientTesting()],
    }).compileComponents();
    const el = await shell(null);
    expect(navTexts(el)).toContain('Home');
    expect(brandHref(el)).toBe('/');
  });
});

describe('homeGuard', () => {
  const run = (role: DemoRole | null, mode: 'portal' | 'demo' = 'portal') => {
    TestBed.configureTestingModule({ providers: [provideRouter([])] });
    const auth = TestBed.inject(AuthService);
    auth.config.set({ mode });
    if (role) auth.portalUser.set({ email: 'x@bu.edu', name: 'X', role, student_id: role === 'Student' ? 'SYN-24002' : null,
                                    department: role === 'Department' ? 'Biology' : null });
    const res = TestBed.runInInjectionContext(() => homeGuard({} as never, {} as never));
    return res instanceof UrlTree ? res.toString() : res;
  };
  beforeEach(() => localStorage.clear());

  it('sends a signed-in student to their own status page and a department to the workbench', () => {
    expect(run('Student')).toBe('/student/SYN-24002');
    TestBed.resetTestingModule();
    expect(run('Department')).toBe('/review');
  });

  it('sends signed-in staff to their own page; signed-out visitors and demo mode open the home page', () => {
    expect(run('Registrar')).toBe('/registrar');
    TestBed.resetTestingModule();
    expect(run('Advisor')).toBe('/advisor');
    TestBed.resetTestingModule();
    expect(run('FinancialAid')).toBe('/financial-aid');
    TestBed.resetTestingModule();
    expect(run(null)).toBe(true);
    TestBed.resetTestingModule();
    expect(run(null, 'demo')).toBe(true);
  });
});
