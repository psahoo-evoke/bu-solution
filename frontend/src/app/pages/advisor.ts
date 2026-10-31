import { DecimalPipe } from '@angular/common';
import { Component, computed, effect, inject, signal, untracked } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { ApiService } from '../api/api.service';
import { describeError } from '../api/errors';
import { Attention, CourseEvaluation, StudentSummary } from '../api/models';
import { can, switchRoleMessage, suggestedRole } from '../api/permissions';
import { RoleService } from '../api/role.service';
import { ErrorBanner } from '../shared/error-banner';
import { displayStatus, nextStepText } from '../shared/status';
import { StatusChip } from '../shared/status-chip';
import { ATTENTION_LABEL, ATTENTION_ORDER, ATTENTION_TONE, SORT_LABEL, SortKey, deadlineText, matchesQuery, sortRows } from '../shared/summary';

/** Lines that still need something from someone; settled lines are summarised, not listed. */
const OPEN_STATES = new Set(['maybe_ts', 'maybe_tm', 'maybe_review', 'pending_age', 'approved']);

@Component({
  selector: 'app-advisor',
  imports: [FormsModule, RouterLink, DecimalPipe, ErrorBanner, StatusChip],
  templateUrl: './advisor.html',
})
export class AdvisorPage {
  private readonly api = inject(ApiService);
  protected readonly roles = inject(RoleService);

  protected readonly rows = signal<StudentSummary[]>([]);
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);
  protected readonly query = signal('');
  protected readonly filter = signal<'all' | Attention>('all');
  protected readonly sort = signal<SortKey>('attention');

  protected readonly openId = signal<string | null>(null);
  protected readonly detail = signal<CourseEvaluation[] | null>(null);
  protected readonly detailError = signal<string | null>(null);

  protected readonly allowed = computed(() => can(this.roles.role(), 'studentSummary'));
  protected readonly switchHint = switchRoleMessage('studentSummary');
  protected readonly suggested = suggestedRole('studentSummary');

  protected readonly attentions = ATTENTION_ORDER;
  protected readonly sortKeys = Object.keys(SORT_LABEL) as SortKey[];
  protected readonly sortLabel = SORT_LABEL;
  protected readonly label = ATTENTION_LABEL;
  protected readonly tone = ATTENTION_TONE;
  protected readonly deadlineText = deadlineText;
  protected readonly displayStatus = displayStatus;
  protected readonly nextStepText = nextStepText;

  protected readonly counts = computed(() => {
    const c: Record<string, number> = { all: this.rows().length };
    for (const a of ATTENTION_ORDER) c[a] = this.rows().filter((r) => r.attention === a).length;
    return c;
  });
  protected readonly visible = computed(() => {
    const f = this.filter();
    const q = this.query();
    return sortRows(this.rows().filter((r) => (f === 'all' || r.attention === f) && matchesQuery(r, q)), this.sort());
  });

  constructor() {
    // Reload when the demo role changes: a blocked role gets the data as soon as it switches to an allowed one.
    effect(() => {
      this.roles.role();
      untracked(() => this.load());
    });
  }

  load(): void {
    if (!this.allowed()) {
      this.rows.set([]);
      this.openId.set(null);
      this.error.set(null);
      this.loading.set(false);
      return;
    }
    this.loading.set(true);
    this.error.set(null);
    this.api.getStudentSummaries().subscribe({
      next: (rows) => {
        this.rows.set(rows);
        this.loading.set(false);
      },
      error: (err) => {
        this.loading.set(false);
        this.error.set(describeError(err, this.roles.role(), 'studentSummary'));
      },
    });
  }

  switchRole(): void {
    void this.roles.switchTo(this.suggested);
  }

  clearFilters(): void {
    this.query.set('');
    this.filter.set('all');
  }

  /** Expand or collapse a student's open courses. Only the latest request may fill the panel. */
  toggle(s: StudentSummary): void {
    if (this.openId() === s.student_id) {
      this.openId.set(null);
      return;
    }
    const id = s.student_id;
    this.openId.set(id);
    this.detail.set(null);
    this.detailError.set(null);
    this.api.getStudentEvaluation(id).subscribe({
      next: (ev) => {
        if (this.openId() === id) this.detail.set(ev.lines.filter((l) => OPEN_STATES.has(l.state)));
      },
      error: (err) => {
        if (this.openId() === id) this.detailError.set(describeError(err, this.roles.role(), 'studentEvaluation'));
      },
    });
  }
}
