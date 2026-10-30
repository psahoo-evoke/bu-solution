import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { DemoRole, StudentEvaluation } from '../api/models';
import { RoleService } from '../api/role.service';
import { StudentStatusPage, syllabusAskedMessage, transcriptUploadMessage, uploadProblem } from './student-status';

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
      bu_course: null, units: 0, units_if_approved: 4, reason_code: 'PD-TS', flags: [], next_step: 'Upload the course syllabus. We email a reminder every 2 days until it arrives.', ai_tier: null, ai_overlap_pct: null,
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
    expect(text).toContain('We email a reminder every 2 days until it arrives.');
    expect(text).not.toContain('Reminders are sent');
    expect((fixture.nativeElement as HTMLElement).querySelector('input[aria-label="Upload syllabus for PSYCH-UA 25"]')).not.toBeNull();
  });

  it('removes Upload syllabus once a syllabus was uploaded for the course (upload once)', async () => {
    TestBed.configureTestingModule({
      imports: [StudentStatusPage],
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
    });
    const fixture = TestBed.createComponent(StudentStatusPage);
    fixture.componentRef.setInput('id', 'SYN-24001');
    fixture.detectChanges();
    const http = TestBed.inject(HttpTestingController);
    const uploaded = { ...maya, lines: maya.lines.map((l) => (l.state === 'maybe_ts' ? { ...l, syllabus_uploaded: true } : l)) };
    http.expectOne('/api/students').flush([maya.student]);
    http.expectOne('/api/students/SYN-24001/evaluation').flush(uploaded);
    await fixture.whenStable();
    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector('input[aria-label="Upload syllabus for PSYCH-UA 25"]')).toBeNull();
    expect(el.textContent).not.toContain('Upload syllabus');
    expect(el.textContent).toContain('✓ Syllabus uploaded');
  });
});

describe('transcriptUploadMessage', () => {
  const up = {
    transcript_id: 'TR-1', school_code: 'NYU', school_name: 'New York University', school_student_id: 'N1',
    duplicate: false, replaced: false, added: [], removed: [], updated: [],
  };
  it('counts the courses read from a first transcript', () => {
    expect(transcriptUploadMessage('t.pdf', { ...maya, upload: up })).toBe('Transcript "t.pdf" read: 3 New York University courses evaluated.');
  });
  it('says a duplicate changed nothing', () => {
    expect(transcriptUploadMessage('t.pdf', { ...maya, upload: { ...up, duplicate: true } })).toContain('already on file');
  });
  it('lists what a replacing transcript changed', () => {
    const msg = transcriptUploadMessage('t.pdf', { ...maya, upload: { ...up, replaced: true, added: ['PSYCH-UA 30 (Fall 2025)'], removed: ['PSYCH-UA 25 (Spring 2025)'] } });
    expect(msg).toBe('Replaced the earlier New York University transcript: 1 added (PSYCH-UA 30 (Fall 2025)); 1 removed (PSYCH-UA 25 (Spring 2025)).');
  });
});

describe('syllabusAskedMessage (automatic request after a transcript upload)', () => {
  it('names the courses and says the student was emailed', () => {
    expect(syllabusAskedMessage({ status: 'sent', courses: ['PSYCH-UA 25'], emailed_student: true }))
      .toBe('Syllabus needed for PSYCH-UA 25: please upload it below. We also emailed you this request.');
  });
  it('does not claim an email when none went to the student or none was sent', () => {
    expect(syllabusAskedMessage({ status: 'sent', courses: ['A 1', 'B 2'], emailed_student: false }))
      .toBe('Syllabus needed for A 1, B 2: please upload them below. The Credit Evaluation Department was notified by email.');
    expect(syllabusAskedMessage({ status: 'not_sent', courses: ['A 1'] })).toBe('Syllabus needed for A 1: please upload it below.');
  });
  it('says nothing when there was nothing to ask for', () => {
    expect(syllabusAskedMessage({ status: 'none', courses: [] })).toBe('');
    expect(syllabusAskedMessage(undefined)).toBe('');
  });
});

