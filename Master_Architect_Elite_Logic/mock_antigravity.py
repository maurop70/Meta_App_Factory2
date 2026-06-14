import sys
import os
import json
import time

# ─────────────────────────────────────────────────────────────────────────────
# LOCAL AY2 ACTUATOR
#
# Spawned by ipc_bridge.start_ipc_bridge() as the fallback executor whenever the
# global `antigravity` CLI is absent (which is the normal case in this workspace).
# Historically this was a no-op "mock" that printed success and wrote nothing — so
# autonomous builds spooled and archived but never produced a file on disk. It now
# genuinely applies the blueprint by writing each ast_mutation's full file content,
# strictly sandboxed under generated_builds/<app_name>/ so a build can never touch
# live MAF source.
#
# Blueprint envelope (spooled by server.py):
#   { "blueprint_data": "<json string>", "Strategic_Pause": bool,
#     "Strategic_Fail": bool, "timestamp": int }
# where blueprint_data parses to:
#   { "app_name": "...", "summary": "...",
#     "ast_mutations": [ { "target_file": "<rel path>", "code_payload": "<full content>" } ] }
# ─────────────────────────────────────────────────────────────────────────────

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SANDBOX_ROOT = os.path.join(_SCRIPT_DIR, "generated_builds")


def _sanitize_app_name(name: str) -> str:
    safe = "".join(c if (c.isalnum() or c in "-_") else "-" for c in (name or "").strip())
    safe = safe.strip("-_")
    return safe or "app"


def _resolve_within(root: str, relative: str) -> str:
    """Resolve `relative` under `root`, refusing absolute paths and traversal."""
    if not relative or not isinstance(relative, str):
        raise RuntimeError("Mutation missing 'target_file'.")
    rel = relative.replace("\\", "/").lstrip("/")
    if os.path.isabs(relative) or (len(relative) > 1 and relative[1] == ":"):
        raise RuntimeError(f"SECURITY: absolute target_file rejected: {relative!r}")
    root_abs = os.path.abspath(root)
    dest_abs = os.path.abspath(os.path.join(root_abs, rel))
    if dest_abs != root_abs and not dest_abs.startswith(root_abs + os.sep):
        raise RuntimeError(f"SECURITY: path traversal rejected: {relative!r}")
    return dest_abs


def main():
    print("[AY2 Actuator] Actuating Native IPC Bridge...")
    time.sleep(0.5)

    # Parse arguments
    args = sys.argv[1:]
    blueprint_path = None
    for i, arg in enumerate(args):
        if arg == "--execute-blueprint" and i + 1 < len(args):
            blueprint_path = args[i + 1]
            break

    if not blueprint_path or not os.path.exists(blueprint_path):
        print(f"[AY2 Actuator ERROR] Target blueprint path not found: {blueprint_path}", file=sys.stderr)
        sys.exit(1)

    try:
        with open(blueprint_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"[AY2 Actuator ERROR] Failed to parse blueprint: {e}", file=sys.stderr)
        sys.exit(1)

    # Rule 1: crash-test hook (preserved for the failure-injection E2E spec).
    if data.get("Strategic_Fail") is True or "fail" in os.path.basename(blueprint_path).lower():
        print("[AY2 Actuator ERROR] Fatal physical exception detected in AY2 thread!", file=sys.stderr)
        print("Traceback (most recent call last):", file=sys.stderr)
        print("  File \"cpo_verify.py\", line 128, in execute_blueprint", file=sys.stderr)
        print("    db_cursor.execute(\"INSERT INTO system_state (key, val) VALUES (?, ?)\")", file=sys.stderr)
        print("sqlite3.IntegrityError: UNIQUE constraint failed: system_state.key", file=sys.stderr)
        sys.exit(1)

    # Unwrap the inner blueprint (may be a JSON string or already a dict).
    inner = data.get("blueprint_data", data)
    if isinstance(inner, str):
        try:
            inner = json.loads(inner)
        except Exception as e:
            print(f"[AY2 Actuator ERROR] blueprint_data is not valid JSON: {e}", file=sys.stderr)
            sys.exit(1)
    if not isinstance(inner, dict):
        print("[AY2 Actuator ERROR] blueprint_data did not resolve to an object.", file=sys.stderr)
        sys.exit(1)

    mutations = inner.get("ast_mutations") or []
    if not isinstance(mutations, list) or not mutations:
        print("[AY2 Actuator ERROR] Blueprint contains no ast_mutations to apply.", file=sys.stderr)
        sys.exit(1)

    app_name = _sanitize_app_name(inner.get("app_name", "app"))
    app_root = os.path.join(SANDBOX_ROOT, app_name)

    print(f"[AY2 Actuator] Applying {len(mutations)} mutation(s) for app '{app_name}'...")
    written = []
    try:
        for idx, mutation in enumerate(mutations):
            if not isinstance(mutation, dict):
                raise RuntimeError(f"Mutation #{idx} is not an object.")
            target_file = mutation.get("target_file")
            payload = mutation.get("code_payload")
            if payload is None:
                raise RuntimeError(f"Mutation for {target_file!r} missing 'code_payload'.")
            dest_abs = _resolve_within(app_root, target_file)
            os.makedirs(os.path.dirname(dest_abs) or app_root, exist_ok=True)
            with open(dest_abs, "w", encoding="utf-8") as out:
                out.write(payload if isinstance(payload, str) else json.dumps(payload, indent=2))
            rel_display = os.path.relpath(dest_abs, SANDBOX_ROOT)
            written.append(rel_display)
            print(f"[AY2 Actuator] Wrote {rel_display}")
    except Exception as e:
        print(f"[AY2 Actuator ERROR] Mutation apply failed: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"[AY2 Actuator] Physical Software Contract actuated successfully! "
          f"{len(written)} file(s) under generated_builds/{app_name}/")
    sys.exit(0)


if __name__ == "__main__":
    main()
