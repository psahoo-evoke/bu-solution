import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { Candidate, ReviewItem } from '../api/models';
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
});

describe('ReviewPage candidate Approve', () => {
  let http: HttpTestingController;

  const cand = (bu_code: string, overlap_pct: number): Candidate => ({
    bu_code, title: bu_code, overlap_pct, tier: 'equivalent', covered: [], missing: [],
  });
  const item = {
    ext_id: 'EXT-1', course_code: 'BIO 101', title: 'Biology', school_code: 'SCH', department: 'Biology',
    students: ['SYN-1'], syllabus_state: 'complete', top_candidate: cand('CAS BI 107', 90), confidence_pct: 90,
    batch_eligible: false,
  } as ReviewItem;

  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({
      imports: [ReviewPage],
      providers: [provideHttpClient(withInterceptors([roleInterceptor])), provideHttpClientTesting()],
    });
    http = TestBed.inject(HttpTestingController);
  });

  async function openCourse(role: 'Department' | 'Evaluator') {
    TestBed.inject(RoleService).set(role);
    const fixture = TestBed.createComponent(ReviewPage);
    fixture.detectChanges();
    http.expectOne('/api/reason-codes').flush([
      { reason_code: 'EQ-CONTENT', decision: 'Equivalent', meaning: 'Substantially equivalent' },
      { reason_code: 'EQ-EVALUATOR', decision: 'Equivalent', meaning: 'Evaluator judgement' },
    ]);
    http.expectOne((r) => r.url === '/api/review-queue').flush([item]);
    fixture.componentInstance.open(item);
    http.expectOne('/api/courses/EXT-1/recommendation').flush({
      ext_id: 'EXT-1', preliminary: false, engine: 'offline-fallback',
      candidates: [cand('CAS BI 107', 90), cand('CAS BI 108', 70)],
      suggested_decision: 'Equivalent', suggested_code: 'CAS BI 107', confidence_pct: 90,
      injection_detected: false, past_decisions: [],
    });
    fixture.detectChanges();
    await fixture.whenStable();
    return fixture;
  }

  it('shows Approve only on the selected candidate and posts it as Equivalent for Department', async () => {
    const fixture = await openCourse('Department');
    const el = fixture.nativeElement as HTMLElement;
    const radios = el.querySelectorAll<HTMLInputElement>('input[name="candidate"]');
    radios[1].click();
    fixture.detectChanges();
    const buttons = el.querySelectorAll<HTMLButtonElement>('.candidate__approve');
    expect(buttons.length).toBe(1);
    expect(buttons[0].closest('.candidate')?.textContent).toContain('CAS BI 108');
    buttons[0].click();
    const req = http.expectOne((r) => r.method === 'POST' && r.url === '/api/decisions');
    expect(req.request.body).toEqual(expect.objectContaining({
      ext_id: 'EXT-1', decision: 'Equivalent', bu_course: 'CAS BI 108', reason_code: 'EQ-EVALUATOR',
    }));
  });

  it('does not show the candidate Approve button for Evaluator', async () => {
    const fixture = await openCourse('Evaluator');
    expect((fixture.nativeElement as HTMLElement).querySelector('.candidate__approve')).toBeNull();
  });
});
