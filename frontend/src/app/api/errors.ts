import { HttpErrorResponse } from '@angular/common/http';
import { Operation, switchRoleMessage } from './permissions';

/**
 * Turns an HTTP failure into a sentence a demo audience can read.
 * Pass the operation so 401/403 can say which role to switch to.
 */
export function describeError(err: unknown, role?: string, op?: Operation): string {
  if (err instanceof HttpErrorResponse) {
    const detail = typeof err.error === 'object' && typeof err.error?.detail === 'string' ? err.error.detail : '';
    if (err.status === 502 && detail) return detail;   // API-reported upstream failure, e.g. storing an upload
    if (err.status === 0 || err.status === 502 || err.status === 503 || err.status === 504) {
      return 'The TransferIQ API is not reachable. Start the backend on http://localhost:8000 and try again.';
    }
    if (err.status === 401) {
      return detail.startsWith('Sign in') || detail.startsWith('Invalid or expired') || detail.includes('session has expired')
        ? 'You are not signed in or your session has expired. Sign in again.'
        : 'No valid demo role was sent. Pick a role in the top bar (Demo role) and try again.';
    }
    if (err.status === 403 && (detail.includes('not assigned to your account') || detail.includes('no TransferIQ role'))) {
      return detail;
    }
    if (err.status === 403) {
      const who = role ? `The ${role} role can't do this. ` : '';
      return op ? `${who}${switchRoleMessage(op)}` : `${who}Switch role in the top bar.`;
    }
    if (err.status === 404) return 'Not found. The record may not exist.';
    if (err.status === 409 && detail) return detail;   // e.g. "A syllabus for X has already been uploaded…"
    if (err.status === 422) {
      const detail = typeof err.error === 'object' && err.error?.detail ? ` ${stringifyDetail(err.error.detail)}` : '';
      return `The request was rejected.${detail}`;
    }
    return `The API returned an error (${err.status} ${err.statusText || ''}).`.replace(' )', ')');
  }
  return 'Something went wrong. Please try again.';
}

function stringifyDetail(detail: unknown): string {
  if (typeof detail === 'string') return detail;
  try {
    return JSON.stringify(detail);
  } catch {
    return '';
  }
}
