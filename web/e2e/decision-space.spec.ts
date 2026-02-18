import { test, expect } from '@playwright/test';

test.describe('Decision Space', () => {
  test('page loads without error', async ({ page }) => {
    await page.goto('/space');
    await expect(page.locator('body')).toBeVisible();
  });

  test('no console errors on load', async ({ page }) => {
    const errors: string[] = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        errors.push(msg.text());
      }
    });

    await page.goto('/space');
    await page.waitForTimeout(1000);

    // Filter out expected errors (e.g. WebSocket connection failures in test env)
    const unexpectedErrors = errors.filter(
      (e) => !e.includes('WebSocket') && !e.includes('ERR_CONNECTION_REFUSED'),
    );
    expect(unexpectedErrors).toEqual([]);
  });
});
