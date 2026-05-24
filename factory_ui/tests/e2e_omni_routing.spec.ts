import { test, expect } from '@playwright/test';

test('verify Pre-Flight Classifier intent-based semantic routing', async ({ page }) => {
  // Set larger timeout to allow multiple streams to complete
  test.setTimeout(60000);

  // Test A: Technical Intent routing to EXECUTIVE_ARCHITECT
  console.log('[E2E Routing Test] Navigating to Omni-Gateway...');
  await page.goto('http://localhost:5173/#/builder');

  const textareaA = page.locator('textarea');
  await expect(textareaA).toBeVisible({ timeout: 15000 });

  // Clear any existing session storage to ensure clean test turn
  await page.evaluate(() => sessionStorage.clear());
  await page.reload();
  
  const textarea = page.locator('textarea');
  await expect(textarea).toBeVisible({ timeout: 15000 });

  console.log('[E2E Routing Test] Test A: Injecting technical prompt...');
  await textarea.fill("Write a Python script for an API.");
  
  const sendBtn = page.locator('.send-btn');
  await sendBtn.click();

  console.log('[E2E Routing Test] Test A: Waiting for streaming completion...');
  await expect(textarea).toBeEnabled({ timeout: 45000 });

  // Extract the assistant header and mathematically assert routing to EXECUTIVE_ARCHITECT
  const assistantHeaders = page.locator('.msg.assistant strong');
  await expect(assistantHeaders.first()).toBeVisible({ timeout: 15000 });
  const firstHeader = await assistantHeaders.first().textContent();
  console.log(`[E2E Routing Test] Test A Routed To: "${firstHeader}"`);
  expect(firstHeader).toContain("EXECUTIVE ARCHITECT");

  // Test B: Business Intent routing to VENTURE_ARCHITECT
  console.log('[E2E Routing Test] Test B: Clearing session and reloading for Turn 2...');
  await page.evaluate(() => sessionStorage.clear());
  await page.reload();

  // Re-locate elements after page reload to prevent locator detachment
  const textareaB = page.locator('textarea');
  await expect(textareaB).toBeVisible({ timeout: 15000 });
  const sendBtnB = page.locator('.send-btn');

  console.log('[E2E Routing Test] Test B: Injecting strategic/business prompt...');
  await textareaB.fill("Analyze this market strategy for our new SaaS product.");
  await sendBtnB.click();

  console.log('[E2E Routing Test] Test B: Waiting for streaming completion...');
  await expect(textareaB).toBeEnabled({ timeout: 45000 });

  // Extract the assistant header and mathematically assert routing to VENTURE_ARCHITECT
  const assistantHeadersB = page.locator('.msg.assistant strong');
  const lastHeader = await assistantHeadersB.first().textContent();
  console.log(`[E2E Routing Test] Test B Routed To: "${lastHeader}"`);
  expect(lastHeader).toContain("VENTURE ARCHITECT");
});

test('verify C-Suite Swarm streaming and Blueprint handoff interceptor', async ({ page }) => {
  test.setTimeout(45000);
  
  await page.goto('http://localhost:5173/#/builder');
  await page.evaluate(() => sessionStorage.clear());
  await page.reload();
  
  const textarea = page.locator('textarea');
  await expect(textarea).toBeVisible({ timeout: 15000 });
  
  // Intercept the API call to return a tagged stream for C-Suite agents
  await page.route('**/api/orchestrate', async (route) => {
    const mockIdentity = '{"type": "agent_identity", "agent": "VENTURE_ARCHITECT"}\n';
    const chunk1 = '{"type": "agent_stream", "emitter": "CEO", "content": "Deliberating on strategic roadmap.\\n"}\n';
    const chunk2 = '{"type": "agent_stream", "emitter": "CMO", "content": "Marketing channels are vetted.\\n"}\n';
    const chunk3 = '{"type": "agent_stream", "emitter": "CTO", "content": "Understood. Synthesizing software blueprint contract:\\n"}\n';
    const chunk4 = '{"type": "agent_stream", "emitter": "CTO", "content": "{\\n  \\"name\\": \\"War Room Primary Infrastructure Blueprint\\",\\n  \\"version\\": \\"1.0.0\\",\\n  \\"nodes\\": [\\n    {\\n      \\"name\\": \\"Verification_Worker\\",\\n      \\"type\\": \\"verifier\\",\\n      \\"parameters\\": {\\n        \\"relative_path\\": \\"scratch/worker_status.json\\",\\n        \\"content\\": \\"ACTIVE\\"\\n      }\\n    }\\n  ]\\n}"}\n';
    
    await route.fulfill({
      status: 200,
      contentType: 'text/plain',
      body: mockIdentity + chunk1 + chunk2 + chunk3 + chunk4
    });
  });
  
  console.log('[E2E Swarm Test] Injecting business prompt for C-Suite swarm E2E...');
  await textarea.fill("Assemble boardroom debate and generate blueprint.");
  const sendBtn = page.locator('.send-btn');
  await sendBtn.click();
  
  console.log('[E2E Swarm Test] Asserting C-Suite card painting...');
  const ceoCard = page.locator('span:has-text("C-SUITE: CEO")');
  await expect(ceoCard).toBeVisible({ timeout: 15000 });
  
  const cmoCard = page.locator('span:has-text("C-SUITE: CMO")');
  await expect(cmoCard).toBeVisible({ timeout: 15000 });
  
  const ctoCard = page.locator('span:has-text("C-SUITE: CTO")');
  await expect(ctoCard).toBeVisible({ timeout: 15000 });
  
  console.log('[E2E Swarm Test] Asserting automated Blueprint Handoff Interceptor trigger...');
  const handoffMsg = page.locator('div:has-text("[BLUEPRINT HANDOFF INTERCEPTED]")').last();
  await expect(handoffMsg).toBeVisible({ timeout: 15000 });
});
