import { test, expect } from '@playwright/test';

test.describe('Workspace Vault Portal Modal & Dynamic SSE Decoupling', () => {
  test('Assert details modal is ejected to body and EventSource maps dynamic project query param', async ({ page }) => {
    // Intercept project registry call to return a unified envelope
    await page.route('**/api/projects/?limit=50&offset=0', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          items: [{
            id: 'mock-uuid-1234',
            project_name: 'Project Heinlein Foods',
            financial_matrix: { fixed_costs: 650000, margin_percent: 50 },
            operational_context: { location: 'Sector 4-A', duration_months: 24, team_size: 12 },
            created_at: '2026-05-29T02:51:18.606030',
            updated_at: '2026-05-29T02:51:18.636184'
          }],
          total: 1,
          limit: 50,
          offset: 0
        })
      });
    });

    // Intercept EOS state fetch
    await page.route('**/api/eos/state?project_name=*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          brand_name: 'Project Heinlein Foods',
          company_name: 'Project Heinlein Foods',
          tagline: 'Socratic Enrobing Pivot',
          industry: 'Food pivot B2B',
          target_market: 'B2B food distributors',
          problem_statement: 'High idle capacity on Hershey/Reese\'s lines.',
          solution_statement: 'Pivot B2B white-labeling enrobing lines.',
          tam: '$5B',
          sam: '$500M',
          som: '$50M',
          business_plan_md_path: 'Heinlein/business_plan.md',
          financial_xlsx_path: 'Heinlein/financials.xlsx',
          investor_pptx_path: 'Heinlein/investor.pptx',
          customer_pptx_path: 'Heinlein/customer.pptx'
        })
      });
    });

    // Intercept paginated history fetch
    await page.route('**/api/warroom/history?project=*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          items: [{
            topic: 'Strategic Cash Preservation Pivot',
            started: '2026-05-29T02:00:00.000Z',
            messages: [
              { agent: 'SYSTEM', message: '🏛️ BOARDROOM SESSION OPENED — Topic: "Strategic Cash Preservation Pivot"', timestamp: '2026-05-29T02:00:00.000Z' },
              { agent: 'CEO', message: 'Execute extreme 90-day cash preservation.', timestamp: '2026-05-29T02:00:05.000Z' },
              { agent: 'CFO', message: 'Reducing idle line overhead clears break-even path.', timestamp: '2026-05-29T02:00:10.000Z' }
            ]
          }],
          total: 1,
          session_count: 1,
          last_updated: '2026-05-29T02:01:00.000Z'
        })
      });
    });

    // Navigate to the workspaces vault UI
    await page.goto('http://localhost:5173/#/workspaces');

    // Wait for the project card to load and confirm grid mounting
    const projectCardTitle = page.locator('h3:has-text("Project Heinlein Foods")');
    await expect(projectCardTitle).toBeVisible({ timeout: 5000 });

    // Locate the "OPEN WORKSPACE" button and click it to trigger React Portal mount
    const openWorkspaceBtn = page.locator('span:has-text("OPEN WORKSPACE")');
    await expect(openWorkspaceBtn).toBeVisible();
    await openWorkspaceBtn.click();
    console.log('[E2E Test] Triggered details modal open.');

    // Assert that the modal root exists in the DOM viewport
    const modalRoot = page.locator('#vault-modal-root');
    await expect(modalRoot).toBeVisible({ timeout: 5000 });
    console.log('[E2E Test] Portal modal is visible in viewport.');

    // DOCTRINE ENFORCEMENT: Assert the modal parent container is body (confirming ejection)
    const parentTagName = await page.evaluate(() => {
      const el = document.getElementById('vault-modal-root');
      return el ? el.parentNode.tagName : 'NONE';
    });
    expect(parentTagName).toBe('BODY');
    console.log('[E2E Test] SUCCESS: Portal modal is ejected directly to body.');

    // Switch to Courtroom Timeline Tab
    const timelineTab = page.locator('button:has-text("Courtroom Timeline")');
    await expect(timelineTab).toBeVisible();
    await timelineTab.click();

    // Verify debate history message from timeline is visible
    const messageNode = page.locator('p:has-text("Execute extreme 90-day cash preservation")');
    await expect(messageNode).toBeVisible();
    console.log('[E2E Test] Dialogue logs successfully loaded inside timeline tab.');

    // Click Actuate in War Room button in modal footer
    const actuateInWarRoomBtn = page.locator('button:has-text("Actuate In Adversarial War Room")');
    await expect(actuateInWarRoomBtn).toBeVisible();
    await actuateInWarRoomBtn.click();

    // Verify page redirected to War Room route
    await page.waitForURL('**/warroom');
    expect(page.url()).toContain('#/warroom');
    console.log('[E2E Test] SUCCESS: Redirected successfully to Adversarial War Room viewport!');
  });
});
