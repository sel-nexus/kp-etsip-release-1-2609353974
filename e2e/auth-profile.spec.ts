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
  await page.getByRole('link', { name: 'Profile' }).click();
  const profileResponse = await profileResponsePromise;
  expect(profileResponse.ok()).toBeTruthy();
  const currentUser = await profileResponse.json() as { id: string; name: string; email: string; role: string };
  expect(currentUser.id).toBe(loginPayload.user.id);
  await expect(page.getByRole('heading', { name: 'Your profile' })).toBeVisible();
  await expect(page.getByText(currentUser.name)).toBeVisible();
  await expect(page.getByText(currentUser.email)).toBeVisible();
  await expect(page.getByText(currentUser.role, { exact: true })).toBeVisible();

  await page.getByLabel('After sign in').selectOption('/applications');
  const preferenceResponsePromise = page.waitForResponse((response) => response.url().includes('/api/auth/me/preferences') && response.request().method() === 'PUT');
  await page.getByRole('button', { name: 'Save preference' }).click();
  const preferenceResponse = await preferenceResponsePromise;
  expect(preferenceResponse.ok()).toBeTruthy();
  const preferencePayload = await preferenceResponse.json() as { user: { defaultLandingPage: string | null } };
  expect(preferencePayload.user.defaultLandingPage).toBe('/applications');
  await expect(page.getByRole('status').filter({ hasText: 'Default page saved.' })).toBeVisible();

  const refreshedProfilePromise = page.waitForResponse((response) => response.url().includes('/api/auth/me') && response.request().method() === 'GET');
  await page.reload();
  const refreshedProfileResponse = await refreshedProfilePromise;
  expect(refreshedProfileResponse.ok()).toBeTruthy();
  const refreshedProfile = await refreshedProfileResponse.json() as { defaultLandingPage: string | null; landingPage: string };
  expect(refreshedProfile.defaultLandingPage).toBe('/applications');
  expect(refreshedProfile.landingPage).toBe('/applications');
  await expect(page.getByLabel('After sign in')).toHaveValue('/applications');
  expect(browserErrors).toEqual([]);
});

test('bad credentials show a safe inline failure and stay on login', async ({ page }) => {
  const browserErrors: string[] = [];
  const expectedResourceErrors: string[] = [];
  const expectedResourceError = 'Failed to load resource: the server responded with a status of 401 (Unauthorized)';
  page.on('console', (message) => {
    if (message.type() === 'error') {
      if (message.text() === expectedResourceError) {
        expectedResourceErrors.push(message.text());
      } else {
        browserErrors.push(message.text());
      }
    }
  });
  page.on('pageerror', (error) => browserErrors.push(error.message));

  await page.goto('/login');
  await page.getByLabel('Email address').fill('executive@ketsip.local');
  await page.getByLabel('Password').fill('incorrect-value');
  const responsePromise = page.waitForResponse((response) => response.url().includes('/api/auth/login'));
  await page.getByRole('button', { name: 'Sign in' }).click();
  const response = await responsePromise;
  expect(response.status()).toBe(401);
  await expect(page.getByRole('alert')).toHaveText('Invalid email or password.');
  await expect(page).toHaveURL((url) => url.pathname === '/login');
  expect(expectedResourceErrors).toEqual([expectedResourceError]);
  expect(browserErrors).toEqual([]);
});

