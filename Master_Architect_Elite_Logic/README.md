# Master Architect Elite Logic

**Port 5050** | Meta App Factory | Antigravity V3

The Master Architect is a standalone multi-agent app that provides **architecture review intelligence** for the Meta App Factory ecosystem. Every proposed feature, build, or refactor is analyzed by three specialized agents (the **Triad**) and stress-tested by the **Adversarial Gate** before finalization.

## The Triad

| Agent | Weight | Domain |
|---|---|---|
| **Structural Engineer** | 40% | DB schemas, API contracts, migrations, port conflicts |
| **Logic Weaver** | 30% | n8n workflows, agent routing, fallback chains |
| **Security Auditor** | 30% | Credentials, PII, CORS, Deploy Shield compliance |

## Adversarial Gate (Socratic Bridge)

| Score | Action |
|---|---|
| ≥ 85 | ✅ Auto-approve → store in memory |
| 60–84 | ⚠️ Challenge → 3 weakness probes → await Commander reasoning |
| < 60 | ❌ Reject → detailed report |

## Quick Start

```bash
# Windows
Launch_Master_Architect.bat

# Manual
pip install -r requirements.txt
python server.py
```

## API Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/` | Service info |
| GET | `/api/health` | Health + memory stats |
| POST | `/api/review` | Full Triad review (blocking) |
| POST | `/api/review/stream` | SSE streaming review |
| POST | `/api/review/quick` | Single-agent fast review |
| GET | `/api/gate/status` | Active challenges |
| POST | `/api/gate/respond` | Submit reasoning |
| POST | `/api/gate/override` | Commander Hard Override |
| GET | `/api/patterns` | Winning patterns |
| POST | `/api/patterns/similar` | Find similar patterns |
| GET | `/api/regressions` | Regression warnings |
| POST | `/api/audit/flow` | FlowAuditor scan |
| POST | `/api/audit/leitner` | Leitner deep review |
| POST | `/api/warroom/respond` | War Room integration |

## Architecture

```
server.py → triad_engine.py → [3 agents in parallel] → adversarial_gate.py → memory_engine.py
```

## Files

- `TECHNICAL_SPEC.md` — Human-readable specification
- `INGESTION_SPEC.json` — Machine-readable Factory ingestion file
- `config.json` — App configuration
- `architect_memory.db` — SQLite pattern memory (auto-created on first run)
