import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { StudentEvaluation } from '../api/models';
import { StudentStatusPage } from './student-status';

const maya: StudentEvaluation = {
  student: { student_id: 'SYN-24001', name: 'Maya R. Delgado', intended_major: 'Psychology', bu_start_term: 'Fall 2026' },
  totals: { secured_units: 14.67, pending_units: 8, approved_units: 4, no_credit_lines: 0, cap_units: 68 },
  lines: [
    {
      ext_id: 'NYU|PSYCH-UA 1', school_code: 'NYU', term: 'Fall 2024', course_code: 'PSYCH-UA 1', title: 'Intro to Psychology',
      credits: 4, calendar: 'Semester', grade: 'A-', state: 'matched', status: 'Matched - existing equivalency', bu_status_code: 'T',
      bu_course: 'CAS PS 101', units: 4, units_if_approved: 4, reason_code: 'EQ-CONTENT', flags: [], next_step: 'None', ai_tier: null, ai_overlap_pct: null,
    },
    {
      ext_id: 'NYU|PSYCH-UA 10', school_code: 'NYU', term: 'Spring 2025', course_code: 'PSYCH-UA 10', title: 'Statistics',
      credits: 4, calendar: 'Semester', grade: 'A', state: 'approved', status: 'Approved', bu_status_code: 'TP',
      bu_course: 'CAS PS 211', units: 4, units_if_approved: 4, reason_code: 'EQ-EVALUATOR', flags: [], next_step: 'Awaiting posting', ai_tier: null, ai_overlap_pct: null,
    },
    {
      ext_id: 'NYU|PSYCH-UA 25', school_code: 'NYU', term: 'Spring 2025', course_code: 'PSYCH-UA 25', title: 'Cognitive Neuroscience',
      credits: 4, calendar: 'Semester', grade: 'B+', state: 'maybe_ts', status: 'Maybe - syllabus requested', bu_status_code: 'TS',
      bu_course: null, units: 0, units_if_approved: 4, reason_code: 'PD-TS', flags: [], next_step: 'Upload the course syllabus. Reminders are sent on days 7, 21 and 45.', ai_tier: null, ai_overlap_pct: null,
    },
  ],
};

describe('StudentStatusPage', () => {
  it('shows secured vs pending totals, status chips with BU codes and a syllabus upload', async () => {
    TestBed.configureTestingModule({
      imports: [StudentStatusPage],
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
    });
    const fixture = TestBed.createComponent(StudentStatusPage);
    fixture.componentRef.setInput('id', 'SYN-24001');
    fixture.detectChanges();
    const http = TestBed.inject(HttpTestingController);
    http.expectOne('/api/students').flush([maya.student]);
    http.expectOne('/api/students/SYN-24001/evaluation').flush(maya);
    await fixture.whenStable();
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('Secured');
    expect(text).toContain('14.67 units');
    expect(text).toContain('8 units');
    const chips = Array.from((fixture.nativeElement as HTMLElement).querySelectorAll('.chip__code')).map((c) => c.textContent);
    expect(chips).toEqual(['T', 'TP', 'TS']);
    expect(text).toContain('Approved – awaiting posting');
    expect(text).toContain('incl. 4 approved, awaiting posting');
    expect(text).toContain('email sending not enabled in this prototype');
    expect(text).not.toContain('Reminders are sent');
    expect((fixture.nativeElement as HTMLElement).querySelector('input[aria-label="Upload syllabus for PSYCH-UA 25"]')).not.toBeNull();
  });
});
