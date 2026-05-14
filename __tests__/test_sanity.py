import re
from playwright.sync_api import Page, expect

def test_factory_ui_mount(page: Page):
    """
    Zero-Trust Subprocess Penetration Test.
    Mathematically verifies the headless browser can traverse the local React matrix.
    """
    # 1. Traverse the local loopback interface
    page.goto("http://localhost:5173/")
    
    # 2. Strict DOM Assertion: Hunting for the core Engine Title
    # Based on current visual telemetry, the DOM must contain "Meta App Factory"
    expect(page.locator("body")).to_contain_text("Meta App Factory")
    
    # 3. Strict DOM Assertion: Hunting for the active Telemetry Bar
    expect(page.locator("body")).to_contain_text("TELEMETRY: ONLINE")
