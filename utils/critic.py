import requests
import time
import sys
import os
import subprocess
import json
from datetime import datetime, timezone


class ArtisanCritic:
    """
    The Artisan Critic (formerly Inspector).
    Validates newly built apps before "official" handover.
    Global Quality Sync Component.

    V2: Active Recall — runs auto-generated test suites
    and returns structured verdicts for the Validation Loop.
    """
    def __init__(self):
        pass

    def run_smoke_test(self, app_name, webhook_url):
        """Sends a test ping to the app's webhook."""
        print(f"--- Artisan Critic: Running Smoke Test for '{app_name}' ---")
        print(f"- Testing URL: {webhook_url}")
        
        test_payload = {
            "prompt": "PING_TEST",
            "context": "POST-BUILD_INSPECTION"
        }

        try:
            # Give N8N a moment to fully initialize the new workflow
            time.sleep(5)
            response = requests.post(webhook_url, json=test_payload, timeout=30)
            
            if response.status_code == 200:
                print(f"--- Artisan Critic: SUCCESS! App '{app_name}' is alive and responsive. ---", flush=True)
                return True
            else:
                print(f"--- Artisan Critic: WARNING! App '{app_name}' returned status {response.status_code}. ---", flush=True)
                if response.text:
                    print(f"- Feedback: {response.text[:100]}...", flush=True)
                return False
        except Exception as e:
            print(f"--- Artisan Critic: FAILED! Could not reach App '{app_name}'. Error: {e} ---", flush=True)
            return False

    # ── Active Recall: Validation Loop ────────────────────────

    def validate_refinement(self, app_dir, app_name, test_filename="test_case.py"):
        """
        Run the auto-generated test suite for a refined app.
        Returns a CriticVerdict dict with pass/fail status and details.

        Flow:
          1. Locate test_filename in app_dir
          2. Run via `python -m unittest` (stdlib, no dependencies)
          3. Parse stdout/stderr for pass/fail
          4. Return structured verdict
        """
        print(f"--- Artisan Critic: Validation Loop for '{app_name}' ---", flush=True)

        test_path = os.path.join(app_dir, test_filename)
        if not os.path.isfile(test_path):
            return self._verdict(
                passed=False,
                app_name=app_name,
                total_tests=0,
                failures=1,
                failure_details=["Test file not found: " + test_filename],
            )

        # Syntax-check the test file first
        try:
            with open(test_path, "r", encoding="utf-8", errors="replace") as f:
                source = f.read()
            compile(source, test_filename, "exec")
        except SyntaxError as e:
            return self._verdict(
                passed=False,
                app_name=app_name,
                total_tests=0,
                failures=1,
                failure_details=[f"Test file syntax error: {e.msg} (line {e.lineno})"],
            )

        # Run tests via unittest
        python = sys.executable or "python"
        try:
            result = subprocess.run(
                [python, "-m", "unittest", test_filename[:-3], "-v"],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=app_dir,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            )
            stdout = result.stdout or ""
            stderr = result.stderr or ""
            combined = stdout + "\n" + stderr

            # Parse results from unittest output
            total, failures, errors, failure_details = self._parse_unittest_output(combined)
            passed = result.returncode == 0

            print(f"--- Artisan Critic: {'PASSED' if passed else 'FAILED'} "
                  f"({total} tests, {failures} failures, {errors} errors) ---", flush=True)

            return self._verdict(
                passed=passed,
                app_name=app_name,
                total_tests=total,
                failures=failures + errors,
                failure_details=failure_details,
                raw_output=combined[-2000:] if combined else "",
            )

        except subprocess.TimeoutExpired:
            return self._verdict(
                passed=False,
                app_name=app_name,
                total_tests=0,
                failures=1,
                failure_details=["Test execution timed out (60s limit)"],
            )
        except Exception as e:
            return self._verdict(
                passed=False,
                app_name=app_name,
                total_tests=0,
                failures=1,
                failure_details=[f"Test execution error: {str(e)}"],
            )

    def _parse_unittest_output(self, output):
        """
        Parse unittest verbose output to extract test counts and failure details.
        Returns: (total, failures, errors, failure_details_list)
        """
        import re

        total = 0
        failures = 0
        errors = 0
        failure_details = []

        # Look for the summary line: "Ran X test(s) in Y.YYYs"
        ran_match = re.search(r"Ran (\d+) test", output)
        if ran_match:
            total = int(ran_match.group(1))

        # "FAILED (failures=X, errors=Y)" or variants
        fail_match = re.search(r"FAILED \((.+?)\)", output)
        if fail_match:
            detail = fail_match.group(1)
            f_match = re.search(r"failures=(\d+)", detail)
            e_match = re.search(r"errors=(\d+)", detail)
            if f_match:
                failures = int(f_match.group(1))
            if e_match:
                errors = int(e_match.group(1))

        # Extract individual failure/error blocks
        # Pattern: FAIL: test_name (module)\n------\nTraceback...
        fail_blocks = re.findall(
            r"(?:FAIL|ERROR): (\S+.*?)\n[-=]+\n(.*?)(?=\n(?:FAIL|ERROR): |\nRan \d+ test|\Z)",
            output,
            re.DOTALL,
        )
        for test_name, traceback_text in fail_blocks:
            # Get the last line of the traceback as the summary
            tb_lines = [l.strip() for l in traceback_text.strip().split("\n") if l.strip()]
            summary = tb_lines[-1] if tb_lines else "Unknown failure"
            failure_details.append(f"{test_name.strip()}: {summary}")

        # If we found failures but no detail blocks, add a generic entry
        if (failures + errors) > 0 and not failure_details:
            # Grab the last meaningful lines
            lines = [l for l in output.strip().split("\n") if l.strip()]
            failure_details.append("; ".join(lines[-3:]) if lines else "Test failed (details unavailable)")

        return total, failures, errors, failure_details

    def _verdict(self, passed, app_name, total_tests, failures, failure_details,
                 raw_output=""):
        """Build a structured CriticVerdict dict."""
        return {
            "passed": passed,
            "app_name": app_name,
            "total_tests": total_tests,
            "failures": failures,
            "failure_details": failure_details,
            "raw_output": raw_output,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "verdict": "APPROVE" if passed else "REVISE",
        }


if __name__ == "__main__":
    # Test smoke
    critic = ArtisanCritic()
    critic.run_smoke_test("TestApp", "https://httpbin.org/post")