test('seeded executive changes password, signs in with it, and restores the seeded credential', async ({ page }) => {
  const browserErrors: string[] = [];
  page.on('console', (message) => {
    if (message.type() === 'error') browserErrors.push(message.text());
  });
  page.on('pageerror', (error) => browserErrors.push(error.message));

  const originalPassword = 'KetsipDemo2025!';
  const replacementPassword = `E2EExec-${Date.now()}-Secure!`;
  try {
  await page.goto('/login');
  await page.getByLabel('Email address').fill('executive@ketsip.local');
  await page.getByLabel('Password').fill(originalPassword);
  const initialLoginPromise = page.waitForResponse((response) => response.url().includes('/api/auth/login') && response.request().method() === 'POST');
  await page.getByRole('button', { name: 'Sign in' }).click();
  const initialLogin = await initialLoginPromise;
  expect(initialLogin.ok()).toBeTruthy();

  const initialProfilePromise = page.waitForResponse((response) => response.url().includes('/api/auth/me') && response.request().method() === 'GET');
  await page.getByRole('link', { name: 'Profile' }).click();
  expect((await initialProfilePromise).ok()).toBeTruthy();

  await page.getByLabel('Current password').fill(originalPassword);
  await page.getByLabel('New password').fill(replacementPassword);
  const changeResponsePromise = page.waitForResponse((response) => response.url().includes('/api/auth/me/password') && response.request().method() === 'PUT');
  await page.getByRole('button', { name: 'Update password' }).click();
  const changeResponse = await changeResponsePromise;
  expect(changeResponse.ok()).toBeTruthy();
  const changedProfile = await changeResponse.json() as { email: string };
  expect(changedProfile.email).toBe('executive@ketsip.local');
  await expect(page.getByRole('status').filter({ hasText: 'Password changed successfully.' })).toBeVisible();

  await page.locator('main').getByRole('button', { name: 'Sign out' }).click();
  await expect(page).toHaveURL((url) => url.pathname === '/login');
  await page.getByLabel('Email address').fill('executive@ketsip.local');
  await page.getByLabel('Password').fill(replacementPassword);
  const replacementLoginPromise = page.waitForResponse((response) => response.url().includes('/api/auth/login') && response.request().method() === 'POST');
  await page.getByRole('button', { name: 'Sign in' }).click();
  const replacementLogin = await replacementLoginPromise;
  expect(replacementLogin.ok()).toBeTruthy();
  const replacementLoginData = await replacementLogin.json() as { user: { email: string } };
  expect(replacementLoginData.user.email).toBe('executive@ketsip.local');

  const replacementProfilePromise = page.waitForResponse((response) => response.url().includes('/api/auth/me') && response.request().method() === 'GET');
  await page.getByRole('link', { name: 'Profile' }).click();
  expect((await replacementProfilePromise).ok()).toBeTruthy();
  await page.getByLabel('Current password').fill(replacementPassword);
  await page.getByLabel('New password').fill(originalPassword);
  const restoreResponsePromise = page.waitForResponse((response) => response.url().includes('/api/auth/me/password') && response.request().method() === 'PUT');
  await page.getByRole('button', { name: 'Update password' }).click();
  const restoreResponse = await restoreResponsePromise;
  expect(restoreResponse.ok()).toBeTruthy();
  await expect(page.getByRole('status').filter({ hasText: 'Password changed successfully.' })).toBeVisible();

  await page.locator('main').getByRole('button', { name: 'Sign out' }).click();
  await expect(page).toHaveURL((url) => url.pathname === '/login');
  await page.getByLabel('Email address').fill('executive@ketsip.local');
  await page.getByLabel('Password').fill(originalPassword);
  const restoredLoginPromise = page.waitForResponse((response) => response.url().includes('/api/auth/login') && response.request().method() === 'POST');
  await page.getByRole('button', { name: 'Sign in' }).click();
  const restoredLogin = await restoredLoginPromise;
  expect(restoredLogin.ok()).toBeTruthy();
  expect(browserErrors).toEqual([]);
  } finally {
    const login = async (password: string) => page.request.post('/api/auth/login', {
      data: { email: 'executive@ketsip.local', password },
    });
    const originalLogin = await login(originalPassword);
    if (!originalLogin.ok()) {
      const replacementLogin = await login(replacementPassword);
      expect(replacementLogin.ok(), 'the current seeded credential must remain usable for restoration').toBeTruthy();
      const replacementLoginData = await replacementLogin.json() as { token: string };
      const restoreResponse = await page.request.put('/api/auth/me/password', {
        data: { currentPassword: replacementPassword, newPassword: originalPassword },
        headers: { Authorization: `Bearer ${replacementLoginData.token}` },
      });
      expect(restoreResponse.ok(), 'the seeded password must be restored in finally').toBeTruthy();
      expect((await login(originalPassword)).ok(), 'the restored seeded credential must sign in').toBeTruthy();
    }
  }
});
