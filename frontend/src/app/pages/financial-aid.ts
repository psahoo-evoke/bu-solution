import { DecimalPipe } from '@angular/common';
import { Component, computed, effect, inject, signal, untracked } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { ApiService } from '../api/api.service';
import { describeError } from '../api/errors';
import { AidStatus, StudentSummary } from '../api/models';
import { can, suggestedRole, switchRoleMessage } from '../api/permissions';
import { RoleService } from '../api/role.service';
import { ErrorBanner } from '../shared/error-banner';
import { AID_LABEL, AID_MEANING, AID_TONE, SORT_LABEL, SortKey, aidCsv, deadlineText, matchesQuery, openItems, sortRows, sumUnits } from '../shared/summary';

const STATUSES: readonly AidStatus[] = ['provisional', 'confirmed', 'no_data'];

@Component({
  selector: 'app-financial-aid',
  imports: [FormsModule, RouterLink, DecimalPipe, ErrorBanner],
  templateUrl: './financial-aid.html',
})
export class FinancialAidPage {
  private readonly api = inject(ApiService);
  protected readonly roles = inject(RoleService);

  protected readonly rows = signal<StudentSummary[]>([]);
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);
  protected readonly query = signal('');
  protected readonly filter = signal<'all' | AidStatus>('all');
  protected readonly sort = signal<SortKey>('pending');

  protected readonly allowed = computed(() => can(this.roles.role(), 'studentSummary'));
  protected readonly switchHint = switchRoleMessage('studentSummary');
  protected readonly suggested = suggestedRole('studentSummary');

  protected readonly statuses = STATUSES;
  protected readonly sortKeys = Object.keys(SORT_LABEL) as SortKey[];
  protected readonly sortLabel = SORT_LABEL;
  protected readonly label = AID_LABEL;
  protected readonly tone = AID_TONE;
  protected readonly meaning = AID_MEANING;
  protected readonly deadlineText = deadlineText;
  protected readonly openItems = openItems;

  protected readonly count = (s: AidStatus) => this.rows().filter((r) => r.aid_status === s).length;
  protected readonly secured = computed(() => sumUnits(this.rows().map((r) => r.secured_units)));
  protected readonly pending = computed(() => sumUnits(this.rows().map((r) => r.pending_units)));
  protected readonly visible = computed(() => {
    const f = this.filter();
    const q = this.query();
    return sortRows(this.rows().filter((r) => (f === 'all' || r.aid_status === f) && matchesQuery(r, q)), this.sort());
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
    this.roles.set(this.suggested);
  }

  clearFilters(): void {
    this.query.set('');
    this.filter.set('all');
  }

  /** Downloads exactly the rows on screen (after search and filter), so the file matches what was reviewed. */
  download(): void {
    const rows = this.visible();
    if (!rows.length) return;
    const url = URL.createObjectURL(new Blob([aidCsv(rows)], { type: 'text/csv;charset=utf-8' }));
    const a = document.createElement('a');
    a.href = url;
    a.download = 'transfer-credit-aid-readiness.csv';
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
}
