import { DecimalPipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, computed, effect, inject, input, signal, untracked } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { ApiService } from '../api/api.service';
import { describeError } from '../api/errors';
import { CourseEvaluation, Student, StudentEvaluation, SyllabusCheck, TranscriptUpload } from '../api/models';
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
  imports: [StatusChip, ErrorBanner, DecimalPipe, RouterLink],
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
  /** Retry reloads the page data, so it is offered only when loading failed: a refused upload needs another file. */
  protected readonly errorRetryable = signal(true);
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
    this.errorRetryable.set(true);
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
      this.uploadFailed(problem);
      return;
    }
    this.uploadingTranscript.set(true);
    this.error.set(null);
    this.api.uploadTranscript(this.id(), file).subscribe({
      next: (ev) => {
        this.evaluation.set(ev);
        this.uploadingTranscript.set(false);
        this.notice.set([transcriptUploadMessage(file.name, ev), syllabusAskedMessage(ev.upload?.syllabus_request)]
          .filter(Boolean).join(' '));
      },
      error: (err) => {
        this.uploadingTranscript.set(false);
        this.uploadFailed(uploadErrorMessage(err, 'transcript', this.roles.role()));
      },
    });
  }

  onSyllabus(line: CourseEvaluation, event: Event): void {
    const file = takeFile(event);
    if (!file) return;
    const problem = uploadProblem(file);
    if (problem) {
      this.uploadFailed(problem);
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
        this.uploadFailed(uploadErrorMessage(err, 'syllabus', this.roles.role()));
      },
    });
  }

  private uploadFailed(message: string): void {
    this.error.set(message);
    this.errorRetryable.set(false);
  }
}

/**
 * Why an upload was not accepted, in plain words, and what to do. Not "Retry": the browser does not keep the file,
 * and a file the API refused (not a transcript, not a PDF, too large, already uploaded) needs another file anyway.
 */
export function uploadErrorMessage(err: unknown, kind: 'transcript' | 'syllabus', role?: string): string {
  const what = kind === 'transcript' ? 'the official transcript PDF from your previous school' : 'the course syllabus as a PDF';
  if (err instanceof HttpErrorResponse && [409, 413, 415, 422].includes(err.status)) {
    const detail = typeof err.error?.detail === 'string' ? err.error.detail.trim() : '';
    if (err.status === 409) return detail || 'This file was already uploaded.';
    const reason = detail ? ` ${detail.endsWith('.') ? detail : detail + '.'}` : '';
    return `This file was not accepted.${reason} Choose ${what} and upload it again.`;
  }
  if (err instanceof HttpErrorResponse && (err.status === 0 || err.status >= 500)) {
    return `The upload did not go through because the service did not answer. Please upload the file again in a moment.`;
  }
  return describeError(err, role, kind === 'transcript' ? 'uploadTranscript' : 'uploadSyllabus');
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

/** Step 5 is automatic: after a transcript upload the Credit Evaluation Department asks for the syllabus of every
 * "maybe" course without a complete one. Tell the student which, and whether an email went out. */
export function syllabusAskedMessage(req: TranscriptUpload['syllabus_request']): string {
  if (!req || req.status === 'none' || !req.courses.length) return '';
  const what = `Syllabus needed for ${req.courses.join(', ')}: please upload ${req.courses.length === 1 ? 'it' : 'them'} below.`;
  if (req.status === 'sent' && req.emailed_student) return `${what} We also emailed you this request.`;
  if (req.status === 'sent') return `${what} The Credit Evaluation Department was notified by email.`;
  return what;
}
