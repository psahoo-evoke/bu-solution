import { DEFAULT_STUDENT } from '../app.routes';
import { DemoRole } from './models';

/** Where each role starts after signing in or choosing a view on the home page. */
export function homeRoute(role: DemoRole): string {
  switch (role) {
    case 'Department':
    case 'Evaluator':
    case 'CreditStaff':
      return '/review';
    case 'Registrar':
      return '/registrar';
    case 'Student':
    case 'Advisor':
    default:
      return `/student/${DEFAULT_STUDENT}`;
  }
}

/** Human labels for roles (CreditStaff reads better with a space). */
export const ROLE_LABELS: Record<DemoRole, string> = {
  Student: 'Student',
  CreditStaff: 'Credit staff',
  Evaluator: 'Evaluator',
  Department: 'Department',
  Registrar: 'Registrar',
  Advisor: 'Advisor',
};
