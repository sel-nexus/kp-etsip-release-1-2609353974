import { expect, test } from '@playwright/test';
import { loginAsAdmin } from './admin-login';

test('seeded administrator manages audit view and seeded auditor is read-only', async ({ page }) => {
  const browserErrors: string[] = [];
  page.on('console', (message) => {
    if (message.type() === 'error') browserErrors.push(message.text());
  });
  page.on('pageerror', (error) => browserErrors.push(error.message));

  await loginAsAdmin(page);
  const usersResponse = page.waitForResponse((response) => response.url().includes('/api/users') && response.request().method() === 'GET');
  await page.getByRole('link', { name: 'Administration' }).click();
  await expect(page.getByRole('heading', { name: 'Administration' })).toBeVisible();
  const users = await usersResponse;
  expect(users.ok()).toBeTruthy();
  const userData = await users.json() as { items: Array<{ id: string; email: string; status: 'Active' | 'Inactive' }> };
  const managedAccount = userData.items.find((user) => user.email === 'engineer@ketsip.local');
  expect(managedAccount).toBeDefined();
  if (!managedAccount) throw new Error('The seeded engineer account was not returned by the administration API.');
  const originalStatus = managedAccount.status;
  const changedStatus = originalStatus === 'Active' ? 'Inactive' : 'Active';
  const accountRow = page.getByRole('row').filter({ has: page.getByRole('cell', { name: managedAccount.email, exact: true }) });
  await expect(accountRow).toBeVisible();

  try {
    const statusMutationPromise = page.waitForResponse((response) =>
      response.url().includes(`/api/users/${managedAccount.id}`)
      && response.request().method() === (originalStatus === 'Active' ? 'DELETE' : 'PUT'));
    await accountRow.getByRole('button', { name: originalStatus === 'Active' ? 'Deactivate' : 'Reactivate' }).click();
    const statusMutation = await statusMutationPromise;
    expect(statusMutation.status()).toBe(200);
    expect((await statusMutation.json() as { status: string }).status).toBe(changedStatus);

    const changedUsersPromise = page.waitForResponse((response) => response.url().includes('/api/users') && response.request().method() === 'GET');
    await page.reload();
    const changedUsersResponse = await changedUsersPromise;
    expect(changedUsersResponse.status()).toBe(200);
    const changedUsers = await changedUsersResponse.json() as { items: Array<{ id: string; status: 'Active' | 'Inactive' }> };
    expect(changedUsers.items.find((user) => user.id === managedAccount.id)?.status).toBe(changedStatus);
    await expect(page.getByRole('row').filter({ has: page.getByRole('cell', { name: managedAccount.email, exact: true }) })
      .getByRole('cell', { name: changedStatus, exact: true })).toBeVisible();
  } finally {
    const currentUsersPromise = page.waitForResponse((response) => response.url().includes('/api/users') && response.request().method() === 'GET');
    await page.reload();
    const currentUsersResponse = await currentUsersPromise;
    expect(currentUsersResponse.status()).toBe(200);
    const currentUsers = await currentUsersResponse.json() as { items: Array<{ id: string; status: 'Active' | 'Inactive' }> };
    const currentAccount = currentUsers.items.find((user) => user.id === managedAccount.id);
    expect(currentAccount).toBeDefined();
    if (!currentAccount) throw new Error('The managed account disappeared before its status could be restored.');

    if (currentAccount.status !== originalStatus) {
      const restorePromise = page.waitForResponse((response) =>
        response.url().includes(`/api/users/${managedAccount.id}`)
        && response.request().method() === (currentAccount.status === 'Active' ? 'DELETE' : 'PUT'));
      const currentAccountRow = page.getByRole('row').filter({ has: page.getByRole('cell', { name: managedAccount.email, exact: true }) });
      await currentAccountRow.getByRole('button', { name: currentAccount.status === 'Active' ? 'Deactivate' : 'Reactivate' }).click();
      const restoreResponse = await restorePromise;
      expect(restoreResponse.status()).toBe(200);
      expect((await restoreResponse.json() as { status: string }).status).toBe(originalStatus);

      const restoredUsersPromise = page.waitForResponse((response) => response.url().includes('/api/users') && response.request().method() === 'GET');
      await page.reload();
      const restoredUsersResponse = await restoredUsersPromise;
      expect(restoredUsersResponse.status()).toBe(200);
      const restoredUsers = await restoredUsersResponse.json() as { items: Array<{ id: string; status: 'Active' | 'Inactive' }> };
      expect(restoredUsers.items.find((user) => user.id === managedAccount.id)?.status).toBe(originalStatus);
      await expect(page.getByRole('row').filter({ has: page.getByRole('cell', { name: managedAccount.email, exact: true }) })
        .getByRole('cell', { name: originalStatus, exact: true })).toBeVisible();
    }
  }

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

  await page.getByRole('navigation', { name: 'Account navigation' }).getByRole('button', { name: 'Sign out' }).click();
  await page.getByLabel('Email address').fill('auditor@ketsip.local');
  await page.getByLabel('Password').fill('KetsipDemo2025!');
  const auditorLogin = page.waitForResponse((response) => response.url().includes('/api/auth/login') && response.request().method() === 'POST');
  await page.getByRole('button', { name: 'Sign in' }).click();
  expect((await auditorLogin).ok()).toBeTruthy();
  const auditorAuditPromise = page.waitForResponse((response) => response.url().includes('/api/audit-logs') && response.request().method() === 'GET');
  await page.getByRole('link', { name: 'Audit history' }).click();
  const auditorAudit = await auditorAuditPromise;
  expect(auditorAudit.ok()).toBeTruthy();
  await expect(page.getByRole('heading', { name: 'Audit history' })).toBeVisible();
  await expect(page.getByRole('tab', { name: 'Audit history' })).toBeVisible();
  await expect(page.getByRole('tab', { name: 'Users' })).toHaveCount(0);
  await expect(page.getByRole('tab', { name: 'Roles' })).toHaveCount(0);
  await page.getByRole('link', { name: 'Applications', exact: true }).click();
  await expect(page).toHaveURL(/\/applications$/);
  expect(browserErrors).toEqual([]);
});
