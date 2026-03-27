"""
triad_engine.py — Triad Orchestration Engine
══════════════════════════════════════════════
Master_Architect_Elite_Logic | Meta App Factory

Routes review requests to all three agents in parallel,
collects their verdicts, and merges into a composite score.
Passes the merged result through the Adversarial Gate.
"""

import os
import sys
import json
import logging
import concurrent.futures
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from agents.structural_engineer import StructuralEngineer
from agents.logic_weaver import LogicWeaver
from agents.security_auditor import SecurityAuditor
from memory_engine import ArchitectMemory

logger = logging.getLogger("TriadEngine")

# ── Load config ──────────────────────────────────────────
_CONFIG_PATH = os.path.join(SCRIPT_DIR, "config.json")


def _load_config() -> dict:
    try:
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


class TriadVerdict:
    """Composite verdict from all three Triad agents."""

    def __init__(self, structural: dict, logic: dict, security: dict,
                 weights: dict = None):
        self.structural = structural
        self.logic = logic
        self.security = security
        self.weights = weights or {"structural": 0.40, "logic": 0.30, "security": 0.30}

        # Compute composite
        self.composite_score = round(
            structural.get("score", 0) * self.weights["structural"]
            + logic.get("score", 0) * self.weights["logic"]
            + security.get("score", 0) * self.weights["security"]
        )

        # Merge concerns and recommendations
        self.concerns = []
        self.recommendations = []
        for agent_result in [structural, logic, security]:
            self.concerns.extend(agent_result.get("concerns", []))
            self.recommendations.extend(agent_result.get("recommendations", []))

        # Determine verdict
        if self.composite_score >= 85:
            self.verdict = "APPROVE"
        elif self.composite_score >= 60:
            self.verdict = "REVIEW"
        else:
            self.verdict = "REJECT"

    def to_dict(self) -> dict:
        return {
            "composite_score": self.composite_score,
            "verdict": self.verdict,
            "structural_score": self.structural.get("score", 0),
            "logic_score": self.logic.get("score", 0),
            "security_score": self.security.get("score", 0),
            "structural": self.structural,
            "logic": self.logic,
            "security": self.security,
            "concerns": self.concerns[:6],
            "recommendations": self.recommendations[:6],
            "timestamp": datetime.now().isoformat(),
        }