describe('StudentStatusPage header', () => {
  beforeEach(() => {
    try {
      localStorage.clear();
    } catch {
      /* ignore */
    }
    TestBed.configureTestingModule({
      imports: [StudentStatusPage],
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
    });
  });

  function render(role: DemoRole): HTMLElement {
    TestBed.inject(RoleService).set(role);
    const fixture = TestBed.createComponent(StudentStatusPage);
    fixture.detectChanges();
    return fixture.nativeElement as HTMLElement;
  }

  it('is titled for who is signed in', () => {
    expect(render('Student').querySelector('h1')?.textContent?.trim()).toBe('My transfer credit status');
  });
  it('is titled "Student transfer credit status" for a department', () => {
    expect(render('Department').querySelector('h1')?.textContent?.trim()).toBe('Student transfer credit status');
  });
  it('keeps "Transfer credit status" for other staff', () => {
    expect(render('Evaluator').querySelector('h1')?.textContent?.trim()).toBe('Transfer credit status');
  });

  async function renderEvaluation(lines: StudentEvaluation['lines'], uploading = false): Promise<HTMLElement> {
    TestBed.inject(RoleService).set('Student');
    const fixture = TestBed.createComponent(StudentStatusPage);
    fixture.componentRef.setInput('id', 'SYN-24001');
    fixture.detectChanges();
    TestBed.inject(HttpTestingController).expectOne('/api/students/SYN-24001/evaluation').flush({ ...maya, lines });
    await fixture.whenStable();
    (fixture.componentInstance as unknown as { uploadingTranscript: { set(v: boolean): void } }).uploadingTranscript.set(uploading);
    fixture.detectChanges();
    return fixture.nativeElement as HTMLElement;
  }

  it('shows a loader in place of the start panel while a first transcript is read', async () => {
    const el = await renderEvaluation([], true);
    const loader = el.querySelector('.loader-panel');
    expect(loader?.getAttribute('role')).toBe('status');
    expect(loader?.textContent).toContain('Reading your transcript');
    expect(el.querySelector('.start-panel')).toBeNull();
  });

  it('keeps the courses visible but dimmed and busy while another transcript is read', async () => {
    const el = await renderEvaluation(maya.lines, true);
    expect(el.querySelector('.loader-panel')).not.toBeNull();
    expect(el.querySelector('.student-card .file-btn .spinner')).not.toBeNull();
    const term = el.querySelector('section.term');
    expect(term?.classList).toContain('is-stale');
    expect(term?.getAttribute('aria-busy')).toBe('true');
  });

  it('leads a new student with no courses to the transcript upload, without empty totals', async () => {
    const el = await renderEvaluation([]);
    const panel = el.querySelector('.start-panel');
    expect(panel?.textContent).toContain('Start here: upload your transcript');
    expect(panel?.querySelector('.btn--primary')?.textContent).toContain('Upload transcript (PDF)');
    expect(el.querySelector('[aria-label="Credit totals"]')).toBeNull();
    expect(el.textContent).not.toContain('Add another transcript');
  });

  it('makes the transcript upload a secondary action once courses are on file', async () => {
    const el = await renderEvaluation(maya.lines);
    expect(el.querySelector('.start-panel')).toBeNull();
    const btn = Array.from(el.querySelectorAll('.student-card .file-btn')).map((b) => b.className + b.textContent);
    expect(btn.length).toBe(1);
    expect(btn[0]).toContain('Add another transcript (PDF)');
    expect(btn[0]).not.toContain('btn--primary');
  });

  it('hides the student picker for a student and shows it for staff', () => {
    expect(render('Student').querySelector('#student-picker')).toBeNull();
    TestBed.resetTestingModule();
    TestBed.configureTestingModule({
      imports: [StudentStatusPage],
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
    });
    expect(render('CreditStaff').querySelector('#student-picker')).not.toBeNull();
  });
});

describe('uploadProblem', () => {
  const file = (name: string, size: number, type = 'application/pdf') =>
    ({ name, size, type }) as unknown as File;
  it('accepts a PDF within the limit', () => {
    expect(uploadProblem(file('t.pdf', 200_000))).toBeNull();
  });
  it('rejects other file types, empty files and files over 10 MB', () => {
    expect(uploadProblem(file('notes.docx', 1000, 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'))).toContain('not a PDF');
    expect(uploadProblem(file('t.pdf', 0))).toContain('is empty');
    expect(uploadProblem(file('big.pdf', 11 * 1024 * 1024))).toBe('"big.pdf" is 11.0 MB. The limit is 10 MB.');
  });
});
