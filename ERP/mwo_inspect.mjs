/**
 * MWO App — Full Visual Inspection via Playwright
 * Covers every role, every screen, every tab. Report only — no changes.
 */

import { chromium } from 'playwright';
import { mkdirSync } from 'fs';

const BASE = 'http://localhost:5175';
const SHOTS = 'C:\\Dev\\Antigravity_AI_Agents\\Meta_App_Factory\\ERP\\screenshots';
mkdirSync(SHOTS, { recursive: true });

const CREDS = {
  admin: { id: 'ERP-1000', pin: '1234',  role: 'ADMINISTRATOR' },
  hm:    { id: 'ERP-2000', pin: '2345',  role: 'HM' },
  tech:  { id: 'ERP-3000', pin: '3456',  role: 'TECHNICIAN' },
};

const results = {
  working:    [],
  broken:     [],
  incomplete: [],
  features:   [],
  apiErrors:  [],
  consoleErr: [],
};

const shot = async (page, name) => {
  await page.screenshot({ path: `${SHOTS}\\${name}.png`, fullPage: true });
};

const log = (tag, msg) => console.log(`[${tag}] ${msg}`);

// ── Login helper ───────────────────────────────────────────────
async function loginAs(page, cred) {
  await page.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded', timeout: 15000 });
  await page.waitForTimeout(600);
  await page.fill("input[name='mwo_operator_id']", cred.id);
  await page.fill("input[name='mwo_operator_pin']", cred.pin);
  await page.click("button[type='submit']");
  await page.waitForTimeout(2000);
  const url = page.url();
  return url;
}

async function logout(page) {
  // Try logout button
  const btn = page.locator('button:has-text("Terminate Session"), button:has-text("Logout"), button:has-text("Sign Out")');
  if (await btn.count() > 0) {
    await btn.first().click();
    await page.waitForTimeout(1000);
  } else {
    await page.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded' });
  }
  // Clear storage
  await page.evaluate(() => { localStorage.clear(); sessionStorage.clear(); });
}

// ── Check for visible error states ────────────────────────────
async function checkForErrors(page, context) {
  const errSelectors = [
    'text=Error', 'text=404', 'text=500', 'text=Failed', 'text=undefined',
    'text=NaN', 'text=null', '.error', '[class*="error"]',
    'text=Cannot read', 'text=is not a function'
  ];
  const found = [];
  for (const sel of errSelectors) {
    try {
      const count = await page.locator(sel).count();
      if (count > 0) {
        const text = await page.locator(sel).first().textContent().catch(() => sel);
        if (text && text.length < 200) found.push(text.trim().slice(0, 80));
      }
    } catch (_) {}
  }
  if (found.length) results.broken.push(`${context}: visible error text — ${[...new Set(found)].join(' | ')}`);
  return found.length;
}

// ── Inspect a table/grid ──────────────────────────────────────
async function inspectTable(page, context) {
  const rows = await page.locator('table tbody tr, [class*="row"], [class*="entry"]').count();
  const empty = await page.locator('text=No data, text=No records, text=Empty, text=No work orders, text=No results').count();
  if (empty) results.incomplete.push(`${context}: shows empty-state (no data)`);
  else if (rows > 0) results.working.push(`${context}: table rendered with ${rows} rows`);
  else results.incomplete.push(`${context}: table present but 0 rows found`);
  return rows;
}

