"""
network_mapper.py — Agent Network Mapper & Mermaid Diagram Generator
═══════════════════════════════════════════════════════════════════════
Meta App Factory | Aether Protocol | Antigravity-AI

Scans registry.json and Aether agent configs to build a complete
connection graph of apps ↔ agents ↔ capabilities. Generates Mermaid.js
flowcharts highlighting Orphaned and Bottleneck agents.
"""

import os
import sys
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("NetworkMapper")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REGISTRY_PATH = os.path.join(SCRIPT_DIR, "registry.json")
STATE_DIR = os.path.join(SCRIPT_DIR, ".Gemini_state")
CALL_STATS_PATH = os.path.join(STATE_DIR, "agent_call_stats.json")
MAPS_DIR = os.path.join(SCRIPT_DIR, "data", "network_maps")

# ── Thresholds ───────────────────────────────────────────

ORPHAN_THRESHOLD = 2       # < 2 calls in 7 days → Orphaned
BOTTLENECK_PERCENTILE = 80  # > 80th percentile → Bottleneck
LOOKBACK_DAYS = 7           # Window for call analysis


class NetworkMapper:
    """
    Scans the Meta App Factory ecosystem, builds an agent
    connection graph, and generates visual Mermaid.js diagrams.
    """

    def __init__(self):
        self.apps: Dict[str, dict] = {}
        self.agents: List[str] = []
        self.connections: List[Tuple[str, str, str]] = []  # (from, to, label)
        self.call_stats: Dict[str, dict] = {}
        self.classifications: Dict[str, str] = {}  # agent → ORPHANED|BOTTLENECK|NORMAL

    # ── Phase 1: Scan ────────────────────────────────────

    def scan_network(self) -> dict:
        """
        Build the complete agent network graph from all sources.
        Returns a summary dict.
        """
        self.apps = self._load_registry()
        self.agents = self._discover_agents()
        self.connections = self._map_connections()
        self.call_stats = self.load_call_stats()
        self.classifications = self.classify_agents()

        return {
            "apps": len(self.apps),
            "agents": len(self.agents),
            "connections": len(self.connections),
            "orphaned": sum(1 for v in self.classifications.values() if v == "ORPHANED"),
            "bottleneck": sum(1 for v in self.classifications.values() if v == "BOTTLENECK"),
        }

    def _load_registry(self) -> Dict[str, dict]:
        """Load all apps from registry.json."""
        if not os.path.isfile(REGISTRY_PATH):
            return {}
        try:
            with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("apps", {})
        except Exception as e:
            logger.warning(f"Could not load registry: {e}")
            return {}

    def _discover_agents(self) -> List[str]:
        """Discover all agents from registry + agent_skills_router."""
        agents = set()

        # From registry → Project_Aether agents
        aether = self.apps.get("Project_Aether", {})
        agent_info = aether.get("agents", {})
        for agent_list in agent_info.values():
            if isinstance(agent_list, list):
                # Normalize: "CEO" → "CEO", "Deep_Crawler" stays
                agents.update(a.strip() for a in agent_list)

        # From agent_skills_router.py AGENTS list
        router_path = os.path.join(SCRIPT_DIR, "agent_skills_router.py")
        if os.path.isfile(router_path):
            try:
                with open(router_path, "r", encoding="utf-8") as f:
                    content = f.read()
                import re
                match = re.search(r'AGENTS\s*=\s*\[(.*?)\]', content, re.DOTALL)
                if match:
                    names = re.findall(r'"([^"]+)"', match.group(1))
                    for n in names:
                        # "deep-crawler" → "Deep_Crawler"
                        normalized = n.replace("-", "_").replace(" ", "_")
                        normalized = "_".join(
                            part.capitalize() for part in normalized.split("_")
                        )
                        # Skip if a matching name already exists (case-insensitive)
                        if not any(
                            existing.lower() == normalized.lower()
                            for existing in agents
                        ):
                            agents.add(normalized)
            except Exception:
                pass

        # Ensure a consistent sorted list
        return sorted(agents)

    def _map_connections(self) -> List[Tuple[str, str, str]]:
        """Map connections between apps and agents."""
        connections = []

        # Apps → their capabilities
        for app_name, app_data in self.apps.items():
            # App → Agent connections (from Project_Aether)
            agent_info = app_data.get("agents", {})
            for status, agent_list in agent_info.items():
                if isinstance(agent_list, list):
                    for agent in agent_list:
                        label = "active" if status == "active" else "placeholder"
                        connections.append((app_name, agent, label))

            # App → App connections via shared infrastructure
            if app_data.get("webhook_url"):
                connections.append((app_name, "n8n_Cloud", "webhook"))
            if app_data.get("port"):
                connections.append(("Factory_API", app_name, f"port:{app_data['port']}"))

        # Factory infrastructure connections
        connections.append(("Factory_API", "Agent_Skills_Router", "routes"))
        for agent in self.agents:
            connections.append(("Agent_Skills_Router", agent, "dispatch"))

        # Sentinel_Bridge monitoring connections
        for app_name in self.apps:
            if app_name != "Sentinel_Bridge":
                connections.append(("Sentinel_Bridge", app_name, "monitors"))

        return connections

    # ── Phase 2: Call Stats ──────────────────────────────

    def load_call_stats(self) -> Dict[str, dict]:
        """Load agent call frequency data."""
        if not os.path.isfile(CALL_STATS_PATH):
            return {}
        try:
            with open(CALL_STATS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, Exception):
            return {}

    # ── Phase 3: Classify ────────────────────────────────

    def classify_agents(self) -> Dict[str, str]:
        """
        Classify each agent as ORPHANED, BOTTLENECK, or NORMAL
        based on call frequency in the lookback window.
        """
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=LOOKBACK_DAYS)

        # Count recent calls per agent
        recent_calls: Dict[str, int] = {}
        for agent in self.agents:
            stats = self.call_stats.get(agent.lower().replace("_", "-"), {})
            # Count calls within lookback window
            call_log = stats.get("call_log", [])
            recent = sum(
                1 for ts in call_log
                if self._parse_ts(ts) and self._parse_ts(ts) > cutoff
            )
            # Fallback: use total_calls if no timestamped log
            if not call_log and stats.get("total_calls"):
                recent = stats["total_calls"]
            recent_calls[agent] = recent

        # Calculate percentile threshold
        if recent_calls:
            call_values = sorted(recent_calls.values())
            p80_idx = int(len(call_values) * BOTTLENECK_PERCENTILE / 100)
            p80_threshold = call_values[min(p80_idx, len(call_values) - 1)]
        else:
            p80_threshold = 999

        # Classify
        classifications = {}
        for agent in self.agents:
            calls = recent_calls.get(agent, 0)
            if calls < ORPHAN_THRESHOLD:
                classifications[agent] = "ORPHANED"
            elif calls >= p80_threshold and p80_threshold > ORPHAN_THRESHOLD:
                classifications[agent] = "BOTTLENECK"
            else:
                classifications[agent] = "NORMAL"

        return classifications

    def _parse_ts(self, ts_str: str) -> Optional[datetime]:
        """Parse an ISO timestamp string."""
        try:
            return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return None

    # ── Phase 4: Generate Mermaid ────────────────────────

    def generate_mermaid(self) -> str:
        """
        Generate a Mermaid.js flowchart of the agent network.
        Orphaned agents: dashed borders, grey
        Bottleneck agents: thick red borders
        """
        lines = [
            "```mermaid",
            "flowchart TB",
            "",
            "    %% === META APP FACTORY AGENT NETWORK ===",
            "",
        ]

        # Subgraph: Apps
        lines.append("    subgraph APPS[\"📦 MetaApps\"]")
        for app_name, app_data in self.apps.items():
            status = app_data.get("status", "unknown")
            icon = "🟢" if status == "active" else "⚪"
            safe_id = self._safe_id(app_name)
            port = app_data.get("port", "")
            port_label = f" :{port}" if port else ""
            lines.append(f'        {safe_id}["{icon} {app_name}{port_label}"]')
        lines.append("    end")
        lines.append("")

        # Subgraph: Agents (with classification styling)
        lines.append("    subgraph AGENTS[\"🤖 Specialist Agents\"]")
        for agent in self.agents:
            safe_id = self._safe_id(agent)
            cls = self.classifications.get(agent, "NORMAL")
            if cls == "ORPHANED":
                lines.append(f'        {safe_id}["👻 {agent}"]')
            elif cls == "BOTTLENECK":
                lines.append(f'        {safe_id}["🔥 {agent}"]')
            else:
                lines.append(f'        {safe_id}["{agent}"]')
        lines.append("    end")
        lines.append("")

        # Subgraph: Infrastructure
        lines.append("    subgraph INFRA[\"⚙️ Infrastructure\"]")
        lines.append('        FactoryAPI["Factory API :8000"]')
        lines.append('        SkillsRouter["Agent Skills Router :8001"]')
        lines.append('        n8nCloud["n8n Cloud"]')
        lines.append('        CommandCenter["Command Center :5010"]')
        lines.append("    end")
        lines.append("")

        # Connections: Apps → Infrastructure
        for app_name, app_data in self.apps.items():
            safe_id = self._safe_id(app_name)
            if app_data.get("port"):
                lines.append(f"    FactoryAPI --> {safe_id}")
            if app_data.get("webhook_url"):
                lines.append(f"    {safe_id} -.->|webhook| n8nCloud")

        lines.append("")
        lines.append("    FactoryAPI --> SkillsRouter")
        lines.append("    FactoryAPI --> CommandCenter")
        lines.append("")

        # Connections: Router → Agents
        for agent in self.agents:
            safe_id = self._safe_id(agent)
            cls = self.classifications.get(agent, "NORMAL")
            if cls == "BOTTLENECK":
                lines.append(f"    SkillsRouter ==>|heavy| {safe_id}")
            elif cls == "ORPHANED":
                lines.append(f"    SkillsRouter -.->|rare| {safe_id}")
            else:
                lines.append(f"    SkillsRouter -->|dispatch| {safe_id}")
        lines.append("")

        # Monitoring connections from Sentinel_Bridge
        sentinel_id = self._safe_id("Sentinel_Bridge")
        for app_name in self.apps:
            if app_name != "Sentinel_Bridge":
                lines.append(f"    {sentinel_id} -.->|monitor| {self._safe_id(app_name)}")
        lines.append("")

        # Styling
        lines.append("    %% Styling")
        for agent in self.agents:
            safe_id = self._safe_id(agent)
            cls = self.classifications.get(agent, "NORMAL")
            if cls == "ORPHANED":
                lines.append(f"    style {safe_id} stroke:#999,stroke-width:1px,stroke-dasharray: 5 5,color:#999")
            elif cls == "BOTTLENECK":
                lines.append(f"    style {safe_id} stroke:#e74c3c,stroke-width:4px,fill:#ffeaea")

        lines.append("```")
        return "\n".join(lines)

    def _safe_id(self, name: str) -> str:
        """Convert a name to a safe Mermaid node ID."""
        return name.replace(" ", "_").replace("-", "_").replace(".", "_")

    # ── Phase 5: Load Report ─────────────────────────────

    def generate_load_report(self) -> dict:
        """
        Generate a JSON report with agent utilization and
        rebalancing recommendations.
        """
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "lookback_days": LOOKBACK_DAYS,
            "total_agents": len(self.agents),
            "total_apps": len(self.apps),
            "agent_status": {},
            "recommendations": [],
        }

        for agent in self.agents:
            cls = self.classifications.get(agent, "NORMAL")
            stats = self.call_stats.get(agent.lower().replace("_", "-"), {})
            report["agent_status"][agent] = {
                "classification": cls,
                "total_calls": stats.get("total_calls", 0),
                "last_called": stats.get("last_called", "never"),
            }

        # Generate recommendations
        orphaned = [a for a, c in self.classifications.items() if c == "ORPHANED"]
        bottlenecks = [a for a, c in self.classifications.items() if c == "BOTTLENECK"]

        if orphaned:
            report["recommendations"].append({
                "type": "ORPHAN_REVIEW",
                "priority": "MEDIUM",
                "agents": orphaned,
                "action": (
                    f"{len(orphaned)} agent(s) have low utilization. "
                    f"Consider: (1) integrating them into more workflows, "
                    f"(2) merging their capabilities into other agents, or "
                    f"(3) marking them as inactive in registry.json."
                ),
            })

        if bottlenecks:
            report["recommendations"].append({
                "type": "BOTTLENECK_RELIEF",
                "priority": "HIGH",
                "agents": bottlenecks,
                "action": (
                    f"{len(bottlenecks)} agent(s) are over-taxed. "
                    f"Consider: (1) distributing their tasks to underutilized agents, "
                    f"(2) adding caching for repeated queries, or "
                    f"(3) splitting responsibilities into sub-agents."
                ),
            })

        if not orphaned and not bottlenecks:
            report["recommendations"].append({
                "type": "BALANCED",
                "priority": "LOW",
                "action": "Agent load is well-distributed. No rebalancing needed.",
            })

        return report

    # ── Phase 6: Save ────────────────────────────────────

    def save_diagram(self, mermaid_content: str, report: dict) -> Tuple[str, str]:
        """
        Save the Mermaid diagram and load report to data/network_maps/.
        Returns (diagram_path, report_path).
        """
        os.makedirs(MAPS_DIR, exist_ok=True)
        ts = datetime.now().strftime("%Y-%m-%d_%H%M")

        # Save Mermaid diagram as markdown
        md_path = os.path.join(MAPS_DIR, f"network_map_{ts}.md")
        md_content = (
            f"# Agent Network Map — {ts}\n\n"
            f"Generated by Visual Mapping Protocol\n\n"
            f"## Legend\n"
            f"- 🟢 Active App | ⚪ Inactive App\n"
            f"- 👻 Orphaned Agent (< {ORPHAN_THRESHOLD} calls/week)\n"
            f"- 🔥 Bottleneck Agent (> {BOTTLENECK_PERCENTILE}th percentile)\n\n"
            f"## Network Diagram\n\n{mermaid_content}\n\n"
            f"## Agent Classifications\n\n"
        )
        for agent in self.agents:
            cls = self.classifications.get(agent, "NORMAL")
            icon = {"ORPHANED": "👻", "BOTTLENECK": "🔥", "NORMAL": "✅"}.get(cls, "❓")
            md_content += f"- {icon} **{agent}**: {cls}\n"

        # Add recommendations
        md_content += "\n## Recommendations\n\n"
        for rec in report.get("recommendations", []):
            md_content += f"- **[{rec.get('priority', '?')}]** {rec.get('action', '')}\n"

        with open(md_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(md_content)

        # Save JSON report
        json_path = os.path.join(MAPS_DIR, f"load_report_{ts}.json")
        with open(json_path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(report, f, indent=2)

        # Also save as "latest" for easy access
        latest_md = os.path.join(MAPS_DIR, "latest_network_map.md")
        latest_json = os.path.join(MAPS_DIR, "latest_load_report.json")
        with open(latest_md, "w", encoding="utf-8", newline="\n") as f:
            f.write(md_content)
        with open(latest_json, "w", encoding="utf-8", newline="\n") as f:
            json.dump(report, f, indent=2)

        return md_path, json_path


# ── Entry Point ──────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    mapper = NetworkMapper()

    print("Scanning agent network...")
    summary = mapper.scan_network()
    print(f"  Apps: {summary['apps']}")
    print(f"  Agents: {summary['agents']}")
    print(f"  Connections: {summary['connections']}")
    print(f"  Orphaned: {summary['orphaned']}")
    print(f"  Bottleneck: {summary['bottleneck']}")

    print("\nGenerating Mermaid diagram...")
    mermaid = mapper.generate_mermaid()
    report = mapper.generate_load_report()

    print("\nSaving to data/network_maps/...")
    md_path, json_path = mapper.save_diagram(mermaid, report)
    print(f"  Diagram: {md_path}")
    print(f"  Report:  {json_path}")

    print("\n--- Sample Mermaid Output ---")
    try:
        sample = mermaid[:500] + "..." if len(mermaid) > 500 else mermaid
        print(sample)
    except UnicodeEncodeError:
        print("(Mermaid output contains unicode — see saved file for full diagram)")
