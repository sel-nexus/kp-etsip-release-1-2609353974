import { expect, test } from '@playwright/test';

test('executive reviews real dashboard metrics and shares filtered comparisons', async ({ page }, testInfo) => {
  const browserErrors: string[] = [];
  page.on('console', (message) => { if (message.type() === 'error') browserErrors.push(message.text()); });
  page.on('pageerror', (error) => browserErrors.push(error.message));

  await page.goto('/login');
  await page.getByLabel('Email address').fill('executive@ketsip.local');
  await page.getByLabel('Password').fill('KetsipDemo2025!');
  const loginResponse = page.waitForResponse((response) => response.url().includes('/api/auth/login') && response.request().method() === 'POST');
  await page.getByRole('button', { name: 'Sign in' }).click();
  expect((await loginResponse).ok()).toBeTruthy();

  await page.getByRole('link', { name: 'Applications' }).click();
  const dashboardResponse = page.waitForResponse((response) => response.url().includes('/api/dashboard/executive') && response.request().method() === 'GET');
  await page.getByRole('link', { name: 'Dashboard' }).click();
  const response = await dashboardResponse;
  expect(response.ok()).toBeTruthy();
  const metrics = await response.json() as {
    enterpriseQualityScore: number | null;
    averageApplicationHealthScore: number | null;
    automationMaturityScore: number | null;
    openCriticalDefects: number;
    applicationsAtRisk: number;
    totalApplications: number;
    totalPortfolios: number;
    portfolioQualityScores: Array<{ portfolioId: string; portfolioName: string; qualityScore: number | null; highRiskApplicationCount: number }>;
  };
  expect(metrics).toMatchObject({
    enterpriseQualityScore: 81,
    averageApplicationHealthScore: 84,
    automationMaturityScore: 75,
    openCriticalDefects: 11,
    applicationsAtRisk: 3,
    totalApplications: 10,
    totalPortfolios: 3,
  });
  await expect(page.getByText('Enterprise quality')).toBeVisible();
  await expect(page.getByText('81 / 100')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Critical defects', exact: true })).toBeVisible();
  await expect(page.getByRole('list', { name: 'Portfolio comparisons' })).toContainText('Payments');

  const filteredResponse = page.waitForResponse((filtered) => filtered.url().includes('/api/dashboard/executive') && filtered.url().includes('riskLevel=High'));
  await page.getByLabel('Risk level').selectOption('High');
  await expect(page).toHaveURL(/riskLevel=High/);
  const filtered = await filteredResponse;
  expect(filtered.ok()).toBeTruthy();
  const highRiskMetrics = await filtered.json() as { totalApplications: number; applicationsAtRisk: number; totalPortfolios: number };
  expect(highRiskMetrics).toMatchObject({ totalApplications: 3, applicationsAtRisk: 3, totalPortfolios: 3 });

  const emptyArea = `No such product area ${Date.now()}`;
  await page.getByLabel('Product area').fill(emptyArea);
  const emptyResponsePromise = page.waitForResponse((candidate) => {
    const url = new URL(candidate.url());
    return url.pathname === '/api/dashboard/executive' && url.searchParams.get('productArea') === emptyArea;
  });
  await page.getByRole('button', { name: 'Apply filters' }).click();
  const emptyResponse = await emptyResponsePromise;
  expect(emptyResponse.ok()).toBeTruthy();
  expect((await emptyResponse.json() as { totalApplications: number }).totalApplications).toBe(0);
  await expect(page.getByText(/no applications|no matching|no results/i)).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath('dashboard-empty-state.png'), fullPage: true });
  expect(browserErrors).toEqual([]);
});

