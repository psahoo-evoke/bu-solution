import { DEMO_ROLES, DemoRole } from './models';

/**
 * Role matrix copied from `x-roles` in docs/api/openapi.yaml (v0.3.0, default deny).
 * The server is the authority (401 missing role, 403 wrong role); this only lets the UI
 * hide or disable actions the current role cannot use and explain why.
 */
export type Operation =
  | 'listStudents'
  | 'studentEvaluation'
  | 'uploadTranscript'
  | 'uploadSyllabus'
  | 'recommendation'
  | 'reviewQueue'
  | 'decide'
  | 'batch'
  | 'export'
  | 'post'
  | 'metrics'
  | 'rules'
  | 'reasonCodes'
  | 'reset';

const ALL: readonly DemoRole[] = DEMO_ROLES;

export const OPERATION_ROLES: Record<Operation, readonly DemoRole[]> = {
  listStudents: ALL,
  studentEvaluation: ALL,
  uploadTranscript: ['Student', 'CreditStaff'],
  uploadSyllabus: ['Student', 'CreditStaff', 'Evaluator', 'Department'],
  recommendation: ['CreditStaff', 'Evaluator', 'Department'],
  reviewQueue: ['CreditStaff', 'Evaluator', 'Department'],
  decide: ['Evaluator', 'Department'],
  batch: ['Evaluator', 'Department'],
  export: ['Registrar', 'CreditStaff'],
  post: ['Registrar', 'CreditStaff'],
  metrics: ALL,
  rules: ALL,
  reasonCodes: ALL,
  reset: ['CreditStaff', 'Registrar'],
};

/** Plain-words verb for each operation, used in "Switch role to X to <verb>". */
const VERBS: Record<Operation, string> = {
  listStudents: 'see students',
  studentEvaluation: 'see this status page',
  uploadTranscript: 'upload a transcript',
  uploadSyllabus: 'upload a syllabus',
  recommendation: 'see the AI comparison',
  reviewQueue: 'open the review queue',
  decide: 'decide',
  batch: 'approve a batch',
  export: 'download the MyBU export',
  post: 'post approved courses',
  metrics: 'see the metrics',
  rules: 'see the rules',
  reasonCodes: 'load reason codes',
  reset: 'reset the demo',
};

export function can(role: DemoRole, op: Operation): boolean {
  return OPERATION_ROLES[op].includes(role);
}

function joinOr(items: readonly string[]): string {
  if (items.length <= 1) return items.join('');
  return `${items.slice(0, -1).join(', ')} or ${items[items.length - 1]}`;
}

/** e.g. "Switch role to Evaluator or Department to decide." */
export function switchRoleMessage(op: Operation): string {
  return `Switch role to ${joinOr(OPERATION_ROLES[op])} to ${VERBS[op]}.`;
}

/** The role to suggest in a one-click "Switch to …" button. */
export function suggestedRole(op: Operation): DemoRole {
  return OPERATION_ROLES[op][0];
}
