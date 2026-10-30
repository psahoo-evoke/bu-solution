import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { Candidate, ReviewItem } from '../api/models';
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

  it('filters the queue by search text and says when nothing matches', async () => {
    TestBed.inject(RoleService).set('Evaluator');
    const fixture = TestBed.createComponent(ReviewPage);
    fixture.detectChanges();
    http.expectOne('/api/reason-codes').flush([]);
    const mk = (ext_id: string, course_code: string, title: string, bu_code: string) => ({
      ext_id, course_code, title, school_code: 'NYU', department: 'Psychology', students: ['SYN-1'], syllabus_state: 'complete',
      confidence_pct: 70, batch_eligible: false, top_candidate: { bu_code, title, overlap_pct: 70 },
    });
    http.expectOne((r) => r.url === '/api/review-queue').flush([
      mk('A', 'PSYCH-UA 25', 'Social Psychology', 'CAS PS 261'), mk('B', 'MATH-UA 9', 'Algebra', 'CAS MA 121'),
    ]);
    await fixture.whenStable();
    fixture.detectChanges();
    const el = fixture.nativeElement as HTMLElement;
    const search = el.querySelector('#queue-search') as HTMLInputElement;
    search.value = 'ma 121';
    search.dispatchEvent(new Event('input'));
    fixture.detectChanges();
    expect(Array.from(el.querySelectorAll('.queue__item')).map((b) => b.textContent)).toEqual([expect.stringContaining('MATH-UA 9')]);
    search.value = 'chemistry';
    search.dispatchEvent(new Event('input'));
    fixture.detectChanges();
    expect(el.querySelectorAll('.queue__item').length).toBe(0);
    expect(el.querySelector('.queue__nomatch')?.textContent).toContain('No ready course matches');
    expect(el.querySelector('.queue__done')).toBeNull();
  });

  describe('courses waiting for a syllabus (R22)', () => {
    const mk = (ext_id: string, syllabus_state: string, decidable: boolean | undefined, confidence_pct = 70) => ({
      ext_id, course_code: ext_id, title: 'T', school_code: 'NYU', department: 'Psychology', students: ['SYN-1'],
      syllabus_state, decidable, preliminary: syllabus_state !== 'complete', confidence_pct, batch_eligible: false,
      top_candidate: { bu_code: 'CAS PS 101', title: 'T', overlap_pct: 100 },
    });

    async function render(items: unknown[]): Promise<HTMLElement> {
      TestBed.inject(RoleService).set('Evaluator');
      const fixture = TestBed.createComponent(ReviewPage);
      fixture.detectChanges();
      http.expectOne('/api/reason-codes').flush([]);
      http.expectOne((r) => r.url === '/api/review-queue').flush(items);
      await fixture.whenStable();
      fixture.detectChanges();
      return fixture.nativeElement as HTMLElement;
    }

    const titles = (el: HTMLElement, list: string) =>
      Array.from(el.querySelectorAll(`[aria-label="${list}"] .queue__title strong`)).map((s) => s.textContent?.trim());

    it('keeps them out of the work queue and its count, in a collapsed list without a confidence bar', async () => {
      const el = await render([mk('READY 1', 'complete', true), mk('TS 1', 'missing', false, 100), mk('TM 1', 'incomplete', false)]);
      expect(titles(el, 'Courses awaiting a decision')).toEqual(['NYU READY 1']);
      expect(el.querySelector('#queue-h')?.textContent).toContain('1');
      const waiting = el.querySelector<HTMLDetailsElement>('details.queue__waiting')!;
      expect(waiting.open).toBe(false);
      expect(waiting.querySelector('summary')?.textContent).toContain('Waiting for a syllabus');
      expect(titles(el, 'Courses waiting for a syllabus')).toEqual(['NYU TS 1', 'NYU TM 1']);
      expect(waiting.querySelector('.conf')).toBeNull();                       // no "100% confidence" on a description
      expect(el.querySelector('.detail-empty h2')?.textContent).toContain('1 course is ready for a decision');
    });

    it('says nothing is ready when every course waits for a syllabus', async () => {
      const el = await render([mk('TS 1', 'missing', false)]);
      expect(el.querySelector('.queue__done')?.textContent).toContain('Nothing is ready to decide');
      expect(el.querySelector('.detail-empty h2')?.textContent).toContain('Nothing is ready to decide');
      expect(el.querySelector('.batch-empty')).toBeNull();
    });

    it('falls back to the syllabus state when the API does not send decidable', async () => {
      const el = await render([mk('READY 1', 'complete', undefined), mk('TS 1', 'missing', undefined)]);
      expect(titles(el, 'Courses awaiting a decision')).toEqual(['NYU READY 1']);
      expect(titles(el, 'Courses waiting for a syllabus')).toEqual(['NYU TS 1']);
    });
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
                                     last_sent_at: '2026-11-01T09:15:00+00:00', reminders: 1,
                                     next_reminder_at: '2026-11-03T09:15:00+00:00', status: 'sent', automatic: true,
                                     emailed_student: true }],
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
    expect(banner).toContain('reminded 1×');
    expect(banner).toContain('next reminder 3 Nov');
    expect(banner).not.toContain('Request the syllabus');
    expect(el.querySelector('.syllabus-panel')?.textContent).toContain('No syllabus on file yet');
    expect(el.querySelector('.wb-notes')).toBeNull();                       // no workbook note for this course
    const suggestion = el.querySelector('.suggestion') as HTMLElement;
    expect(suggestion.classList).toContain('suggestion--prelim');
    expect(suggestion.textContent).toContain('Preliminary');
    expect(suggestion.textContent).toContain('Likely elective');
  });

  it('shows the catalogue outcomes the score used when the syllabus lists none', async () => {
    TestBed.inject(RoleService).set('Evaluator');
    const fixture = TestBed.createComponent(ReviewPage);
    fixture.detectChanges();
    http.expectOne('/api/reason-codes').flush([]);
    const item = { ext_id: 'NEU|CS 2700', course_code: 'CS 2700', title: 'Data Structures', school_code: 'NEU',
                   department: 'Computer Science', students: ['SYN-24002'], syllabus_state: 'incomplete', confidence_pct: 83,
                   batch_eligible: false, top_candidate: { bu_code: 'CAS CS 112', title: 'CS 2', overlap_pct: 83 },
                   workbook_notes: [{ bu_course: 'CAS CS 112', match_level: 'Partial - syllabus review', note: 'NU splits program design and data structures.' }] };
    http.expectOne((r) => r.url === '/api/review-queue').flush([item]);
    await fixture.whenStable();
    fixture.detectChanges();
    const el = fixture.nativeElement as HTMLElement;
    (el.querySelector('.queue__item') as HTMLButtonElement).click();
    http.expectOne('/api/courses/NEU%7CCS%202700/syllabus').flush({
      ext_id: 'NEU|CS 2700', state: 'incomplete', missing_sections: ['learning_outcomes', 'schedule'],
      source: 'on file', uploaded_at: null, injection_detected: false,
      text: 'Course description\nData Structures.\nLearning outcomes\nTo be discussed in the first class meeting.\nAssessment',
      truncated: false, requests: [], catalogue_outcomes: ['Explain the core ideas of linked lists', 'Analyze problems involving hash tables'],
    });
    http.expectOne('/api/courses/NEU%7CCS%202700/recommendation').flush({
      ext_id: 'NEU|CS 2700', suggested_decision: 'Equivalent', suggested_code: 'CAS CS 112', confidence_pct: 83,
      engine: 'azure-openai', injection_detected: false, preliminary: true, past_decisions: [],
      candidates: [{ bu_code: 'CAS CS 112', title: 'CS 2', overlap_pct: 83, tier: 'equivalent', description_match_pct: 90,
                     covered: ['a', 'b', 'c', 'd', 'e'], missing: ['f'] }],
    });
    await fixture.whenStable();
    fixture.detectChanges();
    const panel = el.querySelector('.syllabus-panel')?.textContent ?? '';
    expect(el.querySelector('.syl-reason')?.textContent?.trim()).toBe('no learning outcomes, no weekly schedule');
    expect(panel).toContain('Syllabus: To be discussed in the first class meeting.');
    expect(panel).toContain('Catalogue lists');
    expect(el.querySelectorAll('.syl-sec__catalogue li').length).toBe(2);
    expect(panel).toContain('90% match · CAS CS 112');
    expect(panel).toContain('5 of 6 CAS CS 112 outcomes');
    expect(el.querySelector('.suggestion')?.textContent).toContain('Likely equivalent');
    expect(el.querySelector('.suggestion')?.textContent).toContain('catalogue estimate');
    const notes = el.querySelector('.wb-notes')?.textContent ?? '';
    expect(notes).toContain('reference only, not used by the AI');
    expect(notes).toContain('CAS CS 112 · Partial - syllabus review');
    expect(notes).toContain('NU splits program design and data structures.');

    const banner = el.querySelector('.banner--warning') as HTMLElement;
    expect(banner.textContent).toContain('Syllabus incomplete (no learning outcomes, no weekly schedule).');
    expect(banner.textContent).toContain('No syllabus request sent yet to SYN-24002.');
    const ask = banner.querySelector('.req-line--ask button') as HTMLButtonElement;
    expect(ask.textContent?.trim()).toBe('Request syllabus');
    ask.click();
    const post = http.expectOne('/api/students/SYN-24002/courses/NEU%7CCS%202700/syllabus-request');
    expect(post.request.method).toBe('POST');
    post.flush({ student_id: 'SYN-24002', ext_id: 'NEU|CS 2700', status: 'not_sent', to: [], cc: [], requested_at: '2026-10-30T12:00:00+00:00' });
    http.expectOne('/api/courses/NEU%7CCS%202700/syllabus').flush({
      ext_id: 'NEU|CS 2700', state: 'incomplete', missing_sections: ['learning_outcomes', 'schedule'], source: 'on file',
      uploaded_at: null, injection_detected: false, text: null, truncated: false, catalogue_outcomes: [],
      requests: [{ student_id: 'SYN-24002', student_name: 'Jordan Reyes', requested_at: '2026-10-30T12:00:00+00:00',
                   last_sent_at: null, reminders: 0, next_reminder_at: null, status: 'not_sent', automatic: false,
                   emailed_student: false }],
    });
    await fixture.whenStable();
    fixture.detectChanges();
    expect(banner.textContent).toContain('Requested from Jordan Reyes');
    expect(banner.querySelector('.req-line--ask')).toBeNull();
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

  function approveButtons(el: HTMLElement): HTMLButtonElement[] {
    return Array.from(el.querySelectorAll<HTMLButtonElement>('button')).filter((b) => /Approve/.test(b.textContent ?? ''));
  }

  it('has one Approve, in the decision bar, and it posts the picked candidate for Department', async () => {
    const fixture = await openCourse('Department');
    const el = fixture.nativeElement as HTMLElement;
    el.querySelectorAll<HTMLInputElement>('input[name="candidate"]')[1].click();
    fixture.detectChanges();
    expect(el.querySelector('.decision output')?.textContent).toContain('CAS BI 108');
    const buttons = approveButtons(el);
    expect(buttons.length).toBe(1);
    expect(buttons[0].closest('.decision')).not.toBeNull();
    expect(buttons[0].classList).toContain('btn--success');
    buttons[0].click();
    const req = http.expectOne((r) => r.method === 'POST' && r.url === '/api/decisions');
    expect(req.request.body).toEqual(expect.objectContaining({
      ext_id: 'EXT-1', decision: 'Equivalent', bu_course: 'CAS BI 108', reason_code: 'EQ-EVALUATOR',
    }));
  });

  it('has no per-candidate Approve button for Evaluator either', async () => {
    const fixture = await openCourse('Evaluator');
    const buttons = approveButtons(fixture.nativeElement as HTMLElement);
    expect(buttons.length).toBe(1);
    expect(buttons[0].closest('.candidate')).toBeNull();
  });

  it('shows a failed save next to the decision button, not only at the top of the page', async () => {
    const fixture = await openCourse('Evaluator');
    const el = fixture.nativeElement as HTMLElement;
    approveButtons(el)[0].click();
    http.expectOne((r) => r.method === 'POST' && r.url === '/api/decisions')
      .flush({ detail: 'boom' }, { status: 500, statusText: 'Server Error' });
    fixture.detectChanges();
    const err = el.querySelector('.decision [role="alert"]');
    expect(err?.textContent).toContain('Not saved');
    expect(el.querySelector('.decision')).not.toBeNull();   // the course stays open, so the evaluator can retry
  });

  describe('a late AI comparison for a course no longer open', () => {
    const other = { ...item, ext_id: 'EXT-2', course_code: 'BIO 202', title: 'Genetics' } as ReviewItem;
    const recFor = (ext_id: string, code: string) => ({
      ext_id, preliminary: false, engine: 'offline-fallback', candidates: [cand(code, 95)],
      suggested_decision: 'Equivalent', suggested_code: code, confidence_pct: 95,
      injection_detected: false, past_decisions: [],
    });

    // Opens EXT-1, then EXT-2 before EXT-1's comparison has come back. `second` is EXT-2's pending comparison.
    async function switchCourses() {
      TestBed.inject(RoleService).set('Evaluator');
      const fixture = TestBed.createComponent(ReviewPage);
      fixture.detectChanges();
      http.expectOne('/api/reason-codes').flush([
        { reason_code: 'EQ-CONTENT', decision: 'Equivalent', meaning: 'Substantially equivalent' },
      ]);
      http.expectOne((r) => r.url === '/api/review-queue').flush([item, other]);
      fixture.componentInstance.open(item);
      const first = http.expectOne('/api/courses/EXT-1/recommendation');
      fixture.componentInstance.open(other);
      const second = http.expectOne('/api/courses/EXT-2/recommendation');
      return { fixture, first, second };
    }

    async function approvedBody(fixture: Awaited<ReturnType<typeof switchCourses>>['fixture']) {
      fixture.detectChanges();
      await fixture.whenStable();
      approveButtons(fixture.nativeElement as HTMLElement)[0].click();
      return http.expectOne((r) => r.method === 'POST' && r.url === '/api/decisions').request.body;
    }

    it('does not fill the open course with the other course\'s BU code', async () => {
      const { fixture, first, second } = await switchCourses();
      second.flush(recFor('EXT-2', 'CAS BI 206'));
      first.flush(recFor('EXT-1', 'CAS BI 107'));
      expect(await approvedBody(fixture)).toEqual(expect.objectContaining({ ext_id: 'EXT-2', bu_course: 'CAS BI 206' }));
    });

    it('does not show the other course\'s error or stop the open course loading', async () => {
      const { fixture, first, second } = await switchCourses();
      first.flush({ detail: 'boom' }, { status: 500, statusText: 'Server Error' });
      fixture.detectChanges();
      const el = fixture.nativeElement as HTMLElement;
      expect(el.querySelector('.banner--error')).toBeNull();
      expect(el.textContent).toContain('Loading AI recommendation');
      second.flush(recFor('EXT-2', 'CAS BI 206'));
      expect(await approvedBody(fixture)).toEqual(expect.objectContaining({ ext_id: 'EXT-2', bu_course: 'CAS BI 206' }));
    });
  });

  it('shows outcomes for the selected candidate and the others on request', async () => {
    const fixture = await openCourse('Evaluator');
    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelectorAll('.candidate .outcomes').length).toBe(1);
    const toggle = el.querySelector<HTMLButtonElement>('.candidate__toggle')!;
    expect(toggle.getAttribute('aria-expanded')).toBe('false');
    toggle.click();
    fixture.detectChanges();
    expect(el.querySelectorAll('.candidate .outcomes').length).toBe(2);
    expect(toggle.getAttribute('aria-expanded')).toBe('true');
  });
});
