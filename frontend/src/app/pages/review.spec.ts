import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { AuthService } from '../api/auth.service';
import { roleInterceptor } from '../api/role.interceptor';
import { RoleService } from '../api/role.service';
import { ReviewPage } from './review';

describe('ReviewPage role gating', () => {
  let http: HttpTestingController;

  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({
      imports: [ReviewPage],
      providers: [provideHttpClient(withInterceptors([roleInterceptor])), provideHttpClientTesting()],
    });
    http = TestBed.inject(HttpTestingController);
  });

  it('does not request review data as Student and explains which role to use', async () => {
    const fixture = TestBed.createComponent(ReviewPage);
    fixture.detectChanges();
    http.expectOne('/api/reason-codes').flush([]);
    http.expectNone((r) => r.url === '/api/review-queue');
    await fixture.whenStable();
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('Switch role to CreditStaff, Evaluator or Department to open the review queue.');
    expect((fixture.nativeElement as HTMLElement).querySelector('.workbench')).toBeNull();
  });

  it('loads reason codes from the API and the queue as Evaluator', async () => {
    TestBed.inject(RoleService).set('Evaluator');
    const fixture = TestBed.createComponent(ReviewPage);
    fixture.detectChanges();
    const codes = http.expectOne('/api/reason-codes');
    expect(codes.request.headers.get('X-Demo-Role')).toBe('Evaluator');
    codes.flush([
      { reason_code: 'EQ-CONTENT', decision: 'Equivalent', meaning: 'Substantially equivalent' },
      { reason_code: 'NC-GRADE', decision: 'No credit', meaning: 'Grade below C' },
    ]);
    http.expectOne((r) => r.url === '/api/review-queue').flush([]);
    await fixture.whenStable();
    expect((fixture.nativeElement as HTMLElement).querySelector('.workbench')).not.toBeNull();
  });

  it("opens a department account on its own department, with no department picker", async () => {
    TestBed.inject(RoleService).set('Department');
    TestBed.inject(AuthService).portalUser.set({ email: 'cs@bu.edu', name: 'CS', role: 'Department', student_id: null,
                                                 department: 'Computer Science' });
    const fixture = TestBed.createComponent(ReviewPage);
    fixture.detectChanges();
    http.expectOne('/api/reason-codes').flush([]);
    const q = http.expectOne((r) => r.url === '/api/review-queue');
    expect(q.request.params.get('department')).toBe('Computer Science');
    q.flush([]);
    await fixture.whenStable();
    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector('#dept-filter')).toBeNull();
    expect(el.querySelector('.dept-fixed__name')?.textContent).toBe('Computer Science');
    expect(el.querySelector('#evaluator-name')).toBeNull();                   // the account decides, not a typed name
    expect(el.querySelector('.evaluator-fixed strong')?.textContent).toBe('CS');
  });

  it('keeps the department picker for staff', async () => {
    TestBed.inject(RoleService).set('Evaluator');
    const fixture = TestBed.createComponent(ReviewPage);
    fixture.detectChanges();
    http.expectOne('/api/reason-codes').flush([]);
    const q = http.expectOne((r) => r.url === '/api/review-queue');
    expect(q.request.params.has('department')).toBe(false);
    q.flush([]);
    await fixture.whenStable();
    expect((fixture.nativeElement as HTMLElement).querySelector('#dept-filter')).not.toBeNull();
    expect((fixture.nativeElement as HTMLElement).querySelector('#evaluator-name')).not.toBeNull();   // demo: no account
  });
});
