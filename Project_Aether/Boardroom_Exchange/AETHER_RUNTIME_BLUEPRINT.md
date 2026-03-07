# 🏗️ AETHER RUNTIME — Technical Blueprint
## CTO First Cycle Deliverable | Filed: 2026-03-07
### Author: CTO (Lead Systems Architect) | Audit ID: CTO-RUNTIME-001

---

## Executive Summary

The Aether Runtime is the execution engine that transforms static `agent_config.json` declarations into a live, routable multi-agent system. It bridges Project Aether's C-Suite configs with the existing n8n webhook infrastructure and Meta_App_Factory's FastAPI server.

**Design Philosophy:** Build on what exists. The Meta_App_Factory already has a FastAPI server (`api.py`), an n8n bridge pattern (`factory.py:_generate_bridge`), and an `AGENT_REGISTRY` with verified webhooks. The Runtime extends these — it does not replace them.

---

## Architecture

```
                    ┌─────────────────────────────────────────┐
                    │            EXECUTIVE (User)              │
                    └─────────────┬───────────────────────────┘
                                  │ Prompt / Directive
                                  ▼
                    ┌─────────────────────────────────────────┐
                    │         AETHER RUNTIME (FastAPI)         │
                    │  Port: 8001 | aether_runtime.py          │
                    │                                          │
                    │  1. Config Loader                         │
                    │  2. Intent Classifier                     │
                    │  3. Agent Router                          │
                    │  4. Critic Gate                            │
                    │  5. Boardroom Logger                      │
                    └──┬──────┬──────┬──────┬─────────────────┘
                       │      │      │      │
               ┌───────┘  ┌───┘  ┌───┘  ┌───┘
               ▼          ▼      ▼      ▼
         ┌─────────┐ ┌────────┐ ┌────────┐ ┌────────────────┐
         │   CEO   │ │  CFO   │ │ CRITIC │ │  Deep Crawler  │
         │ webhook │ │webhook │ │webhook │ │   webhook      │
         └─────────┘ └────────┘ └────────┘ └────────────────┘
              │           │          │              │
              └───────────┴──────────┴──────────────┘
                          │
                          ▼
              ┌────────────────────────┐
              │  n8n Cloud Webhooks    │
              │  (AGENT_REGISTRY)      │
              └────────────────────────┘
```

---

## Component Design

### 1. Config Loader
```python
# Reads all agent_config.json files at startup
# Returns: Dict[agent_name, AgentConfig]
def load_agents(config_dir: str) -> dict:
    agents = {}
    for agent_dir in Path(config_dir).iterdir():
        config_path = agent_dir / "agent_config.json"
        if config_path.exists():
            with open(config_path) as f:
                config = json.load(f)
            if config.get("status") != "placeholder":
                agents[config["name"]] = config
    return agents
```
- Hot-reload on file change (watchdog)
- Validates schema on load
- Rejects configs with isolation violations

### 2. Intent Classifier
Maps incoming prompts to the correct agent using keyword matching + LLM fallback:

| Intent Pattern | Target Agent | Confidence |
|---|---|---|
| "financial", "budget", "revenue", "sheets" | CFO | HIGH |
| "search", "research", "find", "crawl" | Deep Crawler | HIGH |
| "audit", "review", "security", "compliance" | Compliance Officer / The Critic | HIGH |
| "data", "schema", "pipeline", "architecture" | Data Architect | HIGH |
| "index", "master", "sync", "register" | The Librarian | HIGH |
| ambiguous / multi-domain | CEO (for delegation) | MEDIUM |

Fallback: If confidence < 0.6, route to CEO for manual delegation.

