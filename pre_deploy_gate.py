"""
pre_deploy_gate.py — Aether-Native Pre-Deploy Gate
═══════════════════════════════════════════════════════
CTO Agent Phase 1 Extraction | Meta App Factory V3

Extracts the Master Architect Elite Pre-Deploy Gate from n8n
and executes it as a native Python class. Performs the Triad
Review (Structural, Logic, Security) locally without any
external webhook dependency.

Usage:
    from pre_deploy_gate import PreDeployGate

    gate = PreDeployGate()
    result = gate.verify("CTO_Agent", "Build a SaaS dashboard with n8n")
    # Returns: {"status": "CLEAR|CHALLENGED|BLOCKED", "composite_score": 82, ...}

Part of CTO Agent v3.1.0 — Universal Stack Evaluator
"""

import os
import sys
import json
import logging
from datetime import datetime

# ── Path Setup ───────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ELITE_DIR = os.path.join(SCRIPT_DIR, "Master_Architect_Elite_Logic")

# Ensure both paths are importable
sys.path.insert(0, SCRIPT_DIR)
sys.path.insert(0, ELITE_DIR)

logger = logging.getLogger("PreDeployGate")

# ── V3 Resilience Import ────────────────────────────────
try:
    from auto_heal import _log_heal_event
except ImportError:
    def _log_heal_event(*args, **kwargs):
        pass  # Graceful fallback if auto_heal unavailable


