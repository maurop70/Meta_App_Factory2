# AGENTS.md — MAF claude-mcp-bridge

Agent roles and wiring for the Meta App Factory QA Lab.

---

## E2E Orchestrator (e2e_orchestrator.py)

**Role**: Coordinates Inspector + Seed + Playwright agents. Manages run state on disk. Streams events to QA Lab UI. Entry point for all E2E evaluation requests.

**MCP tool**: `run_e2e_evaluation`  
**Gemini**: `run_e2e_evaluation`  
**Command**: `"test <app_name>"` in loop_ui.py terminal  
**Sub-agents**: `inspector_agent.py`, `seed_agent.py`, `playwright_agent.py`

### Pipeline phases

| Phase | Agent | Output |
|---|---|---|
| 1 | `InspectorAgent.inspect(app_config)` | `TestPlan` — routes, pages, auth flows, test cases, seed requirements |
| 2 | `SeedAgent.seed(app_config, test_plan, run_id)` | `SeedReport` — tables seeded, records inserted |
| 3 | `PlaywrightAgent.run(app_config, test_plan, run_id, callback)` | `EvaluationReport` — pass/fail/escalate + screenshots |

### Run state lifecycle

```
created → inspecting → seeding → testing → (fixing)* → complete | escalate | failed
```

State persisted at: `logs/qa_runs/{run_id}.json`  
Final report at: `logs/e2e_reports/{run_id}_report.json`

---

## InspectorAgent (inspector_agent.py)

**Role**: Reads app code + docs, produces `TestPlan`.

**Signature**: `InspectorAgent.inspect(app_config: dict) -> TestPlan`

Phases 1–7: docs → backend routes → frontend pages → auth flows → test cases (LLM) → seed requirements → save.

---

## SeedAgent (seed_agent.py)

**Role**: Schema-driven DB seeding. INSERT OR IGNORE only. Never deletes.

**Signature**: `SeedAgent.seed(app_config: dict, test_plan: Any, run_id: str) -> SeedReport`

---

## PlaywrightAgent (playwright_agent.py)

**Role**: Runs all test cases, fires ClaudeAY fix mandates on failures (max 5 cycles), escalates on architectural decisions.

**Signature**: `PlaywrightAgent.run(app_config: dict, test_plan: Any, run_id: str, event_callback: Callable) -> EvaluationReport`

**event_callback contract**: `callback(event_type: str, data: Any)` — fired for `test_start`, `test_pass`, `test_fail`, `fix_cycle_start`, `fix_cycle_complete`, `escalate`, `complete`.
