"""
v3_safety_check.py — Pre/Post-Migration Syntax Validator
═════════════════════════════════════════════════════════
Scans every .py file in Meta_App_Factory and validates
syntax using py_compile. Run before AND after any V3
migration to catch damage early.

Usage:
    python v3_safety_check.py           # scan all
    python v3_safety_check.py --fix     # scan + show broken line patterns

Exit codes:
    0 = all files pass
    1 = syntax errors found
"""

import os
import sys
import py_compile
import re

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

FACTORY_DIR = os.path.dirname(os.path.abspath(__file__))

SKIP_DIRS = {"__pycache__", ".git", "node_modules", "pending_sync", ".venv", "venv"}


def scan_all(show_patterns: bool = False) -> list:
    """Compile-check every .py file. Returns list of failures."""
    failures = []
    checked = 0

    for root, dirs, files in os.walk(FACTORY_DIR):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            if not f.endswith(".py"):
                continue
            fpath = os.path.join(root, f)
            checked += 1
            try:
                py_compile.compile(fpath, doraise=True)
            except py_compile.PyCompileError as e:
                rel = os.path.relpath(fpath, FACTORY_DIR)
                entry = {"file": rel, "path": fpath, "error": str(e)}

                # Detect the known V3 split-line pattern
                if show_patterns:
                    entry["patterns"] = detect_split_lines(fpath)

                failures.append(entry)

    return failures, checked


def detect_split_lines(fpath: str) -> list:
    """Detect the known V3 migration broken-line patterns."""
    patterns_found = []
    try:
        with open(fpath, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        for i, line in enumerate(lines):
            stripped = line.rstrip()
            # Pattern: variable assignment ending with = on its own
            if re.match(r'^\s+\w+\s*=$', stripped):
                next_line = lines[i + 1].lstrip() if i + 1 < len(lines) else ""
                if next_line.startswith("requests.") or next_line.startswith("safe_post(") or next_line.startswith("healed_post("):
                    patterns_found.append({
                        "line": i + 1,
                        "content": stripped,
                        "next": next_line.rstrip(),
                        "type": "split_assignment",
                    })
            # Pattern: 'with' keyword ending the line
            if re.match(r'^\s+with$', stripped):
                next_line = lines[i + 1].lstrip() if i + 1 < len(lines) else ""
                if next_line.startswith("requests."):
                    patterns_found.append({
                        "line": i + 1,
                        "content": stripped,
                        "next": next_line.rstrip(),
                        "type": "split_with",
                    })
    except Exception:
        pass
    return patterns_found


def compile_check(fpath: str) -> bool:
    """Check if a single file compiles. Returns True if OK."""
    try:
        py_compile.compile(fpath, doraise=True)
        return True
    except py_compile.PyCompileError:
        return False


def main():
    show = "--fix" in sys.argv or "--patterns" in sys.argv

    print(f"\n{'='*60}")
    print(f"  V3 Safety Check — Syntax Validator")
    print(f"{'='*60}\n")

    failures, checked = scan_all(show_patterns=show)

    if not failures:
        print(f"  ✅ All {checked} files pass syntax check.\n")
        sys.exit(0)

    print(f"  ❌ {len(failures)} / {checked} files have syntax errors:\n")
    for f in failures:
        print(f"    🔴 {f['file']}")
        if show and f.get("patterns"):
            for p in f["patterns"]:
                print(f"       L{p['line']}: {p['type']} → {p['content']}")
                print(f"       L{p['line']+1}: {p['next']}")

    print(f"\n{'='*60}\n")
    sys.exit(1)


if __name__ == "__main__":
    main()
