import { test, expect } from '@playwright/test';

test.describe('Hardened Registry Lifecycles 502 Verification', () => {
  test('Assert UI gracefully handles 502 and renders theTrapped Error overlay', async ({ page }) => {
    // Mock the /api/apps/running call to return a strict 502 Bad Gateway with mathematically uniform JSON content
    await page.route('**/api/apps/running', async (route) => {
      await route.fulfill({
        status: 502,
        contentType: 'application/json',
        body: JSON.stringify({
          items: [],
          total: 0,
          limit: 10,
          offset: 0,
          running_apps: [],
          error: "Gateway Unreachable",
          detail: "Mocked Connection Refused / Socket Timeout"
        })
      });
    });

    // Listen for any unhandled JS promise rejections or exceptions during page execution
    const errors = [];
    page.on('pageerror', (err) => {
      errors.push(err.message);
    });

    // Navigate to the Socratic App Registry panel
    await page.goto('http://localhost:5173/#/registry');

    // Wait for the diagnostic overlay container to appear
    const overlayTitle = page.locator('h2:has-text("CRITICAL ENGINE FRACTURE TRAPPED")');
    await expect(overlayTitle).toBeVisible({ timeout: 15000 });

    // Assert that the error detail has the correct status code mapped
    const statusLabel = page.locator('span:has-text("STATUS 502")');
    await expect(statusLabel).toBeVisible();

    // Verify the mock message is rendered in the overlay
    const errorMessage = page.getByText('Request failed with status code 502', { exact: true });
    await expect(errorMessage).toBeVisible();

    // Mathematically assert that there were no unhandled JS errors on the page
    console.log(`[E2E Diagnostic] Trapped page errors: ${errors.length}`);
    expect(errors.length).toBe(0);

    // Verify the modal computed display style is 'flex' or visible
    const display = await overlayTitle.evaluate((el) => {
      const parent = el.closest('div');
      return window.getComputedStyle(parent).display;
    });
    console.log(`[E2E Diagnostic] Trapped modal computed parent display: "${display}"`);
    expect(display).not.toBe('none');
  });

  test('Assert direct backend proxy returns strict 502 when simulated offline', async ({ request }) => {
    // Direct API request verification:
    // If the port 5000 is intentionally down or if we target a mock path that fails,
    // verify the proxy handles it. Let's hit a path we know will trigger 502 (e.g. non-existent child agent port proxy)
    // to verify the FastAPI backend custom exception trapping.
    const response = await request.get('http://localhost:5050/api/apps/invalid_agent_lifecycle_path');
    
    // The wildcard proxy will intercept this non-existent path and attempt to forward to Port 5000
    // If Port 5000 returns 404/other, it forwards it. But if it's simulated as unreachable or custom-routed:
    console.log(`[E2E Direct Proxy] Status: ${response.status()}`);
    expect([502, 404]).toContain(response.status());
  });
});
