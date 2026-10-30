// TransferIQ browser driver. Needs the backend on :8000 and `ng serve` on :4200 (see SKILL.md).
// Uses Playwright from frontend/node_modules and the locally installed Chrome (no `playwright install`).
//
//   node .claude/skills/run-transferiq/driver.mjs tour                 # screenshot every page
//   node .claude/skills/run-transferiq/driver.mjs shot /review Evaluator
//   node .claude/skills/run-transferiq/driver.mjs decide PSYCH-UA 10   # evaluator approves a course
//   node .claude/skills/run-transferiq/driver.mjs reset                # reseed demo data via API
//
// Env: TIQ_URL (default http://localhost:4200), TIQ_SHOTS (default <unit>/.shots), TIQ_BROWSER (chrome|msedge|chromium).
import { createRequire } from 'node:module';
import { mkdirSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const unit = resolve(dirname(fileURLToPath(import.meta.url)), '../../..');
const { chromium } = createRequire(join(unit, 'frontend/package.json'))('@playwright/test');

const BASE = process.env.TIQ_URL ?? 'http://localhost:4200';
const SHOTS = process.env.TIQ_SHOTS ?? join(unit, '.shots');
const channel = process.env.TIQ_BROWSER ?? 'chrome';
mkdirSync(SHOTS, { recursive: true });

const browser = await chromium.launch(channel === 'chromium' ? {} : { channel });
const page = await browser.newPage({ viewport: { width: 1400, height: 900 } });
const errors = [];
page.on('console', (m) => m.type() === 'error' && errors.push(m.text()));
page.on('pageerror', (e) => errors.push(String(e)));

async function open(path, role) {
  await page.goto(BASE + path);
  if (role) await page.getByLabel('Demo role').selectOption(role);
  await page.waitForLoadState('networkidle');
}
async function shot(name) {
  const file = join(SHOTS, `${name}.png`);
  await page.screenshot({ path: file, fullPage: true });
  console.log('screenshot', file);
}

const [cmd = 'tour', ...args] = process.argv.slice(2);
try {
  if (cmd === 'tour') {
    await open('/student/SYN-24001', 'Student');
    await page.getByRole('heading', { name: 'Maya R. Delgado' }).waitFor();
    await shot('student');
    await open('/review', 'Evaluator');
    await page.getByRole('button', { name: /PSYCH-UA 10/ }).click();
    await page.getByRole('heading', { name: 'BU candidates' }).waitFor();
    await shot('review');
    await open('/evaluation');
    await page.getByRole('heading', { name: 'Top-1 candidate agreement' }).waitFor();
    await shot('evaluation');
    await open('/registrar', 'Registrar');
    await shot('registrar');
  } else if (cmd === 'shot') {
    const [path = '/', role] = args;
    await open(path, role);
    await shot(path.replace(/[^\w]+/g, '_').replace(/^_|_$/g, '') || 'root');
  } else if (cmd === 'decide') {
    const course = args.join(' ') || 'PSYCH-UA 10';
    await open('/review', 'Evaluator');
    await page.getByRole('button', { name: new RegExp(course.replace(/ /g, '\\s+') + '\\b') }).click();
    await page.getByLabel('Approve equivalent').check();
    await page.getByRole('button', { name: 'Approve equivalent' }).click();
    console.log(await page.getByRole('status').filter({ hasText: 'Saved.' }).innerText());
    await shot('decided');
  } else if (cmd === 'reset') {
    const r = await page.request.post(BASE + '/api/demo/reset', { headers: { 'X-Demo-Role': 'Registrar' } });
    console.log('reset', r.status());
  } else {
    throw new Error(`unknown command: ${cmd}`);
  }
} finally {
  if (errors.length) console.log('console errors:\n  ' + errors.join('\n  '));
  await browser.close();
}
process.exit(errors.length ? 1 : 0);
