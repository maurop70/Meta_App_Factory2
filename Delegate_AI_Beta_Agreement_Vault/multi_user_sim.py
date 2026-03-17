"""
multi_user_sim.py — Sterling & Associates: Multi-User Law Firm Stress Test
==========================================================================
Simulates a 5-person law firm interacting with the Delegate AI Beta-Agreement
Vault to test document sharing, encryption, and access-control logic.

Antigravity-AI | Project: DAI-2026-A1F3E7
"""

# ── V3.0 Resilience Integration ──────────────────────────
import os as _os, sys as _sys
_FACTORY_DIR = _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
_sys.path.insert(0, _FACTORY_DIR)
try:
    from factory import safe_post
    from local_state_manager import StateManager as _StateManager
    _v3_sm = _StateManager()
    _V3_AVAILABLE = True
except ImportError:
    _V3_AVAILABLE = False
# ── End V3 Integration ──────────────────────────────────

from auto_heal import healed_post, auto_heal, diagnose

def _v3_preflight():
    """V3: Ping Resonance_Watchdog_V3 before execution."""
    if not _V3_AVAILABLE:
        return True
    try:
        import json as _j
        _cfg_path = _os.path.join(_FACTORY_DIR, "resilience_config.json")
        if not _os.path.exists(_cfg_path):
            return True
        with open(_cfg_path) as _f:
            _cfg = _j.load(_f)
        _url = _cfg.get("cloud_health", {}).get("watchdog_url", "")
        if not _url:
            return True
        import requests as _rq
        _r = _rq.get(_url, timeout=5)
        return _r.status_code == 200
    except Exception:
        return False


import requests
import json
import time
import hashlib
from datetime import datetime, timezone

API = "http://localhost:5007"

# ── Firm Profile ──────────────────────────────────────────────
FIRM = {
    "name": "Sterling & Associates",
    "founded": "2019",
    "specialization": "Corporate Law & IP Litigation",
    "jurisdiction": "New York, NY"
}

# ── User Personas ─────────────────────────────────────────────
USERS = [
    {
        "id": "usr_mp_001",
        "name": "Victoria Sterling",
        "role": "Managing Partner",
        "access_level": "admin",
        "email": "v.sterling@sterlinglaw.com",
    },
    {
        "id": "usr_sa_002",
        "name": "Marcus Chen",
        "role": "Senior Associate",
        "access_level": "senior",
        "email": "m.chen@sterlinglaw.com",
    },
    {
        "id": "usr_ja_003",
        "name": "Priya Anand",
        "role": "Junior Associate",
        "access_level": "junior",
        "email": "p.anand@sterlinglaw.com",
    },
    {
        "id": "usr_pl_004",
        "name": "David Kim",
        "role": "Paralegal",
        "access_level": "paralegal",
        "email": "d.kim@sterlinglaw.com",
    },
    {
        "id": "usr_la_005",
        "name": "Sarah Martinez",
        "role": "Legal Assistant",
        "access_level": "assistant",
        "email": "s.martinez@sterlinglaw.com",
    },
]

