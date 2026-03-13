"""
bootstrap_project.py — Venture Studio Project Bootstrapper
═══════════════════════════════════════════════════════════
Meta_App_Factory | Antigravity V3.0 | Inheritance Engine Phase 1

Creates new venture projects that inherit the V3 architecture:
- Unique project folder in projects/
- Symbolic links to .system_core skills
- Project-specific soul/ with brand_identity.json + market_intel.db
- V3 resilience DNA (healed_post, preflight, StateManager)

Usage:
    python bootstrap_project.py Project_Alpha
    python bootstrap_project.py "Fashion Venture" --sector fashion --no-test
"""

import os
import sys
import json
import shutil
import argparse
import subprocess
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

FACTORY_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECTS_DIR = os.path.join(FACTORY_DIR, "projects")
SYSTEM_CORE = os.path.join(FACTORY_DIR, ".system_core")
TEMPLATE = os.path.join(FACTORY_DIR, "child_app_template.py")

# Files from .system_core to symlink into each project
CORE_LINKS = [
    "pii_masker.py",
    "visual_engine.py",
    "market_crawler.py",
]

# Factory-level files every project needs access to
FACTORY_LINKS = [
    "auto_heal.py",
    "factory.py",
    "local_state_manager.py",
    "recovery_sync.py",
]

# Default brand identity template
DEFAULT_BRAND = {
    "version": "1.0",
    "company_name": "",
    "mission": "",
    "tagline": "",
    "sector": "general",
    "colors": {
        "primary": "#3b82f6",
        "secondary": "#8b5cf6",
        "accent": "#06b6d4",
        "background": "#0b0f1a",
        "text": "#e2e8f0",
    },
    "fonts": {
        "heading": "Inter",
        "body": "Inter",
        "mono": "JetBrains Mono",
    },
    "tone_of_voice": "Professional, innovative, confident",
    "visual_style": "Modern dark theme, glassmorphism, gradient accents",
    "logo_path": "",
    "created_at": "",
    "last_updated": "",
}


def safe_name(name: str) -> str:
    """Sanitize project name for filesystem."""
    return name.replace(" ", "_").replace("-", "_").strip(".")


def create_symlink(source, target):
    """Create symlink; copies on Windows if symlinks require elevation."""
    try:
        if os.path.exists(target):
            return "exists"
        os.symlink(source, target)
        return "linked"
    except OSError:
        # Windows: symlinks may require admin
        try:
            shutil.copy2(source, target)
            return "copied"
        except Exception as e:
            return f"error: {e}"


