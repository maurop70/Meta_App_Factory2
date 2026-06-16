// Headless render-verifier for self-healing builds.
// Renders a served app in headless Chromium, captures load-time console/runtime/
// network errors + a screenshot, and writes a JSON report. Lives in factory_ui/
// so `playwright` and the Chromium binary resolve from the local install.
//   node verify_app.mjs <url> <screenshotPath> <reportPath>
import { chromium } from 'playwright';
import fs from 'fs';

async function main() {
  const url = process.argv[2];
  const screenshotPath = process.argv[3];
  const reportPath = process.argv[4];
  if (!url || !screenshotPath || !reportPath) {
    console.error("Usage: node verify_app.mjs <url> <screenshotPath> <reportPath>");
    process.exit(1);
  }

  const consoleErrors = [];
  const pageErrors = [];
  const networkErrors = [];

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  // Block non-local network egress: untrusted generated code may only talk to localhost.
  await page.route('**', route => {
    const requestUrl = route.request().url();
    if (
      requestUrl.startsWith('http://localhost') ||
      requestUrl.startsWith('http://127.0.0.1') ||
      requestUrl.startsWith('file://')
    ) {
      route.continue();
    } else {
      route.abort('blockedbyclient');
    }
  });

  page.on('console', msg => {
    if (msg.type() === 'error') consoleErrors.push(msg.text());
  });
  page.on('pageerror', err => {
    pageErrors.push(err.message + (err.stack ? '\n' + err.stack : ''));
  });
  page.on('requestfailed', req => {
    const failureText = req.failure()?.errorText || 'unknown';
    // Ignore requests we aborted on purpose via the egress blocker.
    if (
      failureText !== 'net::ERR_ABORTED' &&
      failureText !== 'net::ERR_BLOCKED_BY_CLIENT' &&
      failureText !== 'blockedbyclient'
    ) {
      networkErrors.push(`Failed to load ${req.url()}: ${failureText}`);
    }
  });
  page.on('response', res => {
    if (res.status() >= 400) {
      networkErrors.push(`HTTP ${res.status()} for ${res.url()}`);
    }
  });

  try {
    await page.goto(url, { waitUntil: 'networkidle', timeout: 15000 });
    await page.waitForTimeout(2000); // let dynamic rendering settle
    await page.screenshot({ path: screenshotPath, fullPage: true });
  } catch (err) {
    pageErrors.push(`Navigation failed: ${err.message}`);
  } finally {
    await browser.close();
  }

  const report = {
    url,
    success: consoleErrors.length === 0 && pageErrors.length === 0 && networkErrors.length === 0,
    consoleErrors,
    pageErrors,
    networkErrors,
    screenshotPath
  };
  fs.writeFileSync(reportPath, JSON.stringify(report, null, 2), 'utf-8');
  process.exit(0);
}

main().catch(err => {
  console.error("Verification script crashed:", err);
  process.exit(1);
});
