// Hand-written from docs/api/openapi.yaml (components/schemas). Keep in sync with the contract.

export type DemoRole = 'Student' | 'CreditStaff' | 'Evaluator' | 'Department' | 'Registrar' | 'Advisor';
export const DEMO_ROLES: readonly DemoRole[] = [
  'Student',
  'CreditStaff',
  'Evaluator',
  'Department',
  'Registrar',
  'Advisor',
];

export interface Student {
  student_id: string;
  name: string;
  intended_major: string;
  bu_start_term: string;
}

export type CourseState =
  | 'matched'
  | 'approved'
  | 'posted'
  | 'posted_no_credit'
  | 'maybe_review'
  | 'maybe_ts'
  | 'maybe_tm'
  | 'pending_age';

export type BuStatusCode = 'T' | 'TX' | 'TP' | 'TS' | 'TM';

export interface CourseEvaluation {
  ext_id: string;
  school_code: string;
  term: string;
  course_code: string;
  title: string;
  credits: number;
  calendar: 'Semester' | 'Quarter';
  grade: string;
  state: CourseState;
  /** Plain-words status */
  status: string;
  /** BU portal code */
  bu_status_code: BuStatusCode;
  bu_course: string | null;
  /** Units posted or approved (0 while pending) */
  units: number;
  units_if_approved: number;
  reason_code: string;
  flags: string[];
  next_step: string;
  ai_tier: string | null;
  ai_overlap_pct: number | null;
}

export interface EvaluationTotals {
  /** Matched from the equivalency table or posted */
  secured_units: number;
  /** Approved, awaiting posting (already included in pending_units) */
  approved_units?: number;
  pending_units: number;
  no_credit_lines: number;
  cap_units: number;
}

export interface StudentEvaluation {
  student: Student;
  lines: CourseEvaluation[];
  totals: EvaluationTotals;
}

export type CandidateTier = 'equivalent' | 'evaluator_decides' | 'elective';

export interface Candidate {
  bu_code: string;
  title: string;
  overlap_pct: number;
  tier: CandidateTier;
  covered: string[];
  missing: string[];
}

export interface Recommendation {
  ext_id: string;
  /** True when based on a description only (not decidable) */
  preliminary: boolean;
  engine: 'azure-openai' | 'offline-fallback';
  candidates: Candidate[];
  suggested_decision: 'Equivalent' | 'Elective' | 'Evaluator decides';
  suggested_code: string;
  confidence_pct: number;
  injection_detected: boolean;
  past_decisions: Decision[];
}

export interface ReviewItem {
  ext_id: string;
  course_code: string;
  title: string;
  school_code: string;
  department: string;
  students: string[];
  syllabus_state: 'complete' | 'incomplete' | 'missing';
  top_candidate: Candidate;
  confidence_pct: number;
  batch_eligible: boolean;
}

export type DecisionKind = 'Equivalent' | 'Elective' | 'No credit';

export interface DecisionInput {
  ext_id: string;
  decision: DecisionKind;
  bu_course: string;
  reason_code: string;
  reusable?: boolean;
  evaluator: string;
  catalog_year?: string;
  note?: string;
}

export interface Decision extends DecisionInput {
  decision_id: string;
  decided_at: string;
  ai_suggestion: string | null;
  ai_agreed: boolean | null;
}

export interface BatchDecisionInput {
  ext_ids: string[];
  evaluator: string;
}

export interface PostingInput {
  student_id?: string;
}

export interface PostingResult {
  posted: number;
  /** MyBU-style CSV rows that were posted */
  csv: string;
}

export interface SyllabusCheck {
  ext_id: string;
  complete: boolean;
  missing_sections: string[];
  status_code: 'TP' | 'TM';
  injection_detected: boolean;
}

/** openapi: components.schemas.SyllabusRequest (POST /students/{id}/courses/{ext_id}/syllabus-request). */
export interface SyllabusRequest {
  student_id: string;
  ext_id: string;
  /** not_sent = no mail service configured yet (the request is still recorded) */
  status: 'sent' | 'not_sent' | 'already_requested';
  to: string[];
  cc: string[];
  requested_at: string;
}

export interface Metrics {
  engine: string;
  n: number;
  /** Top-1 candidate agreement (gate metric) */
  top1_agreement: number;
  /** Suggested decision equals recorded decision */
  strict_agreement?: number;
  /** Holdout items where the matcher deferred to the evaluator (50-79% band) */
  deferrals?: number;
  wrong_credit_rate: number;
  gates_met: boolean;
  by_tier: Record<string, Record<string, unknown>>;
}

export interface Rule {
  rule_id: string;
  category: string;
  rule: string;
  reason_code: string;
}

/** openapi: components.schemas.ReasonCode (GET /reason-codes). */
export interface ReasonCode {
  reason_code: string;
  /** Equivalent | Elective | No credit, plus non-decision groups such as Pending or Flag */
  decision: string;
  meaning: string;
}
