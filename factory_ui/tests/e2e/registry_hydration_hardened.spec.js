import { test, expect } from '@playwright/test';

test.describe('Hardened Registry Lifecycles Verification', () => {
  test('Assert /api/apps/running is strictly 200 OK', async ({ request }) => {
    const response = await request.get('http://localhost:5173/api/apps/running');
    
    // Mathematically assert that the proxy doesn't shatter and returns 200 OK
    expect(response.status()).toBe(200);

    const body = await response.json();
    console.log(`[/api/apps/running Telemetry] Keys: ${JSON.stringify(Object.keys(body))}`);

    // Assert it contains pagination keys or fallback keys
    expect(body).toHaveProperty('items');
    expect(Array.isArray(body.items)).toBeTruthy();
  });

  test('Assert Red "CRITICAL ENGINE FRACTURE" modal is not present in the DOM', async ({ page }) => {
    // Navigate to the registry page
    await page.goto('http://localhost:5173/#/registry');

    // Wait for the main registry panel to load
    const panel = page.locator('.registry-panel');
    await expect(panel).toBeVisible({ timeout: 15000 });

    // Assert that the critical error modal is absent or invisible
    const modal = page.locator('.critical-error-modal, .error-boundary-modal, [data-testid="critical-error"]');
    
    const count = await modal.count();
    if (count > 0) {
      const display = await modal.evaluate((el) => window.getComputedStyle(el).display);
      console.log(`[E2E Diagnostic] Computed display of error modal: "${display}"`);
      expect(display).toBe('none');
    } else {
      console.log('[E2E Diagnostic] Critical error modal is physically absent from the DOM.');
      expect(count).toBe(0);
    }
  });
});
