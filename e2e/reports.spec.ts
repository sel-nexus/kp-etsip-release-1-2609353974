import { expect, test } from '@playwright/test';

type ReportPage<T> = { items: T[]; page: number; pageSize: number; total: number };

async function signIn(page: import('@playwright/test').Page, email: string, password = 'KetsipDemo2025!'): Promise<string> {
  if (page.url() === 'about:blank') await page.goto('/login');
  await page.getByLabel('Email address').fill(email);
  await page.getByLabel('Password').fill(password);
  const loginResponse = page.waitForResponse((response) => response.url().includes('/api/auth/login') && response.request().method() === 'POST');
  await page.getByRole('button', { name: 'Sign in' }).click();
  expect((await loginResponse).ok()).toBeTruthy();
  const token = await page.evaluate(() => sessionStorage.getItem('ketsip.auth.token'));
  expect(token).toBeTruthy();
  return token as string;
}

test('executive sees bounded Mongo reports and downloads complete CSV; read-only cannot export', async ({ page }) => {
  const browserErrors: string[] = [];
  page.on('console', (message) => { if (message.type() === 'error') browserErrors.push(message.text()); });
  page.on('pageerror', (error) => browserErrors.push(error.message));

  const executiveToken = await signIn(page, 'executive@ketsip.local');
  const executiveHeaders = { Authorization: `Bearer ${executiveToken}` };
  const [applicationPageResponse, portfolioPageResponse] = await Promise.all([
    page.request.get('/api/reports/applications?search=Payment%20Gateway&page=1&pageSize=2', { headers: executiveHeaders }),
    page.request.get('/api/reports/portfolios?search=Payments&page=1&pageSize=2', { headers: executiveHeaders }),
  ]);
  expect(applicationPageResponse.ok()).toBeTruthy();
  expect(portfolioPageResponse.ok()).toBeTruthy();
  const applicationPage = await applicationPageResponse.json() as ReportPage<{ name: string; portfolioName: string }>;
  const portfolioPage = await portfolioPageResponse.json() as ReportPage<{ name: string; applicationCount: number }>;
  expect(applicationPage.items).toHaveLength(1);
  expect(applicationPage.items[0]).toMatchObject({ name: 'Payment Gateway', portfolioName: 'Payments' });
  expect(applicationPage.pageSize).toBe(2);
  expect(portfolioPage.items).toHaveLength(1);
  expect(portfolioPage.items[0]).toMatchObject({ name: 'Payments', applicationCount: 3 });
  expect(portfolioPage.pageSize).toBe(2);

  const reportsResponse = page.waitForResponse((response) => response.url().includes('/api/reports/applications') && response.request().method() === 'GET');
  const portfolioReportsResponse = page.waitForResponse((response) => response.url().includes('/api/reports/portfolios') && response.request().method() === 'GET');
  await page.getByRole('link', { name: 'Reports' }).click();
  expect((await reportsResponse).ok()).toBeTruthy();
  expect((await portfolioReportsResponse).ok()).toBeTruthy();
  await expect(page.getByRole('heading', { name: /reports/i })).toBeVisible();
  await expect(page.getByRole('table').first()).toContainText('Payment Gateway');
  await expect(page.getByRole('table').nth(1)).toContainText('Payments');

  const [applicationsCsv, portfoliosCsv] = await Promise.all([
    page.request.get('/api/reports/applications?format=csv&search=Payment%20Gateway', { headers: executiveHeaders }),
    page.request.get('/api/reports/portfolios?format=csv&search=Payments', { headers: executiveHeaders }),
  ]);
  expect(applicationsCsv.ok()).toBeTruthy();
  expect(portfoliosCsv.ok()).toBeTruthy();
  expect(applicationsCsv.headers()['content-type']).toContain('text/csv');
  expect(applicationsCsv.headers()['content-disposition']).toContain('applications.csv');
  expect(await applicationsCsv.text()).toContain('Payment Gateway');
  expect(await portfoliosCsv.text()).toContain('Payments');

  await page.getByRole('button', { name: 'Sign out' }).click();
  const readOnlyToken = await signIn(page, 'readonly@ketsip.local');
  await expect(page.getByRole('link', { name: 'Reports' })).toHaveCount(0);
  for (const path of ['/api/reports/applications?format=csv', '/api/reports/portfolios?format=csv']) {
    const denied = await page.request.get(path, { headers: { Authorization: `Bearer ${readOnlyToken}` } });
    expect(denied.status()).toBe(403);
  }
  expect(browserErrors).toEqual([]);
});

test('auditor downloads audit CSV from history and the successful export is persisted', async ({ page }) => {
  const browserErrors: string[] = [];
  page.on('console', (message) => { if (message.type() === 'error') browserErrors.push(message.text()); });
  page.on('pageerror', (error) => browserErrors.push(error.message));

  const token = await signIn(page, 'auditor@ketsip.local');
  const headers = { Authorization: `Bearer ${token}` };
  const history = await page.request.get('/api/audit-logs?action=login&page=1&pageSize=10', { headers });
  expect(history.ok()).toBeTruthy();
  const before = await history.json() as ReportPage<{ action: string }>;
  expect(before.items.some((entry) => entry.action === 'login')).toBeTruthy();
  const oldExports = await page.request.get('/api/audit-logs?action=export&page=1&pageSize=100', { headers });
  expect(oldExports.ok()).toBeTruthy();
  const oldExportRows = await oldExports.json() as ReportPage<{ entityType: string; details: string }>;
  const previousAuditExports = oldExportRows.items.filter((entry) => entry.entityType === 'audit' && entry.details === 'CSV export: audit history').length;

  const auditPageResponse = page.waitForResponse((response) => response.url().includes('/api/audit-logs') && response.request().method() === 'GET');
  await page.getByRole('link', { name: 'Audit history' }).click();
  expect((await auditPageResponse).ok()).toBeTruthy();
  await expect(page.getByRole('heading', { name: 'Audit history' })).toBeVisible();
  await expect(page.getByText(/Local account authentication/).first()).toBeVisible();
  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Export audit CSV' }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe('audit-logs.csv');

  const exportsResponse = await page.request.get('/api/audit-logs?action=export&page=1&pageSize=100', { headers });
  expect(exportsResponse.ok()).toBeTruthy();
  const exports = await exportsResponse.json() as ReportPage<{ entityType: string; details: string }>;
  const auditExports = exports.items.filter((entry) => entry.entityType === 'audit' && entry.details === 'CSV export: audit history');
  expect(auditExports).toHaveLength(previousAuditExports + 1);
  expect(browserErrors).toEqual([]);
});
