import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { CreditCheckResult } from '../api/models';
import { CreditCheckPage, trimHistory } from './credit-check';

const decided: CreditCheckResult = {
  kind: 'decided_equivalent', message: 'Already decided: transfers as CAS PS 101 (General Psychology).',
  school_code: 'NYU', course_code: 'PSYCH-UA 1', bu_course: 'CAS PS 101', bu_title: 'General Psychology', units: 4,
  reason_code: 'EQ-CONTENT', estimate: null, caveats: ['This is an estimate before evaluation.'],
};
const pending: CreditCheckResult = {
  kind: 'needs_evaluation', message: 'No decision yet.', school_code: 'NYU', course_code: 'PSYCH-UA 10',
  bu_course: null, units: 4, reason_code: null, caveats: [],
  estimate: { preliminary: true, engine: 'offline-fallback', injection_detected: false,
              candidates: [{ bu_code: 'CAS PS 211', title: 'Experimental Design', overlap_pct: 75 }] },
};

function setup() {
  TestBed.configureTestingModule({
    imports: [CreditCheckPage],
    providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
  });
  const fixture = TestBed.createComponent(CreditCheckPage);
  fixture.detectChanges();
  const http = TestBed.inject(HttpTestingController);
  http.expectOne('/api/credit-check/schools').flush([{ school_code: 'NYU', name: 'New York University', calendar: 'Semester' }]);
  return { fixture, http, el: fixture.nativeElement as HTMLElement };
}

describe('CreditCheckPage', () => {
  it('sends the question and shows the reply with rules-engine result cards', async () => {
    const { fixture, http, el } = setup();
    (el.querySelector('.cc-suggest button') as HTMLButtonElement).click();
    const req = http.expectOne('/api/credit-chat');
    expect(req.request.body.messages).toEqual([{ role: 'user', content: 'Will NYU PSYCH-UA 1 transfer to BU?' }]);
    req.flush({ reply: 'Already decided: CAS PS 101.', results: [decided], grounded: true });
    await fixture.whenStable();
    fixture.detectChanges();
    const card = el.querySelector('.cc-result--decided_equivalent')?.textContent ?? '';
    expect(card).toContain('Already decided');
    expect(card).toContain('CAS PS 101');
  });

  it('New chat clears the conversation and brings the examples back', async () => {
    const { fixture, http, el } = setup();
    (el.querySelector('.cc-suggest button') as HTMLButtonElement).click();
    http.expectOne('/api/credit-chat').flush({ reply: 'Already decided: CAS PS 101.', results: [decided], grounded: true });
    await fixture.whenStable();
    fixture.detectChanges();
    expect(el.querySelector('.cc-suggest')).toBeNull();
    const newChat = [...el.querySelectorAll('button')].find((b) => b.textContent?.trim() === 'New chat') as HTMLButtonElement;
    newChat.click();
    await fixture.whenStable();
    fixture.detectChanges();
    expect(el.querySelectorAll('.cc-row--user').length).toBe(0);
    expect(el.querySelectorAll('.cc-suggest button').length).toBe(4);
  });

  it('sends the signed reply back and asks about a suggested course in one click', async () => {
    const { fixture, http, el } = setup();
    const partial: CreditCheckResult = {
      kind: 'unknown_course', message: 'Did you mean CS 3000 (Algorithms and Data)?', school_code: 'NEU', course_code: 'CS 30',
      bu_course: null, units: null, reason_code: null, estimate: null, caveats: [],
      suggestions: [{ course_code: 'CS 3000', title: 'Algorithms and Data', credits: 4 }],
    };
    (el.querySelector('.cc-suggest button') as HTMLButtonElement).click();
    http.expectOne('/api/credit-chat').flush({ reply: 'Did you mean CS 3000?', results: [partial], grounded: true, signature: 'sig-1' });
    await fixture.whenStable();
    fixture.detectChanges();
    (el.querySelector('.cc-pick .cc-chip') as HTMLButtonElement).click();
    const req = http.expectOne('/api/credit-chat');
    expect(req.request.body.messages.slice(1)).toEqual([
      { role: 'assistant', content: 'Did you mean CS 3000?', signature: 'sig-1' },
      { role: 'user', content: 'NEU CS 3000', signature: undefined },
    ]);
  });

  it('labels estimates as preliminary, never as credit', async () => {
    const { fixture, http, el } = setup();
    (el.querySelectorAll('.cc-suggest button')[2] as HTMLButtonElement).click();
    http.expectOne('/api/credit-chat').flush({ reply: 'No decision yet.', results: [pending], grounded: true });
    await fixture.whenStable();
    fixture.detectChanges();
    expect(el.querySelector('.cc-estimate')?.textContent).toContain('Preliminary estimate – not a promise of credit');
  });

  it('switches to the quick check when the chat is unavailable', async () => {
    const { fixture, http, el } = setup();
    (el.querySelector('.cc-suggest button') as HTMLButtonElement).click();
    http.expectOne('/api/credit-chat').flush({ detail: 'no AI' }, { status: 503, statusText: 'Unavailable' });
    await fixture.whenStable();
    fixture.detectChanges();
    expect(el.querySelector('#cc-school')).not.toBeNull();
    expect(el.textContent).toContain('The chat is not available right now');
  });

  it("loads the chosen school's courses once and asks what an unlisted course covers", async () => {
    const { fixture, http, el } = setup();
    (el.querySelectorAll('.tabs__tab')[1] as HTMLButtonElement).click();
    fixture.detectChanges();
    const page = fixture.componentInstance;
    const render = async () => {
      await fixture.whenStable();
      fixture.detectChanges();
    };
    page['onSchool']('NYU');
    http.expectOne((r) => r.url === '/api/credit-check/courses' && r.params.get('school') === 'NYU')
      .flush([{ course_code: 'PSYCH-UA 1', title: 'Intro to Psychology', credits: 4 }]);
    await render();
    expect(el.querySelectorAll('#cc-course-list option').length).toBe(1);
    expect((el.querySelector('#cc-code') as HTMLInputElement).placeholder).toBe('PSYCH-UA 1');

    page['courseCode'].set('psych-ua1');
    await render();
    expect(el.querySelector('#cc-covers')).toBeNull();          // listed (case and spaces ignored)
    page['courseCode'].set('PSYCH-UA 999');
    await render();
    expect(el.querySelector('#cc-covers')).not.toBeNull();      // unlisted: its topics give a preliminary estimate

    page['onSchool']('NYU');                                   // same school again: cached, no second request
    http.expectNone((r) => r.url === '/api/credit-check/courses');
    expect(page['courseCode']()).toBe('');
  });
});

describe('trimHistory', () => {
  it('keeps at most 12 turns and starts with a user turn', () => {
    const turns = Array.from({ length: 15 }, (_, i) => ({ role: (i % 2 ? 'assistant' : 'user') as 'user' | 'assistant', content: `${i}` }));
    const out = trimHistory(turns);
    expect(out.length).toBeLessThanOrEqual(12);
    expect(out[0].role).toBe('user');
  });
});
