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

/** R21: only recommendations strictly above 90% may be batch-approved. */
export const BATCH_THRESHOLD = 90;
/** Demo goal: an evaluator decides a maybe course in under 2 minutes (US-05). */
export const TARGET_SECONDS = 120;

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
  protected readonly shownQueue = computed(() => {
    const q = this.queueSearch().trim().toLowerCase();
    if (!q) return this.queue();
    return this.queue().filter((i) =>
      [i.school_code, i.course_code, i.title, i.department, i.top_candidate.bu_code].join(' ').toLowerCase().includes(q),
    );
  });
  protected readonly error = signal<string | null>(null);
  protected readonly success = signal<string | null>(null);

  protected readonly batchSelection = signal<Set<string>>(new Set());
  protected readonly batchItems = computed(() => this.queue().filter(isBatchEligible));
  protected readonly batchBusy = signal(false);

  protected readonly selected = signal<ReviewItem | null>(null);
  protected readonly rec = signal<Recommendation | null>(null);
  protected readonly recLoading = signal(false);
  protected readonly recError = signal<string | null>(null);
  /** The syllabus on file and the requests sent (step 5): the evaluator reads it next to the AI comparison. */
  protected readonly syllabus = signal<CourseSyllabus | null>(null);
  protected readonly syllabusError = signal<string | null>(null);

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
    const q = this.queue();
    return {
      students: new Set(q.flatMap((i) => i.students)).size,
      needSyllabus: q.filter((i) => i.syllabus_state !== 'complete').length,
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

  protected readonly reasonCodes = signal<ReasonCode[]>([]);
  protected readonly reasonError = signal<string | null>(null);
  protected readonly reasonOptions = computed(() => this.reasonCodes().filter((r) => r.decision === this.decision()));

  // What the current role may do (x-roles in docs/api/openapi.yaml)
  protected readonly canQueue = computed(() => can(this.roles.role(), 'reviewQueue'));
  protected readonly canRecommend = computed(() => can(this.roles.role(), 'recommendation'));
  protected readonly canDecide = computed(() => can(this.roles.role(), 'decide'));
  protected readonly canBatch = computed(() => can(this.roles.role(), 'batch'));
  /** Department approvers get a one-click Approve on the selected BU candidate. */
  protected readonly isDepartment = computed(() => this.roles.role() === 'Department');
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
    const first = this.queue()[0];
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
    // Narrow screens stack the queue above the detail: bring the opened course into view.
    if (typeof window !== 'undefined' && window.matchMedia?.('(max-width: 900px)').matches) {
      setTimeout(() => this.detail()?.nativeElement.scrollIntoView({ behavior: 'smooth', block: 'start' }));
    }
    this.syllabus.set(null);
    this.syllabusError.set(null);
    this.api.getSyllabus(item.ext_id).subscribe({
      next: (s) => {
        if (this.selected()?.ext_id === item.ext_id) this.syllabus.set(s);   // ignore a late answer for another course
      },
      error: () => this.syllabusError.set('The syllabus could not be loaded.'),
    });
    this.api.getRecommendation(item.ext_id).subscribe({
      next: (rec) => {
        this.rec.set(rec);
        this.recLoading.set(false);
        this.prefill(rec);
      },
      error: (err) => {
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

  /** Department one-click: record the picked candidate as Equivalent, using the form's catalog year, note and reusable flag. */
  approveCandidate(c: Candidate): void {
    this.candidateCode.set(c.bu_code);
    this.setDecision('Equivalent', c);
    this.submit();
  }

  submit(): void {
    const item = this.selected();
    if (!item || !this.buCourseValid() || !this.reasonCode() || !this.canDecide()) return;
    this.saving.set(true);
    this.error.set(null);
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
        },
        error: (err) => {
          this.saving.set(false);
          this.error.set(this.fail(err, 'decide'));
        },
      });
  }

  tierLabel(tier: string): string {
    return tier === 'evaluator_decides' ? 'Evaluator decides' : tier.charAt(0).toUpperCase() + tier.slice(1);
  }
}
