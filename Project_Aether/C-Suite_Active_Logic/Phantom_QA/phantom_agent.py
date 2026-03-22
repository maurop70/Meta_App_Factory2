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


# ── Main Entry Point ───────────────────────────────────
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Phantom QA Agent")
    parser.add_argument("--app", default="Resonance", help="App to test")
    parser.add_argument("--persona", default="leo_friend", help="Persona to use")
    parser.add_argument("--url", default="http://localhost:5006", help="Base URL")
    args = parser.parse_args()

    persona = Persona(args.persona)

    if args.app.lower() == "resonance":
        results, report = run_resonance_suite(persona, args.url)
    else:
        logger.error(f"No test suite registered for app: {args.app}")
        sys.exit(1)

    # Exit with failure code if any tests failed
    failed = sum(1 for r in results if not r.passed)
    sys.exit(1 if failed > 0 else 0)
