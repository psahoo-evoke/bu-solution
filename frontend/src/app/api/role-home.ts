import { DEFAULT_STUDENT } from '../app.routes';
import { DemoRole } from './models';

/** Where each role starts after signing in or choosing a view on the home page. A signed-in student goes to
 * their own record (`studentId`); in demo mode the default sample student is used. */
export function homeRoute(role: DemoRole, studentId?: string | null): string {
  switch (role) {
    case 'Department':
    case 'Evaluator':
    case 'CreditStaff':
      return '/review';
    case 'Registrar':
      return '/registrar';
    case 'Advisor':
      return '/advisor';
    case 'FinancialAid':
      return '/financial-aid';
    case 'Student':
    default:
      return `/student/${studentId || DEFAULT_STUDENT}`;
  }
}

/** Signed in as one of these roles, the user has no Home: the top bar hides it, the logo and "/" lead to their own
 * page instead (homeRoute). Staff keep Home; demo mode and signed-out visitors need it to choose a view. */
export function homeHidden(role: DemoRole, signedIn: boolean): boolean {
  return signedIn && (role === 'Student' || role === 'Department');
}

/** Human labels for roles (CreditStaff reads better with a space). */
export const ROLE_LABELS: Record<DemoRole, string> = {
  Student: 'Student',
  CreditStaff: 'Credit staff',
  Evaluator: 'Evaluator',
  Department: 'Department',
  Registrar: 'Registrar',
  Advisor: 'Advisor',
  FinancialAid: 'Financial aid',
};