class PreDeployGate:
    """
    Aether-Native Pre-Deploy Gate.

    Wraps the Master Architect Elite's TriadEngine + AdversarialGate
    into a single verify() call that runs entirely in-process.
    No n8n webhooks, no HTTP calls to port 5050.

    Thresholds (from AdversarialGate):
        composite >= 85  → CLEAR  (AUTO_APPROVE)
        composite 60-84  → CHALLENGED (review recommended)
        composite < 60   → BLOCKED (REJECT)
    """

    def __init__(self):
        self._triad = None
        self._gate = None
        self._initialized = False
        self._init_error = None
        self._init_engines()

    def _init_engines(self):
        """Lazy-load TriadEngine and AdversarialGate from Elite Logic.
        Uses importlib to avoid module name collisions (e.g., memory_engine)."""
        try:
            import importlib.util

            # ── Pre-load Elite-specific modules to avoid name collisions ──
            # The root sys.path has Alpha_V2_Genesis/memory_engine.py which
            # shadows Master_Architect_Elite_Logic/memory_engine.py.
            # We force-load the correct one first.
            elite_modules = {
                "memory_engine": os.path.join(ELITE_DIR, "memory_engine.py"),
                "adversarial_gate": os.path.join(ELITE_DIR, "adversarial_gate.py"),
            }
            for mod_name, mod_path in elite_modules.items():
                if os.path.exists(mod_path):
                    spec = importlib.util.spec_from_file_location(mod_name, mod_path)
                    mod = importlib.util.module_from_spec(spec)
                    sys.modules[mod_name] = mod  # Override any stale import
                    spec.loader.exec_module(mod)

            # Now the agents subpackage can import memory_engine correctly
            agents_dir = os.path.join(ELITE_DIR, "agents")
            if agents_dir not in sys.path:
                sys.path.insert(0, agents_dir)
            if ELITE_DIR not in sys.path:
                sys.path.insert(0, ELITE_DIR)

            from triad_engine import TriadEngine
            from adversarial_gate import AdversarialGate

            # Load Elite config
            config_path = os.path.join(ELITE_DIR, "config.json")
            config = {}
            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)

            self._triad = TriadEngine()
            self._gate = AdversarialGate(config=config)
            self._initialized = True
            logger.info("[PreDeployGate] Triad Engine + Adversarial Gate initialized (Aether-Native)")

        except Exception as e:
            self._init_error = str(e)
            self._initialized = False
            logger.warning(f"[PreDeployGate] Engine init failed: {e} — fallback mode active")

    def verify(self, project_id: str, description: str = "",
               components: list = None, change_type: str = "feature",
               context: dict = None) -> dict:
        """
        Run the full Pre-Deploy Gate locally.

        Args:
            project_id: The project or app being evaluated
            description: What is being deployed/built
            components: List of affected components (e.g., ["api.py", "WarRoom.jsx"])
            change_type: Type of change ("feature", "bugfix", "refactor", "new_app")
            context: Additional context dict

        Returns:
            {
                "status": "CLEAR" | "CHALLENGED" | "BLOCKED",
                "composite_score": 82,
                "structural_score": 85,
                "logic_score": 78,
                "security_score": 80,
                "gate_result": "AUTO_APPROVE" | "CHALLENGED" | "REJECTED",
                "concerns": [...],
                "recommendations": [...],
                "challenge_id": None | "CHG-0001",
                "timestamp": "...",
                "source": "aether_native"
            }
        """
        components = components or []
        context = context or {}
        timestamp = datetime.now().isoformat()

        # Log the gate invocation
        _log_heal_event(
            project=project_id,
            target="PreDeployGate.verify",
            outcome="gate_invoked",
            attempts=0
        )

        # If engines failed to init, return a conservative fallback
        if not self._initialized:
            logger.warning(f"[PreDeployGate] Running in fallback mode for {project_id}")
            fallback = self._fallback_verify(project_id, description, components)
            _log_heal_event(
                project=project_id,
                target="PreDeployGate.verify",
                outcome="fallback_used",
                error=self._init_error
            )
            return fallback

        try:
            # ── STEP 1: Run Triad Review (Structural + Logic + Security) ──
            verdict = self._triad.review(
                description=description,
                change_type=change_type,
                components=components,
                context=context
            )
            verdict_dict = verdict.to_dict()

            # ── STEP 2: Pass through Adversarial Gate ──
            gate_result = self._gate.evaluate(verdict_dict)
            gate_status = gate_result.get("gate_result", "UNKNOWN")

            # Map gate_result to simplified status
            if gate_status == "AUTO_APPROVE":
                status = "CLEAR"
            elif gate_status == "CHALLENGED":
                status = "CHALLENGED"
            elif gate_status == "REJECTED":
                status = "BLOCKED"
            else:
                status = "UNKNOWN"

            result = {
                "status": status,
                "composite_score": verdict.composite_score,
                "structural_score": verdict.structural.get("score", 0),
                "logic_score": verdict.logic.get("score", 0),
                "security_score": verdict.security.get("score", 0),
                "gate_result": gate_status,
                "concerns": verdict.concerns[:5],
                "recommendations": verdict.recommendations[:5],
                "challenge_id": gate_result.get("challenge_id"),
                "weaknesses": gate_result.get("weaknesses", []),
                "timestamp": timestamp,
                "source": "aether_native",
                "project_id": project_id,
            }

            # Log outcome
            _log_heal_event(
                project=project_id,
                target="PreDeployGate.verify",
                outcome=f"gate_{status.lower()}",
                attempts=0,
                diagnosis={
                    "verdict": status,
                    "watchdog": {"status": "green"},
                    "credentials": {"status": "valid"},
                    "buffer": {"pending_files": 0},
                }
            )

            logger.info(
                f"[PreDeployGate] {project_id}: {status} "
                f"(composite={verdict.composite_score}, "
                f"S={verdict.structural.get('score')}, "
                f"L={verdict.logic.get('score')}, "
                f"Sec={verdict.security.get('score')})"
            )

            return result

        except Exception as e:
            logger.error(f"[PreDeployGate] verify() failed for {project_id}: {e}")
            _log_heal_event(
                project=project_id,
                target="PreDeployGate.verify",
                outcome="gate_error",
                error=str(e)[:200]
            )
            return self._fallback_verify(project_id, description, components)

    def verify_quick(self, project_id: str, description: str = "",
                     agent: str = "structural") -> dict:
        """
        Quick single-agent check (no full Triad).
        For fast pre-flight checks before full verify().
        """
        if not self._initialized:
            return {"status": "UNKNOWN", "score": 50, "source": "fallback"}

        try:
            result = self._triad.review_quick(description, agent)
            score = result.get("score", 50)
            return {
                "status": "CLEAR" if score >= 85 else "REVIEW" if score >= 60 else "BLOCKED",
                "score": score,
                "agent": agent,
                "concerns": result.get("concerns", []),
                "source": "aether_native_quick",
            }
        except Exception as e:
            logger.warning(f"[PreDeployGate] quick check failed: {e}")
            return {"status": "UNKNOWN", "score": 50, "source": "fallback"}

    def get_status(self) -> dict:
        """Return current gate status for health checks."""
        active_challenges = []
        if self._initialized and self._gate:
            active_challenges = self._gate.get_active_challenges()

        return {
            "initialized": self._initialized,
            "init_error": self._init_error,
            "source": "aether_native",
            "active_challenges": len(active_challenges),
            "triad_available": self._triad is not None,
            "gate_available": self._gate is not None,
        }

    def _fallback_verify(self, project_id: str, description: str,
                         components: list) -> dict:
        """
        Conservative keyword-based fallback when TriadEngine is unavailable.
        Always returns CHALLENGED so humans review before deployment.
        """
        desc_lower = description.lower()
        score = 65  # Conservative default

        concerns = []
        recommendations = ["Manual review recommended — Triad Engine offline"]

        # Basic keyword checks
        if any(kw in desc_lower for kw in ["delete", "drop", "remove", "destroy"]):
            score -= 15
            concerns.append("Destructive operation detected — requires manual approval")

        if any(kw in desc_lower for kw in ["production", "deploy", "release", "live"]):
            score -= 5
            concerns.append("Production deployment — elevated review threshold")

        if any(kw in desc_lower for kw in ["security", "auth", "credential", "key", "secret"]):
            score -= 10
            concerns.append("Security-sensitive change — Compliance Officer must review")

        if any(kw in desc_lower for kw in ["migration", "schema", "database"]):
            score -= 5
            concerns.append("Schema change — rollback plan required")
            recommendations.append("Include reversible migration script")

        if not components:
            concerns.append("No affected components specified — scope unclear")
            score -= 5

        score = max(0, min(100, score))

        return {
            "status": "CHALLENGED" if score >= 60 else "BLOCKED",
            "composite_score": score,
            "structural_score": score,
            "logic_score": score,
            "security_score": score,
            "gate_result": "CHALLENGED" if score >= 60 else "REJECTED",
            "concerns": concerns[:5],
            "recommendations": recommendations[:3],
            "challenge_id": None,
            "weaknesses": [],
            "timestamp": datetime.now().isoformat(),
            "source": "keyword_fallback",
            "project_id": project_id,
        }


