import { CourseEvaluation, ReviewItem } from '../api/models';
import { toPct } from '../pages/evaluation';
import { parseCsv } from '../pages/registrar';
import { formatElapsed, isBatchEligible } from '../pages/review';
import { BU_COURSE_PATTERN, REMINDER_NOTE, displayStatus, electiveCodeFor, groupByTerm, nextStepText, toneFor } from './status';

const line = (term: string, code: string) => ({ term, course_code: code }) as CourseEvaluation;

describe('status helpers', () => {
  it('groups lines by term, oldest first', () => {
    const groups = groupByTerm([line('Summer 2025', 'PSY 215'), line('Fall 2024', 'PSYCH-UA 1'), line('Spring 2025', 'PSYCH-UA 10'), line('Fall 2024', 'MATH-UA 121')]);
    expect(groups.map((g) => g.term)).toEqual(['Fall 2024', 'Spring 2025', 'Summer 2025']);
    expect(groups[0].lines.map((l) => l.course_code)).toEqual(['PSYCH-UA 1', 'MATH-UA 121']);
  });

  it('derives the TR elective code from a BU course', () => {
    expect(electiveCodeFor('CAS PS 211')).toBe('CAS PS 2TR');
    expect(electiveCodeFor('CAS CS 112')).toBe('CAS CS 1TR');
    expect(electiveCodeFor('CAS CH 373')).toBe('CAS CH 2TR');
  });

  it('shows approved lines as TP awaiting posting, posted lines as they come (T)', () => {
    const approved = { state: 'approved', status: 'Approved', bu_status_code: 'T' } as CourseEvaluation;
    expect(displayStatus(approved)).toEqual({ label: 'Approved – awaiting posting', code: 'TP' });
    const posted = { state: 'posted', status: 'Posted', bu_status_code: 'T' } as CourseEvaluation;
    expect(displayStatus(posted)).toEqual({ label: 'Posted', code: 'T' });
  });

  it('never claims reminder emails were sent', () => {
    const ts = { state: 'maybe_ts', next_step: 'Upload the course syllabus. Reminders are sent on days 7, 21 and 45.' } as CourseEvaluation;
    expect(nextStepText(ts)).toBe(`Upload the course syllabus. ${REMINDER_NOTE}`);
    const tm = { state: 'maybe_tm', next_step: 'Upload a syllabus with outcomes. Reminders on days 7, 21 and 45.' } as CourseEvaluation;
    expect(nextStepText(tm)).toBe(`Upload a syllabus with outcomes. ${REMINDER_NOTE}`);
    expect(nextStepText({ state: 'matched', next_step: 'Nothing to do.' } as CourseEvaluation)).toBe('Nothing to do.');
  });

  it('validates bu_course against the contract pattern', () => {
    for (const ok of ['CAS PS 211', 'CAS PS 2TR', 'TFRGEN 1TR', 'TFRGEN NOCRDT']) expect(BU_COURSE_PATTERN.test(ok)).toBe(true);
    for (const bad of ['CAS PS 3TR', '=HYPERLINK("x")', '']) expect(BU_COURSE_PATTERN.test(bad)).toBe(false);
  });

  it('maps BU codes to tones', () => {
    expect(toneFor('T')).toBe('secured');
    expect(toneFor('TX')).toBe('nocredit');
    expect(toneFor('TP')).toBe('pending');
    expect(toneFor('TS')).toBe('action');
  });

  it('only allows batch approval strictly above 90% (R21)', () => {
    expect(isBatchEligible({ batch_eligible: true, confidence_pct: 91 } as ReviewItem)).toBe(true);
    expect(isBatchEligible({ batch_eligible: true, confidence_pct: 90 } as ReviewItem)).toBe(false);
    expect(isBatchEligible({ batch_eligible: false, confidence_pct: 99 } as ReviewItem)).toBe(false);
  });

  it('formats the decision timer', () => {
    expect(formatElapsed(0)).toBe('0:00');
    expect(formatElapsed(75.6)).toBe('1:15');
  });

  it('normalises rates to percent', () => {
    expect(toPct(0.83)).toBeCloseTo(83);
    expect(toPct(83)).toBe(83);
    expect(toPct(0)).toBe(0);
  });

  it('parses the MyBU CSV preview', () => {
    expect(parseCsv('a,b\r\n"x, y",2\n')).toEqual([['a', 'b'], ['x, y', '2']]);
  });
});
