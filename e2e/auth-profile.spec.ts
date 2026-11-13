import { expect, test } from '@playwright/test';

test('seeded executive signs in and sees backend-backed current profile', async ({ page }) => {
  const browserErrors: string[] = [];
  page.on('console', (message) => {
    if (message.type() === 'error') browserErrors.push(message.text());
  });
  page.on('pageerror', (error) => browserErrors.push(error.message));

  await page.goto('/login');
  await page.getByLabel('Email address').fill('executive@ketsip.local');
  await page.getByLabel('Password').fill('KetsipDemo2025!');
  const loginResponsePromise = page.waitForResponse((response) => response.url().includes('/api/auth/login') && response.request().method() === 'POST');
  await page.getByRole('button', { name: 'Sign in' }).click();
  const loginResponse = await loginResponsePromise;
  expect(loginResponse.ok()).toBeTruthy();
  const loginPayload = await loginResponse.json() as { token: string; user: { id: string; email: string; role: string } };
  expect(loginPayload.token.length).toBeGreaterThan(20);
  expect(loginPayload.user.email).toBe('executive@ketsip.local');

  const profileResponsePromise = page.waitForResponse((response) => response.url().includes('/api/auth/me') && response.request().method() === 'GET');
  await page.goto('/profile');
  const profileResponse = await profileResponsePromise;
  expect(profileResponse.ok()).toBeTruthy();
  const currentUser = await profileResponse.json() as { id: string; name: string; email: string; role: string };
  expect(currentUser.id).toBe(loginPayload.user.id);
  await expect(page.getByRole('heading', { name: 'Your profile' })).toBeVisible();
  await expect(page.getByText(currentUser.name)).toBeVisible();
  await expect(page.getByText(currentUser.email)).toBeVisible();
  await expect(page.getByText(currentUser.role, { exact: true })).toBeVisible();
  expect(browserErrors).toEqual([]);
});

test('bad credentials show a safe inline failure and stay on login', async ({ page }) => {
  await page.goto('/login');
  await page.getByLabel('Email address').fill('executive@ketsip.local');
  await page.getByLabel('Password').fill('incorrect-value');
  const responsePromise = page.waitForResponse((response) => response.url().includes('/api/auth/login'));
  await page.getByRole('button', { name: 'Sign in' }).click();
  const response = await responsePromise;
  expect(response.status()).toBe(401);
  await expect(page.getByRole('alert')).toHaveText('Invalid email or password.');
  await expect(page).toHaveURL(/\/login$/);
});
