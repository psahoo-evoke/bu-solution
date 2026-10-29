import { DecimalPipe } from '@angular/common';
import { Component, computed, effect, inject, input, signal, untracked } from '@angular/core';
import { Router } from '@angular/router';
import { ApiService } from '../api/api.service';
import { describeError } from '../api/errors';
import { CourseEvaluation, Student, StudentEvaluation, SyllabusCheck, SyllabusRequest } from '../api/models';
import { can } from '../api/permissions';
import { RoleService } from '../api/role.service';
import { DEFAULT_STUDENT } from '../app.routes';
import { ErrorBanner } from '../shared/error-banner';
import { displayStatus, groupByTerm, nextStepText } from '../shared/status';
import { StatusChip } from '../shared/status-chip';

/** States where a syllabus upload can move the course forward. */
const SYLLABUS_STATES = new Set(['maybe_ts', 'maybe_tm', 'maybe_review', 'pending_age']);

@Component({
  selector: 'app-student-status',
  imports: [StatusChip, ErrorBanner, DecimalPipe],
  templateUrl: './student-status.html',
})
export class StudentStatusPage {
  private readonly api = inject(ApiService);
  private readonly router = inject(Router);
  private readonly roles = inject(RoleService);

  /** Route param :id (component input binding). */
  readonly id = input<string>(DEFAULT_STUDENT);

  protected readonly students = signal<Student[]>([]);
  protected readonly evaluation = signal<StudentEvaluation | null>(null);
  protected readonly loading = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly notice = signal<string | null>(null);
  protected readonly busyExtId = signal<string | null>(null);
  protected readonly uploadingTranscript = signal(false);

  protected readonly canUploadTranscript = computed(() => can(this.roles.role(), 'uploadTranscript'));
  protected readonly canUploadSyllabusRole = computed(() => can(this.roles.role(), 'uploadSyllabus'));
  /** A student only ever sees their own record, so no student picker; staff use it to switch students. */
  protected readonly showPicker = computed(() => this.roles.role() !== 'Student');
  protected readonly groups = computed(() => groupByTerm(this.evaluation()?.lines ?? []));
  protected readonly totals = computed(() => this.evaluation()?.totals ?? null);
  protected readonly hasCourses = computed(() => (this.evaluation()?.lines.length ?? 0) > 0);
  protected readonly displayStatus = displayStatus;
  protected readonly nextStepText = nextStepText;

  constructor() {
    this.loadStudents();
    effect(() => {
      const id = this.id();
      untracked(() => this.load(id));
    });
  }

  loadStudents(): void {
    this.api.listStudents().subscribe({
      next: (s) => this.students.set(s),
      error: () => this.students.set([]),
    });
  }

  load(id = this.id()): void {
    this.loading.set(true);
    this.error.set(null);
    this.api.getStudentEvaluation(id).subscribe({
      next: (ev) => {
        this.evaluation.set(ev);
        this.loading.set(false);
      },
      error: (err) => {
        this.evaluation.set(null);
        this.error.set(describeError(err, this.roles.role(), 'studentEvaluation'));
        this.loading.set(false);
      },
    });
  }

  onPick(studentId: string): void {
    this.notice.set(null);
    this.router.navigate(['/student', studentId]);
  }

  tierText(tier: string): string {
    const t = tier.replace(/_/g, ' ');
    return t.charAt(0).toUpperCase() + t.slice(1);
  }

  canUploadSyllabus(line: CourseEvaluation): boolean {
    // Upload once: after a syllabus was uploaded for this course the button is gone (the API refuses repeats too).
    return this.canUploadSyllabusRole() && SYLLABUS_STATES.has(line.state) && !line.syllabus_uploaded;
  }

  onTranscript(event: Event): void {
    const file = takeFile(event);
    if (!file) return;
    const problem = uploadProblem(file);
    if (problem) {
      this.error.set(problem);
      return;
    }
    this.uploadingTranscript.set(true);
    this.error.set(null);
    this.api.uploadTranscript(this.id(), file).subscribe({
      next: (ev) => {
        this.evaluation.set(ev);
        this.uploadingTranscript.set(false);
        this.notice.set(transcriptUploadMessage(file.name, ev));
      },
      error: (err) => {
        this.uploadingTranscript.set(false);
        this.error.set(describeError(err, this.roles.role(), 'uploadTranscript'));
      },
    });
  }