class TriadEngine:
    """
    Routes a review request to all three agents in parallel,
    collects their verdicts, and merges into a composite score.
    """

    def __init__(self):
        config = _load_config()
        self.weights = config.get("triad_weights", {
            "structural": 0.40,
            "logic": 0.30,
            "security": 0.30,
        })
        model = config.get("model", "gemini-2.5-flash")
        api_key = os.getenv("GEMINI_API_KEY", "")

        self.structural = StructuralEngineer(api_key=api_key, model=model)
        self.logic = LogicWeaver(api_key=api_key, model=model)
        self.security = SecurityAuditor(api_key=api_key, model=model)
        self.memory = ArchitectMemory()

        logger.info(f"TriadEngine initialized (weights: {self.weights})")

    def review(self, description: str, change_type: str = "feature",
               components: list = None, context: dict = None) -> TriadVerdict:
        """
        Run all three agents in parallel, merge scores.
        Returns a TriadVerdict.
        """
        components = components or []
        context = context or {}

        logger.info(f"Triad review started: {change_type} — {description[:80]}...")

        results = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                executor.submit(
                    self.structural.analyze, description, change_type, components, context
                ): "structural",
                executor.submit(
                    self.logic.analyze, description, change_type, components, context
                ): "logic",
                executor.submit(
                    self.security.analyze, description, change_type, components, context
                ): "security",
            }
            for future in concurrent.futures.as_completed(futures, timeout=45):
                agent_name = futures[future]
                try:
                    results[agent_name] = future.result()
                except Exception as e:
                    logger.error(f"{agent_name} agent failed: {e}")
                    results[agent_name] = {
                        "domain": agent_name,
                        "score": 50,
                        "concerns": [f"Agent error: {str(e)[:100]}"],
                        "recommendations": [],
                        "source": "error_fallback",
                    }

        verdict = TriadVerdict(
            structural=results.get("structural", {"score": 50}),
            logic=results.get("logic", {"score": 50}),
            security=results.get("security", {"score": 50}),
            weights=self.weights,
        )

        # Record the review in memory
        self.memory.record_review({
            "request_summary": description[:500],
            "structural_score": verdict.structural.get("score", 0),
            "logic_score": verdict.logic.get("score", 0),
            "security_score": verdict.security.get("score", 0),
            "composite_score": verdict.composite_score,
            "verdict": verdict.verdict,
        })

        logger.info(
            f"Triad verdict: {verdict.verdict} (composite={verdict.composite_score}, "
            f"S={verdict.structural.get('score')}, L={verdict.logic.get('score')}, "
            f"Sec={verdict.security.get('score')})"
        )

        return verdict

    def review_quick(self, description: str, agent: str = "structural",
                     change_type: str = "feature",
                     components: list = None) -> dict:
        """Single-agent fast review for quick checks."""
        agents = {
            "structural": self.structural,
            "logic": self.logic,
            "security": self.security,
        }
        target = agents.get(agent, self.structural)
        return target.analyze(description, change_type, components or [])

    def review_streaming(self, description: str, change_type: str = "feature",
                         components: list = None, context: dict = None):
        """
        Generator that yields progress events as each agent completes.
        Suitable for SSE streaming.
        """
        components = components or []
        context = context or {}

        yield {"step": "TRIAD_START", "text": "🏗️ Master Architect Triad: Starting parallel review..."}

        results = {}
        agent_map = {
            "structural": ("Structural Engineer", self.structural),
            "logic": ("Logic Weaver", self.logic),
            "security": ("Security Auditor", self.security),
        }

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = {}
            for key, (name, agent) in agent_map.items():
                future = executor.submit(
                    agent.analyze, description, change_type, components, context
                )
                futures[future] = (key, name)

            for future in concurrent.futures.as_completed(futures, timeout=45):
                key, name = futures[future]
                try:
                    result = future.result()
                    results[key] = result
                    score = result.get("score", 0)
                    icon = "✅" if score >= 80 else "⚠️" if score >= 60 else "❌"
                    yield {
                        "step": f"AGENT_{key.upper()}",
                        "text": f"{icon} {name}: {score}/100",
                        "agent": key,
                        "score": score,
                        "concerns": result.get("concerns", []),
                    }
                except Exception as e:
                    results[key] = {"score": 50, "concerns": [str(e)[:100]], "recommendations": []}
                    yield {
                        "step": f"AGENT_{key.upper()}",
                        "text": f"⚠️ {name}: Error — using fallback score 50",
                        "agent": key,
                        "score": 50,
                    }

        verdict = TriadVerdict(
            structural=results.get("structural", {"score": 50}),
            logic=results.get("logic", {"score": 50}),
            security=results.get("security", {"score": 50}),
            weights=self.weights,
        )

        self.memory.record_review({
            "request_summary": description[:500],
            "structural_score": verdict.structural.get("score", 0),
            "logic_score": verdict.logic.get("score", 0),
            "security_score": verdict.security.get("score", 0),
            "composite_score": verdict.composite_score,
            "verdict": verdict.verdict,
        })

        icon = "✅" if verdict.verdict == "APPROVE" else "⚠️" if verdict.verdict == "REVIEW" else "❌"
        yield {
            "step": "TRIAD_VERDICT",
            "text": f"{icon} Triad Verdict: {verdict.verdict} (Composite: {verdict.composite_score}/100)",
            "verdict": verdict.to_dict(),
        }

    def get_memory_stats(self) -> dict:
        return self.memory.get_stats()
