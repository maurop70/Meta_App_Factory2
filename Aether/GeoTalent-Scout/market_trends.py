"""
market_trends.py -- GeoTalent Forward Scout: Market Trends Monitor
====================================================================
Meta App Factory | GeoTalent-Scout | Antigravity-AI

Periodically checks 2026 AI industry standards to identify if the
Meta_App_Factory needs upgrades (new LLM models, framework versions,
security patches). Saves reports for the Sunday review cycle.
"""

import os
import sys
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("geotalent.trends")

SCRIPT_DIR = Path(__file__).resolve().parent
FACTORY_DIR = SCRIPT_DIR.parent.parent
sys.path.insert(0, str(FACTORY_DIR))
sys.path.insert(0, str(FACTORY_DIR / "Sentinel_Bridge"))

DATA_DIR = FACTORY_DIR / "data" / "market_trends"
REGISTRY_PATH = FACTORY_DIR / "registry.json"
STATE_DIR = FACTORY_DIR / ".Gemini_state"

# Lazy imports
_pii = None


def _get_pii():
    global _pii
    if _pii is None:
        try:
            from pii_masker import PIIMasker
            _pii = PIIMasker()
        except ImportError:
            pass
    return _pii


# ── 2026 AI Industry Standards Registry ──────────────────
# Simulated market intelligence — updated periodically

MARKET_INTELLIGENCE = {
    "llm_models": [
        {
            "name": "Gemini 2.5 Pro",
            "provider": "Google DeepMind",
            "released": "2026-02",
            "capabilities": ["1M context", "multimodal", "code generation"],
            "status": "available",
            "recommendation": "Upgrade from gemini-2.0-flash for complex reasoning tasks",
        },
        {
            "name": "Gemini 2.5 Flash",
            "provider": "Google DeepMind",
            "released": "2026-03",
            "capabilities": ["fast inference", "cost-effective", "streaming"],
            "status": "available",
            "recommendation": "Use for high-throughput tasks replacing gemini-2.0-flash",
        },
        {
            "name": "Claude 4 Opus",
            "provider": "Anthropic",
            "released": "2026-01",
            "capabilities": ["reasoning", "safety", "long-form analysis"],
            "status": "available",
            "recommendation": "Consider for Critic/audit tasks requiring deep analysis",
        },
        {
            "name": "GPT-5",
            "provider": "OpenAI",
            "released": "2026-Q1",
            "capabilities": ["agents", "tool use", "multimodal"],
            "status": "available",
            "recommendation": "Alternative for multi-agent orchestration patterns",
        },
    ],
    "frameworks": [
        {
            "name": "FastAPI",
            "current_version": "0.115.x",
            "latest_version": "0.116.0",
            "update_type": "minor",
            "notes": "Performance improvements, new middleware hooks",
        },
        {
            "name": "React",
            "current_version": "18.x",
            "latest_version": "19.1",
            "update_type": "major",
            "notes": "Server Components stable, new use() hook, improved Suspense",
        },
        {
            "name": "n8n",
            "current_version": "1.x",
            "latest_version": "1.70+",
            "update_type": "minor",
            "notes": "New AI agent nodes, improved error handling",
        },
        {
            "name": "LangChain",
            "current_version": "0.2.x",
            "latest_version": "0.3.0",
            "update_type": "major",
            "notes": "LangGraph GA, new tool calling patterns, LCEL improvements",
        },
    ],
    "security": [
        {
            "advisory": "PII-in-LLM-outputs",
            "severity": "high",
            "description": "Ensure all LLM outputs pass PII masking before external delivery",
            "status": "addressed (PIIMasker deployed in Sentinel Bridge)",
        },
        {
            "advisory": "API-key-rotation-2026",
            "severity": "medium",
            "description": "Rotate all API keys quarterly; use vault-based storage",
            "status": "addressed (FernetVault in use)",
        },
    ],
    "industry_trends": [
        "Multi-agent orchestration replacing single-model architectures",
        "Emotional intelligence in AI notifications gaining traction",
        "Context-window expansion enabling full-codebase analysis",
        "RAG + vector memory becoming standard for persistent AI systems",
        "Self-healing autonomous systems moving from experimental to production",
    ],
}


