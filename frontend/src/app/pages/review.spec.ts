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

  it('shows the syllabus next to the AI comparison and the automatic request status', async () => {
    TestBed.inject(RoleService).set('Evaluator');
    const fixture = TestBed.createComponent(ReviewPage);
    fixture.detectChanges();
    http.expectOne('/api/reason-codes').flush([]);
    const item = { ext_id: 'NYU|PSYCH-UA 25', course_code: 'PSYCH-UA 25', title: 'Social Psychology', school_code: 'NYU',
                   department: 'Psychology', students: ['SYN-24001'], syllabus_state: 'missing', confidence_pct: 40,
                   batch_eligible: false, top_candidate: { bu_code: 'CAS PS 261', title: 'Social', overlap_pct: 40 } };
    http.expectOne((r) => r.url === '/api/review-queue').flush([item]);
    await fixture.whenStable();
    fixture.detectChanges();
    const el = fixture.nativeElement as HTMLElement;
    (el.querySelector('.queue__item') as HTMLButtonElement).click();
    http.expectOne('/api/courses/NYU%7CPSYCH-UA%2025/syllabus').flush({
      ext_id: 'NYU|PSYCH-UA 25', state: 'missing', source: null, uploaded_at: null, injection_detected: false, text: null,
      truncated: false, requests: [{ student_id: 'SYN-24001', student_name: 'Maya R. Delgado', requested_at: '2026-10-30T09:15:00+00:00',
                                     status: 'sent', automatic: true, emailed_student: true }],
    });
    http.expectOne('/api/courses/NYU%7CPSYCH-UA%2025/recommendation').flush({
      ext_id: 'NYU|PSYCH-UA 25', candidates: [], suggested_decision: 'Elective', suggested_code: 'CAS PS 1TR', confidence_pct: 40,
      engine: 'offline-fallback', injection_detected: false, preliminary: true, past_decisions: [],
    });
    await fixture.whenStable();
    fixture.detectChanges();
    const banner = el.querySelector('.banner--warning')?.textContent ?? '';
    expect(banner).toContain('Requested from Maya R. Delgado');
    expect(banner).toContain('emailed to the student');
    expect(banner).not.toContain('Request the syllabus');
    expect(el.querySelector('.syllabus-panel')?.textContent).toContain('No syllabus on file yet');
  });
});
