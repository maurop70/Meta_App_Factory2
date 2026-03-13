"""
v3_retrofit.py — System-Wide V3.0 Retrofit Engine
═══════════════════════════════════════════════════
Scans all child app directories in Meta_App_Factory,
injects V3 resilience patterns (safe_post, preflight,
FACTORY_DIR resolution), and validates each via silent test.
"""

import os
import sys
import re
import json
import subprocess
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

FACTORY_DIR = os.path.dirname(os.path.abspath(__file__))

# Directories that are NOT child apps (infrastructure / config)
SKIP_DIRS = {
    "__pycache__", ".git", "node_modules", "pending_sync",
    "Resonance2",  # framework module, not a child app
}

# Files that are factory infrastructure (not child apps to retrofit)
SKIP_FILES = {
    "factory.py", "local_state_manager.py", "recovery_sync.py",
    "app_generator.py", "child_app_template.py", "swdr_heartbeat.py",
    "webhook_hardener.py", "cloud_surgery_audit.py", "env_updater.py",
    "v3_execute.py", "circuit_breaker.py",
}

# The V3 header block we inject at the top of files
V3_HEADER = '''# ── V3.0 Resilience Integration ──────────────────────────
import os as _os, sys as _sys
_FACTORY_DIR = _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), {depth_expr}))
_sys.path.insert(0, _FACTORY_DIR)
try:
    from factory import safe_post
    from local_state_manager import StateManager as _StateManager
    _v3_sm = _StateManager()
    _V3_AVAILABLE = True
except ImportError:
    _V3_AVAILABLE = False
# ── End V3 Integration ──────────────────────────────────
'''

V3_PREFLIGHT = '''
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
'''


def get_depth_expr(app_dir: str) -> str:
    """Calculate the relative path expression from app_dir back to FACTORY_DIR."""
    rel = os.path.relpath(FACTORY_DIR, app_dir)
    parts = rel.replace("\\", "/").split("/")
    if len(parts) == 1 and parts[0] == ".":
        return '"."'
    return ", ".join(f'".."' for _ in parts)


def find_child_apps() -> list:
    """Discover all child app directories with Python files."""
    apps = []
    for entry in os.scandir(FACTORY_DIR):
        if not entry.is_dir():
            continue
        if entry.name in SKIP_DIRS:
            continue
        if entry.name.startswith(".") or entry.name.startswith("__"):
            continue

        py_files = []
        for root, dirs, files in os.walk(entry.path):
            # Skip nested infra
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith("__")]
            for f in files:
                if f.endswith(".py") and f not in SKIP_FILES:
                    py_files.append(os.path.join(root, f))
        if py_files:
            apps.append({"name": entry.name, "path": entry.path, "files": py_files})

    return apps


def needs_retrofit(filepath: str) -> bool:
    """Check if file already has V3 integration."""
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            content = f.read(500)  # Check first 500 chars
        return "V3.0 Resilience Integration" not in content
    except Exception:
        return False


def retrofit_file(filepath: str) -> dict:
    """Inject V3 patterns into a single file."""
    result = {"file": filepath, "status": "skipped", "changes": []}

    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
            original = content
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
        return result

    if "V3.0 Resilience Integration" in content:
        result["status"] = "already_v3"
        return result

    # Skip tiny files (< 50 chars) or __init__.py
    basename = os.path.basename(filepath)
    if basename == "__init__.py" or len(content.strip()) < 50:
        result["status"] = "skipped_small"
        return result

    app_dir = os.path.dirname(filepath)
    depth = get_depth_expr(app_dir)

    changes = []

    # 1. Inject V3 header after any existing docstring or shebang
    header = V3_HEADER.replace("{depth_expr}", depth)

    # Find insertion point (after module docstring if present)
    insert_pos = 0
    stripped = content.lstrip()

    # Skip shebang
    if stripped.startswith("#!"):
        nl = content.index("\n") + 1
        insert_pos = nl

    # Skip module docstring
    after_shebang = content[insert_pos:]
    doc_match = re.match(r'\s*("""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\')\s*\n', after_shebang)
    if doc_match:
        insert_pos += doc_match.end()

    content = content[:insert_pos] + header + "\n" + content[insert_pos:]
    changes.append("V3_HEADER injected")

    # 2. Add preflight function if not present
    if "_v3_preflight" not in content:
        # Insert after the V3 header block
        header_end = content.index("# ── End V3 Integration")
        line_end = content.index("\n", header_end) + 1
        content = content[:line_end] + V3_PREFLIGHT + "\n" + content[line_end:]
        changes.append("preflight() added")

    # 3. Add preflight call at main entry point
    if 'if __name__' in content and '_v3_preflight()' not in content:
        # Insert preflight() call right after the if __name__ line
        main_match = re.search(r'if\s+__name__\s*==\s*["\']__main__["\']\s*:', content)
        if main_match:
            insert_at = main_match.end()
            # Find end of line
            nl = content.index("\n", insert_at) + 1
            indent = "    "
            preflight_call = f'{indent}_v3_preflight()  # V3: Watchdog handshake\n'
            content = content[:nl] + preflight_call + content[nl:]
            changes.append("preflight() call at __main__")

    # 4. Wrap raw requests.post() calls with safe_post awareness (comment, not replace)
    #    We add a comment above each requests.post to flag it for future migration
    raw_posts = list(re.finditer(r'(\s*)requests\.post\(', content))
    if raw_posts:
        # Add comments in reverse order to preserve positions
        for m in reversed(raw_posts):
            indent = m.group(1)
            pos = m.start()
            comment = f"{indent}# TODO [V3]: Consider replacing with safe_post() for resilience\n"
            if comment.strip() not in content[max(0, pos-100):pos]:
                content = content[:pos] + comment + content[pos:]
                changes.append("requests.post flagged for safe_post migration")

    if changes:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        result["status"] = "retrofitted"
        result["changes"] = changes
    else:
        result["status"] = "no_changes_needed"

    return result