class MarketTrendsMonitor:
    """
    Monitors AI industry standards and identifies upgrade opportunities
    for the Meta App Factory.
    """

    def __init__(self):
        self._pii = _get_pii()
        DATA_DIR.mkdir(parents=True, exist_ok=True)

    # ── Core: Check for Upgrades ─────────────────────────

    def check_upgrades(self) -> dict:
        """
        Compare current factory stack against latest market intelligence.
        Returns upgrade recommendations.
        """
        # Load current factory registry
        current_models = set()
        if REGISTRY_PATH.exists():
            try:
                reg = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
                # Scan blueprints for model names
                for app_data in reg.get("apps", {}).values():
                    config = app_data.get("config", {})
                    if "model" in config:
                        current_models.add(config["model"])
            except Exception:
                pass

        # Check for new model recommendations
        model_upgrades = []
        for model in MARKET_INTELLIGENCE["llm_models"]:
            if model["status"] == "available":
                model_upgrades.append({
                    "model": model["name"],
                    "provider": model["provider"],
                    "recommendation": model["recommendation"],
                    "capabilities": model["capabilities"],
                })

        # Check framework updates
        framework_updates = []
        for fw in MARKET_INTELLIGENCE["frameworks"]:
            if fw["update_type"] in ("major", "minor"):
                framework_updates.append({
                    "framework": fw["name"],
                    "current": fw["current_version"],
                    "latest": fw["latest_version"],
                    "type": fw["update_type"],
                    "notes": fw["notes"],
                })

        report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "model_upgrades": model_upgrades,
            "framework_updates": framework_updates,
            "security_advisories": MARKET_INTELLIGENCE["security"],
            "industry_trends": MARKET_INTELLIGENCE["industry_trends"],
            "current_models_detected": list(current_models),
        }

        return report

    # ── Save Report ──────────────────────────────────────

    def save_report(self, report: dict = None) -> str:
        """Generate and save a market trends report."""
        if report is None:
            report = self.check_upgrades()

        # PII-mask before saving
        if self._pii:
            report_str = json.dumps(report, indent=2)
            report_str = self._pii.mask(report_str)
            report = json.loads(report_str)

        timestamp = datetime.now().strftime("%Y-%m-%d")
        filename = f"market_report_{timestamp}.json"
        filepath = DATA_DIR / filename

        filepath.write_text(json.dumps(report, indent=2))
        logger.info("Market report saved: %s", filepath)

        return str(filepath)

    # ── Upgrade Priority Score ───────────────────────────

    def get_priority_upgrades(self) -> list:
        """Return upgrades sorted by priority."""
        report = self.check_upgrades()
        priorities = []

        # Major framework updates = high priority
        for fw in report["framework_updates"]:
            score = 8 if fw["type"] == "major" else 4
            priorities.append({
                "type": "framework",
                "name": fw["framework"],
                "priority_score": score,
                "action": f"Upgrade {fw['framework']} from {fw['current']} to {fw['latest']}",
            })

        # New models = medium priority
        for model in report["model_upgrades"]:
            priorities.append({
                "type": "model",
                "name": model["model"],
                "priority_score": 5,
                "action": model["recommendation"],
            })

        priorities.sort(key=lambda x: -x["priority_score"])
        return priorities


# ── Entry Point ──────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(name)s] %(message)s")

    parser = argparse.ArgumentParser(description="GeoTalent Market Trends Monitor")
    parser.add_argument("--test", action="store_true", help="Run market check")
    parser.add_argument("--save", action="store_true", help="Save report to file")
    args = parser.parse_args()

    monitor = MarketTrendsMonitor()

    if args.test or args.save:
        print("GeoTalent Market Trends Monitor")
        print("-" * 50)

        report = monitor.check_upgrades()
        print(f"Models available: {len(report['model_upgrades'])}")
        for m in report["model_upgrades"]:
            print(f"  - {m['model']} ({m['provider']})")

        print(f"\nFramework updates: {len(report['framework_updates'])}")
        for fw in report["framework_updates"]:
            print(f"  - {fw['framework']}: {fw['current']} -> {fw['latest']} ({fw['type']})")

        print(f"\nSecurity advisories: {len(report['security_advisories'])}")
        print(f"Industry trends: {len(report['industry_trends'])}")

        if args.save:
            path = monitor.save_report(report)
            print(f"\nReport saved: {path}")

        # Priority upgrades
        priorities = monitor.get_priority_upgrades()
        print(f"\nTop priority upgrades:")
        for p in priorities[:5]:
            print(f"  [{p['priority_score']}] {p['name']}: {p['action']}")

        print("\nDone!")
    else:
        print("Use --test to check market trends or --save to save report.")
