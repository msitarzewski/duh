import { test, expect } from '@playwright/test';

test.describe('Navigation', () => {
  test('home page loads with correct title', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveTitle(/duh/i);
  });

  test('sidebar navigation is visible on desktop', async ({ page }) => {
    // Shell renders a <nav> inside the Sidebar component
    await page.goto('/');
    const nav = page.locator('nav');
    await expect(nav).toBeVisible();
  });

  test('sidebar contains all nav links', async ({ page }) => {
    await page.goto('/');
    const nav = page.locator('nav');

    await expect(nav.getByText('Consensus')).toBeVisible();
    await expect(nav.getByText('Threads')).toBeVisible();
    await expect(nav.getByText('Decision Space')).toBeVisible();
    await expect(nav.getByText('Preferences')).toBeVisible();
  });

  test('threads page accessible via navigation', async ({ page }) => {
    await page.goto('/');
    await page.getByText('Threads').click();
    await expect(page).toHaveURL(/\/threads/);
    await expect(page.locator('body')).toBeVisible();
  });

  test('decision space page accessible via navigation', async ({ page }) => {
    await page.goto('/');
    await page.getByText('Decision Space').click();
    await expect(page).toHaveURL(/\/space/);
    await expect(page.locator('body')).toBeVisible();
  });

  test('preferences page accessible via navigation', async ({ page }) => {
    await page.goto('/');
    await page.getByText('Preferences').click();
    await expect(page).toHaveURL(/\/preferences/);
    await expect(page.locator('body')).toBeVisible();
  });

  test('consensus page accessible via direct URL', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('body')).toBeVisible();
  });

  test('threads page accessible via direct URL', async ({ page }) => {
    await page.goto('/threads');
    await expect(page.locator('body')).toBeVisible();
  });

  test('space page accessible via direct URL', async ({ page }) => {
    await page.goto('/space');
    await expect(page.locator('body')).toBeVisible();
  });

  test('preferences page accessible via direct URL', async ({ page }) => {
    await page.goto('/preferences');
    await expect(page.locator('body')).toBeVisible();
  });
});