  /** Clicking Upload syllabus also emails "syllabus needed, please upload" to the notification list. The file
   * picker still opens (the click is not prevented); the API skips repeats within 15 minutes. */
  onSyllabusClick(line: CourseEvaluation): void {
    const studentId = this.id();
    if (!studentId) return;
    this.api.requestSyllabus(studentId, line.ext_id).subscribe({
      next: (req) => this.notice.set(syllabusRequestMessage(line, req)),
      error: (err) => this.error.set(describeError(err, this.roles.role(), 'uploadSyllabus')),
    });
  }

  onSyllabus(line: CourseEvaluation, event: Event): void {
    const file = takeFile(event);
    if (!file) return;
    const problem = uploadProblem(file);
    if (problem) {
      this.error.set(problem);
      return;
    }
    this.busyExtId.set(line.ext_id);
    this.error.set(null);
    this.api.uploadSyllabus(line.ext_id, file).subscribe({
      next: (check) => {
        this.busyExtId.set(null);
        this.notice.set(syllabusMessage(line, check));
        this.load();
      },
      error: (err) => {
        this.busyExtId.set(null);
        this.error.set(describeError(err, this.roles.role(), 'uploadSyllabus'));
      },
    });
  }
}

/** Same limit as the API (backend/app/guard.py MAX_UPLOAD_BYTES); the API re-checks everything. */
export const MAX_UPLOAD_MB = 10;

/** Instant feedback before uploading: PDF only, not empty, not over the size limit. Null when the file is fine. */
export function uploadProblem(file: File): string | null {
  const isPdf = file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf');
  if (!isPdf) return `"${file.name}" is not a PDF. Only PDF files can be uploaded.`;
  if (file.size === 0) return `"${file.name}" is empty.`;
  if (file.size > MAX_UPLOAD_MB * 1024 * 1024) {
    return `"${file.name}" is ${(file.size / (1024 * 1024)).toFixed(1)} MB. The limit is ${MAX_UPLOAD_MB} MB.`;
  }
  return null;
}

function takeFile(event: Event): File | null {
  const inputEl = event.target as HTMLInputElement;
  const file = inputEl.files?.[0] ?? null;
  inputEl.value = '';
  return file;
}

export function syllabusMessage(line: CourseEvaluation, check: SyllabusCheck): string {
  const base = check.complete
    ? `Syllabus for ${line.course_code} is complete (status ${check.status_code}): it is now with an evaluator.`
    : `Syllabus for ${line.course_code} is missing: ${check.missing_sections.join(', ') || 'sections'} (status ${check.status_code}).`;
  return check.injection_detected
    ? `${base} Note: the file contained instructions aimed at the AI; they were ignored and flagged for the evaluator.`
    : base;
}

export function transcriptUploadMessage(fileName: string, ev: StudentEvaluation): string {
  const up = ev.upload;
  if (!up) return `Transcript "${fileName}" read: ${ev.lines.length} courses evaluated.`;
  if (up.duplicate) return `"${fileName}" is already on file for ${up.school_name}. Nothing changed.`;
  const courses = ev.lines.filter((l) => l.school_code === up.school_code).length;
  if (!up.replaced) return `Transcript "${fileName}" read: ${courses} ${up.school_name} courses evaluated.`;
  const parts = [
    up.added.length ? `${up.added.length} added (${up.added.join(', ')})` : '',
    up.removed.length ? `${up.removed.length} removed (${up.removed.join(', ')})` : '',
    up.updated.length ? `${up.updated.length} with a new grade or credits (${up.updated.join(', ')})` : '',
  ].filter(Boolean);
  return `Replaced the earlier ${up.school_name} transcript: ${parts.length ? parts.join('; ') : 'no course changes'}.`;
}

export function syllabusRequestMessage(line: CourseEvaluation, req: SyllabusRequest): string {
  const who = [req.to.join(', '), req.cc.length ? `cc ${req.cc.join(', ')}` : ''].filter(Boolean).join(', ');
  switch (req.status) {
    case 'sent':
      return `Syllabus request for ${line.course_code} emailed to ${who}.`;
    case 'already_requested':
      return `A syllabus request for ${line.course_code} was already emailed in the last 15 minutes.`;
    default:
      return `Syllabus request for ${line.course_code} recorded. Email is not set up yet, so no email was sent.`;
  }
}
