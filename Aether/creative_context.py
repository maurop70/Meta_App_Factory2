"""
creative_context.py — Aether Creative Context Engine
═════════════════════════════════════════════════════
Meta App Factory | Aether Protocol | Antigravity-AI

Scans the blueprints folder and recent LEDGER.md entries to
establish a 'Visual & Functional Style Profile' for the system.
This profile is injected into the Aether Engine's Gemini prompt
to maintain consistency across all generated output.
"""

import os
import re
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger("aether.context")

FACTORY_DIR = Path(__file__).resolve().parent.parent
BLUEPRINTS_DIR = FACTORY_DIR / "blueprints"
LEDGER_PATH = FACTORY_DIR / "LEDGER.md"
REGISTRY_PATH = FACTORY_DIR / "registry.json"


class CreativeContext:
    """
    Builds a Visual & Functional Style Profile by scanning
    blueprints, ledger, and registry to inform Aether's
    creative decisions.
    """

    def __init__(self):
        self.blueprints: List[dict] = []
        self.ledger_entries: List[dict] = []
        self.style_profile: Dict = {}

    # ── Phase 1: Scan Blueprints ─────────────────────────

    def scan_blueprints(self) -> List[dict]:
        """
        Parse all JSON blueprints from blueprints/ to extract
        node types, model preferences, and flow patterns.
        """
        self.blueprints = []
        if not BLUEPRINTS_DIR.exists():
            logger.warning("Blueprints directory not found: %s", BLUEPRINTS_DIR)
            return self.blueprints

        for bp_file in BLUEPRINTS_DIR.glob("*.json"):
            try:
                data = json.loads(bp_file.read_text(encoding="utf-8"))
                blueprint = {
                    "name": data.get("name", bp_file.stem),
                    "file": bp_file.name,
                    "nodes": [],
                    "models": [],
                    "node_types": [],
                    "flow_pattern": [],
                }

                for node in data.get("nodes", []):
                    node_name = node.get("name", "Unknown")
                    node_type = node.get("type", "")
                    blueprint["nodes"].append(node_name)
                    blueprint["node_types"].append(node_type)

                    # Extract model names
                    params = node.get("parameters", {})
                    if "modelName" in params:
                        blueprint["models"].append(params["modelName"])

                # Extract connection flow
                for src, conns in data.get("connections", {}).items():
                    for conn_type, targets in conns.items():
                        for target_list in targets:
                            for target in target_list:
                                blueprint["flow_pattern"].append(
                                    f"{src} → {target.get('node', '?')}"
                                )

                self.blueprints.append(blueprint)
            except Exception as e:
                logger.warning("Could not parse blueprint %s: %s", bp_file.name, e)

        return self.blueprints

    # ── Phase 2: Scan Ledger ─────────────────────────────

    def scan_ledger(self) -> List[dict]:
        """
        Parse LEDGER.md for recent entries, extracting
        strategies, outcomes, and system observations.
        """
        self.ledger_entries = []
        if not LEDGER_PATH.exists():
            logger.warning("LEDGER.md not found: %s", LEDGER_PATH)
            return self.ledger_entries

        try:
            content = LEDGER_PATH.read_text(encoding="utf-8")
        except Exception as e:
            logger.warning("Could not read LEDGER.md: %s", e)
            return self.ledger_entries

        # Extract section headers
        sections = re.findall(r'^## (.+)$', content, re.MULTILINE)

        # Extract key metrics from tables
        metrics = {}
        table_rows = re.findall(
            r'\| \*\*(.+?)\*\* \| (.+?) \|', content
        )
        for key, val in table_rows:
            metrics[key.strip()] = val.strip()

        # Extract trade reports
        trades = re.findall(
            r'### (exec_\S+).*?(?=###|\Z)', content, re.DOTALL
        )

        self.ledger_entries = [{
            "sections": sections,
            "metrics": metrics,
            "trade_count": len(trades),
            "has_active_trades": len(trades) > 0,
        }]

        return self.ledger_entries

    # ── Phase 3: Build Style Profile ─────────────────────

    def build_style_profile(self) -> Dict:
        """
        Generate the Visual & Functional Style Profile from
        all scanned sources.
        """
        if not self.blueprints:
            self.scan_blueprints()
        if not self.ledger_entries:
            self.scan_ledger()

        # Aggregate blueprint insights
        all_models = set()
        all_node_types = set()
        all_patterns = []
        blueprint_names = []

        for bp in self.blueprints:
            blueprint_names.append(bp["name"])
            all_models.update(bp["models"])
            all_node_types.update(bp["node_types"])
            all_patterns.extend(bp["flow_pattern"][:5])  # Top 5 per blueprint

        # Load registry for app metadata
        apps = {}
        if REGISTRY_PATH.exists():
            try:
                reg = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
                apps = reg.get("apps", {})
            except Exception:
                pass

        self.style_profile = {
            "system": "Meta App Factory — Aether Creative Protocol",
            "architecture": {
                "preferred_models": sorted(all_models) or ["models/gemini-2.0-flash"],
                "node_types": sorted(all_node_types)[:10],
                "blueprints_available": blueprint_names,
                "flow_patterns": all_patterns[:10],
            },
            "conventions": {
                "naming": "snake_case for files, PascalCase for classes",
                "backend": "FastAPI (Python 3.12+)",
                "frontend": "React + Vite (when applicable)",
                "notifications": "ntfy.sh push, multi-channel fallback",
                "security": "Fernet AES-128 vault, PII masking on exports",
                "scheduling": "APScheduler for cron jobs",
                "self_healing": "SelfHealEngine wrapper on all pipelines",
            },
            "active_apps": list(apps.keys()),
            "active_app_count": len(apps),
            "ledger_status": {
                "has_data": bool(self.ledger_entries),
                "metrics": self.ledger_entries[0].get("metrics", {})
                           if self.ledger_entries else {},
            },
        }

        return self.style_profile

    # ── Phase 4: Context Prompt ──────────────────────────

    def get_context_prompt(self) -> str:
        """
        Render the style profile as a system prompt fragment
        for the Aether Engine's Gemini calls.
        """
        if not self.style_profile:
            self.build_style_profile()

        profile = self.style_profile
        arch = profile.get("architecture", {})
        conv = profile.get("conventions", {})

        prompt = (
            "## Aether Creative Context\n"
            "You are the Aether Creative Architect for the Meta App Factory.\n\n"
            f"**Active Apps:** {', '.join(profile.get('active_apps', []))}\n"
            f"**Preferred Models:** {', '.join(arch.get('preferred_models', []))}\n"
            f"**Blueprints:** {', '.join(arch.get('blueprints_available', []))}\n\n"
            "**Code Conventions:**\n"
        )
        for key, val in conv.items():
            prompt += f"- {key}: {val}\n"

        prompt += (
            "\n**Architecture Patterns (from blueprints):**\n"
        )
        for pattern in arch.get("flow_patterns", [])[:5]:
            prompt += f"- {pattern}\n"

        prompt += (
            "\nApply these conventions consistently in all generated "
            "code, designs, and documentation. Ensure all output is "
            "production-quality and follows the Aether protocol.\n"
        )

        return prompt


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    ctx = CreativeContext()

    print("Phase 1: Scanning blueprints...")
    blueprints = ctx.scan_blueprints()
    print(f"  Found {len(blueprints)} blueprint(s)")
    for bp in blueprints:
        print(f"    - {bp['name']}: {len(bp['nodes'])} nodes, "
              f"models={bp['models']}")

    print("\nPhase 2: Scanning LEDGER.md...")
    entries = ctx.scan_ledger()
    print(f"  Entries: {len(entries)}")

    print("\nPhase 3: Building style profile...")
    profile = ctx.build_style_profile()
    print(f"  Active apps: {profile.get('active_app_count', 0)}")
    print(f"  Blueprints: {profile['architecture']['blueprints_available']}")

    print("\nPhase 4: Context prompt (first 500 chars):")
    prompt = ctx.get_context_prompt()
    print(prompt[:500])