### 3. Agent Router
```python
# Core routing logic
WEBHOOK_MAP = {
    "CEO": "https://humanresource.app.n8n.cloud/webhook/gemini-flash",
    "CFO": "https://humanresource.app.n8n.cloud/webhook/cfo",
    "CRITIC": "https://humanresource.app.n8n.cloud/webhook/critic-v2",
    "CMO": "https://humanresource.app.n8n.cloud/webhook/cmo-v2",
    # ... mapped from existing AGENT_REGISTRY
}

async def route_to_agent(agent_name: str, prompt: str, config: dict):
    # Inject system_prompt from config
    full_prompt = f"SYSTEM: {config['system_prompt']}\n\nTASK: {prompt}"
    webhook = WEBHOOK_MAP.get(agent_name.upper())
    response = await httpx.post(webhook, json={"prompt": full_prompt})
    return response.json()
```

### 4. Critic Gate
**Mandatory review pipeline:**
```
Agent Output → The Critic (webhook) → Verdict
  ├─ APPROVE → Forward to requester
  ├─ REVISE  → Return to originating agent with feedback
  └─ REJECT  → Escalate to CEO with explanation
```

Configurable: Gate can be bypassed for low-priority internal queries by CEO directive.

### 5. Boardroom Logger
Every interaction logged:
```json
{
    "timestamp": "ISO-8601",
    "session_id": "uuid",
    "input_prompt": "...",
    "classified_to": "CFO",
    "agent_response": "...",
    "critic_verdict": "APPROVE",
    "final_output": "...",
    "duration_ms": 1234
}
```

---

## API Endpoints (aether_runtime.py)

| Method | Path | Description |
|---|---|---|
| POST | `/aether/prompt` | Submit a task to the C-Suite |
| POST | `/aether/delegate` | Direct delegation to a specific agent |
| GET | `/aether/agents` | List all loaded agents and their status |
| GET | `/aether/health` | System health check for all webhooks |
| GET | `/aether/boardroom` | Retrieve recent Boardroom logs |
| POST | `/aether/critic/review` | Force a Critic review on any content |

---

## Implementation Plan

| Phase | Deliverable | ETA | Dependencies |
|---|---|---|---|
| **Phase 1** | Config Loader + Agent Router (basic keyword routing) | Day 1 | None |
| **Phase 2** | Critic Gate integration | Day 2 | Critic webhook verified |
| **Phase 3** | Boardroom Logger + `/aether/boardroom` endpoint | Day 2 | Phase 1 |
| **Phase 4** | Intent Classifier (LLM-backed) | Day 3 | Gemini API key secured |
| **Phase 5** | Hot-reload + health monitoring | Day 4 | Phase 1-3 stable |

---

## Integration Points

| System | Interface | Purpose |
|---|---|---|
| Meta_App_Factory `api.py` | Import or mount as sub-app | Shares port 8000 or runs on 8001 |
| `AGENT_REGISTRY` (bridge) | Webhook URL map | Routes to n8n agents |
| `Aether_System_Map.json` | Data pipeline config | Ingestion → Vault flow |
| `Ingestion_Chamber/watcher.py` | File event trigger | Auto-processes incoming data |
| `Compliance_Vault/vault_engine.py` | Secure storage API | Encrypted data retrieval |

---

## Risk Assessment

| Risk | Severity | Mitigation |
|---|---|---|
| n8n webhook latency | MEDIUM | Async routing with timeout fallbacks |
| Credential exposure | CRITICAL | **BLOCKED** — Compliance audit must complete first |
| Single-point-of-failure (n8n cloud) | HIGH | Local fallback mode using direct LLM API calls |
| Config corruption via Drive sync | MEDIUM | Schema validation on load, Git versioning |

---

## CTO Recommendation

**Build Phase 1 first** (Config Loader + Router). This gets agents actually responding to prompts within one session. The Critic Gate (Phase 2) can follow once the basic routing is proven. The LLM-backed classifier (Phase 4) is a refinement, not a blocker — keyword matching covers 80% of use cases.

**Prerequisite:** Compliance Officer must clear the credential remediation (COMPLIANCE-CRED-001) before Phase 4, since the Intent Classifier requires a secured Gemini API connection.

---

*Filed by: CTO — Project Aether*
*Classification: BOARDROOM — Technical Architecture*
*Review required: The Critic → CEO → Executive*
*Implementation blocked on: COMPLIANCE-CRED-001 remediation*