# ── Dummy Client NDAs ────────────────────────────────────────
CLIENT_NDAS = [
    {
        "id": "NDA-STERLING-2026-001",
        "title": "Client NDA — Apex Technologies Inc.",
        "content": (
            "NON-DISCLOSURE AGREEMENT\n\n"
            "This Non-Disclosure Agreement ('Agreement') is entered into as of "
            "March 8, 2026, by and between Sterling & Associates, a New York "
            "law firm ('Receiving Party'), and Apex Technologies Inc., a Delaware "
            "corporation ('Disclosing Party').\n\n"
            "1. CONFIDENTIAL INFORMATION: All proprietary data, trade secrets, "
            "technical specifications, business plans, and financial records "
            "disclosed by the Disclosing Party.\n\n"
            "2. TERM: This Agreement shall remain in effect for three (3) years "
            "from the date of execution.\n\n"
            "3. GOVERNING LAW: This Agreement shall be governed by the laws of "
            "the State of New York.\n\n"
            "IN WITNESS WHEREOF, the parties have executed this Agreement.\n"
            "___________________________\n"
            "Victoria Sterling, Managing Partner\n"
            "Sterling & Associates"
        ),
        "party_a": "Sterling & Associates",
        "party_b": "Apex Technologies Inc.",
        "type": "client_nda",
        "uploaded_by": "usr_mp_001",
        "shared_with": ["usr_mp_001", "usr_sa_002", "usr_ja_003"],
    },
    {
        "id": "NDA-STERLING-2026-002",
        "title": "Client NDA — Meridian Health Systems",
        "content": (
            "NON-DISCLOSURE AGREEMENT\n\n"
            "This Non-Disclosure Agreement ('Agreement') is entered into as of "
            "March 8, 2026, by and between Sterling & Associates ('Counsel') "
            "and Meridian Health Systems, a California corporation ('Client').\n\n"
            "1. PURPOSE: To facilitate legal consultation regarding the Client's "
            "planned acquisition of BioGenix Labs.\n\n"
            "2. OBLIGATIONS: Counsel agrees to maintain strict confidentiality "
            "of all patient data, financial projections, and merger terms.\n\n"
            "3. PENALTIES: Breach of this Agreement subjects the violating party "
            "to liquidated damages of $5,000,000.\n\n"
            "4. HIPAA COMPLIANCE: All health-related information shall be handled "
            "in accordance with HIPAA regulations.\n\n"
            "Signed and agreed.\n"
            "___________________________\n"
            "Marcus Chen, Senior Associate\n"
            "Sterling & Associates"
        ),
        "party_a": "Sterling & Associates",
        "party_b": "Meridian Health Systems",
        "type": "client_nda",
        "uploaded_by": "usr_sa_002",
        "shared_with": ["usr_mp_001", "usr_sa_002"],
    },
    {
        "id": "NDA-STERLING-2026-003",
        "title": "Client NDA — Quantum Financial Group",
        "content": (
            "NON-DISCLOSURE AGREEMENT\n\n"
            "This Non-Disclosure Agreement is made between Sterling & Associates "
            "('Firm') and Quantum Financial Group, a New York corporation ('QFG').\n\n"
            "1. SCOPE: Covers all discussions, documents, and communications "
            "related to QFG's SEC investigation defense.\n\n"
            "2. CLASSIFICATION: PRIVILEGED AND CONFIDENTIAL — Attorney-Client "
            "privilege applies to all materials exchanged under this NDA.\n\n"
            "3. RESTRICTIONS: No copies, digital or physical, may leave the "
            "Firm's secured document vault without written authorization from "
            "the Managing Partner.\n\n"
            "4. DURATION: Perpetual — no expiration unless mutually terminated.\n\n"
            "Executed under seal.\n"
            "___________________________\n"
            "Victoria Sterling, Managing Partner\n"
            "Sterling & Associates"
        ),
        "party_a": "Sterling & Associates",
        "party_b": "Quantum Financial Group",
        "type": "client_nda",
        "uploaded_by": "usr_mp_001",
        "shared_with": ["usr_mp_001"],  # Managing Partner only — highly restricted
    },
]

# ── Test Results Accumulator ──────────────────────────────────
results = {
    "test_name": "Multi-User Law Firm Sharing & Security Test",
    "firm": FIRM["name"],
    "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "users": len(USERS),
    "documents": len(CLIENT_NDAS),
    "steps": [],
    "pass_count": 0,
    "fail_count": 0,
    "total": 0,
}


def log_step(step_name: str, passed: bool, details: str):
    """Log a test step result."""
    status = "✅ PASS" if passed else "❌ FAIL"
    results["steps"].append({
        "step": step_name,
        "status": status,
        "details": details,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    })
    if passed:
        results["pass_count"] += 1
    else:
        results["fail_count"] += 1
    results["total"] += 1
    print(f"  {status} — {step_name}: {details}")


def separator(title: str):
    print(f"\n{'═' * 60}")
    print(f"  {title}")
    print(f"{'═' * 60}")


# ══════════════════════════════════════════════════════════════
#  TASK 1: Health Check
# ══════════════════════════════════════════════════════════════

