import { expect, test } from '@playwright/test';

test('executive reviews real dashboard metrics and shares filtered comparisons', async ({ page }) => {
  const browserErrors: string[] = [];
  page.on('console', (message) => { if (message.type() === 'error') browserErrors.push(message.text()); });
  page.on('pageerror', (error) => browserErrors.push(error.message));

  await page.goto('/login');
  await page.getByLabel('Email address').fill('executive@ketsip.local');
  await page.getByLabel('Password').fill('KetsipDemo2025!');
  const loginResponse = page.waitForResponse((response) => response.url().includes('/api/auth/login') && response.request().method() === 'POST');
  await page.getByRole('button', { name: 'Sign in' }).click();
  expect((await loginResponse).ok()).toBeTruthy();

  const dashboardResponse = page.waitForResponse((response) => response.url().includes('/api/dashboard/executive') && response.request().method() === 'GET');
  await page.goto('/dashboard');
  const response = await dashboardResponse;
  expect(response.ok()).toBeTruthy();
  const metrics = await response.json() as {
    enterpriseQuality: number | null;
    averageHealth: number | null;
    automationMaturity: number | null;
    openCriticalDefects: number;
    applicationsAtRisk: number;
    totalApplications: number;
    totalPortfolios: number;
    portfolios: Array<{ id: string; name: string; qualityScore: number | null; highRiskApplications: number }>;
  };
  expect(metrics).toMatchObject({
    enterpriseQuality: 81,
    averageHealth: 84,
    automationMaturity: 75,
    openCriticalDefects: 11,
    applicationsAtRisk: 3,
    totalApplications: 10,
    totalPortfolios: 3,
  });
  await expect(page.getByText('Enterprise quality')).toBeVisible();
  await expect(page.getByText('81 / 100')).toBeVisible();
  await expect(page.getByText('Critical defects')).toBeVisible();
  await expect(page.getByRole('list', { name: 'Portfolio comparisons' })).toContainText('Payments');

  const filteredResponse = page.waitForResponse((filtered) => filtered.url().includes('/api/dashboard/executive') && filtered.url().includes('riskLevel=High'));
  await page.getByLabel('Risk level').selectOption('High');
  await expect(page).toHaveURL(/riskLevel=High/);
  const filtered = await filteredResponse;
  expect(filtered.ok()).toBeTruthy();
  const highRiskMetrics = await filtered.json() as { totalApplications: number; applicationsAtRisk: number; totalPortfolios: number };
  expect(highRiskMetrics).toMatchObject({ totalApplications: 3, applicationsAtRisk: 3, totalPortfolios: 3 });
  expect(browserErrors).toEqual([]);
});

test('portfolio leader sees only assigned dashboard data and cannot query outside scope', async ({ page, request }) => {
  await page.goto('/login');
  await page.getByLabel('Email address').fill('portfolio.leader@ketsip.local');
  await page.getByLabel('Password').fill('KetsipDemo2025!');
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page).toHaveURL(/dashboard|applications/);
  const token = await page.evaluate(() => sessionStorage.getItem('ketsip.auth.token'));
  expect(token).toBeTruthy();

  const result = await request.get('/api/dashboard/executive', { headers: { Authorization: `Bearer ${token}` } });
  expect(result.ok()).toBeTruthy();
  const scoped = await result.json() as { totalPortfolios: number; totalApplications: number; portfolios: Array<{ name: string }> };
  expect(scoped.totalPortfolios).toBe(1);
  expect(scoped.totalApplications).toBe(3);
  expect(scoped.portfolios.map((portfolio) => portfolio.name)).toEqual(['Payments']);

  const outsider = await request.get('/api/portfolios', { headers: { Authorization: `Bearer ${token}` } });
  expect(outsider.ok()).toBeTruthy();
  const portfolios = await outsider.json() as { items: Array<{ id: string }> };
  const hidden = await request.get('/api/dashboard/executive?portfolioId=000000000000000000000000', { headers: { Authorization: `Bearer ${token}` } });
  expect(hidden.status()).toBe(404);
  expect(portfolios.items).toHaveLength(1);
});
