import pytest
from playwright.sync_api import Page, expect

def test_auto_ghost(page: Page):
    # Navigate to target
    page.goto("http://localhost:5041")
    # Verify basic DOM is rendered
    expect(page.locator("body")).to_be_visible()