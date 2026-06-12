"""
Visual Critic + Interactive Planner Verification Suite (2026-06-12)
--------------------------------------------------------------------
Covers the strategic/visual upgrade: route_multimodal plumbing, the
auditor's visual critic check, verdict parsing, and the loop engine's
planning gate logic. All model calls are mocked — no API keys, no network.

Run: python test_visual_audit.py
Output contract: 'RESULT: N passed, M failed' (auditor-parseable).
"""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest import mock

BRIDGE = Path(__file__).parent
sys.path.insert(0, str(BRIDGE))
sys.path.insert(0, str(BRIDGE.parent))

PASSED = 0
FAILED = 0


def check(label: str, ok: bool, detail: str = ""):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f"  [PASS] {label}")
    else:
        FAILED += 1
        print(f"  [FAIL] {label}  {detail}")


import model_router
import auditor
import loop_engine

# ── 1. Router: task mapping + multimodal plumbing ─────────────────────────────

check("visual_critic routes to GEMINI_PRO",
      model_router.get_model_for_task("visual_critic") == model_router.GEMINI_PRO)

captured = {}
def _fake_post(url, json=None, headers=None, timeout=None):
    captured["url"] = url
    captured["payload"] = json
    class R:
        def json(self):
            return {"candidates": [{"content": {"parts": [{"text": "MOCK_OK"}]}}]}
    return R()

with mock.patch.object(model_router, "requests") as req_mock, \
     mock.patch.dict(os.environ, {"GEMINI_API_KEY": "test-key", "GEMINI_VISION_MODEL": ""}):
    req_mock.post = _fake_post
    out = model_router.route_multimodal("visual_critic", "critique this", "QkFTRTY0",
                                        image_mime="image/png")
check("route_multimodal returns raw text (no prefix/truncation)", out == "MOCK_OK")
_parts = captured["payload"]["contents"][0]["parts"]
check("inlineData part attached", any("inlineData" in p for p in _parts))
check("inlineData carries mime + data",
      any(p.get("inlineData", {}).get("mimeType") == "image/png"
          and p.get("inlineData", {}).get("data") == "QkFTRTY0" for p in _parts))
check("vision model in URL is gemini-2.5-pro", "gemini-2.5-pro" in captured["url"])

with mock.patch.dict(os.environ, {"GEMINI_API_KEY": ""}):
    out = model_router.route_multimodal("visual_critic", "x", "eA==")
check("missing API key returns empty (logged, not silent crash)", out == "")

with mock.patch.object(model_router, "requests") as req_mock, \
     mock.patch.dict(os.environ, {"GEMINI_API_KEY": "test-key",
                                  "GEMINI_VISION_MODEL": "gemini-2.5-flash"}):
    req_mock.post = _fake_post
    model_router.route_multimodal("visual_critic", "x", "eA==")
check("GEMINI_VISION_MODEL env overrides to flash", "gemini-2.5-flash" in captured["url"])

# ── 2. Verdict parsing ────────────────────────────────────────────────────────

ok, v = auditor._parse_visual_verdict('{"verdict": "PASS", "violations": []}')
check("JSON PASS verdict", ok and v == [])
ok, v = auditor._parse_visual_verdict(
    'noise {"verdict": "FAIL", "violations": ["button overlaps table"]} trailing')
check("JSON FAIL verdict with violations", not ok and "button overlaps table" in v[0])
ok, _ = auditor._parse_visual_verdict("The layout FAILs basic alignment")
check("non-JSON with FAIL token fails", not ok)
ok, _ = auditor._parse_visual_verdict("Looks good overall")
check("non-JSON without FAIL token passes", ok)

# ── 3. Auditor visual check ───────────────────────────────────────────────────

_tmp = Path(tempfile.mkdtemp())
_orig_dir = auditor.SCREENSHOT_DIR

checks = auditor._check_visual(["claude-mcp-bridge/auditor.py", "api.py"])
check("no frontend files -> no visual check", checks == [])

auditor.SCREENSHOT_DIR = _tmp / "nonexistent"
checks = auditor._check_visual(["factory_ui/src/pages/QALab.jsx"])
check("frontend files but no screenshot dir -> lenient skip",
      len(checks) == 1 and checks[0].ok and "not evaluated" in checks[0].detail)

