import { HttpErrorResponse } from '@angular/common/http';
import { vi } from 'vitest';
import { describeError } from './errors';
import { can, switchRoleMessage } from './permissions';

describe('role matrix (openapi x-roles v0.3.0)', () => {
  it('lets the default Student role use the student page', () => {
    expect(can('Student', 'listStudents')).toBe(true);
    expect(can('Student', 'studentEvaluation')).toBe(true);
    expect(can('Student', 'uploadTranscript')).toBe(true);
  });

  it('keeps Student out of review data and decisions', () => {
    expect(can('Student', 'reviewQueue')).toBe(false);
    expect(can('Student', 'recommendation')).toBe(false);
    expect(can('Student', 'decide')).toBe(false);
  });

  it('matches the contract for decide, export and reset', () => {
    expect(['Evaluator', 'Department'].every((r) => can(r as never, 'decide'))).toBe(true);
    expect(can('CreditStaff', 'decide')).toBe(false);
    expect(can('Registrar', 'export') && can('CreditStaff', 'export')).toBe(true);
    expect(can('Evaluator', 'export')).toBe(false);
    expect(can('CreditStaff', 'reset') && can('Registrar', 'reset')).toBe(true);
    expect(can('Advisor', 'reset')).toBe(false);
    expect(can('Registrar', 'post') && can('CreditStaff', 'post')).toBe(true);
    expect(can('Evaluator', 'post') || can('Student', 'post')).toBe(false);
  });

  it('builds a clear switch-role message', () => {
    expect(switchRoleMessage('decide')).toBe('Switch role to Evaluator or Department to decide.');
  });

  it('turns 401 and 403 into role guidance, not a generic error', () => {
    const forbidden = new HttpErrorResponse({ status: 403, statusText: 'Forbidden' });
    expect(describeError(forbidden, 'Student', 'decide')).toBe(
      "The Student role can't do this. Switch role to Evaluator or Department to decide.",
    );
    const unauth = new HttpErrorResponse({ status: 401, statusText: 'Unauthorized' });
    expect(describeError(unauth, 'Student', 'decide')).toContain('Pick a role in the top bar');
  });

  it("shows the API's own reason for a 503 instead of 'start the backend on localhost'", () => {
    const busy = new HttpErrorResponse({ status: 503, error: { detail: 'The change could not be saved. Please try again.' } });
    expect(describeError(busy)).toBe('The change could not be saved. Please try again.');
    expect(describeError(busy)).not.toContain('localhost');
  });

  it('gives live users a plain message when the API does not answer, and developers the localhost hint', () => {
    const down = new HttpErrorResponse({ status: 0 });
    const original = location.hostname;
    expect(describeError(down)).toContain(original === 'localhost' ? 'localhost:8000' : 'not reachable right now');
    vi.stubGlobal('location', { hostname: 'bu-solutions.example.io' });
    try {
      expect(describeError(down)).toBe('TransferIQ is not reachable right now. Please try again in a moment.');
    } finally {
      vi.unstubAllGlobals();
    }
  });
});