// ─────────────────────────────────────────────────────────────
async function runAll() {
  const browser = await chromium.launch({ headless: false, slowMo: 120 });
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await ctx.newPage();

  // Collect console errors & network errors globally
  page.on('console', msg => {
    if (msg.type() === 'error') {
      const t = msg.text();
      if (!t.includes('favicon') && !t.includes('ERR_BLOCKED')) {
        results.consoleErr.push(t.slice(0, 120));
      }
    }
  });
  page.on('response', res => {
    const url = res.url();
    if (url.includes('localhost') && res.status() >= 400) {
      results.apiErrors.push(`HTTP ${res.status()} — ${url.replace(/https?:\/\/localhost:\d+/, '')}`);
    }
  });

  // ══════════════════════════════════════════════════════════════
  //  1. LOGIN PAGE
  // ══════════════════════════════════════════════════════════════
  log('LOGIN', 'Inspecting login page...');
  await page.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded', timeout: 15000 });
  await page.waitForTimeout(800);
  await shot(page, '01_login');
  results.features.push('Login page: Employee ID + PIN form');

  // Check form elements
  const idInput  = await page.locator("input[name='mwo_operator_id']").count();
  const pinInput = await page.locator("input[name='mwo_operator_pin']").count();
  const submitBtn = await page.locator("button[type='submit']").count();
  if (idInput && pinInput && submitBtn) results.working.push('Login: form renders with ID + PIN + submit button');
  else results.broken.push('Login: one or more form inputs missing');

  // Bad credentials test
  log('LOGIN', 'Testing bad credentials...');
  await page.fill("input[name='mwo_operator_id']", 'BAD-USER');
  await page.fill("input[name='mwo_operator_pin']", '0000');
  await page.click("button[type='submit']");
  await page.waitForTimeout(1500);
  const errMsg = await page.locator('.erp-status-message.error, [class*="error"]').count();
  if (errMsg > 0) results.working.push('Login: bad-credentials shows error message');
  else results.broken.push('Login: bad-credentials — no error feedback shown');
  await shot(page, '02_login_error');

  // ══════════════════════════════════════════════════════════════
  //  2. ADMIN CONSOLE
  // ══════════════════════════════════════════════════════════════
  log('ADMIN', 'Logging in as ADMINISTRATOR...');
  const adminUrl = await loginAs(page, CREDS.admin);
  log('ADMIN', `Landed at: ${adminUrl}`);
  if (adminUrl.includes('/admin')) results.working.push('Admin login: redirected to /admin correctly');
  else results.broken.push(`Admin login: unexpected redirect to ${adminUrl}`);
  await shot(page, '03_admin_landing');

  // Check header
  const adminHeader = await page.locator('text=Admin Command Console').count();
  if (adminHeader) results.working.push('Admin Console: header renders');
  else results.broken.push('Admin Console: header not found');

  const tabLabels = ['Data Ingestion', 'DM View', 'HM View', 'Tech View', 'Procurement', 'Dispatch Queue'];
  results.features.push(`Admin Console: ${tabLabels.length} tabs — ${tabLabels.join(', ')}`);

  // ── Tab: Dispatch Queue (default) ────────────────────────────
  log('ADMIN', 'Checking Dispatch Queue tab (default)...');
  await page.waitForTimeout(1500);
  await shot(page, '04_admin_dispatch');
  await inspectTable(page, 'Admin/DispatchQueue');
  await checkForErrors(page, 'Admin/DispatchQueue');

  // ── Tab: DM View ─────────────────────────────────────────────
  log('ADMIN', 'Switching to DM View tab...');
  await page.locator('button:has-text("DM View")').click();
  await page.waitForTimeout(1200);
  await shot(page, '05_admin_dm_view');
  const dmForm = await page.locator('form, [class*="form"], textarea, select').count();
  if (dmForm > 0) results.working.push('Admin/DM View: MWO creation form rendered');
  else results.incomplete.push('Admin/DM View: no form elements detected');
  await checkForErrors(page, 'Admin/DMView');
  results.features.push('DM View: Create Maintenance Work Order form');

  // Check form fields in DM view
  const selects = await page.locator('select').count();
  const inputs  = await page.locator('input[type="text"], input[type="date"], textarea').count();
  results.features.push(`DM View form: ${selects} dropdowns, ${inputs} text inputs`);
  const submitMWO = await page.locator('button[type="submit"], button:has-text("Submit"), button:has-text("Create")').count();
  if (submitMWO) results.working.push('DM View: Submit MWO button present');
  else results.broken.push('DM View: No submit button found');

  // ── Tab: HM View ─────────────────────────────────────────────
  log('ADMIN', 'Switching to HM View tab...');
  await page.locator('button:has-text("HM View")').click();
  await page.waitForTimeout(1500);
  await shot(page, '06_admin_hm_view');
  await checkForErrors(page, 'Admin/HMView');
  const hmCards = await page.locator('[class*="card"], [class*="mwo"], [class*="work-order"], table tbody tr').count();
  if (hmCards > 0) results.working.push(`Admin/HM View: ${hmCards} MWO items/rows visible`);
  else results.incomplete.push('Admin/HM View: no MWO cards or rows found');
  results.features.push('HM View: work order assignment & review feed');

  // ── Tab: Tech View ────────────────────────────────────────────
  log('ADMIN', 'Switching to Tech View tab...');
  await page.locator('button:has-text("Tech View")').click();
  await page.waitForTimeout(1500);
  await shot(page, '07_admin_tech_view');
  await checkForErrors(page, 'Admin/TechView');
  const techItems = await page.locator('[class*="card"], [class*="mwo"], table tbody tr').count();
  if (techItems > 0) results.working.push(`Admin/Tech View: ${techItems} items visible`);
  else results.incomplete.push('Admin/Tech View: no items found');
  results.features.push('Tech View: technician work order execution view');

  // ── Tab: Procurement ─────────────────────────────────────────
  log('ADMIN', 'Switching to Procurement tab...');
  await page.locator('button:has-text("Procurement")').click();
  await page.waitForTimeout(1500);
  await shot(page, '08_admin_procurement');
  await checkForErrors(page, 'Admin/Procurement');
  const procRows = await inspectTable(page, 'Admin/Procurement');
  results.features.push('Procurement Matrix: procurement queue management');

  // ── Tab: Data Ingestion ───────────────────────────────────────
  log('ADMIN', 'Switching to Data Ingestion tab...');
  await page.locator('button:has-text("Data Ingestion")').click();
  await page.waitForTimeout(1200);
  await shot(page, '09_admin_ingestion_personnel');
  results.features.push('Data Ingestion: bulk data import system');

  // Sub-tabs
  const ingestionSubTabs = ['PERSONNEL SCHEMA', 'EQUIPMENT', 'TAXONOMY', 'PARTS'];
  for (const sub of ingestionSubTabs) {
    const btn = page.locator(`button:has-text("${sub}")`);
    if (await btn.count() > 0) {
      await btn.click();
      await page.waitForTimeout(800);
      results.working.push(`Ingestion sub-tab "${sub}": clickable`);
    } else {
      results.incomplete.push(`Ingestion sub-tab "${sub}": not found`);
    }
  }
  await shot(page, '09b_admin_ingestion_tabs');

  // Check for upload/import buttons
  const uploadBtns = await page.locator('button:has-text("Upload"), button:has-text("Import"), button:has-text("Download Template"), input[type="file"]').count();
  if (uploadBtns > 0) results.working.push(`Ingestion: ${uploadBtns} upload/import controls present`);
  else results.incomplete.push('Ingestion: no upload/import controls found');

  // ── Enterprise Data Matrix (if accessible from admin) ────────
  // Check for data matrix link/tab
  const matrixLink = page.locator('button:has-text("Enterprise"), a:has-text("Matrix")');
  if (await matrixLink.count() > 0) {
    await matrixLink.click();
    await page.waitForTimeout(1000);
    await shot(page, '10_admin_enterprise_matrix');
    results.features.push('Enterprise Data Matrix: full data overview');
  }

  // ══════════════════════════════════════════════════════════════
  //  3. ARCHIVE (via direct nav while logged in as admin)
  // ══════════════════════════════════════════════════════════════
  log('ARCHIVE', 'Navigating to /archive...');
  await page.goto(`${BASE}/archive`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1500);
  await shot(page, '11_archive_dashboard');
  const archiveHeader = await page.locator('text=Archive, text=Closed, text=Completed, h1, h2').first().textContent().catch(() => null);
  if (archiveHeader) {
    results.working.push(`Archive Dashboard: loaded — "${archiveHeader?.trim().slice(0,50)}"`);
    results.features.push('Archive Dashboard: closed/completed MWO record browser');
  } else {
    results.broken.push('Archive Dashboard: no header found — may not render');
  }
  await checkForErrors(page, 'Archive');
  await inspectTable(page, 'Archive');

  // ══════════════════════════════════════════════════════════════
  //  4. HM DASHBOARD
  // ══════════════════════════════════════════════════════════════
  log('HM', 'Logging out, then logging in as HM...');
  await logout(page);
  await page.waitForTimeout(500);
  const hmUrl = await loginAs(page, CREDS.hm);
  log('HM', `Landed at: ${hmUrl}`);
  if (hmUrl.includes('/hm')) results.working.push('HM login: redirected to /hm correctly');
  else results.broken.push(`HM login: unexpected redirect to ${hmUrl}`);
  await page.waitForTimeout(1500);
  await shot(page, '12_hm_dashboard');

  const hmHeader = await page.locator('h1, h2, h3').first().textContent().catch(() => null);
  results.features.push(`HM Dashboard: "${hmHeader?.trim().slice(0,50) || 'header not found'}"`);

  // Check for MWO feed items
  const hmMwos = await page.locator('[class*="card"], [class*="mwo"], [class*="order"], table tbody tr').count();
  if (hmMwos > 0) {
    results.working.push(`HM Dashboard: ${hmMwos} MWO items visible in feed`);
    // Try clicking the first one
    const firstCard = page.locator('[class*="card"], [class*="mwo"], [class*="order"]').first();
    if (await firstCard.count() > 0) {
      await firstCard.click();
      await page.waitForTimeout(1000);
      const modal = await page.locator('[class*="modal"], [role="dialog"], [class*="overlay"]').count();
      if (modal > 0) {
        results.working.push('HM Dashboard: clicking MWO opens detail modal');
        await shot(page, '13_hm_mwo_modal');
        // Check for assign/dispatch button
        const assignBtn = await page.locator('button:has-text("Assign"), button:has-text("Dispatch"), button:has-text("Review")').count();
        if (assignBtn > 0) results.working.push('HM Modal: Assign/Dispatch button present');
        else results.incomplete.push('HM Modal: no Assign/Dispatch action button found');
        // Close modal
        const closeBtn = page.locator('button:has-text("Close"), button:has-text("×"), button:has-text("Cancel"), [aria-label="close"]');
        if (await closeBtn.count() > 0) await closeBtn.first().click();
        else await page.keyboard.press('Escape');
        await page.waitForTimeout(500);
      } else {
        results.incomplete.push('HM Dashboard: clicking MWO card did not open a modal');
        await shot(page, '13_hm_mwo_clicked');
      }
    }
  } else {
    results.incomplete.push('HM Dashboard: no MWO items/rows found in feed');
  }
  await checkForErrors(page, 'HM Dashboard');
  results.features.push('HM Dashboard: maintenance work order command feed + assignment');

  // Manual dispatch portal
  const manualDispatch = page.locator('button:has-text("Manual Dispatch"), a:has-text("Manual Dispatch")');
  if (await manualDispatch.count() > 0) {
    results.features.push('HM: Manual Dispatch Portal available');
    await manualDispatch.click();
    await page.waitForTimeout(800);
    await shot(page, '14_hm_manual_dispatch');
    const closeBtn = page.locator('button:has-text("Close"), button:has-text("×")');
    if (await closeBtn.count() > 0) await closeBtn.first().click();
  }

  // ══════════════════════════════════════════════════════════════
  //  5. TECHNICIAN DASHBOARD
  // ══════════════════════════════════════════════════════════════
  log('TECH', 'Logging out, then logging in as TECHNICIAN...');
  await logout(page);
  await page.waitForTimeout(500);
  const techUrl = await loginAs(page, CREDS.tech);
  log('TECH', `Landed at: ${techUrl}`);
  if (techUrl.includes('/tech')) results.working.push('Tech login: redirected to /tech correctly');
  else results.broken.push(`Tech login: unexpected redirect to ${techUrl}`);
  await page.waitForTimeout(1500);
  await shot(page, '15_tech_dashboard');

  const techHeader = await page.locator('h1, h2, h3').first().textContent().catch(() => null);
  results.features.push(`Tech Dashboard: "${techHeader?.trim().slice(0,50) || 'header not found'}"`);

  // Check for assigned MWOs
  const techMwos = await page.locator('[class*="card"], [class*="mwo"], [class*="order"], table tbody tr').count();
  if (techMwos > 0) {
    results.working.push(`Tech Dashboard: ${techMwos} MWO items visible`);
    // Click the first
    const firstCard = page.locator('[class*="card"], [class*="mwo"], [class*="order"]').first();
    if (await firstCard.count() > 0) {
      await firstCard.click();
      await page.waitForTimeout(1000);
      const modal = await page.locator('[class*="modal"], [role="dialog"], [class*="overlay"]').count();
      if (modal > 0) {
        results.working.push('Tech Dashboard: clicking MWO opens detail modal');
        await shot(page, '16_tech_mwo_modal');
        // Check for Start/Complete/Parts buttons
        const actionBtns = await page.locator('button:has-text("Start"), button:has-text("Complete"), button:has-text("Parts"), button:has-text("Consume")').count();
        if (actionBtns > 0) results.working.push(`Tech Modal: ${actionBtns} action buttons (Start/Complete/Parts)`);
        else results.incomplete.push('Tech Modal: no action buttons found');
        await shot(page, '16b_tech_modal_actions');
        const closeBtn = page.locator('button:has-text("Close"), button:has-text("×"), button:has-text("Cancel"), [aria-label="close"]');
        if (await closeBtn.count() > 0) await closeBtn.first().click();
        else await page.keyboard.press('Escape');
        await page.waitForTimeout(500);
      } else {
        results.incomplete.push('Tech Dashboard: clicking MWO card did not open modal');
      }
    }
  } else {
    results.incomplete.push('Tech Dashboard: no MWO assignments visible (may be unassigned)');
  }
  await checkForErrors(page, 'Tech Dashboard');
  results.features.push('Tech Dashboard: technician work order execution + parts consumption');

  // ── Check Equipment Matrix accessibility ────────────────────
  const eqBtn = page.locator('button:has-text("Equipment"), a:has-text("Equipment")');
  if (await eqBtn.count() > 0) {
    results.features.push('Equipment Matrix: accessible from UI');
  }

  // ── Check Parts Matrix accessibility ─────────────────────────
  const partsBtn = page.locator('button:has-text("Parts"), a:has-text("Parts")');
  if (await partsBtn.count() > 0) {
    results.features.push('Parts Matrix / SKU Ledger: accessible from UI');
  }

  // ── Archive from tech ─────────────────────────────────────────
  log('TECH', 'Navigating to archive as tech...');
  await page.goto(`${BASE}/archive`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1500);
  const archiveCheck = await page.locator('h1, h2, h3').count();
  if (archiveCheck > 0) results.working.push('Archive: accessible to TECH role');
  else results.broken.push('Archive: not accessible to TECH role (may redirect to login)');
  await shot(page, '17_tech_archive');

  // ══════════════════════════════════════════════════════════════
  //  6. ADDITIONAL SCREENS (Admin — Equipment, Parts, SKU)
  // ══════════════════════════════════════════════════════════════
  log('ADMIN', 'Re-logging as admin to check Equipment/Parts/SKU matrices...');
  await logout(page);
  await page.waitForTimeout(400);
  await loginAs(page, CREDS.admin);
  await page.waitForTimeout(1500);

  // Navigate to each matrix tab via admin ingestion tabs or direct views
  // Try Equipment Matrix button
  const equipBtn = page.locator('button:has-text("Equipment"), button:has-text("EQUIPMENT")');
  if (await equipBtn.count() > 0) {
    await equipBtn.first().click();
    await page.waitForTimeout(1200);
    await shot(page, '18_equipment_matrix');
    const eqRows = await inspectTable(page, 'EquipmentMatrix');
    results.features.push(`Equipment Matrix: ${eqRows} equipment records`);
    await checkForErrors(page, 'EquipmentMatrix');
  } else {
    results.incomplete.push('Equipment Matrix: no direct tab button found from admin landing');
  }

  // Try Parts Matrix
  const partsTabBtn = page.locator('button:has-text("Parts"), button:has-text("PARTS")');
  if (await partsTabBtn.count() > 0) {
    await partsTabBtn.first().click();
    await page.waitForTimeout(1200);
    await shot(page, '19_parts_matrix');
    const partsRows = await inspectTable(page, 'PartsMatrix');
    results.features.push(`Parts Matrix: ${partsRows} parts records`);
    await checkForErrors(page, 'PartsMatrix');
  }

  // ── Final state screenshot ────────────────────────────────────
  await shot(page, '20_final_state');

  await browser.close();

  // ══════════════════════════════════════════════════════════════
  //  REPORT
  // ══════════════════════════════════════════════════════════════
  console.log('\n══════════════════════════════════════════════════════════════');
  console.log('  MWO APP — FULL VISUAL INSPECTION REPORT');
  console.log('══════════════════════════════════════════════════════════════');

  console.log(`\n✅ WORKING (${results.working.length}):`);
  results.working.forEach(r => console.log(`   ✅ ${r}`));

  console.log(`\n⚠️  INCOMPLETE / EMPTY (${results.incomplete.length}):`);
  results.incomplete.forEach(r => console.log(`   ⚠️  ${r}`));

  console.log(`\n❌ BROKEN (${results.broken.length}):`);
  results.broken.forEach(r => console.log(`   ❌ ${r}`));

  console.log(`\n📦 FEATURES FOUND (${results.features.length}):`);
  results.features.forEach(r => console.log(`   📦 ${r}`));

  if (results.apiErrors.length) {
    console.log(`\n🌐 API ERRORS (${results.apiErrors.length}):`);
    [...new Set(results.apiErrors)].forEach(r => console.log(`   🌐 ${r}`));
  }
  if (results.consoleErr.length) {
    console.log(`\n🖥️  CONSOLE ERRORS (${results.consoleErr.length}):`);
    [...new Set(results.consoleErr)].forEach(r => console.log(`   🖥️  ${r}`));
  }

  console.log('\n══════════════════════════════════════════════════════════════');
  console.log(`Screenshots saved to: ${SHOTS}`);
}

runAll().catch(err => {
  console.error('[FATAL]', err);
  process.exit(1);
});
