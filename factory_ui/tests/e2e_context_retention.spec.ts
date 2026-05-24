import { test, expect } from '@playwright/test';

test('verify continuous context retention across a multi-turn conversation', async ({ page }) => {
  // Navigate to Builder Chat endpoint
  await page.goto('http://localhost:5173/#/builder');

  // Wait for the textarea to be visible
  const textarea = page.locator('textarea');
  await expect(textarea).toBeVisible({ timeout: 15000 });

  // TURN 1: Initialize parameter
  console.log('[E2E Context Test] Turn 1: Sending initialization instruction...');
  await textarea.fill("Initialize architectural parameters. Set subsystem variable to OMEGA-9.");
  
  const sendBtn = page.locator('.send-btn');
  await expect(sendBtn).toBeEnabled();
  await sendBtn.click();

  // Wait for Turn 1 response stream to finish (textarea becomes enabled again)
  console.log('[E2E Context Test] Turn 1: Waiting for streaming completion...');
  await expect(textarea).toBeEnabled({ timeout: 45000 });
  console.log('[E2E Context Test] Turn 1: Streaming completed.');

  // TURN 2: Query parameter from Turn 1 context
  console.log('[E2E Context Test] Turn 2: Querying the subsystem variable...');
  await textarea.fill("What is the current subsystem variable?");
  await sendBtn.click();

  // Wait for Turn 2 response stream to finish
  console.log('[E2E Context Test] Turn 2: Waiting for streaming completion...');
  await expect(textarea).toBeEnabled({ timeout: 45000 });
  console.log('[E2E Context Test] Turn 2: Streaming completed.');

  // Extract the last assistant response content and assert context retention
  const assistantMessages = page.locator('.msg.assistant');
  await expect(assistantMessages.first()).toBeVisible();
  
  const lastAssistantMsg = assistantMessages.last();
  const content = await lastAssistantMsg.textContent();
  console.log(`[E2E Context Test] Model's Final Response: "${content}"`);

  // Mathematically assert that Turn Two successfully retrieves context from Turn One without triggering amnesia
  expect(content).toContain("OMEGA-9");
});
