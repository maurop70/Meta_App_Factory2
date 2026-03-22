# SOP_MAINTENANCE.md — Factory Governance & Resilience Protocols
### System Hardening V3.2 — Standard Operating Procedures
*Last Updated: 2026-03-22T02:26:00-04:00*

---

## 1. Key Rotation Protocol

| Rule | Detail |
|:--|:--|
| **When to rotate** | If Watchdog latency consistently exceeds **2000ms** across 3+ consecutive heartbeat cycles |
| **How to rotate** | Use `python env_updater.py` — this updates the `.env` and ensures all child apps inherit the new key automatically via the factory's centralized `.env` access |
| **Never** | Manually edit `.env` in child agent directories. There is only one `.env` (in `Meta_App_Factory/`), and all agents inherit from it |
| **Verification** | After rotation, run `python swdr_heartbeat.py --once` to confirm `Credential Sentinel: 🟢 VALID` |

> [!CAUTION]
> Bypassing `env_updater.py` risks breaking the credential inheritance chain for all child apps.

---

## 2. Watchdog Interpretation

The **SYSTEM_Watchdog_Ping** (ID: `XHYpA1Es2YL9ugjK`) is the primary health indicator. The heartbeat pings it every **60 seconds**.

| Status | Latency | Action |
|:--|:--|:--|
| 🟢 **Green** | < 1000ms | Normal operations. All `safe_post()` calls execute live against n8n Cloud |
| 🟡 **Yellow** | 1000ms – 3000ms | **Degraded**. Monitor `local_pending_sync.json` for buffer growth. Investigate cloud load |
| 🔴 **Red** | > 3000ms *or* 4xx/5xx | **Auto-Pivot to Safe-Buffer Mode**. All live cloud attempts cease. `factory.py` queues payloads to `pending_sync/`. Heartbeat sends ntfy HIGH PRIORITY alert |

**Safe-Buffer Mode is automatic** — the heartbeat (`swdr_heartbeat.py`) toggles it on/off based on Watchdog response. No manual intervention needed for mode switching.

---

## 3. Recovery Procedures

### Daily Check
```bash
python recovery_sync.py --status
```
Run this **every 24 hours** to check buffer health. Output shows:
- Watchdog status (🟢/🔴)
- Safe-Buffer mode (ON/OFF)
- Pending items count
- Archived items count

### Flushing the Buffer
```bash
# Only when Watchdog returns to 🟢 Green:
python recovery_sync.py

# Force flush (use sparingly — bypasses health check):
python recovery_sync.py --force
```

| Rule | Detail |
|:--|:--|
| **When to flush** | Only when Watchdog is 🟢 Green (< 1000ms) |
| **Force flush** | Use `--force` only in emergencies or after confirming cloud health manually |
| **Duplicate prevention** | Successfully synced payloads are moved to `synced_archive.json` and the source file in `pending_sync/` is deleted |

---

## 4. Scaling Protocol — Creating New Agents

### Always Use the Generator
```bash
python app_generator.py my_new_agent
```

This guarantees:
- ✅ `safe_post()` pattern inherited
- ✅ `Antigravity_Full_v2` key inherited via factory `.env`
- ✅ StateManager UUID logging on every outgoing call
- ✅ Watchdog preflight before heavy operations
- ✅ Automatic Safe-Buffer mode during cloud outages
- ✅ Phantom QA regression test auto-triggered after creation

### Rules

| ✅ Do | ❌ Never |
|:--|:--|
| Use `app_generator.py` for all new agents | Manually create agents without the template |
| Import `safe_post` from `factory.py` | Use raw `requests.post()` to n8n endpoints |
| Keep agents in `agents/{name}/` directory | Place agents outside the factory structure |
| Let `FACTORY_DIR` resolve to `Meta_App_Factory/` | Hardcode paths to `.env` or config files |

> [!WARNING]
> Bypassing the `factory.py` import removes Safe-Buffer protection. The agent will crash on cloud outages instead of gracefully buffering.

---

## 5. Audit Logging

All critical system changes must be logged in **`MASTER_INDEX.md`** with the following conventions:

| Change Type | Prefix | Example |
|:--|:--|:--|
| Architecture upgrade | `[SYSTEM_V3_UPGRADE]` | New resilience module deployed |
| Key rotation | `[KEY_ROTATION]` | Antigravity_Full_v2 refreshed |
| Workflow patch | `[WEBHOOK_PATCH]` | Batch responseMode update |
| Incident response | `[INCIDENT]` | Safe-Buffer triggered, recovery executed |
| New agent | `[AGENT_DEPLOYED]` | New agent scaffolded via app_generator |
| Phantom QA run | `[PHANTOM_QA]` | Autonomous regression test executed |
| Vision OCR | `[VISION_OCR]` | Image text extraction via Gemini Vision |
| Model Router | `[MODEL_ROUTER]` | Dynamic API gateway model switch |

### Log Entry Format
```markdown
| Date | Component | Change | Result |
|---|---|---|---|
| YYYY-MM-DDTHH:MM | `component_name` | [PREFIX] Description | Outcome |
```

---

## Quick Reference — File Map

| File | Purpose |
|:--|:--|
| `factory.py` | Central orchestrator + `safe_post()` API |
| `local_state_manager.py` | UUID+timestamp logging, Safe-Buffer toggle |
| `local_pending_sync.json` | Live state buffer (pending/sent/failed entries) |
| `resilience_config.json` | Watchdog URL, latency thresholds, queue settings |
| `recovery_sync.py` | Flushes buffered payloads to cloud |
| `swdr_heartbeat.py` | 60s health monitor + Safe-Buffer auto-toggle |
| `app_generator.py` | Scaffolds new V3-hardened agents |
| `child_app_template.py` | Canonical template for all agents |
| `pending_sync/` | Queued payload files during cloud outages |
| `synced_archive.json` | Archive of successfully recovered payloads |
| `MASTER_INDEX.md` | System audit log |
| `Project_Aether/C-Suite_Active_Logic/Phantom_QA/phantom_agent.py` | Autonomous QA testing engine |
| `Resonance/model_router_v3.py` | Intelligent API model gateway |
| `Resonance/graph_memory_v3.py` | Aether cognitive node-edge memory |