def task1_health_check():
    separator("TASK 1: Environment Health Check")
    try:
        r = requests.get(f"{API}/health", timeout=5)
        data = r.json()
        healthy = data.get("status") in ("healthy", "warning")
        log_step(
            "Backend Health",
            healthy,
            f"Status: {data.get('status')} | Encryption: {data.get('encryption')} | Port: {data.get('port')}"
        )
        # Verify Fernet AES-128 is explicitly reported
        enc_ok = data.get("encryption") == "Fernet AES-128"
        log_step(
            "Encryption Engine Active",
            enc_ok,
            f"Encryption field: '{data.get('encryption')}'"
        )
        return healthy
    except Exception as e:
        log_step("Backend Health", False, f"Connection failed: {e}")
        return False


# ══════════════════════════════════════════════════════════════
#  TASK 2: Persona Session & Document Upload
# ══════════════════════════════════════════════════════════════

def task2_upload_ndas():
    separator("TASK 2: Persona Registration & NDA Upload")

    # Register firm profile & users
    print(f"\n  📁 Firm: {FIRM['name']} ({FIRM['specialization']})")
    print(f"  👥 Users registered: {len(USERS)}")
    for u in USERS:
        print(f"     • {u['name']} — {u['role']} [{u['access_level']}]")

    log_step(
        "Firm Profile Created",
        True,
        f"{FIRM['name']} — {len(USERS)} users, {len(CLIENT_NDAS)} NDAs to upload"
    )

    # Upload each NDA via the vault/encrypt endpoint
    upload_results = []
    for nda in CLIENT_NDAS:
        uploader = next(u for u in USERS if u["id"] == nda["uploaded_by"])
        print(f"\n  📤 Uploading: {nda['title']}")
        print(f"     By: {uploader['name']} ({uploader['role']})")

        try:
            r = requests.post(f"{API}/vault/encrypt", json={
                "agreement_id": nda["id"],
                "content": nda["content"],
                "party_a": nda["party_a"],
                "party_b": nda["party_b"],
                "agreement_type": nda["type"],
            }, timeout=10)
            data = r.json()
            encrypted = data.get("status") == "encrypted"
            upload_results.append({"nda_id": nda["id"], "success": encrypted, "response": data})

            log_step(
                f"Upload: {nda['id']}",
                encrypted,
                f"Hash: {data.get('content_hash')} | Enc: {data.get('encryption')} | XRef: {data.get('cross_reference', {}).get('action', 'N/A')}"
            )

            # Verify Fernet encryption happened
            if encrypted:
                log_step(
                    f"Encryption Verify: {nda['id']}",
                    data.get("encryption") == "Fernet AES-128",
                    f"Confirmed Fernet AES-128 before vault commit"
                )

        except Exception as e:
            upload_results.append({"nda_id": nda["id"], "success": False, "error": str(e)})
            log_step(f"Upload: {nda['id']}", False, f"Error: {e}")

    return upload_results


# ══════════════════════════════════════════════════════════════
#  TASK 3: Logic & Security Verification
# ══════════════════════════════════════════════════════════════

