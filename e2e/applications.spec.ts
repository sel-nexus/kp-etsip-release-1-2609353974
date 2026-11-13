import { expect, test } from '@playwright/test';

test('administrator lists, inspects, creates, and edits an application using live API data', async ({ page }) => {
  const browserErrors: string[] = [];
  page.on('console', (message) => { if (message.type() === 'error') browserErrors.push(message.text()); });
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

  const listResponse = page.waitForResponse((response) => response.url().includes('/api/applications') && response.request().method() === 'GET' && !response.url().includes('/api/applications/'));
  await page.goto('/applications');
  const listed = await listResponse;
  expect(listed.ok()).toBeTruthy();
  const listData = await listed.json() as { items: Array<{ id: string; name: string; criticality: string; tier: number; lifecycleStatus: string; applicationHealthScore: number; automationCoverage: number; openCriticalDefects: number; riskLevel: string }> };
  const seed = listData.items.find((item) => item.name === 'Payment Gateway');
  expect(seed).toBeTruthy();
  expect(seed).toMatchObject({ criticality: 'Critical', tier: 1, lifecycleStatus: 'Active', riskLevel: 'Medium' });
  await expect(page.getByRole('table', { name: /Application inventory/ })).toContainText('Payment Gateway');
  await expect(page.getByRole('table')).toContainText('Open Critical Defects');

  const detailResponse = page.waitForResponse((response) => response.url().includes(`/api/applications/${seed?.id}`) && response.request().method() === 'GET');
  await page.getByRole('link', { name: 'Payment Gateway' }).click();
  const detail = await detailResponse;
  expect(detail.ok()).toBeTruthy();
  const details = await detail.json() as { businessOwner: string; technologyStack: string; portfolio: { name: string } };
  expect(details.businessOwner).toBe('Digital Payments');
  expect(details.technologyStack).toContain('MongoDB');
  expect(details.portfolio.name).toBe('Payments');
  await expect(page.getByRole('heading', { name: 'Payment Gateway' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Payments' })).toHaveAttribute('href', /\/portfolios\//);

  await page.goto('/applications/new');
  await page.getByLabel('Name').fill('E2E Application Record');
  await page.getByLabel('Description').fill('Created in the live application flow.');
  await page.getByLabel('Portfolio').selectOption({ label: 'Payments' });
  await page.getByLabel('Product area').fill('Payments');
  await page.getByLabel('Business owner').fill('E2E business team');
  await page.getByLabel('Technology owner').fill('E2E engineering');
  await page.getByLabel('ETS owner').fill('Quality office');
  await page.getByLabel('Technology stack').fill('TypeScript; MongoDB');
  const createdResponse = page.waitForResponse((response) => response.url().endsWith('/api/applications') && response.request().method() === 'POST');
  await page.getByRole('button', { name: 'Create application' }).click();
  const created = await createdResponse;
  expect(created.status()).toBe(201);
  const createdData = await created.json() as { id: string; name: string };
  expect(createdData.name).toBe('E2E Application Record');
  await expect(page.getByRole('heading', { name: 'E2E Application Record' })).toBeVisible();

  await page.getByRole('link', { name: 'Edit application' }).click();
  await page.getByLabel('Name').fill('E2E Application Edited');
  const updateResponse = page.waitForResponse((response) => response.url().includes(`/api/applications/${createdData.id}`) && response.request().method() === 'PUT');
  await page.getByRole('button', { name: 'Save application' }).click();
  expect((await updateResponse).ok()).toBeTruthy();
  await expect(page.getByRole('heading', { name: 'E2E Application Edited' })).toBeVisible();
  expect(browserErrors).toEqual([]);
});

test('engineer cannot delete an application through direct HTTP request', async ({ page, request }) => {
  await page.goto('/login');
  await page.getByLabel('Email address').fill('engineer@ketsip.local');
  await page.getByLabel('Password').fill('KetsipDemo2025!');
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page).toHaveURL(/applications|dashboard/);
  const token = await page.evaluate(() => sessionStorage.getItem('ketsip.auth.token'));
  expect(token).toBeTruthy();
  const list = await request.get('/api/applications', { headers: { Authorization: `Bearer ${token}` } });
  expect(list.ok()).toBeTruthy();
  const data = await list.json() as { items: Array<{ id: string }> };
  const denied = await request.delete(`/api/applications/${data.items[0].id}`, { headers: { Authorization: `Bearer ${token}` } });
  expect(denied.status()).toBe(403);
});
