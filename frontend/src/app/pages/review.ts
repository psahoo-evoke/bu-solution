import { Component, DestroyRef, ElementRef, computed, effect, inject, signal, untracked, viewChild } from '@angular/core';
import { DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../api/api.service';
import { AuthService } from '../api/auth.service';
import { describeError } from '../api/errors';
import { Candidate, CourseSyllabus, DecisionKind, ReasonCode, Recommendation, ReviewItem } from '../api/models';
import { Operation, can, suggestedRole, switchRoleMessage } from '../api/permissions';
import { RoleService } from '../api/role.service';
import { ErrorBanner } from '../shared/error-banner';
import { BU_COURSE_PATTERN, electiveCodeFor } from '../shared/status';
import { parseSyllabus } from '../shared/syllabus-sections';

/** R21: only recommendations strictly above 90% may be batch-approved. */
export const BATCH_THRESHOLD = 90;
/** Demo goal: an evaluator decides a maybe course in under 2 minutes (US-05). */
export const TARGET_SECONDS = 120;

/** R22: ready for a decision only with a complete syllabus. Falls back to the syllabus state for an older API. */
export function isDecidable(item: ReviewItem): boolean {
  return item.decidable ?? (item.syllabus_state === 'complete' && !item.preliminary);
}

export function isBatchEligible(item: ReviewItem): boolean {
  return item.batch_eligible && item.confidence_pct > BATCH_THRESHOLD;
}

export function formatElapsed(totalSeconds: number): string {
  const s = Math.max(0, Math.floor(totalSeconds));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
}

@Component({
  selector: 'app-review',
  imports: [DatePipe, FormsModule, ErrorBanner],
  templateUrl: './review.html',
})
export class ReviewPage {
  private readonly api = inject(ApiService);
  protected readonly roles = inject(RoleService);
  private readonly auth = inject(AuthService);
  private readonly detail = viewChild<ElementRef<HTMLElement>>('detail');

  protected readonly queue = signal<ReviewItem[]>([]);
  protected readonly departments = signal<string[]>([]);
  protected readonly department = signal('');
  /** A signed-in department account only ever sees its own department (the API enforces it): fixed, not a choice. */
  protected readonly ownDepartment = computed(() => (this.roles.role() === 'Department' ? this.auth.department() : null));
  protected readonly queueLoading = signal(false);
  /** Client-side filter of the loaded queue (course, title, school, department, top BU match). */
  protected readonly queueSearch = signal('');
  private readonly searched = computed(() => {
    const q = this.queueSearch().trim().toLowerCase();
    if (!q) return this.queue();
    return this.queue().filter((i) =>
      [i.school_code, i.course_code, i.title, i.department, i.top_candidate.bu_code].join(' ').toLowerCase().includes(q),
    );
  });
  /** The evaluator's work: courses with a complete syllabus. */
  protected readonly ready = computed(() => this.queue().filter(isDecidable));
  protected readonly shownQueue = computed(() => this.searched().filter(isDecidable));
  /** Waiting for the student's (complete) syllabus (TS/TM): visible for planning and a syllabus request, not decidable. */
  protected readonly waiting = computed(() => this.queue().filter((i) => !isDecidable(i)));
  protected readonly shownWaiting = computed(() => this.searched().filter((i) => !isDecidable(i)));
  protected readonly error = signal<string | null>(null);
  protected readonly success = signal<string | null>(null);

  protected readonly batchSelection = signal<Set<string>>(new Set());
  protected readonly batchItems = computed(() => this.ready().filter(isBatchEligible));
  protected readonly batchBusy = signal(false);

  protected readonly selected = signal<ReviewItem | null>(null);
  protected readonly rec = signal<Recommendation | null>(null);
  protected readonly recLoading = signal(false);
  protected readonly recError = signal<string | null>(null);
  /** The syllabus on file and the requests sent (step 5): the evaluator reads it next to the AI comparison. */
  protected readonly syllabus = signal<CourseSyllabus | null>(null);
  protected readonly syllabusError = signal<string | null>(null);
  /** Only the parts used to compare courses: description, learning outcomes and the weekly schedule. */
  protected readonly syllabusView = computed(() => parseSyllabus(this.syllabus()?.text));
  /** The BU course the syllabus sections are scored against: the selected candidate, or the top one when the
   *  selection is not a candidate (e.g. an elective code). */
  protected readonly matchCandidate = computed(() => {
    const cands = this.rec()?.candidates ?? [];
    return cands.find((c) => c.bu_code === this.candidateCode()) ?? cands[0] ?? null;
  });

  /** R22: a preliminary suggestion is worded as an estimate ("Likely equivalent"); the decision itself is unchanged. */
  protected suggestionLabel(decision: string): string {
    if (!this.notDecidable() || decision === 'Evaluator decides') return decision;
    return `Likely ${decision.toLowerCase()}`;
  }

  /** One line on what the suggestion means for the evaluator, so "Evaluator decides" never reads as an instruction. */
  protected suggestionHint(decision: string): string {
    switch (decision) {
      case 'Evaluator decides':
        return 'Partial match (50–79% overlap): the AI defers this one to your judgement.';
      case 'Equivalent':
        return 'Strong outcome match (80% or more) with this BU course.';
      case 'Elective':
        return 'Too little overlap for an equivalent: elective (TR) credit fits best.';
      case 'No credit':
        return 'No BU course is close enough for credit.';
      default:
        return '';
    }
  }

  /**
   * Why the workbook note deserves a second look, or null: it rates the AI's suggested course as only a partial (or no)
   * match, or it points at a different BU course. Reference data only; it never changes the AI result.
   */
  protected workbookCaution(notes: { bu_course: string; match_level: string }[], suggested: string | null): string | null {
    if (!suggested || !notes.length) return null;
    const same = notes.find((n) => n.bu_course === suggested);
    if (same && /^(partial|no\b|not\b|none)/i.test(same.match_level.trim())) {
      return `The workbook rates ${suggested} as "${same.match_level}", while the AI suggests it.`;
    }
    if (!same) {
      return `The workbook points to ${notes.map((n) => n.bu_course).join(', ')}, not the AI's ${suggested}.`;
    }
    return null;
  }

  /** Candidates other than the selected one show their covered/missing outcomes only when asked. */
  protected readonly expanded = signal<Set<string>>(new Set());
  protected toggleOutcomes(buCode: string): void {
    const next = new Set(this.expanded());
    if (next.has(buCode)) next.delete(buCode);
    else next.add(buCode);
    this.expanded.set(next);
  }

  /** Why a syllabus is incomplete, in words: "no learning outcomes, no weekly schedule". */
  protected missingSectionsLabel(sections: string[]): string {
    const words: Record<string, string> = { learning_outcomes: 'no learning outcomes', schedule: 'no weekly schedule' };
    return sections.map((s) => words[s] ?? `no ${s.replace(/_/g, ' ')}`).join(', ');
  }

  /** Students waiting on this course who have never been asked for its syllabus (e.g. a transcript loaded as seed
   *  data, so the automatic request after an upload never ran). */
  protected readonly unaskedStudents = computed(() => {
    const s = this.syllabus();
    const item = this.selected();
    if (!s || !item || s.state === 'complete') return [];
    const asked = new Set(s.requests.map((q) => q.student_id));
    return item.students.filter((id) => !asked.has(id));
  });
  protected readonly canRequestSyllabus = computed(() => can(this.roles.role(), 'requestSyllabus'));
  protected readonly requestBusy = signal(false);
  protected readonly requestError = signal<string | null>(null);

  /** Ask one student for this course's syllabus, then reload the request list shown in the banner. */
  askForSyllabus(studentId: string): void {
    const item = this.selected();
    if (!item || this.requestBusy()) return;
    this.requestBusy.set(true);
    this.requestError.set(null);
    this.api.requestSyllabus(studentId, item.ext_id).subscribe({
      next: () => {
        this.api.getSyllabus(item.ext_id).subscribe({
          next: (s) => {
            if (this.selected()?.ext_id === item.ext_id) this.syllabus.set(s);
            this.requestBusy.set(false);
          },
          error: () => this.requestBusy.set(false),
        });
      },
      error: (err) => {
        this.requestBusy.set(false);
        this.requestError.set(this.fail(err, 'requestSyllabus'));
      },
    });
  }

  /** Same bands as the R20 tiers: 80+ high, 50-79 mid, below 50 low. */
  protected matchTone(pct: number): 'high' | 'mid' | 'low' {
    return pct >= 80 ? 'high' : pct >= 50 ? 'mid' : 'low';
  }

  // Decision form
  protected readonly typedEvaluator = signal('Demo Evaluator');
  /** Signed in: the account's name (the API records it from the session anyway). Demo mode: the typed name. */
  protected readonly signedInName = computed(() => this.auth.userName() || null);
  /** Up to two initials for the identity badge ("bu.computer1" -> "BC", "Transfer Evaluator" -> "TE"). */
  protected readonly initials = computed(() =>
    (this.signedInName() ?? '').split(/[\s._@-]+/).filter(Boolean).slice(0, 2).map((w) => w[0].toUpperCase()).join(''),
  );
  protected readonly roleLine = computed(() => [this.roles.role(), this.ownDepartment()].filter(Boolean).join(' · '));
  /** Summary for the empty detail panel. */
  protected readonly stats = computed(() => {
    // Ready courses only: a waiting course's confidence is a catalogue estimate, not a decision confidence.
    const q = this.ready();
    return {
      students: new Set(q.flatMap((i) => i.students)).size,
      waiting: this.waiting().length,
      avgConfidence: q.length ? Math.round(q.reduce((n, i) => n + i.confidence_pct, 0) / q.length) : 0,
    };
  });
  protected readonly evaluator = computed(() => this.signedInName() ?? this.typedEvaluator());
  protected readonly decision = signal<DecisionKind>('Equivalent');
  protected readonly candidateCode = signal('');
  protected readonly electiveCode = signal('');
  protected readonly reasonCode = signal('EQ-CONTENT');
  protected readonly reusable = signal(true);
  protected readonly catalogYear = signal('2025-26');
  protected readonly note = signal('');
  protected readonly saving = signal(false);
  /** A failed save, shown next to the decision button (the page-level banner may be far off screen). */
  protected readonly saveError = signal<string | null>(null);

  protected readonly reasonCodes = signal<ReasonCode[]>([]);
  protected readonly reasonError = signal<string | null>(null);
  protected readonly reasonOptions = computed(() => this.reasonCodes().filter((r) => r.decision === this.decision()));

  // What the current role may do (x-roles in docs/api/openapi.yaml)
  protected readonly canQueue = computed(() => can(this.roles.role(), 'reviewQueue'));
  protected readonly canRecommend = computed(() => can(this.roles.role(), 'recommendation'));
  protected readonly canDecide = computed(() => can(this.roles.role(), 'decide'));
  protected readonly canBatch = computed(() => can(this.roles.role(), 'batch'));
  protected readonly queueHint = switchRoleMessage('reviewQueue');
  protected readonly decideHint = switchRoleMessage('decide');
  protected readonly decideRole = suggestedRole('decide');
  protected readonly notDecidable = computed(() => {
    const r = this.rec();
    const item = this.selected();
    return !!r?.preliminary || (item ? item.syllabus_state !== 'complete' : false);
  });
  protected readonly buCourseForDecision = computed(() => {
    switch (this.decision()) {
      case 'Equivalent':
        return this.candidateCode();
      case 'Elective':
        return this.electiveCode();
      default:
        return 'TFRGEN NOCRDT';
    }
  });

  protected readonly buCourseValid = computed(() => BU_COURSE_PATTERN.test(this.buCourseForDecision()));

  // Timer since the item was opened
  private readonly openedAt = signal<number | null>(null);
  private readonly now = signal(Date.now());
  protected readonly elapsedSeconds = computed(() => {
    const t = this.openedAt();
    return t === null ? 0 : (this.now() - t) / 1000;
  });
  protected readonly elapsedLabel = computed(() => formatElapsed(this.elapsedSeconds()));
  protected readonly overTarget = computed(() => this.elapsedSeconds() > TARGET_SECONDS);
  protected readonly targetLabel = formatElapsed(TARGET_SECONDS);

  constructor() {
    const handle = setInterval(() => this.now.set(Date.now()), 1000);
    inject(DestroyRef).onDestroy(() => clearInterval(handle));
    this.loadReasonCodes();
    // Reload whenever the demo role changes; never call routes the role can't use.
    effect(() => {
      const allowed = this.canQueue();
      untracked(() => {
        if (allowed) {
          this.loadQueue();
        } else {
          this.queue.set([]);
          this.close();
          this.error.set(null);
        }
      });
    });
  }

  private fail(err: unknown, op: Operation): string {
    return describeError(err, this.roles.role(), op);
  }

  loadReasonCodes(): void {
    this.reasonError.set(null);
    this.api.listReasonCodes().subscribe({
      next: (codes) => {
        this.reasonCodes.set(codes);
        this.ensureReason();
      },
      error: (err) => this.reasonError.set(this.fail(err, 'reasonCodes')),
    });
  }

  /** Keep the selected reason code valid for the chosen decision. */
  private ensureReason(preferred = this.reasonCode()): void {
    const opts = this.reasonOptions();
    if (!opts.length) {
      this.reasonCode.set(preferred);
      return;
    }
    this.reasonCode.set(opts.some((o) => o.reason_code === preferred) ? preferred : opts[0].reason_code);
  }

  loadQueue(): void {
    if (!this.canQueue()) return;
    this.queueLoading.set(true);
    this.error.set(null);
    const own = this.ownDepartment();
    if (own) this.department.set(own);
    const dept = this.department();
    this.api.getReviewQueue(dept || undefined).subscribe({
      next: (items) => {
        this.queue.set(items);
        if (!dept) {
          this.departments.set([...new Set(items.map((i) => i.department).filter(Boolean))].sort());
        }
        const keep = new Set(items.filter(isBatchEligible).map((i) => i.ext_id));
        this.batchSelection.set(new Set([...this.batchSelection()].filter((id) => keep.has(id))));
        this.queueLoading.set(false);
      },
      error: (err) => {
        this.queue.set([]);
        this.error.set(this.fail(err, 'reviewQueue'));
        this.queueLoading.set(false);
      },
    });
  }

  /** high / mid / low confidence, for the colour of the queue card's meter (the number is always shown too). */
  protected confidenceTone(pct: number): 'high' | 'mid' | 'low' {
    return pct > BATCH_THRESHOLD ? 'high' : pct >= 60 ? 'mid' : 'low';
  }

  protected openFirst(): void {
    const first = this.ready()[0];
    if (first) this.open(first);
  }

  onDepartment(value: string): void {
    this.department.set(value);
    this.loadQueue();
  }

  toggleBatch(extId: string, checked: boolean): void {
    const next = new Set(this.batchSelection());
    if (checked) next.add(extId);
    else next.delete(extId);
    this.batchSelection.set(next);
  }

  selectAllBatch(): void {
    this.batchSelection.set(new Set(this.batchItems().map((i) => i.ext_id)));
  }

  approveBatch(): void {
    const ids = [...this.batchSelection()];
    if (!ids.length || !this.canBatch()) return;
    this.batchBusy.set(true);
    this.error.set(null);
    this.api.postBatch({ ext_ids: ids, evaluator: this.evaluator() }).subscribe({
      next: (decisions) => {
        this.batchBusy.set(false);
        this.batchSelection.set(new Set());
        this.success.set(`Batch approved: ${decisions.length} courses, each logged as its own reusable decision.`);
        if (this.selected() && ids.includes(this.selected()!.ext_id)) this.close();
        this.loadQueue();
      },
      error: (err) => {
        this.batchBusy.set(false);
        this.error.set(this.fail(err, 'batch'));
      },
    });
  }

  open(item: ReviewItem): void {
    if (!this.canRecommend()) return;
    this.selected.set(item);
    this.openedAt.set(Date.now());
    this.now.set(Date.now());
    this.success.set(null);
    this.rec.set(null);
    this.recError.set(null);
    this.recLoading.set(true);
    this.note.set('');
    this.reusable.set(true);
    this.saveError.set(null);
    this.expanded.set(new Set());
    // Narrow screens stack the queue above the detail: bring the opened course into view.
    if (typeof window !== 'undefined' && window.matchMedia?.('(max-width: 900px)').matches) {
      setTimeout(() => this.detail()?.nativeElement.scrollIntoView({ behavior: 'smooth', block: 'start' }));
    }
    this.syllabus.set(null);
    this.syllabusError.set(null);
    this.requestError.set(null);
    this.api.getSyllabus(item.ext_id).subscribe({
      next: (s) => {
        if (this.selected()?.ext_id === item.ext_id) this.syllabus.set(s);   // ignore a late answer for another course
      },
      error: () => this.syllabusError.set('The syllabus could not be loaded.'),
    });
    // A late answer for a course no longer open must not fill this one's decision form (it would post the other
    // course's BU code under this course).
    const stillOpen = () => this.selected()?.ext_id === item.ext_id;
    this.api.getRecommendation(item.ext_id).subscribe({
      next: (rec) => {
        if (!stillOpen()) return;
        this.rec.set(rec);
        this.recLoading.set(false);
        this.prefill(rec);
      },
      error: (err) => {
        if (!stillOpen()) return;
        this.recLoading.set(false);
        this.recError.set(this.fail(err, 'recommendation'));
      },
    });
  }

  close(): void {
    this.selected.set(null);
    this.rec.set(null);
    this.syllabus.set(null);
    this.openedAt.set(null);
  }

  private prefill(rec: Recommendation): void {
    const top = rec.candidates[0];
    this.candidateCode.set(top?.bu_code ?? '');
    this.electiveCode.set(rec.suggested_decision === 'Elective' && rec.suggested_code ? rec.suggested_code : top ? electiveCodeFor(top.bu_code) : '');
    const kind: DecisionKind = rec.suggested_decision === 'Elective' ? 'Elective' : 'Equivalent';
    this.setDecision(kind, top);
  }

  setDecision(kind: DecisionKind, cand?: Candidate): void {
    this.decision.set(kind);
    const c = cand ?? this.rec()?.candidates.find((x) => x.bu_code === this.candidateCode());
    let preferred = '';
    if (kind === 'Equivalent') preferred = c && c.overlap_pct >= 80 ? 'EQ-CONTENT' : 'EQ-EVALUATOR';
    else if (kind === 'Elective') preferred = c && c.overlap_pct < 50 ? 'EL-LOWOVERLAP' : 'EL-PARTIAL';
    this.ensureReason(preferred);
  }

  pickCandidate(c: Candidate): void {
    this.candidateCode.set(c.bu_code);
    this.electiveCode.set(electiveCodeFor(c.bu_code));
    this.setDecision(this.decision(), c);
  }

  submit(): void {
    const item = this.selected();
    if (!item || !this.buCourseValid() || !this.reasonCode() || !this.canDecide()) return;
    this.saving.set(true);
    this.error.set(null);
    this.saveError.set(null);
    const seconds = this.elapsedSeconds();
    this.api
      .postDecision({
        ext_id: item.ext_id,
        decision: this.decision(),
        bu_course: this.buCourseForDecision(),
        reason_code: this.reasonCode(),
        reusable: this.reusable(),
        evaluator: this.evaluator(),
        catalog_year: this.catalogYear(),
        note: this.note() || undefined,
      })
      .subscribe({
        next: (d) => {
          this.saving.set(false);
          const agreed = d.ai_agreed === null || d.ai_agreed === undefined ? '' : d.ai_agreed ? ' Agrees with the AI suggestion.' : ' Differs from the AI suggestion.';
          this.success.set(
            `${item.course_code}: ${d.decision} → ${d.bu_course} (${d.reason_code}) saved in ${formatElapsed(seconds)}.` +
              `${agreed}${d.reusable ? ' Reusable for the next student.' : ''}`,
          );
          this.close();
          this.loadQueue();
          // The pane shrinks to its summary: bring the confirmation into view if the page was scrolled down to decide.
          setTimeout(() => {
            const el = this.detail()?.nativeElement;
            if (el && el.getBoundingClientRect().top < 0) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
          });
        },
        error: (err) => {
          this.saving.set(false);
          this.saveError.set(this.fail(err, 'decide'));
        },
      });
  }

  tierLabel(tier: string): string {
    return tier === 'evaluator_decides' ? 'Evaluator decides' : tier.charAt(0).toUpperCase() + tier.slice(1);
  }
}
