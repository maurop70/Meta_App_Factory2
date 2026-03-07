"""
Aether Runtime — Execution Engine
====================================
Project Aether | Meta_App_Factory
Phase 1: Config Loader + Agent Router
Phase 2: Intent Classifier + Critic Gate + Boardroom Logger

The engine that brings the C-Suite agent configs to life.
Reads agent_config.json files and routes tasks through n8n webhooks.
"""

import os
import sys
import json
import re
import time
import uuid
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, List

# ── Environment Setup ──
RUNTIME_DIR = os.path.dirname(os.path.abspath(__file__))
FACTORY_DIR = os.path.abspath(os.path.join(RUNTIME_DIR, ".."))
sys.path.insert(0, FACTORY_DIR)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(FACTORY_DIR, ".env"))
except ImportError:
    pass

# ── Configuration ──
CONFIG_DIR = os.path.join(RUNTIME_DIR, "C-Suite_Active_Logic")
BOARDROOM_DIR = os.path.join(RUNTIME_DIR, "Boardroom_Exchange")
SYSTEM_MAP_PATH = os.path.join(RUNTIME_DIR, "Aether_System_Map.json")
RUNTIME_LOG = os.path.join(BOARDROOM_DIR, "runtime_log.json")

# n8n Agent Webhooks (from factory.py AGENT_REGISTRY)
WEBHOOK_MAP = {
    "CEO": "https://humanresource.app.n8n.cloud/webhook/gemini-flash",
    "CFO": "https://humanresource.app.n8n.cloud/webhook/cfo",
    "CTO": "https://humanresource.app.n8n.cloud/webhook/gemini-flash",
    "CMO": "https://humanresource.app.n8n.cloud/webhook/cmo-v2",
    "DEEP_CRAWLER": "https://humanresource.app.n8n.cloud/webhook/gemini-flash",
    "THE_LIBRARIAN": "https://humanresource.app.n8n.cloud/webhook/gemini-flash",
    "THE_CRITIC": "https://humanresource.app.n8n.cloud/webhook/critic-v2",
    "COMPLIANCE_OFFICER": "https://humanresource.app.n8n.cloud/webhook/gemini-flash",
    "DATA_ARCHITECT": "https://humanresource.app.n8n.cloud/webhook/gemini-flash",
}

# Fallback routing for placeholder agents
FALLBACK_ROUTES = {
    "CMO": "DEEP_CRAWLER",
    "RESEARCHER": "DEEP_CRAWLER",
    "GRAPHIC_DESIGNER": "CEO",
    "PRESENTATION_EXPERT": "CEO",
    "CX_STRATEGIST": "CEO",
}


# ══════════════════════════════════════════════════
#  PHASE 1: CONFIG LOADER
# ══════════════════════════════════════════════════

class AgentConfig:
    """Parsed agent configuration with validation."""

    def __init__(self, config_dict: dict, config_path: str):
        self.raw = config_dict
        self.config_path = config_path
        self.name = config_dict.get("name", "Unknown")
        self.role = config_dict.get("role", "")
        self.model = config_dict.get("model", "")
        self.temperature = config_dict.get("temperature", 0.3)
        self.max_tokens = config_dict.get("max_tokens", 4096)
        self.system_prompt = config_dict.get("system_prompt", "")
        self.tools = config_dict.get("tools", [])
        self.reports_to = config_dict.get("reports_to", "")
        self.status = config_dict.get("status", "active")
        self.division = config_dict.get("division", "")
        self.isolation = config_dict.get("isolation", {})
        self.is_placeholder = self.status == "placeholder"

    @property
    def agent_key(self) -> str:
        """Normalized key for routing (e.g., 'CEO', 'THE_CRITIC')."""
        return self.name.split("—")[0].strip().upper().replace(" ", "_")

    def validate_isolation(self) -> bool:
        """Verify this config doesn't violate isolation boundaries."""
        forbidden = self.isolation.get("forbidden_references", [])
        prompt_lower = self.system_prompt.lower()
        for ref in forbidden:
            # Skip the isolation protocol mention itself
            if f"separated from the {ref.lower()}" in prompt_lower:
                continue
            if f"forbidden_references" in prompt_lower:
                continue
        return True

    def __repr__(self):
        status = "🟡 PLACEHOLDER" if self.is_placeholder else "✅ ACTIVE"
        return f"<Agent {self.name} | {status} | {self.model}>"


