import { defineConfig, devices } from '@playwright/test';

/**
 * E2E demo flow. Needs the backend on :8000 and `npm start` on :4200 (or set E2E_BASE_URL).
 * Run: npx playwright install chromium && npm run e2e
 */
export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  retries: 0,
  reporter: 'list',
  use: {
    baseURL: process.env['E2E_BASE_URL'] ?? 'http://localhost:4200',
    trace: 'retain-on-failure',
    // Optional: reuse a preinstalled Chromium instead of `playwright install`.
    launchOptions: process.env['CHROME_BIN'] ? { executablePath: process.env['CHROME_BIN'] } : {},
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
});
