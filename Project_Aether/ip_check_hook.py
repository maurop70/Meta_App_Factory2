"""
ip_check_hook.py — Design-Phase IP Evaluation Trigger
======================================================
Project Aether | Antigravity-AI

Dev Agents call this during the Design_Phase of any build.
If a feature is "Patentable" (confidence > 0.7), the agent
should prioritize its development.

Usage:
    from ip_check_hook import check_ip_at_design_phase

    result = check_ip_at_design_phase("MyApp", "/path/to/app")
    if result["patentable"]:
        print(f"PRIORITY BOOST: {result['confidence']:.0%} confidence")
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


import os
import sys
import json
from typing import Optional, Dict

# ── Resolve paths ──────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FACTORY_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
SKILLS_LIB = os.path.join(FACTORY_ROOT, "_ANTIGRAVITY_SKILLS_LIBRARY")
REGISTRY_PATH = os.path.join(FACTORY_ROOT, "registry.json")
LEDGER_PATH = os.path.join(FACTORY_ROOT, "LEDGER.md")

if SKILLS_LIB not in sys.path:
    sys.path.insert(0, SKILLS_LIB)


# ══════════════════════════════════════════════════
#  DESIGN-PHASE IP CHECK
# ══════════════════════════════════════════════════

# ── Known project IDs (mirrors the Apps Script constants) ──
PROJECT_ID_AETHER = "AETHER-2026-9B2D4C"
PROJECT_ID_DAI    = "DAI-2026-A1F3E7"


def check_ip_at_design_phase(
    app_name: str,
    app_dir: str,
    registry_path: Optional[str] = None,
    threshold: float = 0.7,
    project_id: Optional[str] = None,
) -> Dict:
    """
    Background IP evaluation triggered during Design_Phase.

    Dev Agents call this before committing to a build plan.
    If the feature scores above threshold, the agent should
    prioritize its development and flag it for IP protection.

    Args:
        app_name: Name of the application being designed
        app_dir: Absolute path to the app's source directory
        registry_path: Path to factory registry.json (auto-detected)
        threshold: Confidence threshold for patentability (default 0.7)
        project_id: Caller's PROJECT_ID — used to scope LEDGER entries.
                    Use PROJECT_ID_DAI or PROJECT_ID_AETHER constants.
                    Defaults to PROJECT_ID_AETHER if not specified.

    Returns:
        dict with keys:
            - patentable (bool): Whether the feature meets patent threshold
            - trademark_ready (bool): Whether the name meets trademark threshold
            - confidence (float): Normalized confidence score (0.0-1.0)
            - priority_boost (bool): True if agent should prioritize this feature
            - patent_score (int): Raw patent score (0-100)
            - trademark_score (int): Raw trademark score (0-100)
            - recommendation (str): Brief recommendation text
            - ip_shield_available (bool): Whether Shield workflow can be triggered
            - project_id (str): Project identity this evaluation belongs to
    """
    reg = registry_path or REGISTRY_PATH
    caller_project_id = project_id or PROJECT_ID_AETHER

    try:
        from ip_strategist import evaluate
        report = evaluate(app_name, app_dir, reg)

        confidence = report.get("confidence_score", 0.0)
        patent_score = report.get("patent_score", 0)
        trademark_score = report.get("trademark_score", 0)

        patentable = confidence > threshold
        trademark_ready = trademark_score >= 70
        priority_boost = patentable  # Prioritize if patentable

        # Log to LEDGER if noteworthy, tagged with the caller's project_id
        if patentable:
            _log_ip_discovery(
                app_name, confidence, patent_score, trademark_score,
                project_id=caller_project_id,
            )

        return {
            "patentable": patentable,
            "trademark_ready": trademark_ready,
            "confidence": round(confidence, 3),
            "priority_boost": priority_boost,
            "patent_score": patent_score,
            "trademark_score": trademark_score,
            "recommendation": report.get("recommendation", ""),
            "ip_shield_available": confidence > threshold,
            "project_id": caller_project_id,
            "status": "evaluated",
        }

    except ImportError:
        return {
            "patentable": False,
            "trademark_ready": False,
            "confidence": 0.0,
            "priority_boost": False,
            "patent_score": 0,
            "trademark_score": 0,
            "recommendation": "IP Strategist module not available. Install ip_strategist skill.",
            "ip_shield_available": False,
            "project_id": caller_project_id,
            "status": "unavailable",
        }

    except Exception as e:
        return {
            "patentable": False,
            "trademark_ready": False,
            "confidence": 0.0,
            "priority_boost": False,
            "patent_score": 0,
            "trademark_score": 0,
            "recommendation": f"IP check failed: {str(e)[:200]}",
            "ip_shield_available": False,
            "project_id": caller_project_id,
            "status": "error",
        }


# ══════════════════════════════════════════════════
#  BATCH CHECK (multiple apps)
# ══════════════════════════════════════════════════

def batch_ip_check(
    app_dirs: Dict[str, str],
    threshold: float = 0.7,
    project_id: Optional[str] = None,
) -> Dict:
    """
    Run IP checks on multiple apps simultaneously.

    Args:
        app_dirs: Dict of {app_name: app_dir_path}
        threshold: Confidence threshold
        project_id: Project identity for LEDGER scoping (default: AETHER)

    Returns:
        Dict of {app_name: ip_check_result}
    """
    results = {}
    caller_id = project_id or PROJECT_ID_AETHER
    for app_name, app_dir in app_dirs.items():
        results[app_name] = check_ip_at_design_phase(
            app_name, app_dir, threshold=threshold, project_id=caller_id
        )

    patentable_count = sum(1 for r in results.values() if r.get("patentable"))
    return {
        "results": results,
        "project_id": caller_id,
        "summary": {
            "total_checked": len(results),
            "patentable": patentable_count,
            "priority_boosted": patentable_count,
        },
    }


# ── Internal Logger ────────────────────────────────

def _log_ip_discovery(
    app_name: str,
    confidence: float,
    patent: int,
    trademark: int,
    project_id: Optional[str] = None,
):
    """Log noteworthy IP discovery to LEDGER.md, tagged with project_id."""
    pid = project_id or PROJECT_ID_AETHER
    try:
        from ip_strategist import append_ledger
        append_ledger(
            action="DESIGN_PHASE_IP_DISCOVERY",
            app_name=app_name,
            extra=(
                f"CONFIDENCE: {confidence:.3f} | PATENT: {patent}/100 | "
                f"TRADEMARK: {trademark}/100 | PROJECT: {pid}"
            ),
            ledger_path=LEDGER_PATH,
        )
    except (ImportError, Exception):
        pass  # Non-critical — don't block the design phase


# ══════════════════════════════════════════════════
#  STANDALONE TEST
# ══════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="IP Check Hook — Design Phase")
    parser.add_argument("--app", type=str, default="Resonance", help="App name to check")
    parser.add_argument("--dir", type=str, default=None, help="App directory path")
    args = parser.parse_args()

    app_dir = args.dir or os.path.join(FACTORY_ROOT, args.app)

    print(f"\n🛡️ IP Check: Design Phase — {args.app}")
    print(f"   Directory: {app_dir}")
    print("=" * 50)

    result = check_ip_at_design_phase(args.app, app_dir)
    print(json.dumps(result, indent=2))

    if result["priority_boost"]:
        print(f"\n⚡ PRIORITY BOOST: This feature should be prioritized for development!")
    else:
        print(f"\n📋 Standard priority. Confidence: {result['confidence']:.1%}")
# V3 AUTO-HEAL ACTIVE
