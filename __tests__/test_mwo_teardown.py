import re
from playwright.sync_api import Page, expect

def test_mwo_responsive_teardown(page: Page):
    """
    TDD RED PHASE: Strict mathematical assertion of the Responsive Matrix Teardown Doctrine.
    Forces failure if legacy tables persist on mobile viewports.
    """
    # 1. Force a strict mobile viewport (< 900px boundary)
    page.set_viewport_size({"width": 414, "height": 896})
    
    # [BIOLOGICAL OVERRIDE] Intercept API calls to ensure deterministic state
    page.route("**/api/v1/auth/login", lambda route: route.fulfill(
        status=200,
        content_type="application/json",
        body='{"access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJFUlAtMTAwMCIsInJvbGUiOiJBRE1JTklTVFJBVE9SIiwiZXhwIjo5OTk5OTk5OTk5fQ.sig"}'
    ))
    page.route("**/api/v1/auth/refresh", lambda route: route.fulfill(
        status=200,
        content_type="application/json",
        body='{"access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJFUlAtMTAwMCIsInJvbGUiOiJBRE1JTklTVFJBVE9SIiwiZXhwIjo5OTk5OTk5OTk5fQ.sig"}'
    ))
    page.route("**/work-orders/queue*", lambda route: route.fulfill(
        status=200,
        content_type="application/json",
        body='{"data": []}'
    ))
    page.route("**/employees*", lambda route: route.fulfill(
        status=200,
        content_type="application/json",
        body='{"data": []}'
    ))
    
    # Execute Authentication to reach the target matrix
    page.goto("http://localhost:5175/login")
    page.fill("input[name='mwo_operator_id']", "ERP-1000")
    page.fill("input[name='mwo_operator_pin']", "1234")
    page.click("button[type='submit']")
    try:
        page.wait_for_url("**/admin", timeout=5000)
    except:
        pass # In case of auth issues or already logged in, proceed to the URL
    
    # 2. Navigate to the local physical route of the MWO ERP Component
    # OPERATOR: You MUST replace this route with the exact URL where the table renders
    page.goto("http://localhost:5175/admin") 
    
    # 3. DOCTRINE 1: The legacy <table> matrix must be eradicated on mobile
    table_locator = page.locator("table")
    expect(table_locator).not_to_be_visible(timeout=3000)
    
    # 4. DOCTRINE 2: Touch-friendly stacked Key-Value cards must replace the table
    card_locator = page.locator(".mobile-kv-card")
    expect(card_locator.first).to_be_visible(timeout=3000)
    
    # 5. DOCTRINE 3: Destructive actuations must be physically isolated
    # Inline 'Approve' or 'Reject' buttons are strictly forbidden in the list view
    inline_action = page.locator(".mobile-kv-card button:has-text('Approve')")
    expect(inline_action).not_to_be_visible(timeout=1000)
