import { expect, type Page } from '@playwright/test';

const ADMIN_EMAIL = 'admin@ketsip.local';
const INITIAL_ADMIN_PASSWORD = 'TestAdminPassword123!';
const CHANGED_ADMIN_PASSWORD = 'E2EAdminChanged123!';

/** Sign in as the seeded administrator and clear the first-login password gate through the profile UI. */
export async function loginAsAdmin(page: Page): Promise<void> {
  const probe = await page.request.post('/api/auth/login', {
    data: { email: ADMIN_EMAIL, password: INITIAL_ADMIN_PASSWORD },
  });
  const passwordUsed = probe.ok() ? INITIAL_ADMIN_PASSWORD : CHANGED_ADMIN_PASSWORD;
  await page.goto('/login');
  await page.getByLabel('Email address').fill(ADMIN_EMAIL);
  await page.getByLabel('Password').fill(passwordUsed);
  const loginPromise = page.waitForResponse((response) =>
    response.url().includes('/api/auth/login') && response.request().method() === 'POST');
  await page.getByRole('button', { name: 'Sign in' }).click();
  const loginResponse = await loginPromise;
  expect(loginResponse.ok()).toBeTruthy();
  await expect(page).not.toHaveURL(/\/login$/);

  const passwordGate = page.getByRole('alert').filter({
    hasText: 'Change your password before continuing to the platform.',
  });
  if (await passwordGate.isVisible()) {
    await page.getByLabel('Current password').fill(passwordUsed);
    await page.getByLabel('New password').fill(CHANGED_ADMIN_PASSWORD);
    const passwordChangePromise = page.waitForResponse((response) =>
      response.url().includes('/api/auth/me/password') && response.request().method() === 'PUT');
    await page.getByRole('button', { name: 'Update password' }).click();
    const passwordChange = await passwordChangePromise;
    expect(passwordChange.ok()).toBeTruthy();
    await expect(page.getByRole('status').filter({ hasText: 'Password changed successfully.' })).toBeVisible();
  }
}
