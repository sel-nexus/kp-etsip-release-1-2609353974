import { expect, test } from '@playwright/test';
import { loginAsAdmin } from './admin-login';

test('administrator lists, inspects, creates, and edits an application using live API data', async ({ page, request }) => {
  const browserErrors: string[] = [];
  page.on('console', (message) => { if (message.type() === 'error') browserErrors.push(message.text()); });
  page.on('pageerror', (error) => browserErrors.push(error.message));
  const createdApplicationName = `E2E Application Record ${Date.now()}`;
  const editedApplicationName = `${createdApplicationName} Edited`;
  let adminToken: string | null = null;
  let createdApplicationId: string | undefined;

  try {
    await loginAsAdmin(page);
    adminToken = await page.evaluate(() => sessionStorage.getItem('ketsip.auth.token'));
    expect(adminToken).toBeTruthy();

    const isApplicationsListResponse = (response: import('@playwright/test').Response) => {
      const resourceType = response.request().resourceType();
      return new URL(response.url()).pathname === '/api/applications'
        && response.request().method() === 'GET'
        && (resourceType === 'fetch' || resourceType === 'xhr');
    };
    const listResponse = page.waitForResponse(isApplicationsListResponse);
    await page.getByRole('link', { name: 'Applications', exact: true }).click();
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

    await page.getByRole('link', { name: 'Applications', exact: true }).click();
    await page.locator('a[href="/applications/new"]').click();
    await page.getByLabel('Name').fill(createdApplicationName);
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
    createdApplicationId = createdData.id;
    expect(createdData.name).toBe(createdApplicationName);
    await expect(page.getByRole('heading', { name: createdApplicationName })).toBeVisible();

    await page.getByRole('link', { name: 'Edit application' }).click();
    await expect(page).toHaveURL(new RegExp(`/applications/${createdData.id}/edit$`));
    await page.getByLabel('Name').fill(editedApplicationName);
    const updateResponse = page.waitForResponse((response) => response.url().includes(`/api/applications/${createdData.id}`) && response.request().method() === 'PUT');
    await page.getByRole('button', { name: 'Save application' }).click();
    expect((await updateResponse).ok()).toBeTruthy();
    await expect(page.getByRole('heading', { name: editedApplicationName })).toBeVisible();

    const savedListResponse = page.waitForResponse(isApplicationsListResponse);
    await page.getByRole('link', { name: 'Applications', exact: true }).click();
    const savedList = await savedListResponse;
    expect(savedList.ok()).toBeTruthy();
    const savedListData = await savedList.json() as { items: Array<{ id: string; name: string }> };
    expect(savedListData.items).toContainEqual(expect.objectContaining({ id: createdData.id, name: editedApplicationName }));

    const persistedListResponse = page.waitForResponse(isApplicationsListResponse);
    await page.reload();
    const persistedList = await persistedListResponse;
    expect(persistedList.ok()).toBeTruthy();
    const persistedListData = await persistedList.json() as { items: Array<{ id: string; name: string }> };
    expect(persistedListData.items).toContainEqual(expect.objectContaining({ id: createdData.id, name: editedApplicationName }));
    await expect(page.getByRole('table', { name: /Application inventory/ })).toContainText(editedApplicationName);
    expect(browserErrors).toEqual([]);
  } finally {
    if (createdApplicationId && adminToken) {
      const cleanup = await request.delete(`/api/applications/${createdApplicationId}`, {
        headers: { Authorization: `Bearer ${adminToken}` },
      });
      expect(cleanup.ok(), `Expected cleanup of application ${createdApplicationId} to succeed; received ${cleanup.status()}`).toBeTruthy();
    }
  }
});

test('engineer cannot delete an application through direct HTTP request', async ({ page, request }) => {
  const browserErrors: string[] = [];
  page.on('console', (message) => { if (message.type() === 'error') browserErrors.push(message.text()); });
  page.on('pageerror', (error) => browserErrors.push(error.message));
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
  expect(browserErrors).toEqual([]);
});
