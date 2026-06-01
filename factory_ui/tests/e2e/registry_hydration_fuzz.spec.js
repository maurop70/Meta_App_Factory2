import { test, expect } from '@playwright/test';

test.describe('C-Suite Registry Hydration Fuzzing', () => {
  test('Assert visual rendering of CMO_Agent and Venture_Architect rows in Socratic App Registry', async ({ page }) => {
    // Navigate to the Socratic App Registry page
    await page.goto('http://localhost:5173/#/registry');

    // Wait for the registry panel to render
    const panel = page.locator('.registry-panel');
    await expect(panel).toBeVisible({ timeout: 15000 });

    // Wait for the table rows to be present
    const table = page.locator('.registry-table');
    await expect(table).toBeVisible({ timeout: 15000 });

    // Locate the CMO_Agent row by looking for a row containing 'CMO_Agent'
    const cmoRow = page.locator('.registry-table tbody tr', { hasText: 'CMO_Agent' });
    await expect(cmoRow).toBeVisible({ timeout: 15000 });

    // Locate the Venture_Architect row by looking for a row containing 'Venture_Architect'
    const vaRow = page.locator('.registry-table tbody tr', { hasText: 'Venture_Architect' });
    await expect(vaRow).toBeVisible({ timeout: 15000 });

    // Mathematically assert visual rendering by extracting computed display styles
    const cmoDisplay = await cmoRow.evaluate((el) => window.getComputedStyle(el).display);
    const vaDisplay = await vaRow.evaluate((el) => window.getComputedStyle(el).display);

    console.log(`[E2E Verification] CMO_Agent row computed display: "${cmoDisplay}"`);
    console.log(`[E2E Verification] Venture_Architect row computed display: "${vaDisplay}"`);

    // Verify both rows are visible (display !== 'none')
    expect(cmoDisplay).not.toBe('none');
    expect(vaDisplay).not.toBe('none');

    // Extract other computed CSS properties to mathematically prove active paint status
    const cmoVisibility = await cmoRow.evaluate((el) => window.getComputedStyle(el).visibility);
    const vaVisibility = await vaRow.evaluate((el) => window.getComputedStyle(el).visibility);
    
    console.log(`[E2E Verification] CMO_Agent row computed visibility: "${cmoVisibility}"`);
    console.log(`[E2E Verification] Venture_Architect row computed visibility: "${vaVisibility}"`);

    expect(cmoVisibility).toBe('visible');
    expect(vaVisibility).toBe('visible');
  });
});
