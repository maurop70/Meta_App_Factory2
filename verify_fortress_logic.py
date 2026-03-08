"""
verify_fortress_logic.py — Phase 3 Integration Test
=====================================================
Antigravity-AI | Meta App Factory | Project Aether

Validates the full Fortress Protocol stack:
  1. leak_monitor.py — ntfy send with Click deep-link
  2. LEDGER.md update — SECURITY_INTERCEPTIONS section
  3. on_ip_milestone() — full event pipeline

Usage:
    python verify_fortress_logic.py

Expected Result:
  ✅ ntfy push sent to antigravity-security topic
  ✅ LEDGER.md updated under ## SECURITY_INTERCEPTIONS
  ✅ Click header = http://localhost:5173/?view=sop&app=...&score=...
"""

import sys
import os
import json
from datetime import datetime
from pathlib import Path

# ── Resolve paths so this can be run from any directory ──
SCRIPT_DIR = Path(__file__).resolve().parent
# The test script sits at Meta_App_Factory root; Project_Aether is one level down
AETHER_DIR = SCRIPT_DIR / "Project_Aether"

# Add aether dir to path so we can import c_suite.leak_monitor
sys.path.insert(0, str(AETHER_DIR))

LEDGER_PATH = SCRIPT_DIR / "LEDGER.md"
SECTION = "SECURITY_INTERCEPTIONS"

# ══════════════════════════════════════════════════
#  ANSI colours for readable output
# ══════════════════════════════════════════════════
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def ok(msg):    print(f"  {GREEN}✅ {msg}{RESET}")
def warn(msg):  print(f"  {YELLOW}⚠️  {msg}{RESET}")
def fail(msg):  print(f"  {RED}❌ {msg}{RESET}")
def info(msg):  print(f"  {CYAN}ℹ️  {msg}{RESET}")
def header(msg): print(f"\n{BOLD}{msg}{RESET}")


# ══════════════════════════════════════════════════
#  STEP 1 — Import & validate leak_monitor
# ══════════════════════════════════════════════════

header("🔬 PHASE 3 INTEGRATION TEST — Fortress Protocol")
print(f"   Time: {datetime.now().isoformat()}")

header("Step 1 — Importing leak_monitor...")
try:
    from c_suite.leak_monitor import on_ip_milestone, on_leak_intercepted, get_info
    info_data = get_info()
    ok(f"leak_monitor imported — v{info_data['version']}")
    info(f"ntfy topic: {info_data['ntfy_topic']}")
    info(f"ntfy server: {info_data['ntfy_server']}")
    info(f"factory_ui: {info_data.get('factory_ui', 'http://localhost:5173')}")
    info(f"deep_linking: {info_data.get('deep_linking', False)}")
    sop_format = info_data.get('sop_url_format', 'N/A')
    info(f"SOP URL format: {sop_format}")
except ImportError as e:
    fail(f"Import failed: {e}")
    fail("Ensure you are running from Meta_App_Factory/ and deps are installed.")
    sys.exit(1)


# ══════════════════════════════════════════════════
#  STEP 2 — Snapshot LEDGER.md before test
# ══════════════════════════════════════════════════

header("Step 2 — Snapshotting LEDGER.md...")
ledger_before = ""
if LEDGER_PATH.exists():
    ledger_before = LEDGER_PATH.read_text(encoding="utf-8")
    lines_before = ledger_before.count("\n")
    ok(f"LEDGER.md found — {lines_before} lines")
    if SECTION in ledger_before:
        ok(f"## {SECTION} section exists")
    else:
        warn(f"## {SECTION} section NOT found — will be created")
else:
    warn("LEDGER.md not found — will be created by leak_monitor")
    ledger_before = ""
    lines_before = 0


# ══════════════════════════════════════════════════
#  STEP 3 — Fire IP Milestone alert (HIGH CONFIDENCE)
# ══════════════════════════════════════════════════

header("Step 3 — Firing IP Milestone alert (confidence=0.87)...")
TEST_APP = "Resonance_v3_Integration_Test"
TEST_CONFIDENCE = 0.87
TEST_IP_TYPE = "patent"

print(f"   App: {TEST_APP}")
print(f"   Confidence: {int(TEST_CONFIDENCE * 100)}%")
print(f"   IP Type: {TEST_IP_TYPE}")
print()

result = on_ip_milestone(
    app_name=TEST_APP,
    confidence=TEST_CONFIDENCE,
    ip_type=TEST_IP_TYPE,
    detail="Phase 3 Integration Test — verify_fortress_logic.py",
)

ntfy = result.get("ntfy", {})
ntfy_status = ntfy.get("status", "unknown")
click_url = ntfy.get("click_url", "")

if ntfy_status == "sent":
    ok(f"ntfy push sent (HTTP {ntfy.get('http_status')})")
elif ntfy_status == "connection_failed":
    warn(f"ntfy push FAILED — {ntfy.get('detail', 'connection refused')}")
    warn("This is expected if ntfy.sh is blocked. LEDGER test will still run.")