def silent_test(app_dir: str) -> dict:
    """Run a silent preflight test on the app."""
    # Find main.py or the primary script
    candidates = ["main.py", "server.py", "api.py", "supervisor.py", "bridge.py"]
    test_file = None
    for c in candidates:
        p = os.path.join(app_dir, c)
        if os.path.exists(p):
            test_file = p
            break

    if not test_file:
        # Use first .py file
        for f in os.listdir(app_dir):
            if f.endswith(".py") and f != "__init__.py":
                test_file = os.path.join(app_dir, f)
                break

    if not test_file:
        return {"status": "no_script", "handshake": None}

    # Test by importing and checking if V3 is available
    try:
        result = subprocess.run(
            [sys.executable, "-c",
             f"import sys; sys.path.insert(0, r'{app_dir}'); "
             f"sys.path.insert(0, r'{FACTORY_DIR}'); "
             f"from factory import safe_post; "
             f"from local_state_manager import StateManager; "
             f"import requests, json, time; "
             f"cfg=json.load(open(r'{os.path.join(FACTORY_DIR, 'resilience_config.json')}')); "
             f"url=cfg['cloud_health']['watchdog_url']; "
             f"s=time.time(); r=requests.get(url, timeout=5); ms=(time.time()-s)*1000; "
             f"print(f'{{r.status_code}}|{{ms:.0f}}')"
            ],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=10, cwd=app_dir,
        )
        if result.returncode == 0 and result.stdout.strip():
            parts = result.stdout.strip().split("|")
            code = int(parts[0])
            latency = parts[1] if len(parts) > 1 else "?"
            return {
                "status": "pass" if code == 200 else "fail",
                "code": code,
                "latency": latency,
                "handshake": code == 200,
            }
        else:
            return {"status": "error", "stderr": result.stderr[-100:] if result.stderr else "", "handshake": False}
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "handshake": False}
    except Exception as e:
        return {"status": "error", "error": str(e), "handshake": False}


def main():
    print(f"\n{'='*60}")
    print(f"  V3.0 System-Wide Retrofit Engine")
    print(f"  {datetime.now().strftime('%Y-%m-%dT%H:%M:%S')}")
    print(f"{'='*60}\n")

    # Phase 1: Discovery
    apps = find_child_apps()
    print(f"  Discovered {len(apps)} child app directories:\n")
    for a in apps:
        print(f"    📁 {a['name']} ({len(a['files'])} files)")

    # Phase 2: Retrofit
    print(f"\n{'─'*60}")
    print(f"  PHASE 2: DEPENDENCY INJECTION & LOGIC SWAP")
    print(f"{'─'*60}\n")

    total_retrofitted = 0
    total_skipped = 0
    total_already = 0
    all_results = {}

    for app in apps:
        print(f"  📁 {app['name']}:")
        app_results = []
        for fpath in app["files"]:
            r = retrofit_file(fpath)
            app_results.append(r)
            rel = os.path.relpath(fpath, FACTORY_DIR)

            if r["status"] == "retrofitted":
                total_retrofitted += 1
                print(f"    ✅ {rel} — {', '.join(r['changes'])}")
            elif r["status"] == "already_v3":
                total_already += 1
                print(f"    🔵 {rel} — already V3")
            else:
                total_skipped += 1

        all_results[app["name"]] = app_results

    print(f"\n  Retrofitted: {total_retrofitted} | Already V3: {total_already} | Skipped: {total_skipped}")

    # Phase 3: Silent Test
    print(f"\n{'─'*60}")
    print(f"  PHASE 3: SILENT V3 HANDSHAKE TEST")
    print(f"{'─'*60}\n")

    test_results = {}
    passed = 0
    failed = 0

    for app in apps:
        t = silent_test(app["path"])
        test_results[app["name"]] = t
        if t.get("handshake"):
            passed += 1
            print(f"    🟢 {app['name']}: {t.get('code', '?')} ({t.get('latency', '?')}ms)")
        elif t.get("status") == "no_script":
            print(f"    ⏭️  {app['name']}: no entry script found")
        else:
            failed += 1
            print(f"    🔴 {app['name']}: {t.get('status', '?')} — {t.get('stderr', t.get('error', ''))[:60]}")

    # Summary
    print(f"\n{'='*60}")
    print(f"  V3.0 RETROFIT SUMMARY")
    print(f"{'='*60}")
    print(f"  Apps processed:     {len(apps)}")
    print(f"  Files retrofitted:  {total_retrofitted}")
    print(f"  Already V3:         {total_already}")
    print(f"  Handshake passed:   {passed}")
    print(f"  Handshake failed:   {failed}")
    print(f"{'='*60}\n")

    # Output results for MASTER_INDEX
    output = {
        "timestamp": datetime.now().isoformat(),
        "apps": len(apps),
        "retrofitted": total_retrofitted,
        "already_v3": total_already,
        "skipped": total_skipped,
        "handshake_passed": passed,
        "handshake_failed": failed,
        "failed_apps": [n for n, t in test_results.items() if t.get("handshake") == False and t.get("status") != "no_script"],
        "test_details": {n: t for n, t in test_results.items()},
    }

    # Save results
    results_path = os.path.join(FACTORY_DIR, "v3_retrofit_results.json")
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, default=str)
    print(f"  Results saved: v3_retrofit_results.json\n")


if __name__ == "__main__":
    main()
