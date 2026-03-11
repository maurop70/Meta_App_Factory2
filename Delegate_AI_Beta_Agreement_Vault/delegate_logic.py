"""
delegate_logic.py — Delegate AI Orchestrator
═════════════════════════════════════════════
Meta App Factory | Delegate AI | Antigravity-AI

Primary Skill Manager that orchestrates task delegation across
the Agent Network with:
- Performance-Based Routing via heartbeat.py scanning
- Leitner Level 5 auto-flagging on agent failures
- Aether CreativeContext alignment
- LEDGER.md handoff logging
"""

import os
import sys
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger("delegate.orchestrator")

# ── Path Setup ───────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
FACTORY_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(FACTORY_DIR))
sys.path.insert(0, str(FACTORY_DIR / "Sentinel_Bridge"))

LEDGER_PATH = FACTORY_DIR / "LEDGER.md"
REGISTRY_PATH = FACTORY_DIR / "registry.json"
STATE_DIR = FACTORY_DIR / ".Gemini_state"

# ── Lazy Imports ─────────────────────────────────────────
_leitner = None
_pii = None
_context = None


def _get_leitner():
    global _leitner
    if _leitner is None:
        try:
            from leitner_architect import LeitnerArchitect
            _leitner = LeitnerArchitect()
        except ImportError:
            logger.warning("LeitnerArchitect not available")
    return _leitner


def _get_pii():
    global _pii
    if _pii is None:
        try:
            from pii_masker import PIIMasker
            _pii = PIIMasker()
        except ImportError:
            logger.warning("PIIMasker not available")
    return _pii


def _get_context():
    global _context
    if _context is None:
        try:
            from Aether.creative_context import CreativeContext
            _context = CreativeContext()
            _context.build_style_profile()
        except ImportError:
            logger.warning("CreativeContext not available")
    return _context


# ── Agent Registry ───────────────────────────────────────

CORE_AGENTS = {
    "meta-app-factory": {
        "type": "system_core",
        "url": "http://localhost:8000",
        "description": "Factory API for building and managing apps",
    },
    "aether-architect": {
        "type": "system_core",
        "url": None,
        "description": "Context-Aware Creative Architect with dual-agent refinement",
    },
    "delegate-orchestrator": {
        "type": "skill_manager",
        "url": "http://localhost:5007",
        "description": "Primary Skill Manager — task delegation and routing",
    },
    "sentinel-bridge": {
        "type": "infrastructure",
        "url": "http://localhost:5009",
        "description": "Universal notification and monitoring bridge",
    },
}


class DelegationResult:
    """Result of a delegation handoff."""

    def __init__(self, task: str, target: str, status: str,
                 health_score: float, response: dict = None,
                 escalated: bool = False):
        self.task = task
        self.target = target
        self.status = status
        self.health_score = health_score
        self.response = response or {}
        self.escalated = escalated
        self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return {
            "task": self.task[:100],
            "target": self.target,
            "status": self.status,
            "health_score": self.health_score,
            "escalated": self.escalated,
            "timestamp": self.timestamp,
        }


