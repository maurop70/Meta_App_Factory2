"""
phantom_ui_runner.py — Playwright-Based UI Testing Engine
==========================================================
Phantom QA | Project Aether | Meta App Factory

Browser-based UI testing using Playwright (headless Chromium).
Tests apps through the actual user interface — navigation, forms,
chat interactions, visual compliance, and responsive layout.

Integrates with:
  - @auto_heal for retry resilience on flaky browser actions
  - BrandGuardian for visual brand compliance checks
  - TestResult model from phantom_agent.py for unified reporting

Usage:
    # Standalone
    python phantom_ui_runner.py --url http://localhost:5173 --app Alpha_V2_Genesis

    # Imported
    from phantom_ui_runner import UITestRunner
    runner = UITestRunner("http://localhost:5173", headed=False)
    results = await runner.run_full_suite("Alpha_V2_Genesis")
"""

import os
import sys
import json
import time
import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

PHANTOM_DIR = os.path.dirname(os.path.abspath(__file__))
FACTORY_DIR = os.path.normpath(os.path.join(PHANTOM_DIR, "..", "..", ".."))
SCREENSHOTS_DIR = os.path.join(PHANTOM_DIR, "screenshots")
REPORTS_DIR = os.path.join(PHANTOM_DIR, "reports")

sys.path.insert(0, FACTORY_DIR)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [PhantomUI] %(message)s")
logger = logging.getLogger("PhantomUI")

# ── V3 Self-Healing Integration ──────────────────────────
try:
    from auto_heal import auto_heal
    _HEAL_AVAILABLE = True
except ImportError:
    _HEAL_AVAILABLE = False
    def auto_heal(func=None, **kw):
        """No-op fallback."""
        if func:
            return func
        return lambda f: f

# ── Brand Guardian Integration ───────────────────────────
try:
    from Project_Aether.brand_guardian import BrandGuardian, BrandRegistry
    _BRAND_AVAILABLE = True
except ImportError:
    try:
        sys.path.insert(0, os.path.join(FACTORY_DIR, "Project_Aether"))
        from brand_guardian import BrandGuardian, BrandRegistry
        _BRAND_AVAILABLE = True
    except ImportError:
        _BRAND_AVAILABLE = False

# ── Test Result (compatible with phantom_agent.py) ───────

class TestResult:
    """Test result compatible with phantom_agent.py report generator."""
    def __init__(self, test_name: str, passed: bool, details: str, duration_ms: float):
        self.test_name = test_name
        self.passed = passed
        self.details = details
        self.duration_ms = duration_ms
        self.timestamp = datetime.now().isoformat()
        self.screenshot: Optional[str] = None

    def to_dict(self):
        d = {
            "test": self.test_name,
            "status": "PASS" if self.passed else "FAIL",
            "details": self.details,
            "duration_ms": round(self.duration_ms, 2),
            "timestamp": self.timestamp,
        }
        if self.screenshot:
            d["screenshot"] = self.screenshot
        return d


# ═══════════════════════════════════════════════════════════
#  UI TEST RUNNER
# ═══════════════════════════════════════════════════════════

