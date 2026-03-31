SOP: The Triad Collaboration Protocol
Objective: To ensure all application components are architected for maximum efficiency, self-healing capability, and commercial-grade stability.

The Mandatory Consultation Loop:
Before any file is created or modified in the Meta_App_Factory, the following Triad Review must occur:

Strategic Blueprint (Gemini - The Brain):

Analyze the user's high-level intent.

Break the request into logical modules.

Action: Generate the "Master Plan" JSON and pass it to Antigravity.

Implementation Architecture (Antigravity - The Architect):

Review the local environment (Docker, folder paths, existing scripts).

Identify potential "breaking points" or dependency conflicts.

Action: If complex logic or new code is required, Antigravity must trigger the Claude Code Executor.

Code Optimization (Claude - The Specialist):

Write the raw Python/HTML/JS code based on the Architect's requirements.

Implement Self-Healing Blocks (Try/Except logs that report back to the API).

Action: Return the optimized code to Antigravity for physical deployment.

Final Approval Rule:

"No agent shall finalize a file without an explicit 'Review Passed' metadata tag from at least one other member of the Triad. If an error occurs during execution, the Specialist - Critic must be summoned to analyze the logs before a second attempt is made."

---

## V3.1 ADDENDUM: Sentinel Relay & Zero-Trust Protocol

**Status:** ACTIVE | **Deployment Date:** 2026-03-30 | **Aegis Phase:** 2

### Protocol Summary

The Sentinel Relay enforces a mandatory multi-agent audit before any sensitive data (Financial/Structural) is committed to the PulseBoard.

### 1. The Mandatory Signature

Every `POST` to `/api/aegis/sentinel-relay` must include:

| Field | Required Value | Enforcement |
|---|---|---|
| `is_audited` | `True` | Pre-flight gate rejects `False` with **403** |
| `phantom_audit_id` | Valid audit ID string | Pre-flight gate rejects `None` with **403** |

Payloads missing either field are **rejected at the gate** before they ever reach Phantom QA.

### 2. The Zero-Trust Verdict

`api.py` on Port 5000 will **block** any data where the sidecar call to Phantom QA (Port 5030) returns anything other than `status: PASSED`.

| QA Verdict | PulseBoard Result |
|---|---|
| `PASSED` | **COMMITTED** |
| `FAILED` | BLOCKED |
| `UNREACHABLE` | BLOCKED |
| `SKIPPED` | BLOCKED |

**There are no exceptions.** The `SKIPPED` state was permanently removed as a valid pass condition on 2026-03-30.

### 3. CLO Sanction Gate

Alpha_V2_Genesis deployments are restricted via `/api/aegis/sanction-check` (Port 5008) which requires the CLO Agent (Port 5080) to be **online**.

| CLO Status | Sanction Result |
|---|---|
| Online (HTTP 200) | `APPROVED` — deployment proceeds |
| Offline / Error | `BLOCKED` — kill switch active |

### 4. Auto-Push Telemetry

The `FragilityAutoPush` daemon thread in Alpha_V2_Genesis broadcasts the Fragility Index to the Factory Gateway (`/api/aegis/fragility-ingest`) every **60 seconds**, enabling continuous risk monitoring by the Master Architect Elite.

### 5. Visual Confirmation

Refer to the `factory_ui` Neural Network panel. The following nodes must be **Green** for the Sentinel Relay to operate:

- **CLO Node** (Port 5080) — Legal compliance gate
- **Phantom QA Node** (Port 5030) — Audit verification
- **Factory Core** (Port 5000) — Gateway relay

### 6. Verification Tests

| Script | Purpose | Expected |
|---|---|---|
| `test_sentinel_bypass.py` | Sends unaudited data | **403 BLOCKED** |
| `test_sentinel_sanctioned.py` | Sends audited data | **200 PASS** |

Both tests were executed and confirmed on 2026-03-30T23:09 EDT.

---

*V3.1 Addendum authored by: Lead Systems Architect | Verified by: Phantom QA Elite*
*Registry: Project_Aegis — PHASE_2_EXPANSION_ACTIVE*
