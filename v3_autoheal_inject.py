"""
v3_autoheal_inject.py — Inject Auto-Heal into all V3-migrated files
"""
import os, sys, re, py_compile
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

FACTORY_DIR = os.path.dirname(os.path.abspath(__file__))
SKIP_FILES = {
    "factory.py", "local_state_manager.py", "recovery_sync.py",
    "app_generator.py", "child_app_template.py", "swdr_heartbeat.py",
    "webhook_hardener.py", "cloud_surgery_audit.py", "env_updater.py",
    "v3_execute.py", "v3_retrofit.py", "v3_migration.py",
    "v3_autoheal_inject.py", "auto_heal.py", "__init__.py",
    "v3_safety_check.py",
}

IMPORT_LINE = "from auto_heal import healed_post, auto_heal, diagnose"
injected = 0
skipped = 0
already = 0
rolled_back = 0

for root, dirs, files in os.walk(FACTORY_DIR):
    dirs[:] = [d for d in dirs if d not in {"__pycache__", ".git", "node_modules", "pending_sync"}]
    for f in files:
        if not f.endswith(".py") or f in SKIP_FILES:
            continue
        fpath = os.path.join(root, f)
        try:
            with open(fpath, "r", encoding="utf-8", errors="replace") as fp:
                content = fp.read()
                original = content
        except:
            continue

        # Only process V3-migrated files
        if "V3 MIGRATION COMPLETE" not in content and "V3.0 Resilience Integration" not in content:
            skipped += 1
            continue

        if IMPORT_LINE in content:
            already += 1
            continue

        # Inject auto_heal import after the V3 resilience header
        marker = "# ── End V3 Integration"
        if marker in content:
            idx = content.index(marker)
            end_of_line = content.index("\n", idx) + 1
            content = content[:end_of_line] + f"\n{IMPORT_LINE}\n" + content[end_of_line:]
        else:
            # Fallback: add after V3 MIGRATION COMPLETE or at top
            if "from factory import safe_post" in content:
                idx = content.index("from factory import safe_post")
                end_of_line = content.index("\n", idx) + 1
                content = content[:end_of_line] + f"{IMPORT_LINE}\n" + content[end_of_line:]
            else:
                content = f"{IMPORT_LINE}\n\n" + content

        # Replace safe_post() calls with healed_post() calls
        # But only the direct calls, not the import line
        lines = content.split("\n")
        new_lines = []
        for line in lines:
            stripped = line.lstrip()
            # Skip import lines and comments
            if stripped.startswith(("from ", "import ", "#")):
                new_lines.append(line)
                continue
            # Replace safe_post( with healed_post( in code
            if "safe_post(" in line and "import" not in line and "def " not in line:
                line = line.replace("safe_post(", "healed_post(")
            new_lines.append(line)
        content = "\n".join(new_lines)

        # Add AUTO_HEAL stamp
        if "# V3 AUTO-HEAL ACTIVE" not in content:
            content = content.rstrip() + "\n# V3 AUTO-HEAL ACTIVE\n"

        with open(fpath, "w", encoding="utf-8") as fp:
            fp.write(content)

        # SAFETY: Validate syntax — rollback if broken
        try:
            py_compile.compile(fpath, doraise=True)
        except py_compile.PyCompileError:
            with open(fpath, "w", encoding="utf-8") as fp:
                fp.write(original)
            rel = os.path.relpath(fpath, FACTORY_DIR)
            print(f"  🔴 ROLLED BACK: {rel} (syntax error after injection)")
            rolled_back += 1
            continue

        rel = os.path.relpath(fpath, FACTORY_DIR)
        print(f"  ✅ {rel}")
        injected += 1

print(f"\n  Injected: {injected} | Already done: {already} | Skipped: {skipped} | Rolled back: {rolled_back}")
