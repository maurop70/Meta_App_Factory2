import { test, expect } from '@playwright/test';

test('verify computed glassmorphism backdrop-filter on builder-chat', async ({ page }) => {
  // Navigate to Builder Chat endpoint
  await page.goto('http://localhost:5173/#/builder');

  // Wait for the .builder-chat element to be visible
  const element = page.locator('.builder-chat');
  await expect(element).toBeVisible({ timeout: 15000 });

  // Inject JavaScript to execute window.getComputedStyle(element).backdropFilter
  const backdropFilter = await element.evaluate((el) => {
    return window.getComputedStyle(el).backdropFilter || window.getComputedStyle(el).webkitBackdropFilter;
  });

  console.log(`[CSSOM Telemetry] Computed backdrop-filter: "${backdropFilter}"`);

  // Mathematically assert that the returned value is strictly not equal to 'none'
  expect(backdropFilter).not.toBe('none');
  expect(backdropFilter).toContain('blur');
});
