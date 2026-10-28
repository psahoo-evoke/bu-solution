import { expect, test } from '@playwright/test';

/**
 * TransferIQ demo flow (EvoHack 2026, synthetic data only):
 *  1. Student (Maya, SYN-24001) sees secured vs pending units and per-course status.
 *  2. Evaluator opens a maybe course, sees top-3 candidates + timer, decides in under 2 minutes.
 *  3. Evaluation page shows the sponsor gates.
 *  4. Approved course shows as TP "Approved – awaiting posting" (pending) until the Registrar posts it, then T (secured).
 *  5. Registrar downloads the MyBU CSV, then resets the demo.
 * Requires the FastAPI backend on :8000 and the Angular dev server (proxy) on :4200.
 */

test.describe.configure({ mode: 'serial' });

test.beforeAll(async ({ request }) => {
  await request.post('/api/demo/reset', { headers: { 'X-Demo-Role': 'Registrar' } });
});

async function setRole(page: import('@playwright/test').Page, role: string) {
  await page.getByLabel('Demo role').selectOption(role);
}

test('student sees secured vs pending and every course status', async ({ page }) => {
  await page.goto('/');
  await expect(page).toHaveURL(/\/student\/SYN-24001$/);
  await setRole(page, 'Student');
  await expect(page.getByText('Synthetic data – EvoHack 2026')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Maya R. Delgado' })).toBeVisible();

  const totals = page.getByLabel('Credit totals');
  await expect(totals).toContainText('Secured');
  await expect(totals).toContainText('Pending');
  await expect(totals).toContainText('No credit');

  // Grouped by term, chip shows plain words + BU code
  await expect(page.getByRole('heading', { name: 'Fall 2024' })).toBeVisible();
  await expect(page.getByRole('row', { name: /PSYCH-UA 1\b.*CAS PS 101/ })).toContainText('T');
  // Quarter-system summer course converts to 2.67 elective units (US-02)
  await expect(page.getByRole('row', { name: /PSY 215/ })).toContainText('2.67');
  // Missing syllabus course offers an upload (US-03)
  await expect(page.getByLabel('Upload syllabus for PSYCH-UA 25')).toBeAttached();
});

test('a Student cannot open review data and is told which role to use', async ({ page }) => {
  await page.goto('/review');
  await setRole(page, 'Student');
  await expect(page.getByText('Switch role to CreditStaff, Evaluator or Department to open the review queue.')).toBeVisible();
  await expect(page.getByRole('list', { name: 'Courses awaiting a decision' })).toHaveCount(0);
});

test('evaluator decides a maybe course with the comparison already done', async ({ page }) => {
  await page.goto('/review');
  await setRole(page, 'Evaluator');
  await page.getByRole('button', { name: /PSYCH-UA 10/ }).click();

  await expect(page.getByRole('timer')).toContainText('under 2:00');
  await expect(page.getByRole('heading', { name: 'BU candidates' })).toBeVisible();
  await expect(page.getByRole('radiogroup', { name: 'BU candidate course' }).getByRole('radio')).toHaveCount(3);
  await expect(page.getByText('Covered').first()).toBeVisible();
  await expect(page.getByText('Missing').first()).toBeVisible();

  await page.getByLabel('Approve equivalent').check();
  await expect(page.getByLabel('Reusable – apply to the next student with this course')).toBeChecked();
  await page.getByRole('button', { name: 'Approve equivalent' }).click();
  await expect(page.getByRole('status').filter({ hasText: 'Saved.' })).toContainText('PSYCH-UA 10');
});

test('approved course stays pending (TP) until the Registrar posts it, then it is secured (T)', async ({ page }) => {
  const securedUnits = async () =>
    Number((await page.getByLabel('Credit totals').locator('.total--secured .total__value').innerText()).replace(/[^\d.]/g, ''));
  const row = () => page.getByRole('row', { name: /PSYCH-UA 10\b/ });

  // Student view right after the evaluator approved PSYCH-UA 10
  await page.goto('/student/SYN-24001');
  await setRole(page, 'Student');
  await expect(row()).toContainText('Approved – awaiting posting');
  await expect(row().locator('.chip__code')).toHaveText('TP');
  await expect(page.getByLabel('Credit totals')).toContainText('approved, awaiting posting');
  const before = await securedUnits();

  // Registrar posts Maya's approved courses
  await page.goto('/registrar');
  await setRole(page, 'Registrar');
  await page.getByLabel('Student').selectOption('SYN-24001');
  await page.getByRole('button', { name: 'Post approved courses' }).click();
  await expect(page.getByRole('heading', { name: /Posted just now: [1-9]/ })).toBeVisible();

  // Back on the student page: now secured
  await page.goto('/student/SYN-24001');
  await expect(row().locator('.chip__code')).toHaveText('T');
  await expect(row()).not.toContainText('awaiting posting');
  expect(await securedUnits()).toBeGreaterThan(before);
});

test('a course without a syllabus is preliminary and not decidable', async ({ page }) => {
  await page.goto('/review');
  await setRole(page, 'Evaluator');
  await page.getByRole('button', { name: /PSYCH-UA 25/ }).click();
  await expect(page.getByText('Preliminary – not decidable')).toBeVisible();
  await expect(page.getByRole('button', { name: /Approve equivalent|Approve as elective|Record no credit/ })).toBeDisabled();
});

test('evaluation page shows the sponsor gates', async ({ page }) => {
  await page.goto('/evaluation');
  await expect(page.getByRole('heading', { name: 'Top-1 candidate agreement' })).toBeVisible();
  await expect(page.getByText('Strict agreement')).toBeVisible();
  await expect(page.getByText('Deferrals to evaluator')).toBeVisible();
  await expect(page.getByText(/Strict counts a correct deferral to the evaluator/)).toBeVisible();
  await expect(page.getByText(/gate is at least 80%/)).toBeVisible();
  await expect(page.getByText(/gate is at most 2%/)).toBeVisible();
  await expect(page.getByRole('heading', { name: 'By tier' })).toBeVisible();
});

test('registrar downloads the MyBU CSV and resets the demo', async ({ page }) => {
  await page.goto('/registrar');
  await setRole(page, 'Registrar');
  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Download MyBU CSV' }).click();
  expect((await download).suggestedFilename()).toMatch(/^mybu_export.*\.csv$/);
  await expect(page.getByRole('heading', { name: /Preview/ })).toBeVisible();

  page.once('dialog', (d) => d.accept());
  await page.getByRole('button', { name: 'Reset demo data' }).click();
  await expect(page.getByText('Demo reset to the seeded synthetic state.')).toBeVisible();
});
