import { test, expect } from '@playwright/test';

test.describe('Consensus Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('has question textarea', async ({ page }) => {
    const textarea = page.locator('textarea');
    await expect(textarea).toBeVisible();
    await expect(textarea).toHaveAttribute(
      'placeholder',
      'Ask a question to reach consensus...',
    );
  });

  test('has rounds selector', async ({ page }) => {
    const roundsSelect = page.locator('select').first();
    await expect(roundsSelect).toBeVisible();

    // Verify round options 1-5 are available
    const options = roundsSelect.locator('option');
    await expect(options).toHaveCount(5);
  });

  test('has protocol selector', async ({ page }) => {
    const selects = page.locator('select');
    // Second select is the protocol selector
    const protocolSelect = selects.nth(1);
    await expect(protocolSelect).toBeVisible();

    const options = protocolSelect.locator('option');
    await expect(options).toHaveCount(3);
    await expect(options.nth(0)).toHaveText('consensus');
    await expect(options.nth(1)).toHaveText('voting');
    await expect(options.nth(2)).toHaveText('auto');
  });

  test('has Ask submit button', async ({ page }) => {
    const button = page.getByRole('button', { name: /ask/i });
    await expect(button).toBeVisible();
  });

  test('Ask button is disabled when textarea is empty', async ({ page }) => {
    const button = page.getByRole('button', { name: /ask/i });
    await expect(button).toBeDisabled();
  });

  test('Ask button is enabled when question is entered', async ({ page }) => {
    const textarea = page.locator('textarea');
    await textarea.fill('Should we use TypeScript?');

    const button = page.getByRole('button', { name: /ask/i });
    await expect(button).toBeEnabled();
  });
});