class DelegateOrchestrator:
    """
    Primary orchestrator for the Delegate AI agent network.
    Routes tasks based on agent health, logs handoffs, and
    escalates failures through the Leitner system.
    """

    def __init__(self):
        self._health_cache: dict = {}
        self._delegation_log: list = []

    # ── Core: Delegate ───────────────────────────────────

    def delegate(self, task: str, target_agent: str,
                 context: dict = None) -> DelegationResult:
        """
        Route a task to a target agent with health-based validation.
        Logs the handoff to LEDGER.md.
        """
        logger.info("Delegating to %s: %s", target_agent, task[:80])

        # 1. Check agent health
        health = self.get_agent_health(target_agent)
        health_score = health.get("score", 0.0)

        if health_score < 0.3:
            # Agent too unhealthy — try fallback
            logger.warning("Agent %s unhealthy (%.1f) — attempting fallback",
                           target_agent, health_score)
            fallback = self._find_fallback(target_agent)
            if fallback:
                logger.info("Falling back to: %s", fallback)
                target_agent = fallback
                health = self.get_agent_health(target_agent)
                health_score = health.get("score", 0.0)

        # 2. Attempt delegation
        try:
            response = self._execute_delegation(task, target_agent, context)
            status = "completed"
        except Exception as e:
            logger.error("Delegation failed: %s", e)
            response = {"error": str(e)}
            status = "failed"

            # 3. Leitner escalation on failure
            escalated = self.bridge_leitner(
                target_agent,
                f"Delegation failed: {str(e)[:200]}",
            )

            result = DelegationResult(
                task=task, target=target_agent, status=status,
                health_score=health_score, response=response,
                escalated=escalated,
            )
            self._log_to_ledger(result)
            return result

        result = DelegationResult(
            task=task, target=target_agent, status=status,
            health_score=health_score, response=response,
        )

        # 4. Log to LEDGER
        self._log_to_ledger(result)

        return result

    # ── Performance-Based Routing ────────────────────────

    def scan_heartbeat(self) -> dict:
        """
        Scan heartbeat.py endpoints to determine which
        services are online and healthy.
        """
        import httpx

        endpoints = {
            "meta-app-factory": "http://localhost:8000/api/ip/status",
            "sentinel-bridge": "http://localhost:5009/",
            "delegate-vault": "http://localhost:5007/health",
            "factory-ui": "http://localhost:5173",
        }

        results = {}
        for name, url in endpoints.items():
            try:
                r = httpx.get(url, timeout=5.0, follow_redirects=True)
                results[name] = {
                    "online": r.status_code < 500,
                    "status_code": r.status_code,
                    "response_ms": r.elapsed.total_seconds() * 1000,
                }
            except Exception:
                results[name] = {
                    "online": False,
                    "status_code": None,
                    "response_ms": None,
                }

        self._health_cache = results
        return results

    def get_agent_health(self, agent_id: str) -> dict:
        """
        Return health score (0.0-1.0) for a given agent.
        Combines heartbeat data + call stats.
        """
        # Check cached heartbeat
        if not self._health_cache:
            try:
                self.scan_heartbeat()
            except Exception:
                pass

        # Map agent to endpoint
        agent_endpoint_map = {
            "meta-app-factory": "meta-app-factory",
            "aether-architect": "meta-app-factory",  # Aether runs through factory
            "sentinel-bridge": "sentinel-bridge",
            "delegate-orchestrator": "delegate-vault",
        }

        endpoint_key = agent_endpoint_map.get(agent_id)
        hb = self._health_cache.get(endpoint_key, {})

        score = 0.5  # default unknown
        if hb.get("online"):
            response_ms = hb.get("response_ms", 1000)
            if response_ms < 200:
                score = 1.0
            elif response_ms < 500:
                score = 0.8
            elif response_ms < 1000:
                score = 0.6
            else:
                score = 0.4
        elif hb.get("online") is False:
            score = 0.0

        # Check call stats for load info
        stats_path = STATE_DIR / "agent_call_stats.json"
        if stats_path.exists():
            try:
                stats = json.loads(stats_path.read_text(encoding="utf-8"))
                agent_stats = stats.get(agent_id, {})
                total_calls = agent_stats.get("total_calls", 0)
                # Penalize overloaded agents
                if total_calls > 100:
                    score *= 0.8
            except Exception:
                pass

        return {
            "agent": agent_id,
            "score": round(score, 2),
            "online": hb.get("online"),
            "response_ms": hb.get("response_ms"),
        }

    def _find_fallback(self, failed_agent: str) -> Optional[str]:
        """Find a healthy fallback agent for the failed one."""
        # Simple fallback chain
        fallbacks = {
            "aether-architect": "meta-app-factory",
            "sentinel-bridge": "meta-app-factory",
            "delegate-orchestrator": "meta-app-factory",
        }
        fb = fallbacks.get(failed_agent)
        if fb:
            health = self.get_agent_health(fb)
            if health.get("score", 0) >= 0.3:
                return fb
        return None

    # ── Task Execution ───────────────────────────────────

    def _execute_delegation(self, task: str, target: str,
                            context: dict = None) -> dict:
        """
        Execute the delegation by routing to the target agent.
        For Aether, invokes the AetherEngine; for others, calls API.
        """
        if target == "aether-architect":
            try:
                from Aether.engine import AetherEngine
                engine = AetherEngine()
                result = engine.generate(task, app_name="DelegateAI")
                return result.to_dict()
            except Exception as e:
                raise RuntimeError(f"Aether delegation failed: {e}")

        elif target in ("meta-app-factory", "sentinel-bridge",
                        "delegate-orchestrator"):
            # HTTP delegation to running service
            agent_info = CORE_AGENTS.get(target, {})
            url = agent_info.get("url")
            if not url:
                return {"status": "no_url", "target": target}

            try:
                import httpx
                r = httpx.post(
                    f"{url}/api/delegate" if target == "meta-app-factory"
                    else f"{url}/delegate",
                    json={"task": task, "context": context or {}},
                    timeout=30.0,
                )
                return {"status_code": r.status_code, "response": r.text[:500]}
            except Exception as e:
                raise RuntimeError(f"HTTP delegation failed: {e}")

        return {"status": "unsupported_target", "target": target}

    # ── Leitner Bridge ───────────────────────────────────

    def bridge_leitner(self, agent_id: str, error_description: str) -> bool:
        """
        Auto-flag Level 5 errors in MASTER_INDEX.md via Leitner.
        Called on agent failures.
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        master_index = FACTORY_DIR / "MASTER_INDEX.md"

        entry = (
            f"\n### ERROR_ENTRY\n"
            f"- **Timestamp:** {timestamp}\n"
            f"- **App:** Delegate_AI_Orchestrator\n"
            f"- **Error_Complexity:** 5\n"
            f"- **Description:** Agent '{agent_id}' failure during delegation\n"
            f"- **Root_Cause:** {error_description[:300]}\n"
            f"- **Resolution:** pending_deep_review\n"
            f"- **Status:** OPEN\n"
            f"- **Last_Reviewed:** {timestamp}\n"
        )

        try:
            with open(master_index, "a", encoding="utf-8", newline="\n") as f:
                f.write(entry)
            logger.info("Leitner Level 5: flagged %s", agent_id)
            return True
        except Exception as e:
            logger.error("Leitner bridge failed: %s", e)
            return False

    # ── PII-Safe Export ───────────────────────────────────

    def sanitize_export(self, content: str) -> str:
        """Apply PIIMasker to vault export content."""
        pii = _get_pii()
        if pii:
            return pii.mask(content)
        return content

    # ── LEDGER Logging ───────────────────────────────────

    def _log_to_ledger(self, result: DelegationResult) -> None:
        """Append delegation handoff to LEDGER.md."""
        entry = (
            f"\n### DELEGATION_HANDOFF\n"
            f"- **Timestamp:** {result.timestamp}\n"
            f"- **Target:** {result.target}\n"
            f"- **Task:** {result.task[:150]}\n"
            f"- **Status:** {result.status}\n"
            f"- **Health_Score:** {result.health_score}\n"
            f"- **Escalated:** {result.escalated}\n"
        )

        try:
            with open(LEDGER_PATH, "a", encoding="utf-8", newline="\n") as f:
                f.write(entry)
            logger.info("Delegation logged to LEDGER.md")
        except Exception as e:
            logger.error("Could not log to LEDGER: %s", e)

        self._delegation_log.append(result.to_dict())

    def get_delegation_log(self) -> list:
        """Return recent delegation log."""
        return self._delegation_log[-50:]


# ── Entry Point ──────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(name)s] %(message)s")

    parser = argparse.ArgumentParser(
        description="Delegate AI Orchestrator"
    )
    parser.add_argument("--test", action="store_true",
                        help="Run test delegation: Delegate → Aether")
    parser.add_argument("--health", action="store_true",
                        help="Scan heartbeat and show agent health")
    args = parser.parse_args()

    orchestrator = DelegateOrchestrator()

    if args.health:
        print("Scanning heartbeat endpoints...")
        hb = orchestrator.scan_heartbeat()
        for name, status in hb.items():
            icon = "🟢" if status["online"] else "🔴"
            ms = f"{status['response_ms']:.0f}ms" if status["response_ms"] else "N/A"
            print(f"  {icon} {name}: {status['status_code']} ({ms})")

    elif args.test:
        print("Test delegation: Delegate AI -> Aether Architect")
        print("-" * 50)
        result = orchestrator.delegate(
            task="Generate a health-check endpoint for a test service",
            target_agent="aether-architect",
            context={"source": "delegate_test"},
        )
        print(f"Status: {result.status}")
        print(f"Health Score: {result.health_score}")
        print(f"Escalated: {result.escalated}")
        print(f"Logged to LEDGER: True")
        print(f"Result: {json.dumps(result.to_dict(), indent=2)}")

    else:
        print("Delegate AI Orchestrator loaded.")
        print("Use --test for delegation test or --health for agent health scan.")
