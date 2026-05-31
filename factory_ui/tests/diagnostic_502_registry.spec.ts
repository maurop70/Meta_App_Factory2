import { test, expect } from '@playwright/test';

test.describe('V4.0 Runtime Hotfix - App Registry 502 Diagnostics', () => {
  test('Should programmatically audit Vite proxy and direct backend port to isolate 502 faults', async ({ request }) => {
    console.log('[Diagnostic E2E] Commencing dynamic fault isolation audit.');
    
    // 1. Programmatically dispatch a raw HTTP GET request to the Vite proxy
    // Vite UI dev server runs on port 5173
    const proxyUrl = 'http://localhost:5173/api/apps/running';
    console.log(`[Diagnostic E2E] Step 1: Pinging Vite Proxy boundary at: ${proxyUrl}`);
    
    let proxyStatus = 0;
    let proxyText = '';
    try {
      const proxyRes = await request.get(proxyUrl, { timeout: 5000 });
      proxyStatus = proxyRes.status();
      proxyText = await proxyRes.text();
      console.log(`[Diagnostic E2E] Proxy response: status=${proxyStatus}`);
    } catch (err: any) {
      console.log(`[Diagnostic E2E] Proxy connection failed/timed out: ${err.message}`);
    }

    // 2. Direct HTTP GET request to physical backend port (5000)
    const backendUrl = 'http://127.0.0.1:5000/api/apps/running';
    console.log(`[Diagnostic E2E] Step 2: Pinging Direct Backend port at: ${backendUrl}`);
    
    let backendStatus = 0;
    let backendText = '';
    let backendRefused = false;
    try {
      const backendRes = await request.get(backendUrl, { timeout: 12000 });
      backendStatus = backendRes.status();
      backendText = await backendRes.text();
      console.log(`[Diagnostic E2E] Direct backend response: status=${backendStatus}`);
    } catch (err: any) {
      console.log(`[Diagnostic E2E] Direct backend failed/timed out: ${err.message}`);
      if (err.message.includes('ECONNREFUSED')) {
        backendRefused = true;
      }
    }

    // 3. Diagnostic Resolution Tree
    console.log('[Diagnostic E2E] Step 3: Assessing Diagnostic Resolution Tree conditions.');
    
    if (backendRefused) {
      console.log('─────────────────────────────────────────────────────────────────');
      console.log('[DIAGNOSTIC VERDICT] CONDITION A: Backend Dead (Connection Refused)');
      console.log('Uvicorn ASGI server has crashed or failed to start.');
      console.log('Action: AY2 must inspect startup traceback and synthesize AST mutations.');
      console.log('─────────────────────────────────────────────────────────────────');
      expect(backendRefused).toBe(false); // Force failure for Condition A visibility
    } else if (backendStatus === 200) {
      console.log('─────────────────────────────────────────────────────────────────');
      console.log('[DIAGNOSTIC VERDICT] CONDITION B: Proxy Misalignment or Backend Slow');
      console.log('Backend is alive on port 5000, but Vite proxy is misaligned or backend is blocked.');
      console.log('Action: AY2 must correct proxy routing or optimize backend handler latency.');
      console.log('─────────────────────────────────────────────────────────────────');
      // If we got a timeout, it points to synchronous blocking latency
      expect(backendStatus).toBe(200);
    } else {
      console.log(`[Diagnostic E2E] Unhandled state: proxyStatus=${proxyStatus}, backendStatus=${backendStatus}`);
      expect(backendStatus).toBe(200);
    }
  });
});
