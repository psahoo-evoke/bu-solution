import { DecimalPipe } from '@angular/common';
import { Component, computed, inject, signal } from '@angular/core';
import { ApiService } from '../api/api.service';
import { describeError } from '../api/errors';
import { Metrics } from '../api/models';
import { RoleService } from '../api/role.service';
import { ErrorBanner } from '../shared/error-banner';

/** Sponsor gates (US-11). */
export const AGREEMENT_GATE_PCT = 80;
export const WRONG_CREDIT_GATE_PCT = 2;

/** The API may send rates as 0–1 fractions or 0–100 percentages; normalise to percent. */
export function toPct(value: number | null | undefined): number {
  if (value === null || value === undefined || Number.isNaN(value)) return 0;
  return Math.abs(value) <= 1 ? value * 100 : value;
}

@Component({
  selector: 'app-evaluation',
  imports: [ErrorBanner, DecimalPipe],
  templateUrl: './evaluation.html',
})
export class EvaluationPage {
  private readonly api = inject(ApiService);
  private readonly roles = inject(RoleService);

  protected readonly metrics = signal<Metrics | null>(null);
  protected readonly error = signal<string | null>(null);
  protected readonly loading = signal(false);
  protected readonly agreementGate = AGREEMENT_GATE_PCT;
  protected readonly wrongGate = WRONG_CREDIT_GATE_PCT;

  protected readonly agreementPct = computed(() => toPct(this.metrics()?.top1_agreement));
  protected readonly strictPct = computed(() => {
    const v = this.metrics()?.strict_agreement;
    return v === null || v === undefined ? null : toPct(v);
  });
  protected readonly deferrals = computed(() => this.metrics()?.deferrals ?? null);
  protected readonly wrongPct = computed(() => toPct(this.metrics()?.wrong_credit_rate));
  /** Meter scale: 0–10%, stretched to the next 5% when the rate is higher, so the bar never just pins at full. */
  protected readonly wrongMax = computed(() => Math.max(10, Math.ceil(this.wrongPct() / 5) * 5));
  protected readonly agreementOk = computed(() => this.agreementPct() >= AGREEMENT_GATE_PCT);
  protected readonly wrongOk = computed(() => this.wrongPct() <= WRONG_CREDIT_GATE_PCT);

  protected readonly tierRows = computed(() => Object.entries(this.metrics()?.by_tier ?? {}));
  protected readonly tierColumns = computed(() => {
    const cols = new Set<string>();
    for (const [, v] of this.tierRows()) if (v && typeof v === 'object') Object.keys(v).forEach((k) => cols.add(k));
    return [...cols];
  });

  constructor() {
    this.load();
  }

  load(): void {
    this.loading.set(true);
    this.error.set(null);
    this.api.getMetrics().subscribe({
      next: (m) => {
        this.metrics.set(m);
        this.loading.set(false);
      },
      error: (err) => {
        this.error.set(describeError(err, this.roles.role(), 'metrics'));
        this.loading.set(false);
      },
    });
  }

  cell(row: Record<string, unknown>, col: string): string {
    const v = row?.[col];
    if (typeof v === 'number') {
      const isRate = /rate|agreement|pct|accuracy|precision|recall/i.test(col);
      return isRate ? `${toPct(v).toFixed(1)}%` : String(Math.round(v * 100) / 100);
    }
    if (typeof v === 'boolean') return v ? 'Yes' : 'No';
    if (v === null || v === undefined) return '—';
    return typeof v === 'object' ? JSON.stringify(v) : String(v);
  }

  label(col: string): string {
    return COLUMN_LABELS[col] ?? col.replace(/_/g, ' ').replace(/^./, (c) => c.toUpperCase());
  }
}

/** Plain names for the by-tier columns the API returns; unknown columns fall back to their key in words. */
const COLUMN_LABELS: Record<string, string> = {
  n: 'Decisions',
  top1: 'Right course on top',
  top1_deferrals: 'Of which deferred',
  strict: 'Strict correct',
  wrong_credit: 'Wrong credit',
  top1_agreement: 'Top-1 agreement',
};
