import { expect, test } from '@playwright/test';

test('seeded administrator manages audit view and seeded auditor is read-only', async ({ page }) => {
  const browserErrors: string[] = [];
  page.on('console', (message) => {
    if (message.type() === 'error') browserErrors.push(message.text());
  });
  page.on('pageerror', (error) => browserErrors.push(error.message));

  await page.goto('/login');
  await page.getByLabel('Email address').fill('admin@ketsip.local');
  await page.getByLabel('Password').fill('TestAdminPassword123!');
  const adminLogin = page.waitForResponse((response) => response.url().includes('/api/auth/login') && response.request().method() === 'POST');
  await page.getByRole('button', { name: 'Sign in' }).click();
  expect((await adminLogin).ok()).toBeTruthy();
  await page.goto('/profile');
  await page.getByLabel('Current password').fill('TestAdminPassword123!');
  await page.getByLabel('New password').fill('AdminChangedPassword456!');
  await page.getByRole('button', { name: 'Update password' }).click();
  await expect(page.getByText('Password changed successfully.', { exact: true })).toBeVisible();
  const usersResponse = page.waitForResponse((response) => response.url().includes('/api/users') && response.request().method() === 'GET');
  await page.goto('/administration');
  await expect(page.getByRole('heading', { name: 'Administration' })).toBeVisible();
  const users = await usersResponse;
  expect(users.ok()).toBeTruthy();
  const userData = await users.json() as { items: Array<{ email: string }> };
  expect(userData.items.some((user) => user.email === 'engineer@ketsip.local')).toBeTruthy();
  await expect(page.getByRole('cell', { name: 'engineer@ketsip.local', exact: true })).toBeVisible();

  const rolesResponsePromise = page.waitForResponse((response) => response.url().includes('/api/roles') && response.request().method() === 'GET');
  await page.getByRole('tab', { name: 'Roles' }).click();
  const rolesResponse = await rolesResponsePromise;
  expect(rolesResponse.ok()).toBeTruthy();
  const roleData = await rolesResponse.json() as Array<{ name: string }>;
  expect(roleData.map((role) => role.name)).toEqual(['Administrator', 'Executive', 'Portfolio Leader', 'Engineer', 'Auditor', 'Read Only']);
  await expect(page.getByRole('heading', { name: 'Auditor' })).toBeVisible();

  const auditResponsePromise = page.waitForResponse((response) => response.url().includes('/api/audit-logs') && response.request().method() === 'GET');
  await page.getByRole('tab', { name: 'Audit history' }).click();
  const auditResponse = await auditResponsePromise;
  expect(auditResponse.ok()).toBeTruthy();
  const auditData = await auditResponse.json() as { items: Array<{ action: string; entityType: string }> };
  expect(auditData.items.some((entry) => entry.action === 'login' && entry.entityType === 'auth')).toBeTruthy();
  await expect(page.getByText(/Local account authentication/).first()).toBeVisible();

  await page.getByRole('button', { name: 'Sign out' }).click();
  await page.getByLabel('Email address').fill('auditor@ketsip.local');
  await page.getByLabel('Password').fill('KetsipDemo2025!');
  const auditorLogin = page.waitForResponse((response) => response.url().includes('/api/auth/login') && response.request().method() === 'POST');
  await page.getByRole('button', { name: 'Sign in' }).click();
  expect((await auditorLogin).ok()).toBeTruthy();
  await page.goto('/audit');
  const auditorAudit = await page.waitForResponse((response) => response.url().includes('/api/audit-logs') && response.request().method() === 'GET');
  expect(auditorAudit.ok()).toBeTruthy();
  await expect(page.getByRole('heading', { name: 'Audit history' })).toBeVisible();
  await expect(page.getByRole('tab', { name: 'Audit history' })).toBeVisible();
  await expect(page.getByRole('tab', { name: 'Users' })).toHaveCount(0);
  await expect(page.getByRole('tab', { name: 'Roles' })).toHaveCount(0);
  await page.goto('/administration');
  await expect(page).toHaveURL(/\/applications$/);
  expect(browserErrors).toEqual([]);
});