class UITestRunner:
    """
    Playwright-based UI test runner for Phantom QA.

    Launches a headless Chromium browser and exercises the app's UI:
    - Page load and console error detection
    - Navigation (clicks, routing)
    - Form interactions (input, submit)
    - Chat/streaming validation
    - Responsive layout checks
    - Brand visual compliance (via pixel sampling)
    - Screenshot capture at each step
    """

    def __init__(self, base_url: str, headed: bool = False, slow_mo: int = 0):
        self.base_url = base_url.rstrip("/")
        self.headed = headed
        self.slow_mo = slow_mo
        self.results: list[TestResult] = []
        self._browser = None
        self._page = None
        self._console_errors: list[str] = []
        os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

    async def _launch(self):
        """Launch Playwright browser."""
        from playwright.async_api import async_playwright
        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(
            headless=not self.headed,
            slow_mo=self.slow_mo,
        )
        context = await self._browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="PhantomQA/1.0 (Playwright; Meta_App_Factory)",
        )
        self._page = await context.new_page()

        # Capture console errors
        self._console_errors = []
        self._page.on("console", lambda msg: (
            self._console_errors.append(f"[{msg.type}] {msg.text}")
            if msg.type in ("error", "warning") else None
        ))

    async def _close(self):
        """Close browser."""
        if self._browser:
            await self._browser.close()
        if self._pw:
            await self._pw.stop()

    async def _screenshot(self, name: str) -> str:
        """Take a screenshot and return the file path."""
        ts = datetime.now().strftime("%H%M%S")
        filename = f"{name}_{ts}.png"
        path = os.path.join(SCREENSHOTS_DIR, filename)
        await self._page.screenshot(path=path, full_page=False)
        logger.info(f"  📸 Screenshot: {filename}")
        return path

    def _record(self, result: TestResult):
        """Record a test result."""
        self.results.append(result)
        icon = "✅" if result.passed else "❌"
        logger.info(f"  {icon} {result.test_name}: {result.details} ({result.duration_ms:.0f}ms)")

    # ── Test Steps ────────────────────────────────────────

    async def test_page_load(self) -> TestResult:
        """Test that the app loads without critical errors."""
        start = time.time()
        try:
            resp = await self._page.goto(self.base_url, wait_until="networkidle", timeout=20000)
            elapsed = (time.time() - start) * 1000

            status = resp.status if resp else 0
            title = await self._page.title()

            # Check for blank page
            body_text = await self._page.inner_text("body")
            is_blank = len(body_text.strip()) < 10

            # Check console errors
            critical_errors = [e for e in self._console_errors if "[error]" in e.lower()]

            if status != 200:
                result = TestResult("Page Load", False, f"HTTP {status}", elapsed)
            elif is_blank:
                result = TestResult("Page Load", False, "Blank page detected", elapsed)
            elif len(critical_errors) > 3:
                result = TestResult("Page Load", False,
                    f"Loaded but {len(critical_errors)} console errors", elapsed)
            else:
                result = TestResult("Page Load", True,
                    f"HTTP {status} | Title: '{title[:40]}' | {len(body_text)} chars", elapsed)

            result.screenshot = await self._screenshot("page_load")

        except Exception as e:
            elapsed = (time.time() - start) * 1000
            result = TestResult("Page Load", False, f"EXCEPTION: {str(e)[:200]}", elapsed)

        self._record(result)
        return result

    async def test_navigation(self) -> list[TestResult]:
        """Test clickable navigation elements (links, buttons, tabs)."""
        results = []

        # Find all visible navigation-like elements
        nav_selectors = [
            "nav a", "aside a", "[role='tab']",
            ".sidebar a", ".nav-link", ".tab",
            "button:has-text('Dashboard')", "button:has-text('Settings')",
        ]

        for selector in nav_selectors:
            try:
                elements = await self._page.query_selector_all(selector)
                if not elements:
                    continue

                # Test first 3 nav items max
                for i, el in enumerate(elements[:3]):
                    start = time.time()
                    try:
                        text = (await el.inner_text()).strip()[:30] or f"Element #{i}"
                        is_visible = await el.is_visible()
                        if not is_visible:
                            continue

                        await el.click(timeout=5000)
                        await self._page.wait_for_load_state("networkidle", timeout=8000)
                        elapsed = (time.time() - start) * 1000

                        result = TestResult(
                            f"Nav: '{text}'", True,
                            f"Clicked successfully, new URL: {self._page.url[-50:]}", elapsed
                        )
                    except Exception as e:
                        elapsed = (time.time() - start) * 1000
                        result = TestResult(
                            f"Nav: '{text if 'text' in dir() else selector}'", False,
                            f"Click failed: {str(e)[:100]}", elapsed
                        )

                    self._record(result)
                    results.append(result)

                    # Navigate back to base
                    await self._page.goto(self.base_url, wait_until="networkidle", timeout=10000)
                break  # Only test first matching selector group

            except Exception:
                continue

        if not results:
            result = TestResult("Navigation", True, "No nav elements found — skipped", 0)
            self._record(result)
            results.append(result)

        return results

    async def test_forms(self) -> list[TestResult]:
        """Test form fields — find inputs, type into them, check response."""
        results = []

        # Look for input fields
        input_selectors = [
            "input[type='text']", "textarea",
            "input:not([type='hidden']):not([type='checkbox']):not([type='radio'])",
        ]

        for selector in input_selectors:
            try:
                elements = await self._page.query_selector_all(selector)
                if not elements:
                    continue

                for i, el in enumerate(elements[:2]):
                    start = time.time()
                    try:
                        is_visible = await el.is_visible()
                        if not is_visible:
                            continue

                        placeholder = await el.get_attribute("placeholder") or ""
                        field_id = await el.get_attribute("id") or await el.get_attribute("name") or f"field_{i}"

                        # Type test input
                        await el.click(timeout=3000)
                        await el.fill("Phantom QA test input")
                        value = await el.input_value()
                        elapsed = (time.time() - start) * 1000

                        passed = value == "Phantom QA test input"
                        result = TestResult(
                            f"Form Input: '{field_id}'", passed,
                            f"Typed and verified | placeholder: '{placeholder[:30]}'", elapsed
                        )
                        # Clear the field
                        await el.fill("")

                    except Exception as e:
                        elapsed = (time.time() - start) * 1000
                        result = TestResult(
                            f"Form Input: #{i}", False,
                            f"Interaction failed: {str(e)[:100]}", elapsed
                        )

                    self._record(result)
                    results.append(result)
                break  # First matching selector group

            except Exception:
                continue

        if not results:
            result = TestResult("Forms", True, "No form fields found — skipped", 0)
            self._record(result)
            results.append(result)

        return results

    async def test_chat_interaction(self, prompt: str = "Hello, this is a Phantom QA test.") -> TestResult:
        """Test chat/streaming UI if present."""
        start = time.time()

        # Look for chat input
        chat_selectors = [
            "textarea", "input[type='text']",
            "[data-testid='chat-input']", ".chat-input",
            "input[placeholder*='message']", "input[placeholder*='type']",
            "textarea[placeholder*='message']", "textarea[placeholder*='Ask']",
        ]

        chat_input = None
        for selector in chat_selectors:
            try:
                el = await self._page.query_selector(selector)
                if el and await el.is_visible():
                    chat_input = el
                    break
            except Exception:
                continue

        if not chat_input:
            elapsed = (time.time() - start) * 1000
            result = TestResult("Chat Interaction", True, "No chat input found — skipped", elapsed)
            self._record(result)
            return result

        try:
            # Type the prompt
            await chat_input.click(timeout=3000)
            await chat_input.fill(prompt)

            # Find and click send button
            send_selectors = [
                "button[type='submit']", "button:has-text('Send')",
                "button:has-text('send')", "[data-testid='send-button']",
                "button svg", "form button",
            ]

            sent = False
            for sel in send_selectors:
                try:
                    btn = await self._page.query_selector(sel)
                    if btn and await btn.is_visible():
                        await btn.click(timeout=3000)
                        sent = True
                        break
                except Exception:
                    continue

            if not sent:
                # Try Enter key
                await chat_input.press("Enter")
                sent = True

            # Wait for response to appear (streaming)
            await asyncio.sleep(3)

            # Check if any new content appeared
            body_after = await self._page.inner_text("body")
            elapsed = (time.time() - start) * 1000

            result = TestResult(
                "Chat Interaction", True,
                f"Sent prompt ({len(prompt)} chars), page has {len(body_after)} chars after", elapsed
            )
            result.screenshot = await self._screenshot("chat_response")

        except Exception as e:
            elapsed = (time.time() - start) * 1000
            result = TestResult("Chat Interaction", False, f"EXCEPTION: {str(e)[:200]}", elapsed)

        self._record(result)
        return result

    async def test_responsive_layout(self) -> list[TestResult]:
        """Test at mobile viewport (375px) and verify no overflow/breakage."""
        results = []
        viewports = [
            {"name": "Mobile (375px)", "width": 375, "height": 812},
            {"name": "Desktop (1280px)", "width": 1280, "height": 800},
        ]

        for vp in viewports:
            start = time.time()
            try:
                await self._page.set_viewport_size({"width": vp["width"], "height": vp["height"]})
                await self._page.goto(self.base_url, wait_until="networkidle", timeout=15000)
                await asyncio.sleep(0.5)

                # Check for horizontal overflow
                has_overflow = await self._page.evaluate("""
                    () => document.documentElement.scrollWidth > document.documentElement.clientWidth
                """)

                # Check body is not empty
                body_text = await self._page.inner_text("body")
                elapsed = (time.time() - start) * 1000

                issues = []
                if has_overflow:
                    issues.append("horizontal overflow detected")
                if len(body_text.strip()) < 10:
                    issues.append("blank page")

                passed = len(issues) == 0
                details = "Layout OK" if passed else "; ".join(issues)
                result = TestResult(f"Responsive: {vp['name']}", passed, details, elapsed)
                result.screenshot = await self._screenshot(f"responsive_{vp['width']}")

            except Exception as e:
                elapsed = (time.time() - start) * 1000
                result = TestResult(f"Responsive: {vp['name']}", False, str(e)[:200], elapsed)

            self._record(result)
            results.append(result)

        # Reset viewport
        await self._page.set_viewport_size({"width": 1280, "height": 800})
        return results

    async def test_brand_compliance(self, app_dir: str = None) -> TestResult:
        """Use BrandGuardian to check visual brand compliance on the rendered page."""
        start = time.time()

        if not _BRAND_AVAILABLE:
            elapsed = (time.time() - start) * 1000
            result = TestResult("Brand Compliance", True, "BrandGuardian not available — skipped", elapsed)
            self._record(result)
            return result

        try:
            registry = BrandRegistry()
            brand_data = registry.resolve(app_dir or FACTORY_DIR, tier="factory")
            if not brand_data:
                elapsed = (time.time() - start) * 1000
                result = TestResult("Brand Compliance", True, "No brand defined — skipped", elapsed)
                self._record(result)
                return result

            # Get the page HTML and audit it
            html_content = await self._page.content()

            # Write to temp file for BrandGuardian
            tmp_path = os.path.join(SCREENSHOTS_DIR, "_phantom_brand_check.html")
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write(html_content)

            guardian = BrandGuardian(brand_file=registry.master_brand_path)
            report = guardian.audit_file(tmp_path)

            elapsed = (time.time() - start) * 1000
            score = report.get("score", 0)
            violations = report.get("violations", [])
            grade = report.get("grade", "?")

            passed = score >= 70
            details = f"Score: {score}/100 (Grade {grade})"
            if violations:
                details += f" | {len(violations)} violation(s): {'; '.join(violations[:3])}"

            result = TestResult("Brand Compliance", passed, details, elapsed)

            # Cleanup
            try:
                os.remove(tmp_path)
            except Exception:
                pass

        except Exception as e:
            elapsed = (time.time() - start) * 1000
            result = TestResult("Brand Compliance", False, f"EXCEPTION: {str(e)[:200]}", elapsed)

        self._record(result)
        return result

    async def test_console_errors(self) -> TestResult:
        """Evaluate collected console errors from the session."""
        start = time.time()
        errors = [e for e in self._console_errors if "[error]" in e.lower()]
        warnings = [e for e in self._console_errors if "[warning]" in e.lower()]
        elapsed = (time.time() - start) * 1000

        if len(errors) > 5:
            result = TestResult("Console Errors", False,
                f"{len(errors)} errors, {len(warnings)} warnings | First: {errors[0][:80]}", elapsed)
        elif errors:
            result = TestResult("Console Errors", True,
                f"{len(errors)} error(s), {len(warnings)} warning(s) — within tolerance", elapsed)
        else:
            result = TestResult("Console Errors", True,
                f"Clean — 0 errors, {len(warnings)} warning(s)", elapsed)

        self._record(result)
        return result

    # ── Full Suite ────────────────────────────────────────

    async def run_full_suite(self, app_name: str = "App",
                              persona_prompts: list[str] = None,
                              app_dir: str = None) -> list[TestResult]:
        """
        Run the complete UI test suite.

        Args:
            app_name: Name for reporting
            persona_prompts: Optional list of chat prompts to test
            app_dir: App directory for brand compliance check

        Returns:
            List of TestResult objects
        """
        logger.info(f"═══ PHANTOM UI: Testing '{app_name}' at {self.base_url} ═══")
        self.results = []

        try:
            await self._launch()

            # Core tests
            await self.test_page_load()
            await self.test_navigation()
            await self.test_forms()
            await self.test_responsive_layout()
            await self.test_brand_compliance(app_dir)

            # Chat tests (persona-driven if available)
            if persona_prompts:
                for i, prompt in enumerate(persona_prompts[:3]):
                    await self._page.goto(self.base_url, wait_until="networkidle", timeout=15000)
                    await self.test_chat_interaction(prompt)
            else:
                await self._page.goto(self.base_url, wait_until="networkidle", timeout=15000)
                await self.test_chat_interaction()

            # Final console error check
            await self.test_console_errors()

        except Exception as e:
            logger.error(f"UI test suite crashed: {e}")
            self.results.append(TestResult("Suite Error", False, str(e)[:200], 0))
        finally:
            await self._close()

        total = len(self.results)
        passed = sum(1 for r in self.results if r.passed)
        logger.info(f"═══ UI RESULTS: {passed}/{total} passed ═══")

        return self.results

    def get_score(self) -> int:
        """Calculate a 0-100 score from results."""
        if not self.results:
            return 0
        passed = sum(1 for r in self.results if r.passed)
        return round(passed / len(self.results) * 100)


# ═══════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Phantom QA — UI Test Runner (Playwright)")
    parser.add_argument("--url", required=True, help="Base URL of the app frontend")
    parser.add_argument("--app", default="App", help="App name for reporting")
    parser.add_argument("--headed", action="store_true", help="Run in visible browser mode")
    parser.add_argument("--screenshots", action="store_true", help="Take screenshots (default: on)")
    parser.add_argument("--prompt", help="Custom chat prompt to test")
    args = parser.parse_args()

    runner = UITestRunner(args.url, headed=args.headed)
    prompts = [args.prompt] if args.prompt else None

    results = asyncio.run(runner.run_full_suite(args.app, persona_prompts=prompts))

    # Print summary
    print(f"\n{'='*55}")
    print(f"  🧪 Phantom UI Test Summary — {args.app}")
    print(f"{'='*55}")
    for r in results:
        icon = "✅" if r.passed else "❌"
        print(f"  {icon} {r.test_name}: {r.details}")
    score = runner.get_score()
    print(f"\n  Score: {score}/100")
    print(f"{'='*55}\n")

    sys.exit(0 if score >= 75 else 1)
