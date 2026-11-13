import { expect, test } from '@playwright/test';

test('first-run login presents accessible fields and handles a generic API failure', async ({ page }) => {
  const browserErrors: string[] = [];
  const expectedResourceErrors: string[] = [];
  const expectedResourceError = 'Failed to load resource: the server responded with a status of 500 (Internal Server Error)';
  page.on('console', (message) => {
    if (message.type() === 'error') {
      if (message.text() === expectedResourceError) expectedResourceErrors.push(message.text());
      else browserErrors.push(message.text());
    }
  });
  page.on('pageerror', (error) => browserErrors.push(error.message));

  const healthResponse = await page.request.get('/api/health');
  expect(healthResponse.ok()).toBeTruthy();
  await expect(healthResponse.json()).resolves.toEqual({ status: 'ok' });

  await page.route('**/api/auth/login', async (route) => {
    await route.fulfill({ status: 500, json: { error: { code: 'internal_error', message: 'Internal server error.' } } });
  });
  await page.goto('/login');
  await expect(page.getByRole('heading', { name: 'Sign in to KP ETSIP' })).toBeVisible();
  await expect(page.getByLabel('Email address')).toBeVisible();
  await expect(page.getByLabel('Password')).toBeVisible();
  await page.getByLabel('Email address').fill('demo@example.com');
  await page.getByLabel('Password').fill('incorrect-password');
  const loginResponsePromise = page.waitForResponse((response) => response.url().includes('/api/auth/login') && response.request().method() === 'POST');
  await page.getByRole('button', { name: 'Sign in' }).click();
  const loginResponse = await loginResponsePromise;
  expect(loginResponse.status()).toBe(500);
  await expect(page.getByRole('alert')).toHaveText('Unable to sign in right now. Please try again.');
  expect(expectedResourceErrors).toEqual([expectedResourceError]);
  await expect(page).toHaveURL(/\/login$/);
  expect(browserErrors).toEqual([]);
});

test('a clean unauthenticated visit to a protected route redirects to login', async ({ page }) => {
  const browserErrors: string[] = [];
  page.on('console', (message) => {
    if (message.type() === 'error') browserErrors.push(message.text());
  });
  page.on('pageerror', (error) => browserErrors.push(error.message));

  await page.goto('/applications');
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByRole('heading', { name: 'Sign in to KP ETSIP' })).toBeVisible();
  expect(browserErrors).toEqual([]);
});
