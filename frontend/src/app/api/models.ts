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
  bu_school?: string;
  bu_start_term: string;
  /** Contact fields (personal data; never sent to an AI service). */
  email?: string;
  phone?: string;
  address?: string;
  /** school_code of the most recently attended school; the name is resolved by the API. */
  previous_school?: string | null;
  previous_school_name?: string | null;
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
  /** A syllabus was already uploaded for this course through the app (it can be uploaded only once). */
  syllabus_uploaded?: boolean;
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
  /** Only on the response to a transcript upload. */
  upload?: TranscriptUpload;
}

/** What a transcript upload did. Changes are "COURSE (Term)" labels, filled only when it replaced that school's lines. */
export interface TranscriptUpload {
  transcript_id: string;
  school_code: string;
  school_name: string;
  school_student_id: string | null;
  duplicate: boolean;
  replaced: boolean;
  added: string[];
  removed: string[];
  updated: string[];
  /** Step 5, automatic: the syllabus request sent after this upload (openapi TranscriptUploadResult). */
  syllabus_request?: {
    status: 'none' | 'sent' | 'not_sent' | 'failed';
    courses: string[];
    to?: string[];
    cc?: string[];
    emailed_student?: boolean;
  };
}

/** openapi: components.schemas.StudentNotifications (GET /students/{id}/notifications). */
export interface StudentNotification {
  id: string;
  kind: 'transcript' | 'syllabus_request' | 'syllabus_reminder' | 'syllabus_received' | 'decision' | 'posted';
  title: string;
  body: string;
  at: string;
  ext_id: string | null;
  unread: boolean;
}

export interface StudentNotifications {
  items: StudentNotification[];
  unread: number;
  seen_at: string | null;
}

/** openapi: components.schemas.CourseSyllabus (GET /courses/{ext_id}/syllabus, staff only). */
export interface CourseSyllabus {
  ext_id: string;
  state: 'complete' | 'incomplete' | 'missing';
  /** Incomplete only: which R23 requirement the syllabus fails. */
  missing_sections?: ('learning_outcomes' | 'schedule')[];
  source: 'upload' | 'on file' | null;
  uploaded_at: string | null;
  injection_detected: boolean;
  /** Plain text from the PDF: always interpolated, never bound as HTML. */
  text: string | null;
  truncated: boolean;
  /** The catalogue record's outcomes: what the matcher compares when the syllabus lists none. */
  catalogue_outcomes?: string[];
  requests: {
    student_id: string;
    student_name: string;
    /** First request. */
    requested_at: string;
    last_sent_at: string | null;
    reminders: number;
    /** null: no more reminders (syllabus arrived, maximum reached, or reminders off). */
    next_reminder_at: string | null;
    status: 'sent' | 'not_sent' | 'failed';
    automatic: boolean;
    emailed_student: boolean;
  }[];
}

export type CandidateTier = 'equivalent' | 'evaluator_decides' | 'elective';

export interface Candidate {
  bu_code: string;
  title: string;
  overlap_pct: number;
  tier: CandidateTier;
  covered: string[];
  missing: string[];
  /** How much of this BU course's description the external description covers (display only; null: nothing to compare). */
  description_match_pct?: number | null;
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
  /** True when based on the catalogue description only (R22). */
  preliminary?: boolean;
  /** R22: false while the course waits for a (complete) syllabus; the API refuses a decision (409). */
  decidable?: boolean;
  /** Hackathon workbook notes for this course (staff reference; not an AI input). */
  workbook_notes?: { bu_course: string; match_level: string; note: string }[];
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

// ------------------------------------------------------------------ public credit check and chat (no sign-in)
export interface CreditSchool {
  school_code: string;
  name: string;
  calendar: string;
}

/** A school's catalog course, for the quick check's course picker. */
export interface CreditCourse {
  course_code: string;
  title: string;
  credits: number;
}

export interface CreditCheckInput {
  school: string;
  course_code?: string;
  title?: string;
  description?: string;
  grade?: string;
  credits?: number;
  term?: string;
}

export type CreditKind =
  | 'decided_equivalent'
  | 'decided_elective'
  | 'not_transferable'
  | 'pending_review'
  | 'needs_evaluation'
  | 'unknown_school'
  | 'unknown_course';

export interface CreditCheckResult {
  kind: CreditKind;
  message: string;
  school_code?: string;
  school_name?: string;
  course_code?: string | null;
  title?: string | null;
  bu_course: string | null;
  bu_title?: string | null;
  units: number | null;
  reason_code: string | null;
  estimate: {
    preliminary: boolean;
    candidates: { bu_code: string; title: string; overlap_pct: number }[];
    engine: string;
    injection_detected: boolean;
  } | null;
  caveats: string[];
  /** Partial or unknown course code: matching catalog courses to pick from. */
  suggestions?: CreditCourse[];
  /** unknown_school: the schools the input could mean. */
  school_suggestions?: { school_code: string; name: string }[];
}

export interface ChatTurn {
  role: 'user' | 'assistant';
  content: string;
  /** Assistant turns: the server's signature of that reply, sent back so the model keeps its context. */
  signature?: string;
}

export interface CreditChatReply {
  reply: string;
  results: CreditCheckResult[];
  grounded: boolean;
  signature: string;
}
