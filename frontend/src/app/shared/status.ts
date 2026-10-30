import { BuStatusCode, CourseEvaluation, DemoRole } from '../api/models';

export type ChipTone = 'secured' | 'pending' | 'nocredit' | 'action';

/** Visual tone for a BU status code. The chip always shows words + code, so colour is never the only signal. */
export function toneFor(code: BuStatusCode): ChipTone {
  switch (code) {
    case 'T':
      return 'secured';
    case 'TX':
      return 'nocredit';
    case 'TS':
    case 'TM':
      return 'action';
    default:
      return 'pending';
  }
}

export const CODE_MEANING: Record<BuStatusCode, string> = {
  T: 'Transfer credit',
  TX: 'No transfer credit',
  TP: 'Pending evaluation',
  TS: 'Syllabus requested',
  TM: 'More materials requested',
};

export interface TermGroup {
  term: string;
  lines: CourseEvaluation[];
}

const SEASON_ORDER: Record<string, number> = { Winter: 0, Spring: 1, Summer: 2, Fall: 3 };

function termKey(term: string): number {
  const m = /^(\w+)\s+(\d{4})$/.exec(term.trim());
  if (!m) return Number.MAX_SAFE_INTEGER;
  return Number(m[2]) * 10 + (SEASON_ORDER[m[1]] ?? 5);
}

/** Groups lines by term, oldest term first, preserving the API's order within a term. */
export function groupByTerm(lines: CourseEvaluation[]): TermGroup[] {
  const map = new Map<string, CourseEvaluation[]>();
  for (const line of lines) {
    const list = map.get(line.term) ?? [];
    list.push(line);
    map.set(line.term, list);
  }
  return [...map.entries()]
    .map(([term, ls]) => ({ term, lines: ls }))
    .sort((a, b) => termKey(a.term) - termKey(b.term));
}

/**
 * Elective code for a BU course, e.g. "CAS PS 211" -> "CAS PS 2TR".
 * The contract (v0.3.0) only allows 1TR and 2TR, so upper-level courses map to 2TR.
 */
export function electiveCodeFor(buCode: string): string {
  const m = /^(.*\s)(\d)\d*\S*$/.exec(buCode.trim());
  if (!m) return buCode;
  const level = Number(m[2]) <= 1 ? '1' : '2';
  return `${m[1]}${level}TR`;
}

/** openapi v0.3.0 DecisionInput.bu_course pattern. */
export const BU_COURSE_PATTERN = /^(CAS [A-Z]{2} [0-9]{3}|CAS [A-Z]{2} [12]TR|TFRGEN 1TR|TFRGEN NOCRDT)$/;

export const AWAITING_POSTING_LABEL = 'Approved – awaiting posting';

/**
 * Chip label + code for a line. `approved` means an evaluator approved it but the Registrar has
 * not posted it yet: the student still sees TP and it counts as pending (openapi v0.3.0).
 */
export function displayStatus(line: CourseEvaluation): { label: string; code: BuStatusCode } {
  if (line.state === 'approved') return { label: AWAITING_POSTING_LABEL, code: 'TP' };
  return { label: line.status, code: line.bu_status_code };
}

/** The API's next step, as is: it states the real reminder schedule (TRANSFERIQ_SYLLABUS_REMINDER_DAYS), so the page
 * never adds or invents one. */
export function nextStepText(line: CourseEvaluation): string {
  return (line.next_step ?? '').trim();
}

/** The status page's name for who is signed in (heading and menu link). */
export function statusTitle(role: DemoRole): string {
  return role === 'Student' ? 'My Transfer Credit Status'
    : role === 'Department' ? 'Student Transfer Credit Status'
    : 'Transfer credit status';
}
