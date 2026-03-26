"""
ghost_user.py — The Ghost User (Persona-Driven UI Tester)
==========================================================
Phantom QA Elite | Antigravity-AI

Spawns a Playwright browser as a specific user persona and
exercises the application's UI: navigation, forms, responsive
layout, console errors, and screenshot capture.

Uses: Playwright (Chromium headless) + Gemini 2.5 Flash for persona
"""

import os
import time
import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger("Phantom.GhostUser")

SCREENSHOTS_DIR = Path(__file__).parent.parent / "screenshots"
SCREENSHOTS_DIR.mkdir(exist_ok=True)


class TestResult:
    """Individual test result."""
    def __init__(self, name: str, passed: bool, details: str, duration_ms: float):
        self.name = name
        self.passed = passed
        self.details = details
        self.duration_ms = duration_ms
        self.screenshot: Optional[str] = None

    def to_dict(self):
        d = {
            "test_name": self.name,
            "passed": self.passed,
            "details": self.details,
            "duration_ms": round(self.duration_ms, 1),
        }
        if self.screenshot:
            d["screenshot"] = self.screenshot
        return d


# ══════════════════════════════════════════════════════════
#  GHOST USER RUNNER
# ══════════════════════════════════════════════════════════

class GhostUserRunner:
    """
    Playwright-based UI test runner that assumes a specific
    user persona from the Architect's test plan.
    """

    def __init__(self, base_url: str, persona: dict = None, headed: bool = False,
                 event_callback=None):
        self.base_url = base_url.rstrip("/")
        self.persona = persona or {
            "name": "Default Tester",
            "behavior": "Methodical, clicks every element",
            "expertise": "tech-savvy",
        }
        self.headed = headed
        self.event_callback = event_callback
        self.results: list[TestResult] = []
        self._browser = None
        self._page = None
        self._console_errors: list[str] = []
        self._console_warnings: list[str] = []

    async def _launch(self):
        """Launch Playwright Chromium."""
        from playwright.async_api import async_playwright
        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(
            headless=not self.headed,
        )
        context = await self._browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=f"PhantomQA-GhostUser/{self.persona['name'].replace(' ', '_')}",
        )
        self._page = await context.new_page()

        # Capture console messages
        self._console_errors = []
        self._console_warnings = []
        self._page.on("console", self._on_console)

    def _on_console(self, msg):
        if msg.type == "error":
            self._console_errors.append(msg.text)
        elif msg.type == "warning":
            self._console_warnings.append(msg.text)

    async def _close(self):
        if self._browser:
            await self._browser.close()
        if hasattr(self, '_pw') and self._pw:
            await self._pw.stop()

    async def _screenshot(self, name: str) -> str:
        ts = datetime.now().strftime("%H%M%S")
        filename = f"{name}_{ts}.png"
        path = str(SCREENSHOTS_DIR / filename)
        await self._page.screenshot(path=path, full_page=False)
        return path

    def _emit(self, event_type: str, data: dict = None):
        """Emit a Ghost Stream event."""
        if self.event_callback:
            try:
                self.event_callback({
                    "type": event_type,
                    "timestamp": datetime.now().isoformat(),
                    "persona": self.persona.get("name", "Ghost"),
                    **(data or {}),
                })
            except Exception:
                pass

    def _record(self, result: TestResult):
        self.results.append(result)
        icon = "✅" if result.passed else "❌"
        logger.info(f"  {icon} {result.name}: {result.details}")
        self._emit("TEST_PASS" if result.passed else "TEST_FAIL", {
            "test_name": result.name,
            "details": result.details[:200],
            "duration_ms": round(result.duration_ms, 1),
        })

    # ── Individual Tests ──────────────────────────────────

    async def test_page_load(self) -> TestResult:
        """Load the app and verify it's not blank."""
        start = time.time()
        self._emit("PAGE_LOAD", {"url": self.base_url, "action": "Navigating to target URL"})
        try:
            resp = await self._page.goto(self.base_url, wait_until="networkidle", timeout=20000)
            elapsed = (time.time() - start) * 1000

            status = resp.status if resp else 0
            title = await self._page.title()
            body = await self._page.inner_text("body")
            is_blank = len(body.strip()) < 10

            if status != 200:
                result = TestResult("Page Load", False, f"HTTP {status}", elapsed)
            elif is_blank:
                result = TestResult("Page Load", False, "Blank page detected", elapsed)
            else:
                result = TestResult("Page Load", True,
                    f"HTTP {status} | Title: '{title[:50]}' | {len(body)} chars", elapsed)

            result.screenshot = await self._screenshot("page_load")
            self._emit("SCREENSHOT", {"path": result.screenshot, "context": "page_load"})
        except Exception as e:
            elapsed = (time.time() - start) * 1000
            result = TestResult("Page Load", False, f"Error: {str(e)[:200]}", elapsed)

        self._record(result)
        return result

    async def test_navigation(self) -> list[TestResult]:
        """Click navigation elements and verify they work."""
        results = []
        nav_selectors = [
            "nav a", "aside a", "[role='tab']",
            ".sidebar a", ".nav-link", ".nav-item",
            "button[data-panel]",
        ]

        for selector in nav_selectors:
            try:
                elements = await self._page.query_selector_all(selector)
                if not elements:
                    continue

                for i, el in enumerate(elements[:5]):
                    start = time.time()
                    try:
                        text = (await el.inner_text()).strip()[:30] or f"Element #{i}"
                        is_visible = await el.is_visible()
                        if not is_visible:
                            continue

                        self._emit("CLICK", {"element": text, "selector": selector})
                        await el.click(timeout=5000)
                        await self._page.wait_for_load_state("networkidle", timeout=8000)
                        elapsed = (time.time() - start) * 1000

                        result = TestResult(f"Nav: '{text}'", True,
                            f"Clicked OK → {self._page.url[-60:]}", elapsed)
                    except Exception as e:
                        elapsed = (time.time() - start) * 1000
                        result = TestResult(f"Nav: '{text}'" if 'text' in dir() else f"Nav: {selector}",
                            False, f"Click failed: {str(e)[:100]}", elapsed)

                    self._record(result)
                    results.append(result)

                    # Return to base
                    await self._page.goto(self.base_url, wait_until="networkidle", timeout=10000)
                break
            except Exception:
                continue

        if not results:
            result = TestResult("Navigation", True, "No nav elements found — skipped", 0)
            self._record(result)
            results.append(result)

        return results

    async def test_forms(self) -> list[TestResult]:
        """Find input fields, type test data, verify interaction."""
        results = []
        selectors = ["textarea", "input[type='text']",
                      "input:not([type='hidden']):not([type='checkbox'])"]

        for selector in selectors:
            try:
                elements = await self._page.query_selector_all(selector)
                if not elements:
                    continue

                for i, el in enumerate(elements[:3]):
                    start = time.time()
                    try:
                        if not await el.is_visible():
                            continue
                        field_id = await el.get_attribute("id") or await el.get_attribute("name") or f"field_{i}"
                        placeholder = await el.get_attribute("placeholder") or ""

                        self._emit("TYPE", {"field": field_id, "value": "Phantom QA test input"})
                        await el.click(timeout=3000)
                        await el.fill("Phantom QA test input")
                        value = await el.input_value()
                        elapsed = (time.time() - start) * 1000

                        passed = value == "Phantom QA test input"
                        result = TestResult(f"Form: '{field_id}'", passed,
                            f"Input {'accepted' if passed else 'rejected'} | placeholder: '{placeholder[:30]}'", elapsed)
                        await el.fill("")  # Clean up
                    except Exception as e:
                        elapsed = (time.time() - start) * 1000
                        result = TestResult(f"Form: #{i}", False, str(e)[:100], elapsed)

                    self._record(result)
                    results.append(result)
                break
            except Exception:
                continue

        if not results:
            result = TestResult("Forms", True, "No form fields found — skipped", 0)
            self._record(result)
            results.append(result)

        return results

    async def test_responsive(self) -> list[TestResult]:
        """Test at mobile, tablet, and desktop viewports."""
        results = []
        viewports = [
            {"name": "Mobile (375px)", "width": 375, "height": 812},
            {"name": "Tablet (768px)", "width": 768, "height": 1024},
            {"name": "Desktop (1280px)", "width": 1280, "height": 800},
        ]

        for vp in viewports:
            start = time.time()
            try:
                self._emit("VIEWPORT", {"viewport": vp["name"], "width": vp["width"]})
                await self._page.set_viewport_size({"width": vp["width"], "height": vp["height"]})
                await self._page.goto(self.base_url, wait_until="networkidle", timeout=15000)
                await asyncio.sleep(0.5)

                has_overflow = await self._page.evaluate(
                    "() => document.documentElement.scrollWidth > document.documentElement.clientWidth"
                )
                body = await self._page.inner_text("body")
                elapsed = (time.time() - start) * 1000

                issues = []
                if has_overflow:
                    issues.append("horizontal overflow")
                if len(body.strip()) < 10:
                    issues.append("blank page")

                passed = len(issues) == 0
                result = TestResult(f"Responsive: {vp['name']}", passed,
                    "Layout OK" if passed else "; ".join(issues), elapsed)
                result.screenshot = await self._screenshot(f"responsive_{vp['width']}")
            except Exception as e:
                elapsed = (time.time() - start) * 1000
                result = TestResult(f"Responsive: {vp['name']}", False, str(e)[:200], elapsed)

            self._record(result)
            results.append(result)

        await self._page.set_viewport_size({"width": 1280, "height": 800})
        return results

    async def test_console_errors(self) -> TestResult:
        """Evaluate accumulated console errors."""
        start = time.time()
        error_count = len(self._console_errors)
        warn_count = len(self._console_warnings)
        elapsed = (time.time() - start) * 1000

        if error_count > 5:
            result = TestResult("Console Errors", False,
                f"{error_count} errors, {warn_count} warnings | First: {self._console_errors[0][:80]}", elapsed)
        elif error_count > 0:
            result = TestResult("Console Errors", True,
                f"{error_count} error(s), {warn_count} warning(s) — within tolerance", elapsed)
        else:
            result = TestResult("Console Errors", True,
                f"Clean — 0 errors, {warn_count} warning(s)", elapsed)

        self._record(result)
        return result

    # ── Full Suite ────────────────────────────────────────

    async def run_full_suite(self, test_plan: dict = None) -> dict:
        """
        Run the complete Ghost User UI test suite.
        Returns structured results dict.
        """
        app_name = test_plan.get("_discovery", {}).get("app_title", "App") if test_plan else "App"
        logger.info(f"👻 Ghost User '{self.persona['name']}': Testing {self.base_url}")
        self._emit("SUITE_START", {"url": self.base_url, "action": "Starting full UI test suite"})

        try:
            await self._launch()

            await self.test_page_load()
            await self.test_navigation()
            await self.test_forms()
            await self.test_responsive()
            await self.test_console_errors()

        except Exception as e:
            logger.error(f"Ghost User suite crashed: {e}")
            self.results.append(TestResult("Suite Error", False, str(e)[:200], 0))
        finally:
            await self._close()

        total = len(self.results)
        passed = sum(1 for r in self.results if r.passed)
        score = round(passed / total * 100) if total > 0 else 0

        logger.info(f"👻 Ghost User: {passed}/{total} passed (Score: {score}/100)")
        self._emit("SUITE_END", {"passed": passed, "total": total, "score": score})

        return {
            "agent": "ghost_user",
            "persona": self.persona,
            "score": score,
            "total_tests": total,
            "passed": passed,
            "failed": total - passed,
            "results": [r.to_dict() for r in self.results],
            "console_errors": self._console_errors[:10],
            "console_warnings": self._console_warnings[:10],
        }


# ══════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════

async def run_ghost_user(target_url: str, test_plan: dict = None,
                          headed: bool = False, event_callback=None) -> dict:
    """Run the Ghost User agent against a target URL."""
    persona = (test_plan or {}).get("persona_recommendation", {
        "name": "Default Tester",
        "behavior": "Methodical",
        "expertise": "tech-savvy",
    })

    runner = GhostUserRunner(target_url, persona=persona, headed=headed,
                              event_callback=event_callback)
    return await runner.run_full_suite(test_plan)