def bootstrap_project(project_name: str, sector: str = "general", run_test: bool = True):
    """
    Create a new Venture Studio project with full V3 inheritance.
    """
    name = safe_name(project_name)
    project_dir = os.path.join(PROJECTS_DIR, name)

    print(f"\n{'='*60}")
    print(f"  ⚡ Venture Studio — Project Bootstrapper")
    print(f"{'='*60}\n")

    # ── Step 1: Create Project Directory ──────────────────
    if os.path.exists(project_dir):
        print(f"  ⚠️  Project already exists: projects/{name}/")
        print(f"  Use a different name or remove the existing folder.")
        return False

    os.makedirs(project_dir, exist_ok=True)
    print(f"  📁 Created: projects/{name}/")

    # ── Step 2: Initialize Soul Directory ─────────────────
    soul_dir = os.path.join(project_dir, "soul")
    os.makedirs(soul_dir, exist_ok=True)

    # Brand Identity
    brand = dict(DEFAULT_BRAND)
    brand["company_name"] = project_name
    brand["sector"] = sector
    brand["created_at"] = datetime.now().isoformat()
    brand["last_updated"] = datetime.now().isoformat()

    brand_path = os.path.join(soul_dir, "brand_identity.json")
    with open(brand_path, "w", encoding="utf-8") as f:
        json.dump(brand, f, indent=2)
    print(f"  🧬 Soul initialized:")
    print(f"     └── soul/brand_identity.json")

    # Market Intel DB (empty)
    intel_path = os.path.join(soul_dir, "market_intel.db")
    with open(intel_path, "w", encoding="utf-8") as f:
        json.dump([], f)
    print(f"     └── soul/market_intel.db")

    # ── Step 3: Symlink Core Skills ───────────────────────
    core_dir = os.path.join(project_dir, "core")
    os.makedirs(core_dir, exist_ok=True)

    # Create __init__.py for core package
    with open(os.path.join(core_dir, "__init__.py"), "w", encoding="utf-8") as f:
        f.write(f'"""{name} — Inherited Core Skills"""\n')
        f.write("from .pii_masker import PIIMasker\n")
        f.write("from .visual_engine import VisualEngine\n")
        f.write("from .market_crawler import MarketCrawler\n")

    print(f"\n  🔗 Linking Core Skills:")
    for module in CORE_LINKS:
        source = os.path.join(SYSTEM_CORE, module)
        target = os.path.join(core_dir, module)
        if os.path.exists(source):
            status = create_symlink(source, target)
            icon = "✅" if status in ("linked", "copied", "exists") else "❌"
            print(f"     {icon} {module} → {status}")
        else:
            print(f"     ❌ {module} — source not found in .system_core/")

    # ── Step 4: Symlink Factory Infrastructure ────────────
    print(f"\n  🔗 Linking Factory Infrastructure:")
    for module in FACTORY_LINKS:
        source = os.path.join(FACTORY_DIR, module)
        target = os.path.join(project_dir, module)
        if os.path.exists(source):
            status = create_symlink(source, target)
            icon = "✅" if status in ("linked", "copied", "exists") else "❌"
            print(f"     {icon} {module} → {status}")
        else:
            print(f"     ⚠️  {module} — not found in factory root")

    # ── Step 5: Generate main.py ──────────────────────────
    main_py_path = os.path.join(project_dir, "main.py")
    main_content = _generate_main(name, sector)
    with open(main_py_path, "w", encoding="utf-8") as f:
        f.write(main_content)
    print(f"\n  📄 Generated: projects/{name}/main.py")

    # ── Step 6: .env symlink ──────────────────────────────
    env_source = os.path.join(FACTORY_DIR, ".env")
    env_target = os.path.join(project_dir, ".env")
    if os.path.exists(env_source):
        status = create_symlink(env_source, env_target)
        print(f"  🔑 .env → {status}")

    # ── Step 7: Preflight Validation ──────────────────────
    if run_test:
        print(f"\n  Running preflight validation...")
        try:
            result = subprocess.run(
                [sys.executable, main_py_path, "--preflight"],
                capture_output=True, text=True,
                encoding="utf-8", errors="replace",
                timeout=15, cwd=project_dir,
            )
            output = result.stdout.strip()
            if output:
                for line in output.split("\n")[:5]:
                    print(f"    {line}")
            if result.returncode == 0:
                print(f"\n  ✅ Preflight PASSED")
            else:
                print(f"\n  ⚠️  Preflight returned code {result.returncode}")
        except subprocess.TimeoutExpired:
            print(f"  ⚠️  Preflight timed out (15s)")
        except Exception as e:
            print(f"  ⚠️  Preflight error: {e}")

    # ── Summary ───────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"  ✅ Project '{name}' is BOOTSTRAPPED")
    print(f"\n  Structure:")
    print(f"     projects/{name}/")
    print(f"     ├── main.py            (V3 hardened entry point)")
    print(f"     ├── soul/")
    print(f"     │   ├── brand_identity.json")
    print(f"     │   └── market_intel.db")
    print(f"     ├── core/              (symlinked from .system_core)")
    print(f"     │   ├── pii_masker.py")
    print(f"     │   ├── visual_engine.py")
    print(f"     │   └── market_crawler.py")
    print(f"     └── [V3 infrastructure links]")
    print(f"\n  Next Steps:")
    print(f"     1. Edit soul/brand_identity.json with your brand")
    print(f"     2. Run: python projects/{name}/main.py")
    print(f"{'='*60}\n")

    return True