auditor.SCREENSHOT_DIR = _tmp
(_tmp / "shot_001.png").write_bytes(b"\x89PNG fakebytes")

with mock.patch.object(model_router, "route_multimodal",
                       return_value='{"verdict": "PASS", "violations": []}'):
    checks = auditor._check_visual(["factory_ui/src/pages/QALab.jsx"])
check("critic PASS -> visual check ok",
      len(checks) == 1 and checks[0].ok and checks[0].name == "visual_critic")

with mock.patch.object(model_router, "route_multimodal",
                       return_value='{"verdict": "FAIL", "violations": ["table overflows viewport"]}'):
    checks = auditor._check_visual(["factory_ui/src/components/X.css"])
check("critic FAIL -> visual check fails with critique",
      len(checks) == 1 and not checks[0].ok and "table overflows" in checks[0].detail)

with mock.patch.object(model_router, "route_multimodal", return_value=""):
    with mock.patch.dict(os.environ, {"CLAUDEAY_VISUAL_STRICT": "false"}):
        checks = auditor._check_visual(["factory_ui/src/pages/QALab.jsx"])
check("critic unavailable, lenient -> ok with loud detail",
      len(checks) == 1 and checks[0].ok and "NOT evaluated" in checks[0].detail)

with mock.patch.object(model_router, "route_multimodal", return_value=""):
    with mock.patch.dict(os.environ, {"CLAUDEAY_VISUAL_STRICT": "true"}):
        checks = auditor._check_visual(["factory_ui/src/pages/QALab.jsx"])
check("critic unavailable, strict -> check fails",
      len(checks) == 1 and not checks[0].ok)

# audit() integration: non-frontend ledger unaffected (test_sota_upgrade parity)
from ledger_evaluator import LedgerResult, LedgerStatus
_fake = LedgerResult(status=LedgerStatus.COMPLETE, confidence=0.95,
                     summary="done", structured=True,
                     files_changed=["claude-mcp-bridge/auditor.py"])
report = auditor.audit("fix backend", _fake, trace_id="t-vis", run_suites=False)
check("audit() without frontend files has no visual_critic check",
      not any(c.name == "visual_critic" for c in report.checks))

auditor.SCREENSHOT_DIR = _orig_dir

# ── 4. Interactive Planner gate logic ─────────────────────────────────────────

with mock.patch.dict(os.environ, {"CLAUDEAY_PLAN_APPROVAL": "off"}):
    check("mode off -> no gate", not loop_engine._plan_gate_needed("Deploy to prod", True))

with mock.patch.dict(os.environ, {"CLAUDEAY_PLAN_APPROVAL": "always"}):
    check("mode always + web channel -> gated",
          loop_engine._plan_gate_needed("Check status", True))

with mock.patch.dict(os.environ, {"CLAUDEAY_PLAN_APPROVAL": "tier2"}):
    check("mode tier2 + tier0 intent -> no gate",
          not loop_engine._plan_gate_needed("Check the health status", True))
    check("mode tier2 + git intent -> gated",
          loop_engine._plan_gate_needed("git add, commit and push to dev", True))

with mock.patch.dict(os.environ, {"CLAUDEAY_PLAN_APPROVAL": "always"}):
    with mock.patch.object(loop_engine.sys, "stdin") as stdin_mock:
        stdin_mock.isatty.return_value = False
        check("headless (no tty, no web) -> gate skipped, no deadlock",
              not loop_engine._plan_gate_needed("Fix the bug", False))

# ── 5. Plan drafting (mocked router) ──────────────────────────────────────────

_loop = loop_engine.AutonomousLoop()
with mock.patch.object(model_router, "route",
                       return_value="1. Edit X\n2. Test Y\nVERIFICATION: run suite"):
    plan = _loop._draft_plan("Fix frontend styling on QALab dashboard")
check("planner drafts via router", "VERIFICATION" in plan)

with mock.patch.object(model_router, "route", return_value=""):
    plan = _loop._draft_plan("anything")
check("planner unavailable -> explicit notice, no crash", "unavailable" in plan)

# ── Result ────────────────────────────────────────────────────────────────────
print("\n" + "=" * 50)
print(f"RESULT: {PASSED} passed, {FAILED} failed")
sys.exit(1 if FAILED else 0)
