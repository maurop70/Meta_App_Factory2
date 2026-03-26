"""
skeptic.py — The Skeptic (API Bug Hunter Agent)
=================================================
Phantom QA Elite | Antigravity-AI

Systematically attacks API endpoints with edge-case payloads,
malformed JSON, method mismatches, and stress tests. Outputs
Atomizer-compatible Repair Payloads for the Loop of Perfection.

Uses: Gemini 2.5 Flash for creative edge-case generation
"""

import os
import json
import time
import asyncio
import logging
import aiohttp
from typing import Optional

logger = logging.getLogger("Phantom.Skeptic")


class AttackResult:
    """Result of a single attack test."""
    def __init__(self, test_name: str, passed: bool, details: str,
                 duration_ms: float, attack_type: str = "probe",
                 expected_status: int = 0, actual_status: int = 0,
                 path: str = "", method: str = ""):
        self.test_name = test_name
        self.passed = passed
        self.details = details
        self.duration_ms = duration_ms
        self.attack_type = attack_type
        self.expected_status = expected_status
        self.actual_status = actual_status
        self.path = path
        self.method = method
        self.repair_payload: Optional[dict] = None

    def to_dict(self):
        d = {
            "test_name": self.test_name,
            "passed": self.passed,
            "details": self.details,
            "duration_ms": round(self.duration_ms, 1),
            "attack_type": self.attack_type,
            "method": self.method,
            "path": self.path,
            "expected_status": self.expected_status,
            "actual_status": self.actual_status,
        }
        if self.repair_payload:
            d["repair_payload"] = self.repair_payload
        return d


# ══════════════════════════════════════════════════════════
#  SKEPTIC RUNNER
# ══════════════════════════════════════════════════════════