def _generate_main(name: str, sector: str) -> str:
    """Generate the project's main.py with V3 DNA + soul awareness."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    return f'''# Auto-generated by bootstrap_project.py on {timestamp}
"""
{name} — V3.0 Venture Studio Project
{'='*50}
Sector: {sector}
Architecture: Antigravity V3.0 Hardened
Soul: soul/brand_identity.json

Inherited Core Skills:
  - PIIMasker       (PII & secrets redaction)
  - VisualEngine    (Nano Banana 2 — document & image generation)
  - MarketCrawler   (Tavily + competitive intelligence)
"""

import os
import sys
import json
import argparse

# ── V3.0 Resilience ──────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FACTORY_DIR = os.path.normpath(os.path.join(SCRIPT_DIR, "..", ".."))
sys.path.insert(0, FACTORY_DIR)
sys.path.insert(0, SCRIPT_DIR)

try:
    from factory import safe_post
    from local_state_manager import StateManager
    sm = StateManager()
except ImportError:
    safe_post = None
    sm = None

try:
    from auto_heal import healed_post, diagnose
except ImportError:
    healed_post = None
    diagnose = None

# ── Core Skills (from .system_core via symlink) ──────
try:
    from core import PIIMasker, VisualEngine, MarketCrawler
except ImportError:
    PIIMasker = None
    VisualEngine = None
    MarketCrawler = None


def load_soul():
    """Load this project\'s brand identity."""
    soul_path = os.path.join(SCRIPT_DIR, "soul", "brand_identity.json")
    if os.path.exists(soul_path):
        with open(soul_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {{"company_name": "{name}", "sector": "{sector}"}}


def preflight():
    """V3 preflight check — validate infrastructure."""
    print(f"\\n{{\\'='*50}}")
    print(f"  ⚡ {{name}} — V3 Preflight")
    print(f"{{\\'='*50}}")

    soul = load_soul()
    print(f"  🧬 Soul: {{soul.get(\\'company_name\\', \\'Unknown\\')}}")
    print(f"  🏭 Sector: {{soul.get(\\'sector\\', \\'general\\')}}")

    checks = {{
        "factory.py": os.path.exists(os.path.join(SCRIPT_DIR, "factory.py")),
        "auto_heal.py": os.path.exists(os.path.join(SCRIPT_DIR, "auto_heal.py")),
        ".env": os.path.exists(os.path.join(SCRIPT_DIR, ".env")),
        "PIIMasker": PIIMasker is not None,
        "VisualEngine": VisualEngine is not None,
        "MarketCrawler": MarketCrawler is not None,
    }}

    print(f"\\n  Infrastructure:")
    all_ok = True
    for name_check, found in checks.items():
        icon = "✅" if found else "❌"
        print(f"    {{icon}} {{name_check}}")
        if not found:
            all_ok = False

    status = "🟢 READY" if all_ok else "🟡 PARTIAL"
    print(f"\\n  Status: {{status}}")
    print(f"{{\\'='*50}}\\n")
    return all_ok


def execute():
    """Main execution — implement your venture logic here."""
    soul = load_soul()
    print(f"  {name}: Loaded soul ({{soul.get(\\'company_name\\')}})")
    print(f"  Sector: {{soul.get(\\'sector\\')}}")
    print(f"  TODO: Implement venture logic in execute()")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="{name} — V3 Venture Project")
    parser.add_argument("--preflight", action="store_true", help="Run preflight check")
    args = parser.parse_args()

    if args.preflight:
        preflight()
    else:
        preflight()
        execute()
'''


# ── Entry Point ──────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Venture Studio Project Bootstrapper",
        epilog="Example: python bootstrap_project.py Project_Alpha --sector fintech"
    )
    parser.add_argument("project_name", help="Name for the new project")
    parser.add_argument("--sector", default="general", help="Business sector (e.g., fintech, fashion, healthtech)")
    parser.add_argument("--no-test", action="store_true", help="Skip preflight validation")
    args = parser.parse_args()

    bootstrap_project(args.project_name, sector=args.sector, run_test=not args.no_test)
