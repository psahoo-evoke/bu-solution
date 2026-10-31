import { StudentSummary } from '../api/models';
import { can, switchRoleMessage } from '../api/permissions';
import { aidCsv, csvCell, deadlineText, matchesQuery, openItems, sortRows, sumUnits } from './summary';

const row = (o: Partial<StudentSummary>): StudentSummary => ({
  student_id: 'SYN-1', name: 'Ada Lovelace', intended_major: 'Mathematics', bu_start_term: 'Fall 2026', previous_school_name: 'NYU',
  course_count: 3, secured_units: 8, approved_units: 0, pending_units: 4, projected_units: 12, no_credit_lines: 0, cap_units: 68,
  awaiting_student: 0, awaiting_evaluator: 0, awaiting_posting: 0, transfer_deadline: '2027-09-01', days_to_deadline: 100,
  past_deadline: false, advisory_flags: [], attention: 'on_track', attention_reasons: [], aid_status: 'confirmed', ...o,
});

describe('caseload helpers', () => {
  it('searches name, id, major and school, ignoring case and blanks', () => {
    const s = row({});
    expect(matchesQuery(s, '')).toBe(true);
    expect(matchesQuery(s, '  ')).toBe(true);
    for (const q of ['lovelace', 'syn-1', 'MATH', 'nyu']) expect(matchesQuery(s, q)).toBe(true);
    expect(matchesQuery(s, 'chemistry')).toBe(false);
    expect(matchesQuery(row({ previous_school_name: null }), 'nyu')).toBe(false);
  });

  it('sorts the most urgent students first, then by nearest deadline', () => {
    const rows = [
      row({ student_id: 'a', name: 'A', attention: 'on_track' }),
      row({ student_id: 'b', name: 'B', attention: 'action_needed', days_to_deadline: 50 }),
      row({ student_id: 'c', name: 'C', attention: 'action_needed', days_to_deadline: 5 }),
      row({ student_id: 'd', name: 'D', attention: 'in_progress' }),
    ];
    expect(sortRows(rows, 'attention').map((r) => r.student_id)).toEqual(['c', 'b', 'd', 'a']);
    expect(sortRows(rows, 'name').map((r) => r.student_id)).toEqual(['a', 'b', 'c', 'd']);
    expect(rows[0].student_id).toBe('a'); // input is not mutated
  });

  it('sorts by pending units, largest first', () => {
    const rows = [row({ student_id: 'a', pending_units: 1 }), row({ student_id: 'b', pending_units: 9 })];
    expect(sortRows(rows, 'pending').map((r) => r.student_id)).toEqual(['b', 'a']);
  });

  it('words deadlines in plain days', () => {
    expect(deadlineText(45)).toBe('in 45 days');
    expect(deadlineText(1)).toBe('tomorrow');
    expect(deadlineText(0)).toBe('today');
    expect(deadlineText(-1)).toBe('1 day overdue');
    expect(deadlineText(-12)).toBe('12 days overdue');
  });

  it('counts open items and sums units without float noise', () => {
    expect(openItems(row({ awaiting_student: 1, awaiting_evaluator: 2, awaiting_posting: 3 }))).toBe(6);
    expect(sumUnits([2.67, 2.67, 0.1])).toBe(5.44);
    expect(sumUnits([])).toBe(0);
  });

  it('guards CSV cells against formulas and quotes fields that need it', () => {
    expect(csvCell('=HYPERLINK("x")')).toBe(`"'=HYPERLINK(""x"")"`);
    expect(csvCell('+1')).toBe("'+1");
    expect(csvCell('a,b')).toBe('"a,b"');
    expect(csvCell(null)).toBe('');
    expect(csvCell(2.5)).toBe('2.5');
  });

  it('exports one aid-readiness line per student, with no contact data', () => {
    const csv = aidCsv([row({ name: '=cmd|x', awaiting_student: 1 })]);
    const [head, line] = csv.trim().split('\r\n');
    expect(head.split(',')).toHaveLength(11);
    expect(head).not.toMatch(/email|phone|address/);
    expect(line).toContain("'=cmd|x");
    expect(line.split(',')[9]).toBe('1');
  });
});

describe('role matrix for the caseload', () => {
  it('lets Advisor, FinancialAid and CreditStaff see the caseload, nobody else', () => {
    for (const r of ['Advisor', 'FinancialAid', 'CreditStaff'] as const) expect(can(r, 'studentSummary')).toBe(true);
    for (const r of ['Student', 'Evaluator', 'Department', 'Registrar'] as const) expect(can(r, 'studentSummary')).toBe(false);
    expect(switchRoleMessage('studentSummary')).toBe('Switch role to Advisor, FinancialAid or CreditStaff to see the caseload.');
  });

  it('keeps FinancialAid read-only', () => {
    for (const op of ['decide', 'batch', 'post', 'export', 'reset', 'uploadTranscript', 'uploadSyllabus'] as const) {
      expect(can('FinancialAid', op)).toBe(false);
    }
    expect(can('FinancialAid', 'studentEvaluation')).toBe(true);
  });
});