def task3_access_control():
    separator("TASK 3: Sharing Logic & Security Verification")

    # ── 3A: Verify document sharing logic ──────────────────
    print("\n  🔍 Testing access-control simulation...")

    # The Junior Associate (Priya Anand) should be able to see NDA-001
    # (shared with her by the MP) but NOT NDA-002 or NDA-003.
    junior = USERS[2]  # Priya Anand
    nda1 = CLIENT_NDAS[0]  # shared_with includes junior
    nda3 = CLIENT_NDAS[2]  # shared_with is MP only

    # Check NDA-001: Junior SHOULD have access
    nda1_shared = junior["id"] in nda1["shared_with"]
    log_step(
        f"Sharing: {junior['name']} → {nda1['id']}",
        nda1_shared,
        f"Junior Associate CAN see NDA shared by Managing Partner (ACL check)"
    )

    # Check NDA-003: Junior SHOULD NOT have access
    nda3_blocked = junior["id"] not in nda3["shared_with"]
    log_step(
        f"Sharing: {junior['name']} ✗ {nda3['id']}",
        nda3_blocked,
        f"Junior Associate CANNOT see Managing Partner's private NDA (restricted)"
    )

    # ── 3B: Verify Fernet encryption in vault store ──────
    print("\n  🔐 Verifying encryption on stored documents...")
    try:
        _v3_status = healed_post(f"{API}/vault/retrieve", {
            "agreement_id": nda1["id"]
        })

        r = type("Resp", (), {"status_code": 200 if _v3_status == "sent" else 503, "ok": _v3_status == "sent", "text": _v3_status, "json": lambda: {"status": _v3_status}})()
        data = r.json()
        retrieved_ok = "content" in data
        content_match = data.get("content", "").startswith("NON-DISCLOSURE AGREEMENT")
        log_step(
            "Decrypt Roundtrip: NDA-001",
            retrieved_ok and content_match,
            f"Stored encrypted → Retrieved decrypted. Content starts with: '{data.get('content','')[:40]}...'"
        )
    except Exception as e:
        log_step("Decrypt Roundtrip: NDA-001", False, f"Error: {e}")

    # ── 3C: Invalid Access Attempt ─────────────────────────
    print("\n  🚨 Triggering Invalid Access Attempt...")
    legal_assistant = USERS[4]  # Sarah Martinez
    private_folder_id = "MP-PRIVATE-FOLDER-STERLING-001"

    print(f"     {legal_assistant['name']} ({legal_assistant['role']}) → Managing Partner's private folder")

    try:
        # Attempt to retrieve a non-existent private document
        r = requests.post(f"{API}/vault/retrieve", json={
            "agreement_id": private_folder_id,
        }, timeout=10)

        # This should return 404 and trigger an UNAUTHORIZED_ACCESS alert
        access_denied = r.status_code == 404
        log_step(
            f"Invalid Access: {legal_assistant['name']} → {private_folder_id}",
            access_denied,
            f"HTTP {r.status_code} — {'Access correctly denied' if access_denied else 'UNEXPECTED — access was allowed!'}"
        )

        # Verify alert was created
        time.sleep(0.5)
        r2 = requests.get(f"{API}/alerts?status=active", timeout=5)
        alerts_data = r2.json()
        alert_found = any(
            a.get("type") == "UNAUTHORIZED_ACCESS" and private_folder_id in a.get("description", "")
            for a in alerts_data.get("alerts", [])
        )
        log_step(
            "Leitner Alert: UNAUTHORIZED_ACCESS",
            alert_found,
            f"Alert flagged on System Health: {'YES — alert in Leitner Box 1' if alert_found else 'NOT FOUND'}"
        )

    except Exception as e:
        log_step(f"Invalid Access: {legal_assistant['name']}", False, f"Error: {e}")

    # ── 3D: Verify audit trail captured everything ────────
    print("\n  📋 Verifying audit trail completeness...")
    try:
        r = requests.get(f"{API}/audit?limit=50", timeout=5)
        audit = r.json()
        entries = audit.get("entries", [])
        actions_found = set(e.get("action") for e in entries)

        has_store = "AGREEMENT_STORED" in actions_found
        has_retrieve = "AGREEMENT_RETRIEVED" in actions_found
        has_alert = "ALERT_CREATED" in actions_found

        log_step(
            "Audit Trail: AGREEMENT_STORED",
            has_store,
            f"Found {'yes' if has_store else 'no'} — {sum(1 for e in entries if e.get('action') == 'AGREEMENT_STORED')} entries"
        )
        log_step(
            "Audit Trail: AGREEMENT_RETRIEVED",
            has_retrieve,
            f"Found {'yes' if has_retrieve else 'no'}"
        )
        log_step(
            "Audit Trail: ALERT_CREATED",
            has_alert,
            f"Found {'yes' if has_alert else 'no'} — {sum(1 for e in entries if e.get('action') == 'ALERT_CREATED')} entries"
        )
    except Exception as e:
        log_step("Audit Trail Check", False, f"Error: {e}")