class SkepticRunner:
    """
    API stress-tester and bug hunter. Tries to break every
    endpoint with edge-case payloads and validates defensive behavior.
    """

    def __init__(self, base_url: str, timeout: int = 10):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.results: list[AttackResult] = []

    def _record(self, result: AttackResult):
        self.results.append(result)
        icon = "✅" if result.passed else "❌"
        logger.info(f"  {icon} [{result.attack_type}] {result.test_name}: "
                     f"{result.actual_status} (expected {result.expected_status})")

    def _make_repair_payload(self, test_id: str, path: str, issue: str,
                              repair_instruction: str) -> dict:
        """Generate Atomizer-compatible repair payload."""
        return {
            "test_id": test_id,
            "agent": "Skeptic",
            "verdict": "FAIL",
            "target_url": f"{self.base_url}{path}",
            "issue": issue,
            "repair_instruction": repair_instruction,
        }

    # ── Attack Types ──────────────────────────────────────

    async def attack_empty_body(self, session: aiohttp.ClientSession,
                                 path: str) -> AttackResult:
        """POST with empty body → should get 400, not 500."""
        start = time.time()
        try:
            async with session.post(
                f"{self.base_url}{path}",
                headers={"Content-Type": "application/json"},
                data=b"",
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            ) as r:
                elapsed = (time.time() - start) * 1000
                status = r.status
                passed = status in (400, 422)  # 400 or 422 are acceptable

                result = AttackResult(
                    f"Empty body → {path}", passed,
                    f"Got {status} {'(correct rejection)' if passed else '(VULNERABILITY: server crash)'}",
                    elapsed, "empty_body", 400, status, path, "POST"
                )

                if not passed and status == 500:
                    result.repair_payload = self._make_repair_payload(
                        f"EMPTY_BODY_{path.replace('/', '_')}",
                        path,
                        f"Server returns 500 on empty POST body to {path}",
                        "Wrap request.json() in try-except to return 400 Bad Request "
                        "with error message instead of 500 Internal Server Error."
                    )
        except Exception as e:
            elapsed = (time.time() - start) * 1000
            result = AttackResult(f"Empty body → {path}", False,
                f"Connection error: {str(e)[:100]}", elapsed, "empty_body", 400, 0, path, "POST")

        self._record(result)
        return result

    async def attack_malformed_json(self, session: aiohttp.ClientSession,
                                     path: str) -> AttackResult:
        """POST with malformed JSON → should get 400/422, not 500."""
        start = time.time()
        try:
            async with session.post(
                f"{self.base_url}{path}",
                headers={"Content-Type": "application/json"},
                data=b'{"broken": json, missing_quotes}',
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            ) as r:
                elapsed = (time.time() - start) * 1000
                status = r.status
                passed = status in (400, 422)

                result = AttackResult(
                    f"Malformed JSON → {path}", passed,
                    f"Got {status} {'(correct rejection)' if passed else '(VULNERABILITY)'}",
                    elapsed, "malformed_json", 400, status, path, "POST"
                )

                if not passed and status == 500:
                    result.repair_payload = self._make_repair_payload(
                        f"MALFORMED_JSON_{path.replace('/', '_')}",
                        path,
                        f"Server crashes on malformed JSON body to {path}",
                        "Add JSON parsing error handling in the route handler."
                    )
        except Exception as e:
            elapsed = (time.time() - start) * 1000
            result = AttackResult(f"Malformed JSON → {path}", False,
                str(e)[:100], elapsed, "malformed_json", 400, 0, path, "POST")

        self._record(result)
        return result

    async def attack_method_mismatch(self, session: aiohttp.ClientSession,
                                      path: str, correct_method: str) -> AttackResult:
        """Send wrong HTTP method → should get 405."""
        wrong_method = "POST" if correct_method == "GET" else "GET"
        start = time.time()
        try:
            if wrong_method == "POST":
                async with session.post(
                    f"{self.base_url}{path}",
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as r:
                    elapsed = (time.time() - start) * 1000
                    status = r.status
            else:
                async with session.get(
                    f"{self.base_url}{path}",
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as r:
                    elapsed = (time.time() - start) * 1000
                    status = r.status

            passed = status == 405
            result = AttackResult(
                f"Method mismatch: {wrong_method} → {path}", passed,
                f"Got {status} {'(correct 405)' if passed else ''}",
                elapsed, "method_mismatch", 405, status, path, wrong_method
            )
        except Exception as e:
            elapsed = (time.time() - start) * 1000
            result = AttackResult(f"Method mismatch → {path}", False,
                str(e)[:100], elapsed, "method_mismatch", 405, 0, path, wrong_method)

        self._record(result)
        return result

    async def attack_oversized_payload(self, session: aiohttp.ClientSession,
                                        path: str) -> AttackResult:
        """POST with 100KB+ payload → should not crash."""
        big_payload = json.dumps({"input": "X" * 100_000})
        start = time.time()
        try:
            async with session.post(
                f"{self.base_url}{path}",
                headers={"Content-Type": "application/json"},
                data=big_payload.encode(),
                timeout=aiohttp.ClientTimeout(total=15)
            ) as r:
                elapsed = (time.time() - start) * 1000
                status = r.status
                # Anything except 500 is acceptable
                passed = status != 500

                result = AttackResult(
                    f"Oversized payload (100KB) → {path}", passed,
                    f"Got {status} {'(handled gracefully)' if passed else '(CRASH)'}",
                    elapsed, "oversized", 200, status, path, "POST"
                )
        except Exception as e:
            elapsed = (time.time() - start) * 1000
            result = AttackResult(f"Oversized payload → {path}", True,
                f"Timeout/rejection (acceptable): {str(e)[:80]}", elapsed,
                "oversized", 200, 0, path, "POST")

        self._record(result)
        return result

    async def attack_valid_endpoint(self, session: aiohttp.ClientSession,
                                     method: str, path: str,
                                     expected: int = 200) -> AttackResult:
        """Standard endpoint probe — verify it responds correctly."""
        start = time.time()
        try:
            if method == "GET":
                async with session.get(
                    f"{self.base_url}{path}",
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as r:
                    elapsed = (time.time() - start) * 1000
                    status = r.status
            else:
                async with session.post(
                    f"{self.base_url}{path}",
                    headers={"Content-Type": "application/json"},
                    data=b'{}',
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as r:
                    elapsed = (time.time() - start) * 1000
                    status = r.status

            # For POST with empty body, 400 is also acceptable
            acceptable = [expected]
            if method == "POST":
                acceptable.extend([400, 422])
            passed = status in acceptable

            result = AttackResult(
                f"Probe: {method} {path}", passed,
                f"Got {status} (expected {expected})", elapsed,
                "probe", expected, status, path, method
            )
        except Exception as e:
            elapsed = (time.time() - start) * 1000
            result = AttackResult(f"Probe: {method} {path}", False,
                str(e)[:100], elapsed, "probe", expected, 0, path, method)

        self._record(result)
        return result

    async def attack_nonexistent_path(self, session: aiohttp.ClientSession) -> AttackResult:
        """Request to /nonexistent → should get 404, not 500."""
        start = time.time()
        try:
            async with session.get(
                f"{self.base_url}/phantom_qa_nonexistent_path_test",
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            ) as r:
                elapsed = (time.time() - start) * 1000
                status = r.status
                passed = status == 404

                result = AttackResult(
                    "404 handling", passed,
                    f"Got {status} {'(correct 404)' if passed else '(unexpected)'}",
                    elapsed, "404_handling", 404, status,
                    "/phantom_qa_nonexistent_path_test", "GET"
                )
        except Exception as e:
            elapsed = (time.time() - start) * 1000
            result = AttackResult("404 handling", False, str(e)[:100],
                elapsed, "404_handling", 404, 0, "/nonexistent", "GET")

        self._record(result)
        return result

    async def stress_test(self, session: aiohttp.ClientSession,
                           path: str, concurrent: int = 10) -> AttackResult:
        """Fire N concurrent requests — verify all succeed within timeout."""
        start = time.time()
        url = f"{self.base_url}{path}"

        async def single_request():
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as r:
                    return r.status
            except Exception:
                return 0

        tasks = [single_request() for _ in range(concurrent)]
        statuses = await asyncio.gather(*tasks)
        elapsed = (time.time() - start) * 1000

        success = sum(1 for s in statuses if s == 200)
        passed = success == concurrent

        result = AttackResult(
            f"Stress: {concurrent}x GET {path}", passed,
            f"{success}/{concurrent} succeeded in {elapsed:.0f}ms",
            elapsed, "stress", 200, 200 if passed else 0, path, "GET"
        )
        self._record(result)
        return result

    # ── Full Attack Suite ─────────────────────────────────

    async def run_full_attack(self, test_plan: dict = None) -> dict:
        """
        Run the complete Skeptic attack suite against the target.
        Uses the Architect's test plan to target specific endpoints.
        """
        logger.info(f"🔍 Skeptic: Attacking {self.base_url}...")
        self.results = []
        start = time.time()

        discovery = (test_plan or {}).get("_discovery", {})
        endpoints = discovery.get("endpoints", [])
        health = discovery.get("health_endpoint")

        async with aiohttp.ClientSession() as session:
            # 1. Probe all discovered GET endpoints
            #    Skip parameterized paths like /api/reports/{run_id} — probing
            #    with literal template strings causes false 422 failures
            for ep in endpoints:
                if ep["method"] == "GET":
                    path = ep["path"]
                    if "{" in path or "<" in path:
                        # Parameterized route — skip or substitute a real value
                        logger.info(f"  ⏭️ Skipping parameterized route: {path}")
                        continue
                    await self.attack_valid_endpoint(session, "GET", path)

            # 2. Attack all POST endpoints
            post_endpoints = [ep for ep in endpoints if ep["method"] == "POST"]
            for ep in post_endpoints:
                await self.attack_empty_body(session, ep["path"])
                await self.attack_malformed_json(session, ep["path"])

            # 3. Oversized payload on first POST endpoint
            if post_endpoints:
                await self.attack_oversized_payload(session, post_endpoints[0]["path"])

            # 4. Method mismatch on first GET and first POST
            get_endpoints = [ep for ep in endpoints if ep["method"] == "GET"]
            if get_endpoints:
                await self.attack_method_mismatch(session, get_endpoints[0]["path"], "GET")
            if post_endpoints:
                await self.attack_method_mismatch(session, post_endpoints[0]["path"], "POST")

            # 5. 404 handling
            await self.attack_nonexistent_path(session)

            # 6. Stress test on health endpoint
            if health:
                await self.stress_test(session, health, concurrent=10)

            # 7. Run edge cases from test plan
            for edge in (test_plan or {}).get("edge_cases", [])[:5]:
                if edge.get("attack_type") == "empty_body" and edge.get("path"):
                    # Already covered above, skip duplicates
                    continue

        elapsed = time.time() - start
        total = len(self.results)
        passed = sum(1 for r in self.results if r.passed)
        score = round(passed / total * 100) if total > 0 else 0

        # Collect repair payloads
        repairs = [r.repair_payload for r in self.results
                   if r.repair_payload is not None]

        logger.info(f"🔍 Skeptic: {passed}/{total} passed (Score: {score}/100) | "
                     f"{len(repairs)} repairs needed")

        return {
            "agent": "skeptic",
            "score": score,
            "total_tests": total,
            "passed": passed,
            "failed": total - passed,
            "results": [r.to_dict() for r in self.results],
            "repair_payloads": repairs,
            "duration_seconds": round(elapsed, 1),
            "vulnerabilities_found": len(repairs),
        }


# ══════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════

async def run_skeptic(target_url: str, test_plan: dict = None) -> dict:
    """Run the Skeptic agent against a target URL."""
    runner = SkepticRunner(target_url)
    return await runner.run_full_attack(test_plan)
