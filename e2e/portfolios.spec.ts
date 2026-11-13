import { expect, test } from '@playwright/test';

test('administrator reviews portfolio inventory and linked applications from live API data', async ({ page }) => {
  const browserErrors: string[] = [];
  page.on('console', (message) => {
    if (message.type() === 'error') browserErrors.push(message.text());
  });
  page.on('pageerror', (error) => browserErrors.push(error.message));

  await page.goto('/login');
  await page.getByLabel('Email address').fill('admin@ketsip.local');
  await page.getByLabel('Password').fill('TestAdminPassword123!');
  const login = page.waitForResponse((response) => response.url().includes('/api/auth/login') && response.request().method() === 'POST');
  await page.getByRole('button', { name: 'Sign in' }).click();
  expect((await login).ok()).toBeTruthy();
  await page.goto('/profile');
  await page.getByLabel('Current password').fill('TestAdminPassword123!');
  await page.getByLabel('New password').fill('AdminChangedPassword456!');
  await page.getByRole('button', { name: 'Update password' }).click();
  await expect(page.getByText('Password changed successfully.', { exact: true })).toBeVisible();

  const listResponse = page.waitForResponse((response) => response.url().includes('/api/portfolios') && response.request().method() === 'GET' && !response.url().includes('/applications'));
  await page.goto('/portfolios');
  const portfolios = await listResponse;
  expect(portfolios.ok()).toBeTruthy();
  const listData = await portfolios.json() as { items: Array<{ id: string; name: string; applicationCount: number; qualityScore: number | null }> };
  expect(listData.items.some((item) => item.name === 'Payments' && item.applicationCount === 3 && item.qualityScore !== null)).toBeTruthy();
  await expect(page.getByRole('table', { name: /Portfolio inventory/ })).toContainText('Payments');
  await expect(page.getByRole('table')).toContainText('Applications count');

  const detailId = listData.items.find((item) => item.name === 'Payments')?.id;
  expect(detailId).toBeTruthy();
  const detailResponse = page.waitForResponse((response) => response.url().includes(`/api/portfolios/${detailId}`) && !response.url().includes('/applications'));
  const appsResponse = page.waitForResponse((response) => response.url().includes(`/api/portfolios/${detailId}/applications`));
  await page.goto(`/portfolios/${detailId}`);
  expect((await detailResponse).ok()).toBeTruthy();
  expect((await appsResponse).ok()).toBeTruthy();
  const linked = await appsResponse.json() as { items: Array<{ name: string }> };
  expect(linked.items.some((item) => item.name === 'Payment Gateway')).toBeTruthy();
  await expect(page.getByRole('heading', { name: 'Payments' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Payment Gateway' })).toHaveAttribute('href', /\/applications\//);
  expect(browserErrors).toEqual([]);
});