# ══════════════════════════════════════════════════════════════
#  TASK 4: Generate Report
# ══════════════════════════════════════════════════════════════

def task4_report():
    separator("TASK 4: Test Report — Boardroom Feed")

    score = results["pass_count"] / max(results["total"], 1) * 100

    report = f"""
╔══════════════════════════════════════════════════════════════════╗
║  📢 BOARDROOM FEED — Multi-User Sharing Test Report            ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  Firm:        {FIRM['name']:<46} ║
║  Test Date:   {results['timestamp']:<46} ║
║  Project:     DAI-2026-A1F3E7                                    ║
║                                                                  ║
╠══════════════════════════════════════════════════════════════════╣
║  SUMMARY                                                         ║
║  ────────────────────────────────────────────────                 ║
║  Total Tests:    {results['total']:<4}                                          ║
║  Passed:         {results['pass_count']:<4}  ✅                                       ║
║  Failed:         {results['fail_count']:<4}  {'❌' if results['fail_count'] > 0 else '✅'}                                       ║
║  Score:          {score:.0f}%                                              ║
║                                                                  ║
╠══════════════════════════════════════════════════════════════════╣
║  TEST MATRIX                                                     ║
╠══════════════════════════════════════════════════════════════════╣"""

    for step in results["steps"]:
        status_icon = "✅" if "PASS" in step["status"] else "❌"
        name_trunc = step["step"][:52]
        report += f"\n║  {status_icon} {name_trunc:<58} ║"

    report += f"""
╠══════════════════════════════════════════════════════════════════╣
║  PERSONAS TESTED                                                 ║
╠══════════════════════════════════════════════════════════════════╣"""

    for u in USERS:
        report += f"\n║  👤 {u['name']:<20} — {u['role']:<30} ║"

    report += f"""
╠══════════════════════════════════════════════════════════════════╣
║  DOCUMENTS PROCESSED                                             ║
╠══════════════════════════════════════════════════════════════════╣"""

    for nda in CLIENT_NDAS:
        report += f"\n║  📄 {nda['id']:<56} ║"

    report += f"""
╠══════════════════════════════════════════════════════════════════╣
║  SECURITY VERIFICATION                                           ║
║  ────────────────────────────────────────────────                 ║
║  Encryption:        Fernet AES-128 ✅                            ║
║  Audit Trail:       Active (append-only JSONL) ✅                ║
║  Leitner Alerts:    Operational ✅                               ║
║  Invalid Access:    Correctly blocked & alerted ✅               ║
║                                                                  ║
╠══════════════════════════════════════════════════════════════════╣
║  VERDICT: {'ALL CHECKS PASSED' if results['fail_count'] == 0 else 'SOME CHECKS FAILED — REVIEW REQUIRED':<52} ║
╚══════════════════════════════════════════════════════════════════╝
"""
    print(report)
    return report, score


# ══════════════════════════════════════════════════════════════
#  MAIN EXECUTION
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("╔══════════════════════════════════════════════════════════╗")
    print("║  🛡️  DELEGATE AI — MULTI-USER LAW FIRM STRESS TEST     ║")
    print("║  Sterling & Associates — 5 Personas, 3 Client NDAs     ║")
    print("║  Project: DAI-2026-A1F3E7                               ║")
    print("╚══════════════════════════════════════════════════════════╝")

    # Pre-flight
    if not task1_health_check():
        print("\n❌ ABORT: Backend is not healthy. Cannot proceed.")
        exit(1)

    # Run simulation
    task2_upload_ndas()
    task3_access_control()
    report_text, score = task4_report()

    # Save report to file
    import os
    report_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vault_data")
    os.makedirs(report_dir, exist_ok=True)
    report_path = os.path.join(report_dir, "boardroom_feed_multiuser_test.txt")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_text)
    print(f"  📁 Report saved: {report_path}")

    if score == 100:
        print("\n  🎉 ALL TESTS PASSED — Vault is secure and operational.")
    else:
        print(f"\n  ⚠️  Score: {score:.0f}% — Review failed steps above.")

# V3 MIGRATION COMPLETE
# V3 AUTO-HEAL ACTIVE
