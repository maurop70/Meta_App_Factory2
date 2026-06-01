import { test, expect } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';
import { execSync, spawn } from 'child_process';

test('verify Phase 11.4 SRE Autonomic Log Tailing Self-Healing and Spool Archival Matrix', async ({ request }) => {
  test.setTimeout(90000);
  console.log('[E2E Phase 11.4] Initiating Phase 11.4 SRE Autonomic matrix validation...');

  const queueDir = path.resolve(process.cwd(), '../Master_Architect_Elite_Logic/ay2_dispatch_queue');
  const logsDir = path.resolve(process.cwd(), '../Master_Architect_Elite_Logic/logs');

  // Ensure workspace directories exist
  fs.mkdirSync(queueDir, { recursive: true });
  fs.mkdirSync(logsDir, { recursive: true });

  // Clean any old sre patches from queue and logs
  const cleanFootprints = () => {
    if (fs.existsSync(queueDir)) {
      const files = fs.readdirSync(queueDir);
      for (const file of files) {
        if (file.includes('srepatch')) {
          try { fs.unlinkSync(path.join(queueDir, file)); } catch (e) {}
        }
      }
    }
    const mockLogPath = path.join(logsDir, 'mockerragent_runtime.log');
    if (fs.existsSync(mockLogPath)) {
      try { fs.unlinkSync(mockLogPath); } catch (e) {}
    }
  };
  cleanFootprints();

  // 1. Programmatically deploy the real PhantomSRE agent via the deploy_phantom_sre.py pipeline in the background
  console.log('[E2E Phase 11.4] Deploying PhantomSRE dynamically via background process...');
  const deployScript = path.resolve(process.cwd(), '../Master_Architect_Elite_Logic/scripts/deploy_phantom_sre.py');
  
  const pyProcess = spawn('python', ['-u', deployScript], { stdio: 'pipe' });
  let deployOutput = '';
  
  const deploymentPromise = new Promise<void>((resolve, reject) => {
    pyProcess.stdout.on('data', (data) => {
      const chunk = data.toString();
      deployOutput += chunk;
      if (chunk.includes('[SUCCESS]')) {
        console.log('[E2E Phase 11.4] SRE deployment signal captured in stdout!');
        resolve();
      }
    });
    
    pyProcess.stderr.on('data', (data) => {
      console.error('[SRE Deploy Stderr]:', data.toString());
    });
    
    pyProcess.on('close', (code) => {
      if (code !== 0 && !deployOutput.includes('[SUCCESS]')) {
        reject(new Error(`Deployment script exited with code ${code}`));
      }
    });
  });

  try {
    await Promise.race([
      deploymentPromise,
      new Promise((_, r) => setTimeout(() => r(new Error('SRE deployment timed out after 60s')), 60000))
    ]);
    console.log('[E2E Phase 11.4] Dynamic SRE Deployment succeeded in background!');
  } catch (err: any) {
    console.error('[E2E Phase 11.4] Dynamic SRE Deployment failed:', err.message);
    throw err;
  }

  // Allow uvicorn process and the startup hook log tailer task to boot up completely
  await new Promise(r => setTimeout(r, 4000));

  // 2. Query the dynamically mapped proxy route to verify SRE Active Incidents GET endpoint is live
  console.log('[E2E Phase 11.4] Confirming GET /agent/phantomsre/api/sre/incidents endpoint live...');
  const incidentsResponse = await request.get('http://127.0.0.1:5050/agent/phantomsre/api/sre/incidents', {
    headers: {
      'X-API-KEY': 'default_secret_key'
    }
  });
  expect(incidentsResponse.status()).toBe(200);
  const initialData = await incidentsResponse.json();
  expect(initialData.status).toBe('success');
  console.log('[E2E Phase 11.4] PhantomSRE incidents endpoint verified successfully!');

  // 3. Synthesize a mock traceback containing ZeroDivisionError inside mockerragent_runtime.log
  const mockLogPath = path.join(logsDir, 'mockerragent_runtime.log');
  const mockTraceback = [
    "2026-05-25 00:30:00 [MockErrAgent] INFO: Executing endpoint: /api/v1/divide",
    "Traceback (most recent call last):",
    "  File \"c:\\Dev\\Antigravity_AI_Agents\\Meta_App_Factory\\children\\mockerragent\\app.py\", line 15, in divide_by_zero",
    "    result = 1 / 0",
    "ZeroDivisionError: division by zero"
  ].join('\n');

  fs.writeFileSync(mockLogPath, mockTraceback, 'utf-8');
  console.log(`[E2E Phase 11.4] Written mock error log traceback to: ${mockLogPath}`);

  // 4. Poll and assert that the SRE background task seek-tails the log, detects it, and spools
  // a remediation blueprint with "Strategic_Pause": false directly to ay2_dispatch_queue/
  let spooledFile = null;
  let blueprintData = null;

  console.log('[E2E Phase 11.4] Auditing spool queue for SRE remediation blueprint...');
  for (let i = 0; i < 20; i++) {
    if (fs.existsSync(queueDir)) {
      const files = fs.readdirSync(queueDir).filter(f => f.includes('srepatch') && f.startsWith('pending_') && f.endsWith('.json'));
      if (files.length > 0) {
        spooledFile = files[0];
        try {
          const content = fs.readFileSync(path.join(queueDir, spooledFile), 'utf-8');
          blueprintData = JSON.parse(content);
          if (blueprintData && blueprintData.Strategic_Pause === false) {
            break;
          }
        } catch (e) {}
      }
    }
    await new Promise(r => setTimeout(r, 500));
  }

  expect(spooledFile).not.toBeNull();
  expect(blueprintData).not.toBeNull();
  expect(blueprintData.Strategic_Pause).toBe(false);
  console.log(`[E2E Phase 11.4] Autonomic self-healing blueprint successfully spooled: ${spooledFile}`);

  // 5. Poll and verify that the IPC Bridge autonomously consumes the blueprint and archives it
  let archivedFile = null;
  console.log('[E2E Phase 11.4] Auditing spool queue for archived autonomic blueprint...');
  for (let i = 0; i < 20; i++) {
    if (fs.existsSync(queueDir)) {
      const files = fs.readdirSync(queueDir).filter(f => f.includes('srepatch') && f.startsWith('archived_') && f.endsWith('.json'));
      if (files.length > 0) {
        archivedFile = files[0];
        break;
      }
    }
    await new Promise(r => setTimeout(r, 500));
  }

  expect(archivedFile).not.toBeNull();
  console.log(`[E2E Phase 11.4] IPC Bridge autonomously completed and archived blueprint: ${archivedFile}`);

  // 6. Query SRE Active Incidents list to assert that the incident was RESOLVED
  console.log('[E2E Phase 11.4] Querying incidents list for RESOLVED status verification...');
  const updatedResponse = await request.get('http://127.0.0.1:5050/agent/phantomsre/api/sre/incidents', {
    headers: {
      'X-API-KEY': 'default_secret_key'
    }
  });
  expect(updatedResponse.status()).toBe(200);
  const updatedData = await updatedResponse.json();
  const incidents = JSON.parse(updatedData.incidents);
  expect(incidents.length).toBeGreaterThan(0);
  
  const targetIncident = incidents.find((inc: any) => inc.agent_id === 'mockerragent');
  expect(targetIncident).toBeDefined();
  expect(targetIncident.status).toBe('RESOLVED');
  console.log('[E2E Phase 11.4] SRE Autonomic Incident resolved and verified in active feed ledger.');

  // Eradicate E2E footprints
  cleanFootprints();
  pyProcess.kill();
  console.log('[E2E Phase 11.4] Cleaned up E2E mock files. All assertions passed flawlessly!');
});