class ConfigLoader:
    """Reads and manages all agent configurations from C-Suite_Active_Logic/."""

    def __init__(self, config_dir: str = CONFIG_DIR):
        self.config_dir = config_dir
        self.agents: Dict[str, AgentConfig] = {}
        self.load_all()

    def load_all(self):
        """Load all agent configs from subdirectories."""
        self.agents = {}
        config_path = Path(self.config_dir)

        if not config_path.exists():
            print(f"[RUNTIME] ❌ Config directory not found: {self.config_dir}")
            return

        for agent_dir in sorted(config_path.iterdir()):
            if not agent_dir.is_dir():
                continue
            config_file = agent_dir / "agent_config.json"
            if not config_file.exists():
                continue

            try:
                with open(config_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                agent = AgentConfig(data, str(config_file))

                if not agent.validate_isolation():
                    print(f"[RUNTIME] 🚫 ISOLATION VIOLATION: {agent.name} — skipped")
                    continue

                self.agents[agent.agent_key] = agent
                status = "🟡" if agent.is_placeholder else "✅"
                print(f"[RUNTIME] {status} Loaded: {agent.name} ({agent.agent_key})")

            except (json.JSONDecodeError, KeyError) as e:
                print(f"[RUNTIME] ❌ Failed to load {config_file}: {e}")

        active = sum(1 for a in self.agents.values() if not a.is_placeholder)
        placeholder = sum(1 for a in self.agents.values() if a.is_placeholder)
        print(f"\n[RUNTIME] 📊 Loaded {len(self.agents)} agents ({active} active, {placeholder} placeholder)")

    def get_agent(self, key: str) -> Optional[AgentConfig]:
        """Get agent config by normalized key."""
        return self.agents.get(key.upper().replace(" ", "_"))

    def get_active_agents(self) -> List[AgentConfig]:
        """Return only active (non-placeholder) agents."""
        return [a for a in self.agents.values() if not a.is_placeholder]

    def get_all_agents(self) -> List[AgentConfig]:
        return list(self.agents.values())


# ══════════════════════════════════════════════════
#  PHASE 2: INTENT CLASSIFIER
# ══════════════════════════════════════════════════

class IntentClassifier:
    """Maps incoming prompts to the correct agent using keyword matching."""

    # Keyword → Agent mapping (ordered by specificity)
    PATTERNS = [
        # Financial
        (["budget", "revenue", "cost", "fiscal", "financial", "spreadsheet", "sheets", "invoice", "roi"], "CFO"),
        # Technical / Architecture
        (["runtime", "architecture", "deploy", "code", "api", "endpoint", "build", "infrastructure", "server"], "CTO"),
        # Research / Web Mining
        (["search", "research", "find", "crawl", "web", "scrape", "data extraction", "mining"], "DEEP_CRAWLER"),
        # Audit / Quality
        (["audit", "review", "critique", "quality", "skeptic", "evaluate", "assess"], "THE_CRITIC"),
        # Security / Compliance
        (["security", "compliance", "credential", "encryption", "privacy", "audit trail", "vault"], "COMPLIANCE_OFFICER"),
        # Data / Schema
        (["schema", "pipeline", "data model", "database", "json", "normalize", "migration"], "DATA_ARCHITECT"),
        # Index / Documentation
        (["index", "master_index", "sync", "register", "catalog", "documentation", "librarian"], "THE_LIBRARIAN"),
        # Marketing / Brand
        (["market", "brand", "campaign", "customer", "engagement", "competitor"], "CMO"),
    ]

    def classify(self, prompt: str) -> tuple:
        """Return (agent_key, confidence) for the given prompt.
        
        Returns:
            tuple: (agent_key: str, confidence: float)
        """
        prompt_lower = prompt.lower()
        scores = {}

        for keywords, agent_key in self.PATTERNS:
            score = sum(1 for kw in keywords if kw in prompt_lower)
            if score > 0:
                # Normalize by pattern size for fair comparison
                scores[agent_key] = score / len(keywords)

        if not scores:
            return ("CEO", 0.3)  # Default: route to CEO for delegation

        best_agent = max(scores, key=scores.get)
        confidence = min(scores[best_agent] * 2, 1.0)  # Scale up, cap at 1.0

        return (best_agent, round(confidence, 2))


# ══════════════════════════════════════════════════
#  AGENT ROUTER
# ══════════════════════════════════════════════════

class AgentRouter:
    """Routes prompts to agents via n8n webhooks."""

    def __init__(self, config_loader: ConfigLoader):
        self.loader = config_loader
        self.classifier = IntentClassifier()

    def resolve_agent(self, agent_key: str) -> str:
        """Resolve an agent key, applying fallback routing for placeholders."""
        agent = self.loader.get_agent(agent_key)

        if agent and not agent.is_placeholder:
            return agent_key

        # Check fallback routes
        if agent_key in FALLBACK_ROUTES:
            fallback = FALLBACK_ROUTES[agent_key]
            print(f"[ROUTER] ↩️ {agent_key} is placeholder → routing to {fallback}")
            return fallback

        # Default fallback: CEO
        print(f"[ROUTER] ↩️ {agent_key} not found → routing to CEO")
        return "CEO"

    def get_webhook(self, agent_key: str) -> Optional[str]:
        """Get the webhook URL for an agent."""
        resolved = self.resolve_agent(agent_key)
        return WEBHOOK_MAP.get(resolved)

    def build_prompt(self, agent_key: str, user_prompt: str) -> str:
        """Inject the agent's system_prompt into the request."""
        agent = self.loader.get_agent(agent_key)
        if agent:
            return f"SYSTEM CONTEXT:\n{agent.system_prompt}\n\nTASK:\n{user_prompt}"
        return user_prompt

    def route(self, prompt: str, target_agent: str = None) -> dict:
        """Route a prompt to the appropriate agent.
        
        Args:
            prompt: The user's task/question text
            target_agent: Optional direct routing override
            
        Returns:
            dict with routing decision, response placeholder, and metadata
        """
        session_id = str(uuid.uuid4())[:8]
        start_time = time.time()

        # Classify or use direct target
        if target_agent:
            agent_key = target_agent.upper().replace(" ", "_")
            confidence = 1.0
        else:
            agent_key, confidence = self.classifier.classify(prompt)

        # Resolve (handles placeholders + fallbacks)
        resolved_key = self.resolve_agent(agent_key)
        webhook = self.get_webhook(resolved_key)
        full_prompt = self.build_prompt(resolved_key, prompt)

        # Build result
        result = {
            "session_id": session_id,
            "timestamp": datetime.now().isoformat(),
            "input_prompt": prompt,
            "classified_to": agent_key,
            "resolved_to": resolved_key,
            "confidence": confidence,
            "webhook": webhook,
            "full_prompt_preview": full_prompt[:200] + "..." if len(full_prompt) > 200 else full_prompt,
            "status": "READY_TO_DISPATCH",
            "duration_ms": round((time.time() - start_time) * 1000, 2),
        }

        print(f"\n[ROUTER] 📨 Session {session_id}")
        print(f"  → Classified: {agent_key} (confidence: {confidence})")
        if agent_key != resolved_key:
            print(f"  → Resolved: {resolved_key} (fallback)")
        print(f"  → Webhook: {webhook}")

        return result

    def dispatch(self, prompt: str, target_agent: str = None) -> dict:
        """Route AND send the prompt to the agent webhook.
        
        Returns dict with the agent's response.
        """
        import requests

        routing = self.route(prompt, target_agent)
        webhook = routing["webhook"]

        if not webhook:
            routing["status"] = "ERROR_NO_WEBHOOK"
            routing["response"] = "No webhook URL configured for this agent."
            return routing

        try:
            payload = {"prompt": routing["full_prompt_preview"]}
            resp = requests.post(webhook, json=payload, timeout=60)
            routing["status"] = "DISPATCHED"
            routing["response"] = resp.text if resp.status_code == 200 else f"Error: {resp.status_code}"
            routing["http_status"] = resp.status_code
        except Exception as e:
            routing["status"] = "DISPATCH_ERROR"
            routing["response"] = str(e)

        # Log to boardroom
        self._log_to_boardroom(routing)

        return routing

    def _log_to_boardroom(self, routing: dict):
        """Append routing result to the runtime log."""
        log = []
        if os.path.exists(RUNTIME_LOG):
            try:
                with open(RUNTIME_LOG, "r") as f:
                    log = json.load(f)
            except (json.JSONDecodeError, IOError):
                log = []

        # Keep only essential fields for the log
        entry = {
            "session_id": routing["session_id"],
            "timestamp": routing["timestamp"],
            "input_prompt": routing["input_prompt"][:100],
            "classified_to": routing["classified_to"],
            "resolved_to": routing["resolved_to"],
            "confidence": routing["confidence"],
            "status": routing["status"],
            "duration_ms": routing["duration_ms"],
        }
        log.append(entry)

        # Rotate log (keep last 100 entries)
        if len(log) > 100:
            log = log[-100:]

        os.makedirs(BOARDROOM_DIR, exist_ok=True)
        with open(RUNTIME_LOG, "w") as f:
            json.dump(log, f, indent=2)


# ══════════════════════════════════════════════════
#  CRITIC GATE
# ══════════════════════════════════════════════════

class CriticGate:
    """Mandatory review gate — all outputs pass through The Critic before reaching CEO."""

    CRITIC_WEBHOOK = WEBHOOK_MAP.get("THE_CRITIC", "")

    def review(self, content: str, source_agent: str) -> dict:
        """Submit content for Critic review.
        
        Returns:
            dict with verdict (APPROVE/REVISE/REJECT), feedback, and metadata
        """
        review_prompt = (
            f"SYSTEM CONTEXT: You are The Critic. Review the following output from {source_agent}. "
            f"Evaluate for: logical consistency, feasibility, security implications, and quality. "
            f"Respond with VERDICT: APPROVE, REVISE, or REJECT. Include specific feedback.\n\n"
            f"CONTENT TO REVIEW:\n{content}"
        )

        result = {
            "source_agent": source_agent,
            "review_requested": datetime.now().isoformat(),
            "content_preview": content[:200],
            "verdict": "PENDING",
            "feedback": "",
        }

        if not self.CRITIC_WEBHOOK:
            result["verdict"] = "BYPASS"
            result["feedback"] = "No Critic webhook configured — bypassed."
            return result

        try:
            import requests
            resp = requests.post(
                self.CRITIC_WEBHOOK,
                json={"prompt": review_prompt},
                timeout=60
            )
            if resp.status_code == 200:
                response_text = resp.text
                # Parse verdict from response
                if "APPROVE" in response_text.upper():
                    result["verdict"] = "APPROVE"
                elif "REJECT" in response_text.upper():
                    result["verdict"] = "REJECT"
                else:
                    result["verdict"] = "REVISE"
                result["feedback"] = response_text
            else:
                result["verdict"] = "ERROR"
                result["feedback"] = f"HTTP {resp.status_code}"
        except Exception as e:
            result["verdict"] = "ERROR"
            result["feedback"] = str(e)

        return result


# ══════════════════════════════════════════════════
#  AETHER RUNTIME (Main Orchestrator)
# ══════════════════════════════════════════════════

class AetherRuntime:
    """The main execution engine for Project Aether."""

    def __init__(self):
        print("=" * 60)
        print("  AETHER RUNTIME — Initializing...")
        print("=" * 60)

        self.loader = ConfigLoader()
        self.router = AgentRouter(self.loader)
        self.critic = CriticGate()

        print(f"\n[RUNTIME] ✅ Aether Runtime v1.0.0 initialized")
        print(f"[RUNTIME] 📊 {len(self.loader.agents)} agents loaded")
        print(f"[RUNTIME] 🔗 {len(WEBHOOK_MAP)} webhook endpoints configured")
        print("=" * 60)

    def prompt(self, text: str, target: str = None, skip_critic: bool = False) -> dict:
        """Main entry point — submit a task to the C-Suite.
        
        Args:
            text: The task/question
            target: Optional direct agent target (bypass classifier)
            skip_critic: Skip the Critic gate (CEO override only)
        
        Returns:
            dict with full routing, response, and critic review
        """
        # Route to agent
        result = self.router.dispatch(text, target)

        # Critic gate (unless bypassed or errored)
        if not skip_critic and result["status"] == "DISPATCHED":
            critic_result = self.critic.review(
                result.get("response", ""),
                result["resolved_to"]
            )
            result["critic_review"] = critic_result

        return result

    def delegate(self, text: str, agent: str) -> dict:
        """Direct delegation to a specific agent (CEO shorthand)."""
        return self.prompt(text, target=agent)

    def health_check(self) -> dict:
        """Check status of all agents and webhooks."""
        import requests

        report = {
            "timestamp": datetime.now().isoformat(),
            "agents": {},
            "webhooks": {},
        }

        for key, agent in self.loader.agents.items():
            report["agents"][key] = {
                "name": agent.name,
                "status": "placeholder" if agent.is_placeholder else "active",
                "model": agent.model,
            }

        for name, url in WEBHOOK_MAP.items():
            try:
                resp = requests.head(url, timeout=5)
                report["webhooks"][name] = {
                    "url": url[:50] + "...",
                    "status": "reachable" if resp.status_code < 500 else "error",
                    "code": resp.status_code,
                }
            except Exception as e:
                report["webhooks"][name] = {
                    "url": url[:50] + "...",
                    "status": "unreachable",
                    "error": str(e),
                }

        return report

    def list_agents(self) -> List[dict]:
        """List all loaded agents with their status."""
        return [
            {
                "key": key,
                "name": agent.name,
                "role": agent.role,
                "status": "placeholder" if agent.is_placeholder else "active",
                "model": agent.model,
            }
            for key, agent in sorted(self.loader.agents.items())
        ]


# ══════════════════════════════════════════════════
#  CLI Interface
# ══════════════════════════════════════════════════

def main():
    """Command-line interface for the Aether Runtime."""
    import argparse

    parser = argparse.ArgumentParser(description="Aether Runtime — C-Suite Execution Engine")
    subparsers = parser.add_subparsers(dest="command")

    # Prompt command
    prompt_parser = subparsers.add_parser("prompt", help="Submit a task to the C-Suite")
    prompt_parser.add_argument("text", help="Task description")
    prompt_parser.add_argument("--target", help="Direct to specific agent")
    prompt_parser.add_argument("--skip-critic", action="store_true", help="Skip Critic review")

    # List agents
    subparsers.add_parser("agents", help="List all loaded agents")

    # Health check
    subparsers.add_parser("health", help="Check system health")

    # Route only (no dispatch)
    route_parser = subparsers.add_parser("route", help="Classify a prompt without dispatching")
    route_parser.add_argument("text", help="Text to classify")

    args = parser.parse_args()

    runtime = AetherRuntime()

    if args.command == "prompt":
        result = runtime.prompt(args.text, target=args.target, skip_critic=args.skip_critic)
        print(json.dumps(result, indent=2, default=str))

    elif args.command == "agents":
        agents = runtime.list_agents()
        print(json.dumps(agents, indent=2))

    elif args.command == "health":
        report = runtime.health_check()
        print(json.dumps(report, indent=2, default=str))

    elif args.command == "route":
        routing = runtime.router.route(args.text)
        print(json.dumps(routing, indent=2, default=str))

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
