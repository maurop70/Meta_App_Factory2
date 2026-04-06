"""
Phantom QA Agent — Autonomous Testing Engine
=============================================
Permanent member of the Project Aether C-Suite.
Reports to: CTO (technical validation) + Compliance Officer (security audit).

Phantom impersonates configurable user personas and systematically tests
every feature of any app in the Meta App Factory ecosystem. It runs:
  - After every Factory build (triggered via n8n webhook)
  - On a nightly cron schedule
  - On-demand when invoked by the Strategic Commander

Usage:
  python phantom_agent.py                         # Test all registered apps
  python phantom_agent.py --app Resonance          # Test a specific app
  python phantom_agent.py --playbook chat_flow     # Run a specific playbook
"""

import os, sys, json, time, requests, logging
from datetime import datetime
from pathlib import Path

# ── Setup ──────────────────────────────────────────────
PHANTOM_DIR = os.path.dirname(os.path.abspath(__file__))
PERSONAS_DIR = os.path.join(PHANTOM_DIR, "personas")
PLAYBOOKS_DIR = os.path.join(PHANTOM_DIR, "playbooks")
REPORTS_DIR = os.path.join(PHANTOM_DIR, "reports")
FACTORY_DIR = os.path.normpath(os.path.join(PHANTOM_DIR, "..", "..", ".."))

