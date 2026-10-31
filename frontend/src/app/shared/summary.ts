import { AidStatus, Attention, StudentSummary } from '../api/models';
import { ChipTone } from './status';

/** Most urgent first, so an advisor's list opens on the students who need a nudge. */
export const ATTENTION_ORDER: readonly Attention[] = ['action_needed', 'in_progress', 'no_transcript', 'on_track'];

export const ATTENTION_LABEL: Record<Attention, string> = {
  action_needed: 'Action needed',
  in_progress: 'In progress',
  no_transcript: 'No transcript',
  on_track: 'On track',
};

export const ATTENTION_TONE: Record<Attention, ChipTone> = {
  action_needed: 'action',
  in_progress: 'pending',
  no_transcript: 'nocredit',
  on_track: 'secured',
};

export const AID_LABEL: Record<AidStatus, string> = {
  confirmed: 'Confirmed',
  provisional: 'Provisional',
  no_data: 'No transcript',
};

export const AID_TONE: Record<AidStatus, ChipTone> = {
  confirmed: 'secured',
  provisional: 'pending',
  no_data: 'nocredit',
};

export const AID_MEANING: Record<AidStatus, string> = {
  confirmed: 'Every course is decided and posted, so these units will not change.',
  provisional: 'Some courses are still being evaluated, so these units can change.',
  no_data: 'No transcript has been uploaded yet.',
};

export type SortKey = 'attention' | 'name' | 'deadline' | 'pending';

export const SORT_LABEL: Record<SortKey, string> = {
  attention: 'Most urgent first',
  name: 'Name A–Z',
  deadline: 'Nearest deadline',
  pending: 'Most pending units',
};

/** Case-insensitive match on name, student id, major or previous school. A blank query matches everyone. */
export function matchesQuery(s: StudentSummary, query: string): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return true;
  return [s.name, s.student_id, s.intended_major, s.previous_school_name ?? ''].some((v) => v.toLowerCase().includes(q));
}

export function sortRows(rows: readonly StudentSummary[], key: SortKey): StudentSummary[] {
  const byName = (a: StudentSummary, b: StudentSummary) => a.name.localeCompare(b.name);
  const sorted = [...rows];
  switch (key) {
    case 'name':
      return sorted.sort(byName);
    case 'deadline':
      return sorted.sort((a, b) => a.days_to_deadline - b.days_to_deadline || byName(a, b));
    case 'pending':
      return sorted.sort((a, b) => b.pending_units - a.pending_units || byName(a, b));
    default:
      return sorted.sort((a, b) => ATTENTION_ORDER.indexOf(a.attention) - ATTENTION_ORDER.indexOf(b.attention) || a.days_to_deadline - b.days_to_deadline || byName(a, b));
  }
}

/** "in 45 days", "tomorrow", "today" or "12 days overdue". */
export function deadlineText(days: number): string {
  if (days === 0) return 'today';
  if (days === 1) return 'tomorrow';
  if (days === -1) return '1 day overdue';
  return days > 0 ? `in ${days} days` : `${-days} days overdue`;
}

export function openItems(s: StudentSummary): number {
  return s.awaiting_student + s.awaiting_evaluator + s.awaiting_posting;
}

/** Total units, rounded away from float noise (units are quarter-converted, e.g. 2.67). */
export function sumUnits(values: readonly number[]): number {
  return Math.round(values.reduce((a, b) => a + b, 0) * 100) / 100;
}

/** CSV/formula injection guard, same rule as the API export: prefix cells Excel would evaluate. */
export function csvCell(value: string | number | null | undefined): string {
  let v = value === null || value === undefined ? '' : String(value);
  if (/^[=+\-@\t\r]/.test(v)) v = `'${v}`;
  return /[",\n\r]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v;
}

export function aidCsv(rows: readonly StudentSummary[]): string {
  const header = ['student_id', 'name', 'major', 'bu_start_term', 'aid_status', 'secured_units', 'pending_units', 'projected_units', 'no_credit_courses', 'open_items', 'transfer_deadline'];
  const body = rows.map((s) =>
    [s.student_id, s.name, s.intended_major, s.bu_start_term, s.aid_status, s.secured_units, s.pending_units, s.projected_units, s.no_credit_lines, openItems(s), s.transfer_deadline].map(csvCell).join(','),
  );
  return [header.join(','), ...body].join('\r\n') + '\r\n';
}
