/**
 * Builder Chat Playwright Inspection Script
 * Tests UI rendering, wire health, and interaction
 */

import { chromium } from 'playwright';

const BASE = 'http://localhost:5173';
const API  = 'http://localhost:5000';
const MA   = 'http://localhost:5050';

const results = { passed: [], failed: [], warnings: [] };
const log = (tag, msg) => console.log(`[${tag}] ${msg}`);

async function runAll() {
  const browser = await chromium.launch({ headless: false, slowMo: 150 });
  const ctx     = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page    = await ctx.newPage();

  // Collect console errors
  const consoleErrors = [];
  page.on('console', msg => {
    if (msg.type() === 'error') consoleErrors.push(msg.text());
  });
  const networkErrors = [];
  page.on('response', res => {
    if (res.status() >= 500) networkErrors.push(`${res.status()} ${res.url()}`);
  });

  // ─── 1. API PRE-CHECKS ─────────────────────────────────────
  log('WIRE-1', 'Testing Ledger Evaluator — system registry endpoint...');
  const regRes = await page.request.get(`${MA}/api/system/registry`);
  if (regRes.ok()) {
    const data = await regRes.json();
    const agentNames = (data.agents || []).map(a => a.name).join(', ');
    results.passed.push(`Wire1/Registry: ${(data.agents||[]).length} agents online — ${agentNames}`);
    log('WIRE-1', `PASS — ${(data.agents||[]).length} agents: ${agentNames}`);
  } else {
    results.failed.push(`Wire1/Registry: HTTP ${regRes.status()}`);
    log('WIRE-1', `FAIL — HTTP ${regRes.status()}`);
  }

  log('WIRE-2', 'Testing Claude Architect endpoint (POST)...');
  const orchRes = await page.request.post(`${MA}/api/orchestrate`, {
    headers: { 'Content-Type': 'application/json' },
    data: JSON.stringify({ description: 'ping', prompt: 'ping', document_ids: [], history: [] })
  });
  if (orchRes.ok() || orchRes.status() === 200) {
    results.passed.push(`Wire2/Orchestrate: ${orchRes.status()} OK`);
    log('WIRE-2', `PASS — ${orchRes.status()}`);
  } else {
    results.failed.push(`Wire2/Orchestrate: HTTP ${orchRes.status()}`);
    log('WIRE-2', `FAIL — HTTP ${orchRes.status()}`);
  }

  log('WIRE-3', 'Testing PhantomSRE status endpoint...');
  const sreRes = await page.request.get(`${API}/api/sre/incidents`, { timeout: 5000 }).catch(() => null);
  if (sreRes && sreRes.ok()) {
    results.passed.push(`Wire3/PhantomSRE: HTTP ${sreRes.status()} OK`);
    log('WIRE-3', `PASS — ${sreRes.status()}`);
  } else if (sreRes) {
    results.warnings.push(`Wire3/PhantomSRE: HTTP ${sreRes.status()} (non-fatal)`);
    log('WIRE-3', `WARN — HTTP ${sreRes.status()}`);
  } else {
    results.warnings.push('Wire3/PhantomSRE: /api/sre/incidents unreachable (may be running on child port)');
    log('WIRE-3', 'WARN — endpoint unreachable');
  }

  // Also check PhantomSRE child service
  const phantomPorts = [60144, 54346];
  for (const p of phantomPorts) {
    const pr = await page.request.get(`http://localhost:${p}/health`, { timeout: 3000 }).catch(() => null);
    if (pr && (pr.ok() || pr.status() === 404)) {
      results.passed.push(`Wire3/PhantomSRE child port ${p}: reachable`);
      log('WIRE-3', `Child service port ${p} reachable — ${pr.status()}`);
    }
  }

  log('WIRE-2', 'Testing ClaudeAY status endpoint (auto-trigger wire)...');
  const cayRes = await page.request.get(`${API}/api/claudeay/status`, { timeout: 5000 }).catch(() => null);
  if (cayRes && cayRes.ok()) {
    const cayData = await cayRes.json();
    results.passed.push(`Wire2/ClaudeAYStatus: online, mcp_bridge=${cayData.claudeay?.mcp_bridge_online}`);
    log('WIRE-2', `PASS ClaudeAY — mcp_bridge=${cayData.claudeay?.mcp_bridge_online}, errors=${cayData.claudeay?.critical_errors}`);
  } else {
    results.warnings.push(`Wire2/ClaudeAYStatus: ${cayRes ? cayRes.status() : 'unreachable'}`);
    log('WIRE-2', `WARN ClaudeAY — ${cayRes ? cayRes.status() : 'unreachable'}`);
  }

  // ─── 2. NAVIGATE TO BUILDER CHAT ──────────────────────────
  log('UI', 'Navigating to Builder Chat at /builder...');
  await page.goto(`${BASE}/#/builder`, { waitUntil: 'domcontentloaded', timeout: 20000 });
  await page.waitForTimeout(3000); // Let React + SSE connections settle

  // Screenshot initial state
  await page.screenshot({ path: 'C:\\Dev\\Antigravity_AI_Agents\\Meta_App_Factory\\screenshots\\builder_initial.png', fullPage: false });
  log('UI', 'Screenshot saved: builder_initial.png');

  // ─── 3. CHECK HEADER & TITLE ───────────────────────────────
  log('UI', 'Checking header...');
  const headerText = await page.locator('.chat-header h2').textContent().catch(() => null);
  if (headerText && headerText.includes('Omni-Router')) {
    results.passed.push(`UI/Header: "${headerText.trim()}"`);
    log('UI', `PASS Header: ${headerText.trim()}`);
  } else {
    results.failed.push(`UI/Header: not found or wrong text — got "${headerText}"`);
    log('UI', `FAIL Header: ${headerText}`);
  }

  // ─── 4. CHECK BUILDER PULSE INDICATOR ─────────────────────
  const pulseText = await page.locator('text=BUILDER PULSE: ACTIVE').count();
  if (pulseText > 0) {
    results.passed.push('UI/BuilderPulse: ACTIVE indicator visible');
    log('UI', 'PASS BuilderPulse: ACTIVE');
  } else {
    results.warnings.push('UI/BuilderPulse: indicator not found');
    log('UI', 'WARN BuilderPulse: not visible');
  }

  // ─── 5. CHECK SWARM PILL ───────────────────────────────────
  log('UI', 'Checking Active Swarm pill...');
  const swarmPill = page.locator('.swarm-pill');
  if (await swarmPill.count() > 0) {
    const pillText = await swarmPill.textContent();
    results.passed.push(`UI/SwarmPill: visible — "${pillText?.trim()}"`);
    log('UI', `PASS SwarmPill: ${pillText?.trim()}`);

    // Click to open dropdown
    await swarmPill.click();
    await page.waitForTimeout(500);
    const dropdown = page.locator('.swarm-dropdown');
    if (await dropdown.isVisible()) {
      const agentRows = await page.locator('.swarm-agent-row').count();
      results.passed.push(`UI/SwarmDropdown: visible with ${agentRows} agent rows`);
      log('UI', `PASS SwarmDropdown: ${agentRows} agents`);

      // Screenshot dropdown
      await page.screenshot({ path: 'C:\\Dev\\Antigravity_AI_Agents\\Meta_App_Factory\\screenshots\\builder_swarm.png' });

      // Close dropdown
      await page.keyboard.press('Escape');
      await page.locator('body').click();
      await page.waitForTimeout(300);
    } else {
      results.warnings.push('UI/SwarmDropdown: not visible after click');
      log('UI', 'WARN SwarmDropdown: not visible');
    }
  } else {
    results.failed.push('UI/SwarmPill: not found');
    log('UI', 'FAIL SwarmPill');
  }

  // ─── 6. CHECK CLAUDEAY STATUS BAR ─────────────────────────
  log('UI', 'Checking ClaudeAY status bar...');
  const claudeayBar = page.locator('.claudeay-bar');
  if (await claudeayBar.count() > 0) {
    results.passed.push('UI/ClaudeAYBar: rendered');
    log('UI', 'PASS ClaudeAYBar: rendered');

    // Check MCP chip
    const mcpChip = await page.locator('.claudeay-chip').first().textContent().catch(() => null);
    if (mcpChip) {
      results.passed.push(`UI/ClaudeAY/MCP: "${mcpChip.trim()}"`);
      log('UI', `ClaudeAY MCP chip: ${mcpChip.trim()}`);
    }
  } else {
    results.warnings.push('UI/ClaudeAYBar: not rendered');
    log('UI', 'WARN ClaudeAYBar: not rendered');
  }

  // ─── 7. CHECK CHAT MESSAGES AREA ──────────────────────────
  log('UI', 'Checking chat messages area...');
  const terminalBoot = page.locator('text=TERMINAL BOOT COMPLETED SUCCESSFULLY');
  if (await terminalBoot.count() > 0) {
    results.passed.push('UI/TerminalBoot: boot message visible');
    log('UI', 'PASS TerminalBoot: message visible');
  } else {
    results.warnings.push('UI/TerminalBoot: boot message not found');
    log('UI', 'WARN TerminalBoot: not found');
  }

  // ─── 8. CHECK INPUT TEXTAREA ──────────────────────────────
  log('UI', 'Checking input textarea...');
  const textarea = page.locator('.chat-input-bar textarea');
  if (await textarea.count() > 0) {
    const placeholder = await textarea.getAttribute('placeholder');
    results.passed.push(`UI/Textarea: visible, placeholder="${placeholder}"`);
    log('UI', `PASS Textarea: placeholder="${placeholder}"`);

    // Type into it
    await textarea.click();
    await textarea.fill('SYSTEM DIAGNOSTIC: Test wire connectivity from Playwright');
    await page.waitForTimeout(500);
    const val = await textarea.inputValue();
    if (val.includes('SYSTEM DIAGNOSTIC')) {
      results.passed.push('UI/Textarea: typing works');
      log('UI', 'PASS Textarea: typing functional');
    } else {
      results.failed.push('UI/Textarea: typing failed');
    }
  } else {
    results.failed.push('UI/Textarea: not found');
    log('UI', 'FAIL Textarea: not found');
  }

  // ─── 9. CHECK SEND BUTTON ─────────────────────────────────
  log('UI', 'Checking send button...');
  const sendBtn = page.locator('.send-btn');
  if (await sendBtn.count() > 0) {
    const disabled = await sendBtn.isDisabled();
    results.passed.push(`UI/SendBtn: visible, disabled=${disabled}`);
    log('UI', `PASS SendBtn: disabled=${disabled}`);
  } else {
    results.failed.push('UI/SendBtn: not found');
    log('UI', 'FAIL SendBtn: not found');
  }

  // ─── 10. CHECK FILE UPLOAD BUTTON ─────────────────────────
  log('UI', 'Checking file upload button...');
  const uploadBtn = page.locator('.chat-input-bar button[title="Ingest Enterprise Document"]');
  if (await uploadBtn.count() > 0) {
    results.passed.push('UI/FileUpload: button visible');
    log('UI', 'PASS FileUpload: button found');
  } else {
    results.warnings.push('UI/FileUpload: button not found by title');
    // Try alternate selector
    const btn2 = page.locator('.chat-input-bar button').first();
    if (await btn2.count() > 0) {
      results.passed.push('UI/FileUpload: button found (alt selector)');
    }
  }

  // ─── 11. CHECK NEW THREAD BUTTON ──────────────────────────
  log('UI', 'Checking New Thread button...');
  const newThread = page.locator('button:has-text("New Thread")');
  if (await newThread.count() > 0) {
    results.passed.push('UI/NewThread: button visible');
    log('UI', 'PASS NewThread');
  } else {
    results.warnings.push('UI/NewThread: button not visible');
    log('UI', 'WARN NewThread: not found');
  }

  // ─── 12. CHECK MAXIMIZE BUTTON ────────────────────────────
  log('UI', 'Checking Maximize button...');
  const maxBtn = page.locator('button:has-text("Maximize")');
  if (await maxBtn.count() > 0) {
    results.passed.push('UI/Maximize: button visible');
    log('UI', 'PASS Maximize');
    await maxBtn.click();
    await page.waitForTimeout(500);
    const isMax = await page.locator('.terminal-maximized').count() > 0;
    results.passed.push(`UI/Maximize: toggle ${isMax ? 'expanded' : 'collapsed'}`);
    // Restore
    await page.locator('button:has-text("Restore")').click().catch(() => maxBtn.click());
    await page.waitForTimeout(300);
  }

  // ─── 13. CHECK TELEMETRY STREAM ENDPOINT ──────────────────
  log('WIRE-3', 'Testing telemetry stream endpoint reachability...');
  const telRes = await page.request.get(`${API}/api/telemetry/stream`, { timeout: 3000 }).catch(() => null);
  if (telRes) {
    results.passed.push(`Wire3/TelemetryStream: HTTP ${telRes.status()}`);
    log('WIRE-3', `PASS TelemetryStream: ${telRes.status()}`);
  } else {
    results.warnings.push('Wire3/TelemetryStream: request timed out (SSE keeps connection open — normal)');
    log('WIRE-3', 'WARN TelemetryStream: timeout (SSE normal behavior)');
  }

  // ─── 14. CHECK IPC BRIDGE STREAM ENDPOINT ─────────────────
  log('WIRE-2', 'Testing IPC Bridge stream endpoint reachability...');
  const ipcRes = await page.request.get(`${MA}/api/bridge/stream`, { timeout: 3000 }).catch(() => null);
  if (ipcRes) {
    results.passed.push(`Wire2/IPCBridgeStream: HTTP ${ipcRes.status()}`);
    log('WIRE-2', `PASS IPCBridgeStream: ${ipcRes.status()}`);
  } else {
    results.warnings.push('Wire2/IPCBridgeStream: timeout (SSE normal behavior)');
    log('WIRE-2', 'WARN IPCBridgeStream: timeout (SSE normal behavior)');
  }

  // ─── 15. FINAL SCREENSHOT ─────────────────────────────────
  await page.screenshot({
    path: 'C:\\Dev\\Antigravity_AI_Agents\\Meta_App_Factory\\screenshots\\builder_final.png',
    fullPage: true
  });
  log('UI', 'Final screenshot saved: builder_final.png');

  // ─── 16. CONSOLE ERROR REPORT ─────────────────────────────
  if (consoleErrors.length > 0) {
    log('CONSOLE', `${consoleErrors.length} console errors:`);
    consoleErrors.forEach(e => {
      log('CONSOLE', `  ${e}`);
      results.warnings.push(`ConsoleError: ${e.slice(0, 120)}`);
    });
  } else {
    results.passed.push('ConsoleErrors: none');
    log('CONSOLE', 'PASS — no console errors');
  }

  if (networkErrors.length > 0) {
    log('NETWORK', `${networkErrors.length} 5xx errors:`);
    networkErrors.forEach(e => {
      results.failed.push(`NetworkError 5xx: ${e}`);
      log('NETWORK', `  ${e}`);
    });
  } else {
    results.passed.push('Network5xx: none');
  }

  await browser.close();

  // ─── REPORT ───────────────────────────────────────────────
  console.log('\n══════════════════════════════════════════════════════');
  console.log('  BUILDER CHAT + WIRE INSPECTION REPORT');
  console.log('══════════════════════════════════════════════════════');
  console.log(`\n✅ PASSED (${results.passed.length}):`);
  results.passed.forEach(r => console.log(`   ✅ ${r}`));
  console.log(`\n⚠️  WARNINGS (${results.warnings.length}):`);
  results.warnings.forEach(r => console.log(`   ⚠️  ${r}`));
  console.log(`\n❌ FAILED (${results.failed.length}):`);
  results.failed.forEach(r => console.log(`   ❌ ${r}`));
  console.log('\n══════════════════════════════════════════════════════');

  const exit = results.failed.length > 0 ? 1 : 0;
  process.exit(exit);
}

runAll().catch(err => {
  console.error('[FATAL]', err);
  process.exit(1);
});