sys.path.insert(0, FACTORY_DIR)
sys.path.insert(0, os.path.join(FACTORY_DIR, "Alpha_V2_Genesis"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [Phantom] %(message)s")
logger = logging.getLogger("PhantomQA")


# ── Persona Engine ─────────────────────────────────────
class Persona:
    """Loads a user persona from the personas/ directory."""
    def __init__(self, name: str):
        path = os.path.join(PERSONAS_DIR, f"{name}.json")
        if not os.path.exists(path):
            raise FileNotFoundError(f"Persona '{name}' not found at {path}")
        with open(path, "r", encoding="utf-8") as f:
            self.data = json.load(f)
        self.name = self.data["name"]
        self.role = self.data["role"]
        self.behaviors = self.data.get("behaviors", [])
        self.test_prompts = self.data.get("test_prompts", [])
        logger.info(f"Persona loaded: {self.name} ({self.role})")

    def get_prompts(self) -> list:
        return self.test_prompts


# ── Test Result Model ──────────────────────────────────
class TestResult:
    def __init__(self, test_name: str, passed: bool, details: str, duration_ms: float):
        self.test_name = test_name
        self.passed = passed
        self.details = details
        self.duration_ms = duration_ms
        self.timestamp = datetime.now().isoformat()

    def to_dict(self):
        return {
            "test": self.test_name,
            "status": "PASS" if self.passed else "FAIL",
            "details": self.details,
            "duration_ms": round(self.duration_ms, 2),
            "timestamp": self.timestamp
        }


# ── Playbook Runner ────────────────────────────────────
class PlaybookRunner:
    """Executes a YAML/JSON playbook against a target app."""
    def __init__(self, app_base_url: str):
        self.base_url = app_base_url.rstrip("/")
        self.results: list[TestResult] = []

    def test_endpoint(self, method: str, path: str, name: str,
                      expected_status: int = 200, payload: dict = None,
                      files: dict = None, check_field: str = None,
                      check_value=None) -> TestResult:
        """Run a single endpoint test."""
        url = f"{self.base_url}{path}"
        start = time.time()
        try:
            if method.upper() == "GET":
                r = requests.get(url, timeout=15)
            elif method.upper() == "POST" and files:
                r = requests.post(url, files=files, timeout=30)
            else:
                r = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=30)

            elapsed = (time.time() - start) * 1000
            passed = r.status_code == expected_status

            details = f"HTTP {r.status_code}"
            if check_field and passed:
                try:
                    data = r.json()
                    actual = data.get(check_field)
                    if check_value is not None:
                        field_ok = actual == check_value
                        passed = passed and field_ok
                        details += f" | {check_field}={actual} (expected {check_value})"
                    else:
                        details += f" | {check_field}={actual}"
                except Exception:
                    details += " | Could not parse JSON"

            result = TestResult(name, passed, details, elapsed)
        except requests.exceptions.ConnectionError:
            elapsed = (time.time() - start) * 1000
            result = TestResult(name, False, "CONNECTION_REFUSED — server not running", elapsed)
        except Exception as e:
            elapsed = (time.time() - start) * 1000
            result = TestResult(name, False, f"EXCEPTION: {str(e)[:200]}", elapsed)

        self.results.append(result)
        status_icon = "✅" if result.passed else "❌"
        logger.info(f"  {status_icon} {name}: {result.details} ({result.duration_ms:.0f}ms)")
        return result

    def test_chat_stream(self, prompt: str, name: str, expect_error: bool = False) -> TestResult:
        """Test the SSE chat streaming endpoint."""
        url = f"{self.base_url}/api/chat/stream"
        start = time.time()
        try:
            r = requests.post(url, json={"prompt": prompt}, headers={"Content-Type": "application/json"},
                              stream=True, timeout=30)
            elapsed = (time.time() - start) * 1000

            if r.status_code != 200:
                result = TestResult(name, expect_error, f"HTTP {r.status_code}", elapsed)
            else:
                chunks = []
                for line in r.iter_lines(decode_unicode=True):
                    if line and line.startswith("data: "):
                        try:
                            event = json.loads(line[6:])
                            if "text" in event:
                                chunks.append(event["text"])
                            if "error" in event:
                                result = TestResult(name, expect_error,
                                                    f"STREAM_ERROR: {event['error'][:100]}", elapsed)
                                self.results.append(result)
                                return result
                        except json.JSONDecodeError:
                            pass

                full_text = "".join(chunks)
                passed = len(full_text) > 0 and not expect_error
                details = f"Streamed {len(full_text)} chars, {len(chunks)} chunks"
                result = TestResult(name, passed, details, elapsed)

        except Exception as e:
            elapsed = (time.time() - start) * 1000
            result = TestResult(name, False, f"EXCEPTION: {str(e)[:200]}", elapsed)

        self.results.append(result)
        status_icon = "✅" if result.passed else "❌"
        logger.info(f"  {status_icon} {name}: {result.details} ({result.duration_ms:.0f}ms)")
        return result

    def test_file_upload(self, file_path: str, name: str, expect_ocr: bool = False) -> TestResult:
        """Test file upload + optional OCR validation."""
        start = time.time()
        try:
            with open(file_path, "rb") as f:
                r = requests.post(f"{self.base_url}/api/upload",
                                  files={"file": (os.path.basename(file_path), f)}, timeout=30)
            elapsed = (time.time() - start) * 1000

            if r.status_code != 200:
                result = TestResult(name, False, f"HTTP {r.status_code}", elapsed)
            else:
                data = r.json()
                text_len = data.get("text_length", 0)
                study = data.get("study_available", False)

                if expect_ocr:
                    passed = text_len > 50 and study
                    details = f"OCR extracted {text_len} chars, study_available={study}"
                else:
                    passed = text_len > 0
                    details = f"Extracted {text_len} chars"

                result = TestResult(name, passed, details, elapsed)

        except Exception as e:
            elapsed = (time.time() - start) * 1000
            result = TestResult(name, False, f"EXCEPTION: {str(e)[:200]}", elapsed)

        self.results.append(result)
        status_icon = "✅" if result.passed else "❌"
        logger.info(f"  {status_icon} {name}: {result.details} ({result.duration_ms:.0f}ms)")
        return result

    def test_mindmap(self, messages: list, name: str) -> TestResult:
        """Test conversation mind-map generation."""
        url = f"{self.base_url}/api/study/conversation-mindmap"
        start = time.time()
        try:
            r = requests.post(url, json={"messages": messages},
                              headers={"Content-Type": "application/json"}, timeout=30)
            elapsed = (time.time() - start) * 1000
            if r.status_code == 200:
                data = r.json()
                has_mermaid = "mermaid" in data and len(data["mermaid"]) > 20
                result = TestResult(name, has_mermaid,
                                    f"Mermaid code: {len(data.get('mermaid', ''))} chars", elapsed)
            else:
                result = TestResult(name, False, f"HTTP {r.status_code}", elapsed)
        except Exception as e:
            elapsed = (time.time() - start) * 1000
            result = TestResult(name, False, f"EXCEPTION: {str(e)[:200]}", elapsed)

        self.results.append(result)
        status_icon = "✅" if result.passed else "❌"
        logger.info(f"  {status_icon} {name}: {result.details} ({result.duration_ms:.0f}ms)")
        return result


# ── Report Generator ───────────────────────────────────
def generate_report(app_name: str, persona_name: str, results: list[TestResult]) -> str:
    """Generate a markdown test report and save it."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{app_name}_{persona_name}_{timestamp}.md"
    filepath = os.path.join(REPORTS_DIR, filename)

    total = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = total - passed
    pass_rate = (passed / total * 100) if total > 0 else 0

    lines = [
        f"# Phantom QA Report — {app_name}",
        f"**Persona:** {persona_name}",
        f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Pass Rate:** {pass_rate:.0f}% ({passed}/{total})",
        "",
        "| # | Test | Status | Details | Duration |",
        "|---|---|---|---|---|",
    ]
    for i, r in enumerate(results, 1):
        icon = "✅" if r.passed else "❌"
        lines.append(f"| {i} | {r.test_name} | {icon} {r.to_dict()['status']} | {r.details} | {r.duration_ms:.0f}ms |")

    lines.append("")
    if failed > 0:
        lines.append("## Failures")
        for r in results:
            if not r.passed:
                lines.append(f"- **{r.test_name}**: {r.details}")

    report_text = "\n".join(lines)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(report_text)

    logger.info(f"Report saved: {filepath}")
    return filepath


# ── Resonance Test Suite ───────────────────────────────
def run_resonance_suite(persona: Persona, base_url: str = "http://localhost:5006"):
    """Full regression test suite for Resonance."""
    logger.info(f"═══ PHANTOM QA: Testing Resonance as '{persona.name}' ═══")
    runner = PlaybookRunner(base_url)

    # 1. Health Check
    runner.test_endpoint("GET", "/api/health", "Backend Health Check",
                         check_field="status", check_value="healthy")

    # 2. Chat Streaming (per persona prompt)
    for i, prompt in enumerate(persona.get_prompts()):
        runner.test_chat_stream(prompt, f"Chat Stream [{i+1}]: {prompt[:40]}...")

    # 3. File Upload (text)
    txt_path = os.path.join(PHANTOM_DIR, "test_assets", "sample_homework.txt")
    if os.path.exists(txt_path):
        runner.test_file_upload(txt_path, "File Upload (TXT)")

    # 4. Image Upload + OCR
    img_path = os.path.join(FACTORY_DIR, "Resonance", "uploads", "homework_test.png")
    if os.path.exists(img_path):
        runner.test_file_upload(img_path, "Image Upload + Vision OCR", expect_ocr=True)

    # 5. Mind Map Generation
    runner.test_mindmap([
        {"role": "user", "text": "What is photosynthesis?"},
        {"role": "assistant", "text": "Photosynthesis is how plants convert sunlight into energy using chlorophyll."},
        {"role": "user", "text": "How does chlorophyll work?"},
        {"role": "assistant", "text": "Chlorophyll absorbs light energy and uses it to convert CO2 and water into glucose and oxygen."}
    ], "Conversation Mind Map")

    # 6. Uploads List
    runner.test_endpoint("GET", "/api/uploads", "Uploads List API")

    # 7. Chat Clear
    runner.test_endpoint("POST", "/api/chat/clear", "Chat Clear",
                         check_field="status", check_value="ok")

    # Generate Report
    report_path = generate_report("Resonance", persona.name, runner.results)

    total = len(runner.results)
    passed = sum(1 for r in runner.results if r.passed)
    logger.info(f"═══ RESULTS: {passed}/{total} passed ═══")
    return runner.results, report_path


# ── Sentinel Bridge Test Suite ─────────────────────────
def run_sentinel_suite(base_url: str = "http://localhost:5009"):
    """Full regression test suite for Sentinel Bridge."""
    logger.info(f"═══ PHANTOM QA: Testing Sentinel Bridge ═══")
    runner = PlaybookRunner(base_url)

    # 1. Health Check
    runner.test_endpoint("GET", "/", "Root Health Check",
                         check_field="status", check_value="active")

    # 2. Dashboard Loads
    runner.test_endpoint("GET", "/dashboard", "Dashboard HTML Loads", expected_status=200)

    # 3. PWA Manifest
    runner.test_endpoint("GET", "/manifest.json", "PWA Manifest",
                         check_field="short_name", check_value="Sentinel")

    # 4. Service Worker
    runner.test_endpoint("GET", "/sw.js", "Service Worker JS", expected_status=200)

    # 5. Create Reminder
    runner.test_endpoint("POST", "/api/reminders", "Create Reminder",
                         payload={"text": "Phantom QA test reminder — delete me", "source": "phantom_qa"},
                         check_field="status", check_value="created")

    # 6. List Reminders
    runner.test_endpoint("GET", "/api/reminders", "List Reminders",
                         check_field="total")

    # 7. Categories
    runner.test_endpoint("GET", "/api/categories", "List Categories")

    # 8. Calendar Events
    runner.test_endpoint("GET", "/api/calendar/events?month=3&year=2026", "Calendar Events API")

    # 9. Telemetry
    runner.test_endpoint("GET", "/api/telemetry", "Telemetry Dashboard",
                         check_field="app", check_value="Sentinel Bridge")

    # 10. Tunnel Status
    runner.test_endpoint("GET", "/api/tunnel/status", "Tunnel Status API")

    # 11. Vault Audit
    runner.test_endpoint("GET", "/api/vault/audit", "Vault Audit API")

    # 12. Self-Heal Status
    runner.test_endpoint("GET", "/api/selfheal", "Self-Heal Dashboard")

    # Generate Report
    report_path = generate_report("Sentinel", "admin", runner.results)

    total = len(runner.results)
    passed = sum(1 for r in runner.results if r.passed)
    logger.info(f"=== RESULTS: {passed}/{total} passed ===")
    return runner.results, report_path


# ══════════════════════════════════════════════════════════
#  DYNAMIC PERSONA GENERATOR
# ══════════════════════════════════════════════════════════

class DynamicPersonaGenerator:
    """
    Generates task-specific test personas using Gemini AI.
    This ensures Phantom QA is NOT limited to pre-built apps —
    it can create appropriate testers for ANY application or feature.
    """

    @staticmethod
    def generate(app_name: str, app_description: str = "",
                 base_url: str = "", num_personas: int = 2) -> list:
        """
        Generate test personas tailored to a specific app/task.

        Returns a list of persona dicts with: name, role, behaviors, test_prompts
        """
        api_key = os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            logger.warning("No GEMINI_API_KEY — using default generic personas")
            return DynamicPersonaGenerator._generic_personas(app_name)

        gen_prompt = f"""You are Phantom QA, an autonomous testing agent.
Generate {num_personas} distinct test personas for the app "{app_name}".
{f'App description: {app_description}' if app_description else ''}
{f'Base URL: {base_url}' if base_url else ''}

Each persona should simulate a different type of user who would realistically
use this application. Include edge-case testers and adversarial testers.

Respond with a JSON array where each element has:
- "name": short first name for the persona
- "role": 1-line description of who they are
- "behaviors": array of 3-4 testing behaviors they exhibit
- "test_endpoints": array of objects with "method", "path", "name", "payload" (optional)

The test_endpoints should cover realistic user journeys for this specific app.
Include both happy-path and edge-case tests.

Respond ONLY with valid JSON array, no markdown fences."""

        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
            payload = {
                "contents": [{"parts": [{"text": gen_prompt}]}],
                "generationConfig": {"temperature": 0.5, "maxOutputTokens": 4096},
            }
            resp = requests.post(url, json=payload, timeout=30)
            if resp.status_code != 200:
                logger.warning(f"Gemini persona gen failed: {resp.status_code}")
                return DynamicPersonaGenerator._generic_personas(app_name)

            text = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0]

            personas = json.loads(text)
            logger.info(f"Generated {len(personas)} dynamic personas for {app_name}")

            # Save generated personas for future reference
            for p in personas:
                save_path = os.path.join(PERSONAS_DIR, f"dynamic_{app_name}_{p['name'].lower()}.json")
                with open(save_path, "w", encoding="utf-8") as f:
                    json.dump(p, f, indent=2)
                logger.info(f"  Saved persona: {p['name']} ({p['role']})")

            return personas

        except Exception as e:
            logger.warning(f"Dynamic persona generation failed: {e}")
            return DynamicPersonaGenerator._generic_personas(app_name)

    @staticmethod
    def _generic_personas(app_name: str) -> list:
        """Fallback: generate generic test personas without AI."""
        return [
            {
                "name": "PowerUser",
                "role": f"Experienced {app_name} user — exercises every feature",
                "behaviors": [
                    "Rapid API calls", "Tests all CRUD operations",
                    "Uploads files", "Checks edge cases"
                ],
                "test_endpoints": [
                    {"method": "GET", "path": "/", "name": "Root endpoint"},
                    {"method": "GET", "path": "/api/health", "name": "Health check"},
                    {"method": "GET", "path": "/api/status", "name": "Status endpoint"},
                ]
            },
            {
                "name": "Adversary",
                "role": f"Security tester — tries to break {app_name}",
                "behaviors": [
                    "Sends malformed input", "Tests auth boundaries",
                    "Injects special characters", "Tests rate limits"
                ],
                "test_endpoints": [
                    {"method": "GET", "path": "/", "name": "Root access"},
                    {"method": "POST", "path": "/api/health", "name": "POST to GET endpoint"},
                    {"method": "GET", "path": "/nonexistent", "name": "404 handling"},
                ]
            }
        ]


# ══════════════════════════════════════════════════════════
#  UNIVERSAL APP SCANNER (Dynamic Test Suite)
# ══════════════════════════════════════════════════════════

def run_dynamic_suite(app_name: str, base_url: str,
                      app_description: str = "") -> tuple:
    """
    Dynamic test suite that works with ANY application.

    1. Probes the app for common endpoints (OpenAPI, health, root)
    2. Generates AI-powered personas specific to the app
    3. Runs their test_endpoints against the live server
    4. Generates a report

    This ensures Phantom QA is never limited to hardcoded app suites.
    """
    logger.info(f"=== PHANTOM QA: Dynamic Testing '{app_name}' at {base_url} ===")
    runner = PlaybookRunner(base_url)

    # Phase 1: Standard probe endpoints (works for any HTTP app)
    logger.info("Phase 1: Standard endpoint probe")
    runner.test_endpoint("GET", "/", "Root Endpoint Probe")

    # Try common health patterns
    for health_path in ["/api/health", "/health", "/healthz", "/api/status"]:
        try:
            r = requests.get(f"{base_url}{health_path}", timeout=5)
            if r.status_code == 200:
                runner.test_endpoint("GET", health_path, f"Health Check ({health_path})")
                break
        except Exception:
            continue

    # Try OpenAPI/docs for endpoint discovery
    openapi_endpoints = []
    for docs_path in ["/openapi.json", "/docs", "/api/docs"]:
        try:
            r = requests.get(f"{base_url}{docs_path}", timeout=5)
            if r.status_code == 200 and docs_path.endswith(".json"):
                spec = r.json()
                paths = spec.get("paths", {})
                for path, methods in paths.items():
                    for method in methods:
                        if method.upper() in ["GET", "POST", "PUT", "DELETE"]:
                            openapi_endpoints.append({
                                "method": method.upper(),
                                "path": path,
                                "name": f"OpenAPI: {method.upper()} {path}"
                            })
                logger.info(f"Discovered {len(openapi_endpoints)} endpoints from OpenAPI")
                break
        except Exception:
            continue

    # Test discovered OpenAPI endpoints (limit to 10 for sanity)
    if openapi_endpoints:
        logger.info("Phase 2: OpenAPI-discovered endpoints")
        for ep in openapi_endpoints[:10]:
            runner.test_endpoint(ep["method"], ep["path"], ep["name"])

    # Phase 3: Dynamic persona-driven testing
    logger.info("Phase 3: AI persona-driven testing")
    personas = DynamicPersonaGenerator.generate(
        app_name, app_description, base_url
    )

    for persona in personas:
        logger.info(f"  Testing as: {persona['name']} ({persona['role']})")
        for ep in persona.get("test_endpoints", []):
            method = ep.get("method", "GET")
            path = ep.get("path", "/")
            name = f"[{persona['name']}] {ep.get('name', path)}"
            payload = ep.get("payload")
            expected = ep.get("expected_status", 200)
            runner.test_endpoint(method, path, name,
                                 expected_status=expected, payload=payload)

    # Generate Report
    persona_names = "+".join(p["name"] for p in personas)
    report_path = generate_report(app_name, f"dynamic_{persona_names}", runner.results)

    total = len(runner.results)
    passed = sum(1 for r in runner.results if r.passed)
    logger.info(f"=== RESULTS: {passed}/{total} passed ===")
    return runner.results, report_path


# ── Main Entry Point ───────────────────────────────────
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Phantom QA Agent — Universal Testing Engine")
    parser.add_argument("--app", default="Resonance",
                        help="App to test. Use any name — dynamic testing activates for unknown apps.")
    parser.add_argument("--persona", default="leo_friend", help="Persona to use (Resonance only)")
    parser.add_argument("--url", help="Backend API base URL")
    parser.add_argument("--frontend", help="Frontend UI URL (for Playwright browser tests)")
    parser.add_argument("--dir", help="App directory path")
    parser.add_argument("--describe", default="",
                        help="App description for dynamic persona generation")
    parser.add_argument("--headed", action="store_true",
                        help="Run Playwright browser in visible mode (debugging)")
    parser.add_argument("--stage", help="Run specific gate stage(s) only (comma-separated). "
                        "Options: infrastructure,architecture,brand,data_integrity,"
                        "ui_testing,api_testing,critic_review")
    parser.add_argument("--legacy", action="store_true",
                        help="Use legacy test suites (Resonance/Sentinel) instead of full gate")
    args = parser.parse_args()

    app = args.app.lower()

    # Legacy mode: use original built-in suites
    if args.legacy:
        if app == "resonance":
            url = args.url or "http://localhost:5006"
            persona_obj = Persona(args.persona)
            results, report = run_resonance_suite(persona_obj, url)
        elif app == "sentinel":
            url = args.url or "http://localhost:5009"
            results, report = run_sentinel_suite(url)
        else:
            url = args.url
            if not url:
                logger.error(f"--url is required for dynamic testing of '{args.app}'")
                sys.exit(1)
            results, report = run_dynamic_suite(args.app, url, args.describe)

        failed = sum(1 for r in results if not r.passed)
        sys.exit(1 if failed > 0 else 0)

    # Default mode: full Phantom QA Gate pipeline
    try:
        from phantom_gate import run_phantom_gate

        context = {
            "app_name": args.app,
            "base_url": args.url or "",
            "frontend_url": args.frontend or "",
            "app_dir": args.dir or "",
            "description": args.describe,
            "headed": args.headed,
        }
        if args.stage:
            context["stages"] = [s.strip() for s in args.stage.split(",")]

        result = run_phantom_gate(context)

        print(f"\n{'='*55}")
        print(f"  🧪 PHANTOM QA GATE — {result['app_name']}")
        print(f"{'='*55}")
        print(f"  Verdict:  {result['verdict']}")
        print(f"  Score:    {result['score']}/100")
        print(f"  Duration: {result['duration_seconds']}s")
        print(f"  Report:   {result['report_path']}")
        print(f"{'='*55}\n")

        sys.exit(0 if result["verdict"] != "FAIL" else 1)

    except ImportError as e:
        logger.warning(f"phantom_gate not available ({e}) — falling back to dynamic suite")
        url = args.url
        if not url:
            logger.error(f"--url is required for testing '{args.app}'")
            sys.exit(1)
        results, report = run_dynamic_suite(args.app, url, args.describe)
        failed = sum(1 for r in results if not r.passed)
        sys.exit(1 if failed > 0 else 0)

