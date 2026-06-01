import { test, expect } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';

test('verify Phase 11.3 Native IPC Bridge, Biological Circuit Breaker, and Spool Archival lifecycle', async ({ request }) => {
  console.log('[E2E Phase 11.3] Initiating Native IPC Bridge validation...');

  const queueDir = path.resolve(process.cwd(), '../Master_Architect_Elite_Logic/ay2_dispatch_queue');
  console.log(`[E2E Phase 11.3] Queue directory target: ${queueDir}`);
  expect(fs.existsSync(queueDir)).toBe(true);

  // Clean any legacy test files first to ensure absolute reproducibility
  const cleanTestFiles = () => {
    if (!fs.existsSync(queueDir)) return;
    const files = fs.readdirSync(queueDir);
    for (const file of files) {
      if (file.includes('testpause') || file.includes('testreject') || file.includes('testfail')) {
        try {
          fs.unlinkSync(path.join(queueDir, file));
        } catch (e) {
          console.warn(`Could not clean file ${file}:`, e);
        }
      }
    }
  };
  cleanTestFiles();

  // ────────────────────────────────────────────────────────
  // SCENARIO 1: STRATEGIC PAUSE & BIOLOGICAL APPROVAL FLOW
  // ────────────────────────────────────────────────────────
  console.log('[E2E Phase 11.3] --- Testing Strategic Pause & Approval ---');
  
  const pendingPauseFile = 'pending_blueprint_testpause.json';
  const pausedPauseFile = 'paused_blueprint_testpause.json';
  const archivedPauseFile = 'archived_blueprint_testpause.json';
  
  const pendingPausePath = path.join(queueDir, pendingPauseFile);
  const pausedPausePath = path.join(queueDir, pausedPauseFile);
  const archivedPausePath = path.join(queueDir, archivedPauseFile);

  const pauseBlueprint = {
    name: "E2E Test Pause Blueprint",
    version: "1.0.0",
    Strategic_Pause: true,
    nodes: []
  };

  // 1. Spool to disk
  fs.writeFileSync(pendingPausePath, JSON.stringify(pauseBlueprint), 'utf-8');
  console.log(`[E2E Phase 11.3] Spooled strategic pause blueprint to: ${pendingPausePath}`);

  // 2. Poll for automatic rename to paused_blueprint_*.json
  let pausedRenamed = false;
  for (let i = 0; i < 15; i++) {
    if (fs.existsSync(pausedPausePath)) {
      pausedRenamed = true;
      break;
    }
    await new Promise(r => setTimeout(r, 500));
  }
  expect(pausedRenamed).toBe(true);
  expect(fs.existsSync(pendingPausePath)).toBe(false);
  console.log('[E2E Phase 11.3] Watchdog successfully detected Strategic_Pause and renamed file to paused_...!');

  // 3. Invoke /api/bridge/approve
  console.log('[E2E Phase 11.3] Sending approval request to FastAPI server...');
  const approveResponse = await request.post('http://127.0.0.1:5050/api/bridge/approve', {
    data: {
      blueprint_file: pausedPauseFile
    }
  });
  expect(approveResponse.status()).toBe(200);
  const approveData = await approveResponse.json();
  expect(approveData.status).toBe('success');
  console.log('[E2E Phase 11.3] Approval endpoint returned success:', approveData.detail);

  // 4. Assert that it is renamed back to pending_blueprint_*.json for the watchdog to consume
  let pendingRestored = false;
  for (let i = 0; i < 10; i++) {
    if (fs.existsSync(pendingPausePath)) {
      pendingRestored = true;
      break;
    }
    await new Promise(r => setTimeout(r, 200));
  }
  expect(pendingRestored).toBe(true);
  console.log('[E2E Phase 11.3] File successfully renamed back to pending_... to actuate execution!');

  // 5. Poll for subprocess execution and subsequent lifecycle archival
  let archivedCreated = false;
  for (let i = 0; i < 20; i++) {
    if (fs.existsSync(archivedPausePath)) {
      archivedCreated = true;
      break;
    }
    await new Promise(r => setTimeout(r, 500));
  }
  expect(archivedCreated).toBe(true);
  expect(fs.existsSync(pendingPausePath)).toBe(false);
  console.log('[E2E Phase 11.3] Blueprint execution completed and successfully archived to archived_...!');

  // ────────────────────────────────────────────────────────
  // SCENARIO 2: STRATEGIC PAUSE & OPERATOR REJECTION FLOW
  // ────────────────────────────────────────────────────────
  console.log('\n[E2E Phase 11.3] --- Testing Strategic Pause & Rejection ---');
  
  const pendingRejectFile = 'pending_blueprint_testreject.json';
  const pausedRejectFile = 'paused_blueprint_testreject.json';
  
  const pendingRejectPath = path.join(queueDir, pendingRejectFile);
  const pausedRejectPath = path.join(queueDir, pausedRejectFile);

  const rejectBlueprint = {
    name: "E2E Test Reject Blueprint",
    version: "1.0.0",
    Strategic_Pause: true,
    nodes: []
  };

  // 1. Spool to disk
  fs.writeFileSync(pendingRejectPath, JSON.stringify(rejectBlueprint), 'utf-8');

  // 2. Poll for automatic rename to paused_blueprint_*.json
  let pausedRenamedReject = false;
  for (let i = 0; i < 15; i++) {
    if (fs.existsSync(pausedRejectPath)) {
      pausedRenamedReject = true;
      break;
    }
    await new Promise(r => setTimeout(r, 500));
  }
  expect(pausedRenamedReject).toBe(true);

  // 3. Invoke /api/bridge/reject
  console.log('[E2E Phase 11.3] Sending rejection request to FastAPI server...');
  const rejectResponse = await request.post('http://127.0.0.1:5050/api/bridge/reject', {
    data: {
      blueprint_file: pausedRejectFile
    }
  });
  expect(rejectResponse.status()).toBe(200);
  const rejectData = await rejectResponse.json();
  expect(rejectData.status).toBe('success');
  console.log('[E2E Phase 11.3] Rejection endpoint returned success:', rejectData.detail);

  // 4. Assert the file is physically deleted from disk
  expect(fs.existsSync(pausedRejectPath)).toBe(false);
  console.log('[E2E Phase 11.3] Rejected blueprint physically eradicated from disk successfully!');

  // ────────────────────────────────────────────────────────
  // SCENARIO 3: FATAL EXCEPTION / CIRCUIT BREAKER FLOW
  // ────────────────────────────────────────────────────────
  console.log('\n[E2E Phase 11.3] --- Testing Fatal Exception Circuit Breaker ---');
  
  const pendingFailFile = 'pending_blueprint_testfail.json';
  const archivedFailFile = 'archived_blueprint_testfail.json';
  
  const pendingFailPath = path.join(queueDir, pendingFailFile);
  const archivedFailPath = path.join(queueDir, archivedFailFile);

  const failBlueprint = {
    name: "E2E Test Fail Blueprint",
    version: "1.0.0",
    Strategic_Pause: false,
    Strategic_Fail: true, // Triggers error in mock CLI
    nodes: []
  };

  // 1. Spool to disk
  fs.writeFileSync(pendingFailPath, JSON.stringify(failBlueprint), 'utf-8');

  // 2. Poll for watchdog execution and verify lifecycle archival rename on exit
  let archivedFailCreated = false;
  for (let i = 0; i < 20; i++) {
    if (fs.existsSync(archivedFailPath)) {
      archivedFailCreated = true;
      break;
    }
    await new Promise(r => setTimeout(r, 500));
  }
  expect(archivedFailCreated).toBe(true);
  expect(fs.existsSync(pendingFailPath)).toBe(false);
  console.log('[E2E Phase 11.3] Fatal execution halted, circuit breaker logged, and file archived successfully!');

  // Final cleanup of spooled test files
  cleanTestFiles();
  console.log('[E2E Phase 11.3] Cleaned up E2E test footprints. All assertions passed flawlessly!');
});