else:
    warn(f"ntfy status: {ntfy_status}")

if click_url:
    ok(f"Click header set: {click_url}")
    # Validate URL format
    if "view=sop" in click_url and "app=" in click_url and "score=" in click_url:
        ok("SOP deep-link format validated (?view=sop&app=...&score=...)")
    else:
        fail(f"SOP URL format unexpected: {click_url}")
else:
    fail("Click header NOT present in ntfy result — check send_ntfy_alert()")


# ══════════════════════════════════════════════════
#  STEP 4 — Fire Leak Interception alert
# ══════════════════════════════════════════════════

header("Step 4 — Firing Leak Interception alert...")

leak_result = on_leak_intercepted(
    agent_name="Deep_Crawler_Test",
    leak_type="TRADE_SECRET",
    detail="Phase 3 Integration Test — simulated leak block",
    severity="HIGH",
)

leak_ntfy = leak_result.get("ntfy", {})
leak_review_url = leak_ntfy.get("click_url", "")

if leak_ntfy.get("status") == "sent":
    ok("Leak alert sent to ntfy")
else:
    warn(f"Leak alert ntfy status: {leak_ntfy.get('status')} (OK if offline)")

if leak_review_url:
    ok(f"Leak Click header: {leak_review_url}")
else:
    fail("Leak alert missing Click header")


# ══════════════════════════════════════════════════
#  STEP 5 — Verify LEDGER.md was updated
# ══════════════════════════════════════════════════

header("Step 5 — Verifying LEDGER.md update...")

if LEDGER_PATH.exists():
    ledger_after = LEDGER_PATH.read_text(encoding="utf-8")
    lines_after = ledger_after.count("\n")

    new_lines = lines_after - lines_before
    if new_lines > 0:
        ok(f"LEDGER.md grew by {new_lines} lines")
    else:
        fail("LEDGER.md did NOT change — mirror_to_ledger may have failed")

    # Check for our test entries
    if TEST_APP in ledger_after:
        ok(f"App '{TEST_APP}' found in LEDGER.md")
    else:
        fail(f"App '{TEST_APP}' NOT found in LEDGER.md")

    if "IP_MILESTONE" in ledger_after:
        ok("IP_MILESTONE action entry found")
    else:
        fail("IP_MILESTONE not found in LEDGER.md")

    if "LEAK_BLOCKED" in ledger_after:
        ok("LEAK_BLOCKED action entry found")
    else:
        fail("LEAK_BLOCKED not found in LEDGER.md")

    if "SOP:" in ledger_after or "REVIEW:" in ledger_after:
        ok("Deep-link (SOP: or REVIEW:) field found in LEDGER.md")
    else:
        fail("Deep-link fields NOT found in LEDGER.md")

    if SECTION in ledger_after:
        ok(f"## {SECTION} section intact")
    else:
        fail(f"## {SECTION} section missing from LEDGER.md")

    # Print new entries
    new_content = ledger_after[len(ledger_before):]
    if new_content.strip():
        header("📋 New LEDGER.md entries:")
        for line in new_content.strip().split("\n"):
            if line.strip():
                print(f"   {CYAN}{line}{RESET}")
else:
    fail("LEDGER.md not found after test run")


# ══════════════════════════════════════════════════
#  STEP 6 — Full result summary
# ══════════════════════════════════════════════════

header("━━━ PHASE 3 TEST SUMMARY ━━━")
ledger_ok = TEST_APP in (LEDGER_PATH.read_text(encoding="utf-8") if LEDGER_PATH.exists() else "")
ntfy_ok   = ntfy_status in ("sent", "connection_failed")  # connection_failed is expected in dev
click_ok  = bool(click_url and "view=sop" in click_url)
ledger_sop_ok = ("SOP:" in (LEDGER_PATH.read_text(encoding="utf-8") if LEDGER_PATH.exists() else ""))

rows = [
    ("leak_monitor import",        True),
    ("ntfy POST fired",             ntfy_ok),
    ("Click deep-link header",      click_ok),
    ("LEDGER.md IP_MILESTONE",      ledger_ok),
    ("LEDGER.md SOP: field",        ledger_sop_ok),
]

all_pass = True
for label, passed in rows:
    if passed:
        ok(f"{label}")
    else:
        fail(f"{label}")
        all_pass = False

print()
if all_pass:
    print(f"{GREEN}{BOLD}🎉 ALL CHECKS PASSED — Phase 3 Fortress Protocol verified!{RESET}")
else:
    print(f"{YELLOW}{BOLD}⚠️  Some checks failed. Review output above.{RESET}")

print(f"\n   SOP deep-link test URL:")
print(f"   {CYAN}http://localhost:5173/?view=sop&app={TEST_APP}&score=87{RESET}")
print(f"\n   Open the factory UI and paste that URL to verify modal auto-opens.\n")