test('portfolio leader sees only assigned dashboard data and cannot query outside scope', async ({ page, request }) => {
  const browserErrors: string[] = [];
  page.on('console', (message) => { if (message.type() === 'error') browserErrors.push(message.text()); });
  page.on('pageerror', (error) => browserErrors.push(error.message));
  await page.goto('/login');
  await page.getByLabel('Email address').fill('portfolio.leader@ketsip.local');
  await page.getByLabel('Password').fill('KetsipDemo2025!');
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page).toHaveURL(/dashboard|applications/);
  const token = await page.evaluate(() => sessionStorage.getItem('ketsip.auth.token'));
  expect(token).toBeTruthy();

  const result = await request.get('/api/dashboard/executive', { headers: { Authorization: `Bearer ${token}` } });
  expect(result.ok()).toBeTruthy();
  const scoped = await result.json() as { totalPortfolios: number; totalApplications: number; portfolioQualityScores: Array<{ portfolioName: string }> };
  expect(scoped.totalPortfolios).toBe(1);
  expect(scoped.totalApplications).toBe(3);
  expect(scoped.portfolioQualityScores.map((portfolio) => portfolio.portfolioName)).toEqual(['Payments']);

  const outsider = await request.get('/api/portfolios', { headers: { Authorization: `Bearer ${token}` } });
  expect(outsider.ok()).toBeTruthy();
  const portfolios = await outsider.json() as { items: Array<{ id: string }> };
  const hidden = await request.get('/api/dashboard/executive?portfolioId=000000000000000000000000', { headers: { Authorization: `Bearer ${token}` } });
  expect(hidden.status()).toBe(404);
  expect(portfolios.items).toHaveLength(1);
  expect(browserErrors).toEqual([]);
});

test('mobile menu opens and navigates through live pages while dashboard loading is visible', async ({ page }, testInfo) => {
  const browserErrors: string[] = [];
  page.on('console', (message) => { if (message.type() === 'error') browserErrors.push(message.text()); });
  page.on('pageerror', (error) => browserErrors.push(error.message));
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/login');
  await page.getByLabel('Email address').fill('executive@ketsip.local');
  await page.getByLabel('Password').fill('KetsipDemo2025!');
  const loginResponse = page.waitForResponse((response) => response.url().includes('/api/auth/login') && response.request().method() === 'POST');
  await page.getByRole('button', { name: 'Sign in' }).click();
  expect((await loginResponse).ok()).toBeTruthy();

  await page.getByRole('button', { name: 'Open navigation menu' }).click();
  await expect(page.getByRole('navigation', { name: 'Mobile navigation' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Profile' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Sign out' })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath('mobile-navigation-open.png'), fullPage: true });

  const initialPortfolioResponse = page.waitForResponse((response) => response.url().includes('/api/portfolios') && response.request().method() === 'GET');
  await page.getByRole('link', { name: 'Portfolios' }).click();
  expect((await initialPortfolioResponse).ok()).toBeTruthy();
  await expect(page.getByRole('table', { name: /Portfolio inventory/ })).toContainText('Payments');

  await page.getByRole('button', { name: 'Open navigation menu' }).click();
  await expect(page.getByRole('navigation', { name: 'Mobile navigation' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Dashboard' })).toBeVisible();

  let loadingObserved = false;
  let releaseDashboardResponse: (() => void) | undefined;
  let signalDashboardRequest: (() => void) | undefined;
  const dashboardResponseGate = new Promise<void>((resolve) => {
    releaseDashboardResponse = resolve;
  });
  const dashboardRequestStarted = new Promise<void>((resolve) => {
    signalDashboardRequest = resolve;
  });
  await page.route('**/api/dashboard/executive**', async (route) => {
    signalDashboardRequest?.();
    await dashboardResponseGate;
    await route.continue();
  });
  const dashboardResponse = page.waitForResponse((response) => response.url().includes('/api/dashboard/executive') && response.request().method() === 'GET');
  await page.getByRole('link', { name: 'Dashboard' }).click();
  await dashboardRequestStarted;
  try {
    await expect(page.getByRole('status')).toContainText(/loading/i);
    loadingObserved = true;
  } finally {
    releaseDashboardResponse?.();
  }
  expect((await dashboardResponse).ok()).toBeTruthy();
  expect(loadingObserved).toBeTruthy();
  await expect(page.getByText('Enterprise quality')).toBeVisible();

  await page.getByRole('button', { name: 'Open navigation menu' }).click();
  await expect(page.getByRole('navigation', { name: 'Mobile navigation' })).toBeVisible();
  await page.getByRole('button', { name: 'Sign out' }).click();
  await expect(page).toHaveURL(/\/login$/);
  expect(browserErrors).toEqual([]);
});