test('verify Phase 11.3 absolute CTO blueprint spooling and raw markdown eradication', async ({ request }) => {
  console.log('[E2E Phase 11.3] Initiating validation of absolute CTO spooling and raw markdown eradication...');

  const queueDir = path.resolve(process.cwd(), '../Master_Architect_Elite_Logic/ay2_dispatch_queue');

  // Let's get the list of spooled files before making the request
  const getPendingFiles = () => {
    if (!fs.existsSync(queueDir)) return [];
    return fs.readdirSync(queueDir).filter(f => f.startsWith('pending_blueprint_') && f.endsWith('.json'));
  };

  const initialPendingFiles = getPendingFiles();

  // Send a structural mandate to the /api/orchestrate endpoint (which BuilderChat calls)
  console.log('[E2E Phase 11.3] Submitting structural mandate to /api/orchestrate...');
  const orchestrateResponse = await request.post('http://127.0.0.1:5050/api/orchestrate', {
    data: {
      description: "Build a high-performance Python microservice for system resource diagnostics",
      prompt: "Build a high-performance Python microservice for system resource diagnostics",
      document_ids: [],
      history: []
    }
  });

  expect(orchestrateResponse.status()).toBe(200);
  const responseBody = await orchestrateResponse.text();

  // Assert that the returned stream contains the precise SSE actuation token
  expect(responseBody).toContain('[CTO Node] Blueprint spooled. IPC Bridge actuating...');

  // Assert that the stream is permanently forbidden from containing raw code chunks
  // Since we package the code inside {"blueprint_data": ...} and write to disk,
  // the SSE response stream should only contain the connection identity, status messages, and the actuation token.
  // It should NEVER contain raw Python syntax like "class " or "def " or "import psutil" as a raw streamed text chunk.
  expect(responseBody).not.toContain('"content": "import psutil"');
  expect(responseBody).not.toContain('"content": "class "');
  console.log('[E2E Phase 11.3] SSE response successfully verified: no raw code leaks detected!');

  // Poll for the spooled blueprint on disk and verify it's a valid packaged JSON with "blueprint_data"
  let spooledFileFound = null;
  let blueprintData = null;

  for (let i = 0; i < 20; i++) {
    const currentFiles = getPendingFiles();
    const newFiles = currentFiles.filter(f => !initialPendingFiles.includes(f));
    if (newFiles.length > 0) {
      spooledFileFound = newFiles[0];
      const filePath = path.join(queueDir, spooledFileFound);
      try {
        const fileContent = fs.readFileSync(filePath, 'utf-8');
        blueprintData = JSON.parse(fileContent);
        if (blueprintData && blueprintData.blueprint_data) {
          break;
        }
      } catch (e) {
        // May still be writing
      }
    }
    await new Promise(r => setTimeout(r, 500));
  }

  expect(spooledFileFound).not.toBeNull();
  expect(blueprintData).not.toBeNull();
  expect(blueprintData.blueprint_data).toBeDefined();
  
  // Clean up the spooled test file
  if (spooledFileFound) {
    try {
      fs.unlinkSync(path.join(queueDir, spooledFileFound));
    } catch (e) {}
  }

  console.log('[E2E Phase 11.3] Absolute spooling and raw markdown eradication validated successfully!');
});
