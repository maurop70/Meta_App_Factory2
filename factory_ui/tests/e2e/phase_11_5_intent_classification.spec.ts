import { test, expect } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';

test('verify Phase 11.5 Orchestrator Intent Classification Gate and Routing Bifurcation', async ({ request }) => {
  test.setTimeout(120000);
  console.log('[E2E Phase 11.5] Initiating Phase 11.5 Intent Classification Gate E2E validation...');

  const queueDir = path.resolve(process.cwd(), '../Master_Architect_Elite_Logic/ay2_dispatch_queue');
  fs.mkdirSync(queueDir, { recursive: true });

  const cleanSpoolQueue = () => {
    if (fs.existsSync(queueDir)) {
      const files = fs.readdirSync(queueDir);
      for (const file of files) {
        if (file.startsWith('pending_blueprint_') || file.startsWith('paused_blueprint_') || file.startsWith('archived_blueprint_')) {
          try { fs.unlinkSync(path.join(queueDir, file)); } catch (e) {}
        }
      }
    }
  };

  // Clean footprints initially
  cleanSpoolQueue();

  // ----------------------------------------------------
  // Scenario 1: Conversational Query Bypass (Branch A)
  // ----------------------------------------------------
  console.log('[E2E Phase 11.5] Sending conversational query to /api/orchestrate...');
  const conversationalResponse = await request.post('http://127.0.0.1:5050/api/orchestrate', {
    data: {
      description: "What is the status of the CFO agent?",
      prompt: "What is the status of the CFO agent?",
      document_ids: [],
      history: []
    }
  });

  expect(conversationalResponse.status()).toBe(200);
  const convBody = await conversationalResponse.text();

  console.log('[E2E Phase 11.5] Conversational Query SSE Output:', convBody);

  // Assert that response is a standard SSE agent_stream envelope containing conversational text
  expect(convBody).toContain('EXECUTIVE_ARCHITECT');
  expect(convBody).toContain('agent_stream');
  expect(convBody).toContain('CEO');

  // Assert that NO file is spooled in ay2_dispatch_queue
  const filesAfterConversational = fs.readdirSync(queueDir).filter(f => f.startsWith('pending_blueprint_') && f.endsWith('.json'));
  expect(filesAfterConversational.length).toBe(0);
  console.log('[E2E Phase 11.5] Scenario 1 verified successfully: No disk write and correct SSE envelope.');

  // ----------------------------------------------------
  // Scenario 2: Structural Mandate Actuation (Branch B)
  // ----------------------------------------------------
  console.log('[E2E Phase 11.5] Sending structural mandate to /api/orchestrate...');
  const structuralResponse = await request.post('http://127.0.0.1:5050/api/orchestrate', {
    data: {
      description: "[MANDATE START] Execute test",
      prompt: "[MANDATE START] Execute test",
      document_ids: [],
      history: []
    }
  });

  expect(structuralResponse.status()).toBe(200);
  const structBody = await structuralResponse.text();

  console.log('[E2E Phase 11.5] Structural Mandate SSE Output:', structBody);

  // Assert that it yields the correct SSE actuation token
  expect(structBody).toContain('[CTO Node] Blueprint spooled. IPC Bridge actuating...');

  // Assert that the JSON blueprint is successfully spooled on disk
  const filesAfterStructural = fs.readdirSync(queueDir).filter(f => (f.startsWith('pending_blueprint_') || f.startsWith('archived_blueprint_')) && f.endsWith('.json'));
  expect(filesAfterStructural.length).toBeGreaterThan(0);
  console.log(`[E2E Phase 11.5] Scenario 2 verified: Blueprint successfully spooled on disk: ${filesAfterStructural[0]}`);

  // Eradicate E2E footprints
  cleanSpoolQueue();
  console.log('[E2E Phase 11.5] Cleaned up E2E mock files. All assertions passed flawlessly!');
});
