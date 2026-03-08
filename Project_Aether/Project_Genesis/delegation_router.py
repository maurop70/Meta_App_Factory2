"""
Delegate AI — Aether Runtime Bridge
=====================================
Phase 2: Enhanced legal classification + delegation routing.

Bridges the Delegate API to the Aether Runtime, enabling:
1. LLM-enhanced classification (falls back to keyword if LLM unavailable)
2. Intelligent delegation routing (matches tasks to agents)
3. CriticGate integration for quality assurance
4. Boardroom logging for audit trail
"""

import os
import sys
import json
from datetime import datetime, timezone
from typing import Optional

RUNTIME_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(RUNTIME_DIR)
sys.path.insert(0, PARENT_DIR)

# Attempt to load Aether Runtime components
try:
    from aether_runtime import ConfigLoader, AgentRouter, IntentClassifier
    RUNTIME_LOADED = True
except ImportError:
    RUNTIME_LOADED = False


# ══════════════════════════════════════════════════
#  DELEGATION ROUTING RULES
#  Maps task categories to the best C-Suite agent
# ══════════════════════════════════════════════════

DELEGATION_RULES = {
    "MOTION":         {"agent": "CTO",                "reason": "Legal document drafting requires architectural precision"},
    "DISCOVERY":      {"agent": "Deep_Crawler",       "reason": "Discovery requires systematic document analysis"},
    "CLIENT_INTAKE":  {"agent": "CX_Strategist",      "reason": "Client onboarding is a CX function"},
    "BILLING":        {"agent": "CFO",                 "reason": "Financial operations fall under CFO"},
    "RESEARCH":       {"agent": "Researcher",          "reason": "Legal research is core research function"},
    "FILING":         {"agent": "Compliance_Officer",   "reason": "Court filings require compliance oversight"},
    "CORRESPONDENCE": {"agent": "CMO",                 "reason": "Client communications are marketing-adjacent"},
    "REVIEW":         {"agent": "The_Critic",          "reason": "Document review aligns with quality assurance"},
    "CONTRACT":       {"agent": "CTO",                 "reason": "Contract engineering requires technical precision"},
    "COMPLIANCE":     {"agent": "Compliance_Officer",   "reason": "Direct compliance function"},
    "OTHER":          {"agent": "CEO",                 "reason": "Unclassified tasks escalate to CEO for routing"},
}

# Priority-based escalation: URGENT tasks always copy the CEO
ESCALATION_RULES = {
    "URGENT": {"cc": ["CEO"], "sla_hours": 4},
    "HIGH":   {"cc": [],      "sla_hours": 24},
    "NORMAL": {"cc": [],      "sla_hours": 72},
    "LOW":    {"cc": [],      "sla_hours": 168},
}


# ══════════════════════════════════════════════════
#  ENHANCED CLASSIFIER (LLM + Keyword hybrid)
# ══════════════════════════════════════════════════

LEGAL_CLASSIFICATION_PROMPT = """You are a legal task classifier for a law firm delegation system.
Given a natural-language delegation, classify it into exactly one category and one priority.

CATEGORIES: MOTION, DISCOVERY, CLIENT_INTAKE, BILLING, RESEARCH, FILING, CORRESPONDENCE, REVIEW, CONTRACT, COMPLIANCE, OTHER
PRIORITIES: URGENT, HIGH, NORMAL, LOW

Respond in JSON only: {"category": "...", "priority": "...", "title": "...", "confidence": 0.0-1.0}

Delegation: {prompt}"""


class DelegationRouter:
    """Routes delegated tasks to the appropriate C-Suite agent."""

    def __init__(self):
        self.config_loader = None
        self.agent_router = None
        if RUNTIME_LOADED:
            try:
                self.config_loader = ConfigLoader()
                self.agent_router = AgentRouter(self.config_loader)
            except Exception:
                pass

    def route(self, category: str, priority: str) -> dict:
        """
        Determine which agent should handle this task.
        Returns routing info including agent, reason, escalation, and SLA.
        """
        rule = DELEGATION_RULES.get(category, DELEGATION_RULES["OTHER"])
        escalation = ESCALATION_RULES.get(priority, ESCALATION_RULES["NORMAL"])

        routing = {
            "primary_agent": rule["agent"],
            "routing_reason": rule["reason"],
            "cc_agents": escalation["cc"],
            "sla_hours": escalation["sla_hours"],
            "category": category,
            "priority": priority,
            "routed_at": datetime.now(timezone.utc).isoformat(),
        }

        # If Aether Runtime is available, verify agent exists
        if self.config_loader:
            agent_config_path = os.path.join(
                PARENT_DIR, "C-Suite_Active_Logic", rule["agent"], "agent_config.json"
            )
            routing["agent_active"] = os.path.exists(agent_config_path)
            if routing["agent_active"]:
                try:
                    with open(agent_config_path, 'r') as f:
                        config = json.load(f)
                    routing["agent_status"] = config.get("status", "unknown")
                    routing["agent_model"] = config.get("model", "unknown")
                except Exception:
                    routing["agent_status"] = "error"
        else:
            routing["agent_active"] = None  # Unknown without runtime

        return routing

    def log_to_boardroom(self, task_id: str, routing: dict, prompt: str) -> bool:
        """Log the delegation to the Boardroom Exchange for audit trail."""
        boardroom_dir = os.path.join(PARENT_DIR, "Boardroom_Exchange")
        if not os.path.isdir(boardroom_dir):
            return False

        log_entry = {
            "type": "DELEGATION_LOG",
            "task_id": task_id,
            "routing": routing,
            "prompt_preview": prompt[:200],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "delegate_ai_v1",
        }

        log_file = os.path.join(boardroom_dir, "delegation_log.jsonl")
        try:
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_entry) + "\n")
            return True
        except Exception:
            return False


# ══════════════════════════════════════════════════
#  CONFIDENTIALITY ROUTER
#  Tasks marked confidential get special handling
# ══════════════════════════════════════════════════

class ConfidentialityRouter:
    """Routes confidential/privileged tasks through secure channels."""

    VAULT_DIR = os.path.join(PARENT_DIR, "Compliance_Vault")

    @staticmethod
    def should_vault(task: dict) -> bool:
        """Determine if a task requires vault-level security."""
        return (
            task.get("confidential", False) or
            task.get("privilege_flag", False) or
            task.get("category") in ("COMPLIANCE",)
        )

    @staticmethod
    def vault_metadata(task: dict) -> dict:
        """Generate vault metadata for secure storage."""
        return {
            "vault_id": task.get("id"),
            "classification": "PRIVILEGED" if task.get("privilege_flag") else "CONFIDENTIAL",
            "access_control": ["CEO", "Compliance_Officer"],
            "retention_policy": "7_YEARS",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }


# Singleton instances
delegation_router = DelegationRouter()
confidentiality_router = ConfidentialityRouter()