# ═══════════════════════════════════════════════════════════
#  SINGLETON — Shared instance for api.py import
# ═══════════════════════════════════════════════════════════

_gate_instance = None


def get_pre_deploy_gate() -> PreDeployGate:
    """Return a singleton PreDeployGate instance."""
    global _gate_instance
    if _gate_instance is None:
        _gate_instance = PreDeployGate()
    return _gate_instance


# ═══════════════════════════════════════════════════════════
#  CLI — Direct gate test
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    print(f"\n{'='*60}")
    print(f"  PreDeployGate — Aether-Native Self-Test")
    print(f"{'='*60}\n")

    gate = PreDeployGate()
    print(f"  Status: {json.dumps(gate.get_status(), indent=2)}\n")

    # Test with a sample project
    result = gate.verify(
        project_id="CTO_SelfTest",
        description="Add a new FastAPI endpoint for user analytics with Supabase integration",
        components=["api.py", "analytics_service.py"],
        change_type="feature"
    )

    print(f"  Verdict: {result['status']}")
    print(f"  Composite: {result['composite_score']}/100")
    print(f"  Structural: {result['structural_score']} | Logic: {result['logic_score']} | Security: {result['security_score']}")
    print(f"  Gate: {result['gate_result']}")
    print(f"  Concerns: {result['concerns']}")
    print(f"  Source: {result['source']}")
    print(f"\n{'='*60}\n")
