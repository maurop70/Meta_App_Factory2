import { test, expect } from '@playwright/test';

test.describe('Phase 3 - Blueprint Actuation Transport Layer E2E Verification', () => {
  test('Should parse, serialize and cleanly transmit consensus blueprint to Sentinel backend', async ({ page }) => {
    // 1. Intercept outbound /api/workspace/actuate request to verify payload structure
    let interceptedRequestPayload: any = null;
    
    await page.route('**/api/workspace/actuate', async (route) => {
      const request = route.request();
      const postData = request.postData();
      if (postData) {
        try {
          interceptedRequestPayload = JSON.parse(postData);
        } catch (e) {
          console.error("Failed to parse intercepted POST data:", e);
        }
      }
      
      // Mock successful actuation response to prevent side effects
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: "success",
          presentation_id: "mock_presentation_12345",
          url: "https://docs.google.com/presentation/d/mock_presentation_12345/edit"
        })
      });
    });

    // 2. Navigate to the Adversarial War Room
    await page.goto('http://localhost:5173/#/warroom');
    await page.waitForTimeout(1000);

    // Assert that the Actuation Panel is rendered correctly
    const panelTitle = page.locator('h3:has-text("Consensus Actuator Panel")');
    await expect(panelTitle).toBeVisible({ timeout: 10000 });

    // 3. Actuate via Manual Override Input to feed custom boardroom consensus
    const overrideButton = page.locator('button:has-text("MANUAL PAYLOAD OVERRIDE")');
    await expect(overrideButton).toBeVisible();
    await overrideButton.click();

    const overrideTextarea = page.locator('textarea[placeholder*="Paste raw Markdown or JSON consensus strategy"]');
    await expect(overrideTextarea).toBeVisible();

    // Prepare raw Markdown representing typical C-Suite consensus containing the spooled blueprint JSON
    const rawConsensusMarkdown = `
# C-Suite Swarm Consensus Finalized
The board has concluded deliberation. Below is the approved technical workspace blueprint.

\`\`\`json
{
  "presentation_name": "Heinlein_Foods_90_Day_Strategy",
  "template_id": "1QEgXTEkk8C4mIP6QhRvZ0d-DpcuvyniGfwqzkDXC-oY",
  "mutations": {
    "{{PROJECT_NAME}}": "Project Heinlein Foods",
    "{{OBJECTIVE}}": "90-Day Survival: White-Label B2B pivot",
    "{{BUDGET}}": "$50k budget",
    "{{ROI_ESTIMATE}}": "400% ROI"
  }
}
\`\`\`
    `;

    await overrideTextarea.fill(rawConsensusMarkdown);
    await page.waitForTimeout(500);

    // 4. Click the [ ACTUATE BLUEPRINT ] button in the Actuation Panel
    // Note: Locator points specifically to the button inside the Actuation Panel
    const actuateBtn = page.locator('.actuation-panel button:has-text("[ ACTUATE BLUEPRINT ]")');
    await expect(actuateBtn).toBeVisible();
    await expect(actuateBtn).toBeEnabled();
    await actuateBtn.click();

    // Wait for network response and verify success notification renders
    const successAlert = page.locator('span:has-text("ACTUATION SUCCESS")');
    await expect(successAlert).toBeVisible({ timeout: 5000 });

    // 5. Assert that the request payload conforms exactly to the WorkspaceBlueprintInput schema
    expect(interceptedRequestPayload).not.toBeNull();
    console.log("[E2E Playwright] Intercepted payload:", JSON.stringify(interceptedRequestPayload, null, 2));

    // Verify WorkspaceBlueprintInput schema keys
    expect(interceptedRequestPayload.execution_id).toBeDefined();
    expect(typeof interceptedRequestPayload.execution_id).toBe('string');
    expect(interceptedRequestPayload.execution_id.startsWith('exec_')).toBe(true);

    expect(interceptedRequestPayload.target_engine).toBe('Google_Slides');

    expect(interceptedRequestPayload.master_template_id).toBe('1QEgXTEkk8C4mIP6QhRvZ0d-DpcuvyniGfwqzkDXC-oY');
    expect(interceptedRequestPayload.output_filename).toBe('Heinlein_Foods_90_Day_Strategy');

    // Verify mutations list format mapping from the consensus mutations dictionary
    expect(Array.isArray(interceptedRequestPayload.mutations)).toBe(true);
    expect(interceptedRequestPayload.mutations.length).toBe(4);

    // Assert individual mutation structure
    for (const mutation of interceptedRequestPayload.mutations) {
      expect(mutation.replace_tag).toBeDefined();
      expect(typeof mutation.replace_tag).toBe('string');
      expect(mutation.injection_value).toBeDefined();
      expect(typeof mutation.injection_value).toBe('string');
    }

    // Verify specific mutation values mapped from consensus dictionary
    const projectMutation = interceptedRequestPayload.mutations.find((m: any) => m.replace_tag === '{{PROJECT_NAME}}');
    expect(projectMutation).toBeDefined();
    expect(projectMutation.injection_value).toBe('Project Heinlein Foods');

    const roiMutation = interceptedRequestPayload.mutations.find((m: any) => m.replace_tag === '{{ROI_ESTIMATE}}');
    expect(roiMutation).toBeDefined();
    expect(roiMutation.injection_value).toBe('400% ROI');

    console.log("[E2E Playwright] SUCCESS: Actuation transport layer is mathematically and structurally verified!");
  });
});
