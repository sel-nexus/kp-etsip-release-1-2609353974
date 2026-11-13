import { expect, test } from '@playwright/test';
import { writeFile } from 'node:fs/promises';

test('capture representative accessible UI structure and styles', async ({ page }, testInfo) => {
  const captures: string[] = [];
  async function capture(label: string): Promise<void> {
    const tree = await page.locator('body').ariaSnapshot();
    const styles = await page.evaluate(() => {
      const style = getComputedStyle(document.body);
      return { fontFamily: style.fontFamily, color: style.color, background: style.backgroundColor };
    });
    captures.push(`## ${label}\nAccessibility:\n${tree}\nComputed styles: ${JSON.stringify(styles)}\nHTML:\n${await page.content()}\n`);
    await page.screenshot({ path: testInfo.outputPath(`${label}.png`), fullPage: true });
  }

  await page.goto('/login');
  await expect(page.getByRole('heading', { name: /sign in/i })).toBeVisible();
  await capture('desktop-login');
  await page.getByLabel('Email address').fill('executive@ketsip.local');
  await page.getByLabel('Password').fill('KetsipDemo2025!');
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.getByRole('link', { name: 'Portfolios' })).toBeVisible();
  await page.getByRole('link', { name: 'Portfolios' }).click();
  await expect(page.getByRole('table', { name: /portfolio inventory/i })).toBeVisible();
  await capture('desktop-portfolios');
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole('button', { name: 'Open navigation menu' }).click();
  await capture('mobile-navigation');
  await writeFile('preflight-output.txt', captures.join('\n'), 'utf8');
});
