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

test('verify Context Flush [➕ New Thread] clears session state', async ({ page }) => {
  await page.goto('http://localhost:5173/#/builder');
  
  // Set some session storage items
  await page.evaluate(() => {
    sessionStorage.setItem('ma_chat_history', JSON.stringify([{ role: 'user', content: 'test message' }]));
    sessionStorage.setItem('ma_cached_document_ids', JSON.stringify(['doc-123']));
  });
  await page.reload();
  
  // Locate the reset button and click it
  const newThreadBtn = page.locator('button:has-text("[➕ New Thread]")');
  await expect(newThreadBtn).toBeVisible({ timeout: 15000 });
  await newThreadBtn.click();
  
  // Assert state is cleared
  const chatHistoryLength = await page.evaluate(() => {
    const history = sessionStorage.getItem('ma_chat_history');
    return history ? JSON.parse(history).length : 0;
  });
  
  // We added a system reset message, so history length is 1
  expect(chatHistoryLength).toBe(1);
  
  const cachedDocIdsLength = await page.evaluate(() => {
    const docs = sessionStorage.getItem('ma_cached_document_ids');
    return docs ? JSON.parse(docs).length : 0;
  });
  expect(cachedDocIdsLength).toBe(0);
});

test('verify Socratic strategic pause locking and submit loop', async ({ page }) => {
  test.setTimeout(30000);
  
  await page.goto('http://localhost:5173/#/builder');
  await page.evaluate(() => sessionStorage.clear());
  await page.reload();
  
  const textarea = page.locator('textarea.flex-1');
  await expect(textarea).toBeVisible({ timeout: 15000 });
  
  // Intercept the API to yield a socratic_pause event
  await page.route('**/api/orchestrate', async (route) => {
    const mockIdentity = '{"type": "agent_identity", "agent": "VENTURE_ARCHITECT"}\n';
    const chunk1 = '{"type": "agent_stream", "emitter": "CEO", "content": "Roadmap initiated...\\n"}\n';
    const chunk2 = '{"type": "socratic_pause", "challenge_id": "CHG-E2E-999", "weaknesses": [{"category": "Scalability", "severity": "HIGH", "challenge": "No scale plan", "required_evidence": "Provide scale evidence"}]}\n';
    
    await route.fulfill({
      status: 200,
      contentType: 'text/plain',
      body: mockIdentity + chunk1 + chunk2
    });
  });

  // Intercept evaluate endpoint
  await page.route('**/api/challenge/evaluate', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        verdict: 'CONVINCED',
        combined_score: 9.6,
        message: 'Critic satisfied.'
      })
    });
  });
  
  console.log('[E2E Socratic Test] Triggering strategic pause stream...');
  await textarea.fill("Strategy with gaps");
  const sendBtn = page.locator('.send-btn');
  await sendBtn.click();
  
  console.log('[E2E Socratic Test] Asserting Socratic Challenge Form mount and Lock...');
  const challengeTitle = page.locator('span:has-text("ADVERSARIAL CHALLENGE: CHG-E2E-999")');
  await expect(challengeTitle).toBeVisible({ timeout: 15000 });
  
  // Verify standard input is locked/disabled
  await expect(textarea).toBeDisabled();
  
  // Fill the Socratic evidence and submit
  const evidenceTextarea = page.locator('textarea[placeholder*="Provide data-driven evidence"]');
  await expect(evidenceTextarea).toBeVisible();
  await evidenceTextarea.fill("Our test benchmark proves scaling up to 10K RPS.");
  
  const submitBtn = page.locator('button:has-text("Submit Evidence")');
  await submitBtn.click();
  
  console.log('[E2E Socratic Test] Asserting lock released after convinced evaluation...');
  // Standard textarea should be re-enabled
  await expect(textarea).toBeEnabled({ timeout: 15000 });
  // Socratic form should disappear
  await expect(challengeTitle).not.toBeVisible();
});
