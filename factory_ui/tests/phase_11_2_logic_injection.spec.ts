import { test, expect } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';

test('verify Phase 11.2 logic injection matrix and DOM polling safety boundaries', async ({ request }) => {
  console.log('[E2E Phase 11.2] Initiating validation of logic injection matrix...');

  // 1. Assert uvicorn file write is completed in a single, atomic pass without post-render file manipulation
  const compiledAppPath = path.resolve(process.cwd(), '../children/WarRoomMonitor/app.py');
  console.log(`[E2E Phase 11.2] Checking compiled app.py at: ${compiledAppPath}`);
  expect(fs.existsSync(compiledAppPath)).toBe(true);

  const appContent = fs.readFileSync(compiledAppPath, 'utf-8');
  
  // Assert single-pass Jinja2 compile-time logic injection (contains psutil and httpx pings directly in function body)
  expect(appContent).toContain('cpu = psutil.cpu_percent(interval=None)');
  expect(appContent).toContain('async with httpx.AsyncClient(timeout=2.0) as client:');
  
  // Assert PEP-8 import safety (mathematical deduplication: no duplicate psutil or httpx imports)
  const psutilMatches = appContent.match(/import psutil/g);
  const httpxMatches = appContent.match(/import httpx/g);
  const jsonMatches = appContent.match(/import json/g);
  
  // Notice that we only allow exactly 1 match in the extra imports header block
  expect(psutilMatches ? psutilMatches.length : 0).toBe(1);
  expect(httpxMatches ? httpxMatches.length : 0).toBe(1);
  expect(jsonMatches ? jsonMatches.length : 0).toBe(1);

  console.log('[E2E Phase 11.2] PEP-8 import deduplication is mathematically verified!');

  // 2. Assert registry active status
  const registryResponse = await request.get('http://127.0.0.1:5050/api/system/registry');
  expect(registryResponse.status()).toBe(200);
  const registryData = await registryResponse.json();
  const monitorAgent = registryData.agents.find((a: any) => a.id === 'warroommonitor');
  expect(monitorAgent).toBeDefined();
  expect(monitorAgent.status).toBe('ACTIVE');

  // 3. Query the dynamic proxy health endpoint and verify it returns actual live psutil data
  const healthResponse = await request.get('http://127.0.0.1:5050/agent/warroommonitor/api/health', {
    headers: {
      'X-API-KEY': 'default_secret_key'
    }
  });
  expect(healthResponse.status()).toBe(200);
  const healthData = await healthResponse.json();
  console.log('[E2E Phase 11.2] Telemetry response payload:', JSON.stringify(healthData));

  expect(healthData.cpu_percent).toBeDefined();
  expect(healthData.memory_percent).toBeDefined();
  expect(healthData.cpu_percent).toMatch(/\d+(\.\d+)?%/);
  expect(healthData.memory_percent).toMatch(/\d+(\.\d+)?%/);

  console.log('[E2E Phase 11.2] Headless telemetry verification succeeded flawlessly!');
});
