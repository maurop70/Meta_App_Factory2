import { test, expect } from '@playwright/test';

test.describe('Ignite Boardroom Swarm Strategic Debate', () => {
  test('Assert War Room loads and ignites survival matrix', async ({ page }) => {
    // Navigate to the live War Room interface
    await page.goto('http://localhost:5173/#/warroom');

    // Wait for the gateway panel to load and verify title
    const title = page.locator('h2:has-text("Adversarial Threat Ingestion Gateway")');
    await expect(title).toBeVisible({ timeout: 15000 });

    // Locate the intent input textarea
    const textarea = page.locator('textarea[placeholder*="Describe the architectural parameters"]');
    await expect(textarea).toBeVisible();

    // Input the exact Heinlein Foods B2B cash-preservation operational payload
    const payload = 'Project Heinlein Foods. Fixed Costs: $600,000. Contribution Margin: 50%. Monthly Breakeven Required: $1,200,000. Marketing Budget: $0. Objective: 90-day extreme cash-preservation, B2B/White-Label pivot strategies for universal enrobing and new drink line to replace idle Hershey/Reese\'s capacity.';
    await textarea.fill(payload);
    console.log('[E2E WarRoom] Operational payload successfully pasted.');

    // Click the TRANSMIT INTENT button
    const transmitBtn = page.locator('button:has-text("TRANSMIT INTENT")');
    await expect(transmitBtn).toBeVisible();
    await transmitBtn.click();
    console.log('[E2E WarRoom] TRANSMIT INTENT actuated.');

    // Wait for MAF ORCHESTRATOR response dialogue
    const cmoStatus = page.getByText('Intent captured and mapped to the structural matrix', { exact: false }).first();
    await expect(cmoStatus).toBeVisible({ timeout: 5000 });
    console.log('[E2E WarRoom] MAF ORCHESTRATOR confirmed intent mapping.');

    // Click the [ ACTUATE BLUEPRINT ] button
    const actuateBtn = page.locator('button:has-text("[ ACTUATE BLUEPRINT ]")');
    await expect(actuateBtn).toBeVisible();
    await actuateBtn.click();
    console.log('[E2E WarRoom] [ ACTUATE BLUEPRINT ] clicked. Strategic debate initiated.');

    // Wait for boardroom session success system confirmation message in the dialog feed
    const successMsg = page.getByText('Boardroom session successfully opened', { exact: false }).first();
    await expect(successMsg).toBeVisible({ timeout: 10000 });
    console.log('[E2E WarRoom] SUCCESS: Strategic C-Suite debate successfully ignited!');

    // Wait 5 seconds to let the live debate spool up and broadcast initial dialogue logs
    await page.waitForTimeout(5000);
  });
});
