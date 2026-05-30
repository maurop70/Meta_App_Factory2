import { test, expect } from '@playwright/test';

test.describe('Phase 4 - Closed-Loop Memory Ingestion & Asset Delivery E2E Verification', () => {
  test('Should execute live workspace actuation, verify Pydantic JSON envelope, and bind asset URL to UI anchor', async ({ page }) => {
    
    // 1. Navigate to the Adversarial War Room
    await page.goto('http://localhost:5173/#/warroom');
    await page.waitForTimeout(1000);

    // Assert that the Actuation Panel is rendered correctly
    const panelTitle = page.locator('h3:has-text("Consensus Actuator Panel")');
    await expect(panelTitle).toBeVisible({ timeout: 10000 });

    // 2. Actuate via Manual Override Input to feed custom boardroom consensus
    const overrideButton = page.locator('button:has-text("MANUAL PAYLOAD OVERRIDE")');
    await expect(overrideButton).toBeVisible();
    await overrideButton.click();

    const overrideTextarea = page.locator('textarea[placeholder*="Paste raw Markdown or JSON consensus strategy"]');
    await expect(overrideTextarea).toBeVisible();

    // Prepare raw Markdown representing typical C-Suite consensus containing the spooled blueprint JSON
    // We will use a valid template_id stub
    const rawConsensusMarkdown = `
# C-Suite Swarm Consensus Finalized
The board has concluded deliberation. Below is the approved technical workspace blueprint.

\`\`\`json
{
  "presentation_name": "Heinlein_Foods_E2E_Phase_4_Live",
  "template_id": "1QEgXTEkk8C4mIP6QhRvZ0d-DpcuvyniGfwqzkDXC-oY",
  "mutations": {
    "{{PROJECT_NAME}}": "Project Heinlein Foods Live Phase 4",
    "{{OBJECTIVE}}": "Closed-Loop Vector Ingestion Audit",
    "{{BUDGET}}": "$75k live budget",
    "{{ROI_ESTIMATE}}": "500% ROI"
  }
}
\`\`\`
    `;

    await overrideTextarea.fill(rawConsensusMarkdown);
    await page.waitForTimeout(500);

    // 3. Set up the unmocked live response waiter
    const responsePromise = page.waitForResponse(
      response => response.url().includes('/api/workspace/actuate') && response.status() === 200,
      { timeout: 30000 }
    );

    // 4. Click the [ ACTUATE BLUEPRINT ] button in the Actuation Panel
    const actuateBtn = page.locator('.actuation-panel button:has-text("[ ACTUATE BLUEPRINT ]")');
    await expect(actuateBtn).toBeVisible();
    await expect(actuateBtn).toBeEnabled();
    await actuateBtn.click();

    // 5. Await the live backend network response and parse/validate its schema
    console.log("[E2E Playwright] Waiting for live backend network response...");
    const response = await responsePromise;
    const responseBody = await response.json();
    console.log("[E2E Playwright] Live response body:", JSON.stringify(responseBody, null, 2));

    // Assert actual backend serialized Pydantic JSON envelope matches the new Phase 4 schema
    expect(responseBody.status).toBe('success');
    expect(responseBody.asset_url).toBeDefined();
    expect(typeof responseBody.asset_url).toBe('string');
    expect(responseBody.asset_url.startsWith('https://docs.google.com/presentation/d/')).toBe(true);
    expect(responseBody.document_id).toBeDefined();
    expect(typeof responseBody.document_id).toBe('string');

    // 6. Assert success notification and anchor tag [ VIEW DEPLOYED ASSET ] mounts in the UI
    const successAlert = page.locator('span:has-text("ACTUATION SUCCESS")');
    await expect(successAlert).toBeVisible({ timeout: 10000 });

    const viewAssetLink = page.locator('a:has-text("[ VIEW DEPLOYED ASSET ]")');
    await expect(viewAssetLink).toBeVisible({ timeout: 5000 });

    // 7. Mathematically assert the href strictly matches standard Google Presentation URL pattern via regex
    const href = await viewAssetLink.getAttribute('href');
    console.log("[E2E Playwright] Found Deployed Asset URL:", href);
    expect(href).not.toBeNull();

    // Pattern matching standard google presentation URL: https://docs.google.com/presentation/d/[id]/edit
    const googlePresentationPattern = /^https:\/\/docs\.google\.com\/presentation\/d\/[a-zA-Z0-9_-]+\/edit$/;
    expect(href).toMatch(googlePresentationPattern);

    console.log("[E2E Playwright] SUCCESS: Live closed-loop asset delivery E2E verification is complete!");
  });
});
