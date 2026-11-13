import { expect, test } from '@playwright/test';
import { loginAsAdmin } from './admin-login';

test('administrator reviews portfolio inventory and manages records through visible controls', async ({ page }) => {
  const browserErrors: string[] = [];
  page.on('console', (message) => {
    if (message.type() === 'error') browserErrors.push(message.text());
  });
  page.on('pageerror', (error) => browserErrors.push(error.message));

  await loginAsAdmin(page);

  const inventoryResponsePromise = page.waitForResponse((response) => response.url().includes('/api/portfolios') && response.request().method() === 'GET' && !response.url().includes('/applications'));
  await page.getByRole('link', { name: 'Portfolios' }).click();
  const inventoryResponse = await inventoryResponsePromise;
  expect(inventoryResponse.ok()).toBeTruthy();
  const inventory = await inventoryResponse.json() as { items: Array<{ id: string; name: string; applicationCount: number; qualityScore: number | null }> };
  expect(inventory.items.some((item) => item.name === 'Payments' && item.applicationCount === 3 && item.qualityScore !== null)).toBe(true);
  await expect(page.getByRole('table', { name: /Portfolio inventory/ })).toContainText('Payments');
  await expect(page.getByRole('table')).toContainText('Applications count');

  const seededPortfolioId = inventory.items.find((item) => item.name === 'Payments')?.id;
  expect(seededPortfolioId).toBeTruthy();
  const seededDetailPromise = page.waitForResponse((response) => response.url().includes(`/api/portfolios/${seededPortfolioId}`) && response.request().method() === 'GET' && !response.url().includes('/applications'));
  const linkedApplicationsPromise = page.waitForResponse((response) => response.url().includes(`/api/portfolios/${seededPortfolioId}/applications`));
  await page.getByRole('link', { name: 'Payments' }).click();
  expect((await seededDetailPromise).ok()).toBeTruthy();
  const linkedApplications = await linkedApplicationsPromise;
  expect(linkedApplications.ok()).toBeTruthy();
  const linked = await linkedApplications.json() as { items: Array<{ name: string }> };
  expect(linked.items.some((item) => item.name === 'Payment Gateway')).toBe(true);
  await expect(page.getByRole('heading', { name: 'Payments' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Payment Gateway' })).toHaveAttribute('href', /\/applications\//);

  const returnToListPromise = page.waitForResponse((response) => response.url().includes('/api/portfolios?') && response.request().method() === 'GET');
  await page.getByRole('link', { name: 'All portfolios' }).click();
  expect((await returnToListPromise).ok()).toBeTruthy();
  await page.getByRole('link', { name: 'Create portfolio' }).click();

  const portfolioName = `E2E Persistence ${Date.now()}`;
  const originalDescription = 'Created by the portfolio persistence end-to-end test.';
  await page.getByLabel('Name').fill(portfolioName);
  await page.getByLabel('Owner').fill('E2E Test Owner');
  await page.getByLabel('Description').fill(originalDescription);
  await page.getByLabel('Product area').fill('E2E Testing');
  await page.getByLabel('Status').selectOption('Active');
  const createResponsePromise = page.waitForResponse((response) => response.url().endsWith('/api/portfolios') && response.request().method() === 'POST');
  await page.getByRole('button', { name: 'Create portfolio' }).click();
  const createResponse = await createResponsePromise;
  expect(createResponse.status()).toBe(201);
  const created = await createResponse.json() as { id: string; name: string; description: string; owner: string; productArea: string; status: string; applicationCount: number };
  expect(created).toMatchObject({ name: portfolioName, description: originalDescription, owner: 'E2E Test Owner', productArea: 'E2E Testing', status: 'Active', applicationCount: 0 });
  expect(new URL(page.url()).pathname).toBe(`/portfolios/${created.id}`);
  await expect(page.getByRole('heading', { name: portfolioName })).toBeVisible();

  const listResponsePromise = page.waitForResponse((response) => {
    const responseUrl = new URL(response.url());
    return responseUrl.pathname === '/api/portfolios' && responseUrl.searchParams.get('search') === portfolioName && response.request().method() === 'GET';
  });
  await page.getByRole('link', { name: 'All portfolios' }).click();
  await page.getByLabel('Search portfolios').fill(portfolioName);
  await page.getByRole('button', { name: 'Apply filters' }).click();
  const listResponse = await listResponsePromise;
  expect(listResponse.ok()).toBeTruthy();
  const listData = await listResponse.json() as { items: Array<{ id: string; name: string }> };
  expect(listData.items.some((item) => item.id === created.id && item.name === portfolioName)).toBe(true);
  await expect(page.getByRole('link', { name: portfolioName, exact: true })).toBeVisible();

  const createdDetailPromise = page.waitForResponse((response) => response.url().includes(`/api/portfolios/${created.id}`) && response.request().method() === 'GET' && !response.url().includes('/applications'));
  await page.getByRole('link', { name: portfolioName, exact: true }).click();
  const createdDetail = await createdDetailPromise;
  expect(createdDetail.ok()).toBeTruthy();
  expect(await createdDetail.json()).toMatchObject({ id: created.id, name: portfolioName, description: originalDescription, applicationCount: 0 });

  await expect(page.getByRole('heading', { name: portfolioName })).toBeVisible();
  await page.reload();
  await expect(page.getByRole('heading', { name: portfolioName })).toBeVisible();
  const token = await page.evaluate(() => sessionStorage.getItem('ketsip.auth.token'));
  expect(token).toBeTruthy();
  const reloadedDetail = await page.request.get(`/api/portfolios/${created.id}`, { headers: { Authorization: `Bearer ${token}` } });
  expect(reloadedDetail.ok()).toBeTruthy();
  expect(await reloadedDetail.json()).toMatchObject({ id: created.id, name: portfolioName, description: originalDescription, applicationCount: 0 });
  await expect(page.getByText(originalDescription)).toBeVisible();

  const updatedName = `${portfolioName} Edited`;
  const updatedDescription = 'Updated by the portfolio mutation end-to-end test.';
  await page.getByRole('link', { name: 'Edit portfolio' }).click();
  await page.getByLabel('Name').fill(updatedName);
  await page.getByLabel('Description').fill(updatedDescription);
  await page.getByLabel('Owner').fill('E2E Updated Owner');
  await page.getByLabel('Product area').fill('E2E Mutation');
  await page.getByLabel('Status').selectOption('Archived');
  const updateResponsePromise = page.waitForResponse((response) => response.url().includes(`/api/portfolios/${created.id}`) && response.request().method() === 'PUT');
  await page.getByRole('button', { name: 'Save portfolio' }).click();
  const updateResponse = await updateResponsePromise;
  expect(updateResponse.status()).toBe(200);
  expect(await updateResponse.json()).toMatchObject({
    id: created.id, name: updatedName, description: updatedDescription, owner: 'E2E Updated Owner',
    productArea: 'E2E Mutation', status: 'Archived', applicationCount: 0,
  });

  await expect(page.getByRole('heading', { name: updatedName })).toBeVisible();
  await page.reload();
  await expect(page.getByRole('heading', { name: updatedName })).toBeVisible();
  const editedDetail = await page.request.get(`/api/portfolios/${created.id}`, { headers: { Authorization: `Bearer ${token}` } });
  expect(editedDetail.ok()).toBeTruthy();
  expect(await editedDetail.json()).toMatchObject({
    id: created.id, name: updatedName, description: updatedDescription, owner: 'E2E Updated Owner',
    productArea: 'E2E Mutation', status: 'Archived', applicationCount: 0,
  });
  await expect(page.getByRole('heading', { name: updatedName })).toBeVisible();
  await expect(page.getByText(updatedDescription)).toBeVisible();

  await page.getByRole('button', { name: 'Delete portfolio' }).click();
  await expect(page.getByRole('group', { name: 'Delete portfolio?' })).toBeVisible();
  const deleteResponsePromise = page.waitForResponse((response) => response.url().includes(`/api/portfolios/${created.id}`) && response.request().method() === 'DELETE');
  const postDeleteListPromise = page.waitForResponse((response) => response.url().includes('/api/portfolios?') && response.request().method() === 'GET');
  await page.getByRole('button', { name: 'Confirm delete' }).click();
  const deleteResponse = await deleteResponsePromise;
  expect(deleteResponse.status()).toBe(204);

  await expect(page.getByText('Portfolio deleted successfully.')).toBeVisible();
  expect((await postDeleteListPromise).ok()).toBeTruthy();
  await page.getByLabel('Search portfolios').fill(updatedName);
  const deletedListPromise = page.waitForResponse((response) => {
    const responseUrl = new URL(response.url());
    return responseUrl.pathname === '/api/portfolios' && responseUrl.searchParams.get('search') === updatedName && response.request().method() === 'GET';
  });
  await page.getByRole('button', { name: 'Apply filters' }).click();
  const deletedList = await deletedListPromise;
  expect(deletedList.ok()).toBeTruthy();
  const deletedData = await deletedList.json() as { items: Array<{ id: string; name: string }> };
  expect(deletedData.items.some((item) => item.id === created.id)).toBe(false);
  await expect(page.getByText('No portfolios match these filters.')).toBeVisible();
  expect(browserErrors).toEqual([]);
});
