const { chromium } = require('playwright');
const fs = require('fs');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();

  const consoleErrors = [];
  const networkFailures = [];
  const httpErrors = [];

  page.on('console', msg => {
    if (['error', 'warning'].includes(msg.type())) {
      consoleErrors.push(`[${msg.type().toUpperCase()}] ${msg.text()}`);
    }
  });

  page.on('requestfailed', req => {
    networkFailures.push({
      method: req.method(),
      url: req.url(),
      error: req.failure()?.errorText
    });
  });

  page.on('response', async res => {
    if (res.status() >= 400) {
      httpErrors.push({
        status: res.status(),
        url: res.url(),
        method: res.request().method()
      });
    }
  });

  // ── PHASE 1: Initial Load ──────────────────────────────────────────────────
  console.log('[PHASE 1] Loading Builder Chat...');
  await page.goto('http://localhost:5173/#/builder', {
    waitUntil: 'load',
    timeout: 30000
  });
  await page.waitForTimeout(3000);
  await page.screenshot({ path: 'scratch/phase1_initial_load.png', fullPage: true });

  // Capture initial UI error badges
  const errorBadges = await page.$$eval(
    '[class*="err"], [class*="error"], [class*="ERR"]',
    els => els.map(el => ({ text: el.innerText, class: el.className })).filter(e => e.text.trim())
  );

  // Capture status indicators
  const statusBars = await page.$$eval(
    '[class*="status"], [class*="badge"], [class*="indicator"]',
    els => els.map(el => el.innerText).filter(t => t.trim())
  );

  // ── PHASE 2: API Health Check ──────────────────────────────────────────────
  console.log('[PHASE 2] Checking API endpoints...');
  const endpoints = [
    'http://localhost:5000/api/health',
    'http://localhost:5050/api/loop/status',
    'http://localhost:5009/api/health',
    'http://localhost:9002/api/status',
    'http://localhost:5020/api/health',
    'http://localhost:5070/api/health',
    'http://localhost:5090/api/health'
  ];

  const endpointResults = [];
  for (const url of endpoints) {
    // Use page.request (Node-side HTTP, outside browser context) so the app's
    // fetch interceptor in client.js is never triggered and no global-api-error
    // events are fired during health probing.
    try {
      const res = await page.request.get(url, { timeout: 3000 });
      endpointResults.push({ url, status: res.status(), ok: res.ok() });
    } catch(e) {
      endpointResults.push({ url, status: 0, error: e.message.split('\n')[0] });
    }
  }

  // ── PHASE 3: Submit Test Intent ────────────────────────────────────────────
  console.log('[PHASE 3] Submitting test intent...');
  const inputSelectors = [
    'textarea',
    'input[type="text"]',
    '[placeholder*="Enter"]',
    '[placeholder*="brief"]',
    '[placeholder*="system"]',
    '[contenteditable="true"]'
  ];

  let inputFound = false;
  try {
    for (const sel of inputSelectors) {
      const el = await page.$(sel);
      if (el) {
        await el.click({ force: true, timeout: 5000 });
        await el.fill('system status check');
        inputFound = true;
        break;
      }
    }

    if (inputFound) {
      const sendSelectors = ['#sendBtn', 'button[type="submit"]', 'button:has-text("Send")'];
      for (const sel of sendSelectors) {
        const btn = await page.$(sel);
        if (btn) { await btn.click({ force: true, timeout: 5000 }); break; }
      }
      await page.waitForTimeout(10000);
    }
  } catch (phase3Err) {
    console.log('[PHASE 3] Input interaction failed (overlay intercept):', phase3Err.message.split('\n')[0]);
  }

  await page.screenshot({ path: 'scratch/phase3_after_submit.png', fullPage: true });
  const pageText = await page.evaluate(() => document.body.innerText);
  fs.writeFileSync('scratch/builder_page_output.txt', pageText);

  await browser.close();

  // ── REPORT ─────────────────────────────────────────────────────────────────
  const report = {
    consoleErrors,
    networkFailures,
    httpErrors,
    errorBadges,
    statusBars,
    endpointResults,
    inputFound
  };

  fs.writeFileSync('scratch/diagnostic_report.json', JSON.stringify(report, null, 2));

  console.log('\n════════════════════════════════════════');
  console.log('         BUILDER CHAT DIAGNOSTIC REPORT');
  console.log('════════════════════════════════════════');
  console.log(`\n[CONSOLE ERRORS] ${consoleErrors.length} found:`);
  consoleErrors.forEach(e => console.log(' ', e));
  console.log(`\n[NETWORK FAILURES] ${networkFailures.length} found:`);
  networkFailures.forEach(e => console.log(' ', JSON.stringify(e)));
  console.log(`\n[HTTP ERRORS] ${httpErrors.length} found:`);
  httpErrors.forEach(e => console.log(' ', JSON.stringify(e)));
  console.log(`\n[UI ERROR BADGES] ${errorBadges.length} found:`);
  errorBadges.forEach(e => console.log(' ', JSON.stringify(e)));
  console.log(`\n[ENDPOINT HEALTH]:`);
  endpointResults.forEach(e => console.log(' ', JSON.stringify(e)));
  console.log('\n════════════════════════════════════════\n');

})();
