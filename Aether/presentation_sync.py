"""
presentation_sync.py — Auto-Update Presentations on Feature Changes
=====================================================================
Meta App Factory | Aether | Antigravity-AI

Introspects the codebase (file counts, agents, apps, features) and
patches the HTML presentations in Presentations/ with current data.

Triggered:
  - After Factory builds (api.py post-build hook)
  - After Phantom QA PASS (post-gate)
  - Manually: python presentation_sync.py [--dry-run]

Patches:
  - Cover stat badges (file counts, agent counts, version)
  - Footer timestamps and version badges
  - Date badges in cover headers

Usage:
  python presentation_sync.py               # Sync all presentations
  python presentation_sync.py --dry-run     # Preview changes without writing
  python presentation_sync.py --project Resonance  # Sync one project only
"""

import os
import sys
import re
import json
import glob
import logging
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
FACTORY_DIR = SCRIPT_DIR.parent
WORKSPACE_DIR = FACTORY_DIR.parent  # Antigravity-AI Agents
PRESENTATIONS_DIR = WORKSPACE_DIR / "Presentations"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [PresentationSync] %(message)s")
logger = logging.getLogger("PresentationSync")


# ═══════════════════════════════════════════════════════════
#  CODEBASE SCANNER
# ═══════════════════════════════════════════════════════════

def scan_codebase() -> dict:
    """Introspect the Meta_App_Factory codebase for live stats."""
    stats = {
        "python_files": 0,
        "live_apps": 0,
        "app_list": [],
        "agents": 0,
        "agent_list": [],
        "architecture_version": "V3.2",
        "month_year": datetime.now().strftime("%B %Y"),
        "date_full": datetime.now().strftime("%B %d, %Y"),
        "date_iso": datetime.now().strftime("%Y-%m-%d"),
        "scan_timestamp": datetime.now().isoformat(),
    }

    # Count Python files
    py_files = list(FACTORY_DIR.rglob("*.py"))
    py_files = [f for f in py_files if "node_modules" not in str(f)
                and "__pycache__" not in str(f)
                and ".git" not in str(f)]
    stats["python_files"] = len(py_files)

    # Count live apps from registry.json
    registry_path = FACTORY_DIR / "registry.json"
    if registry_path.exists():
        try:
            with open(registry_path, "r", encoding="utf-8") as f:
                registry = json.load(f)
            if isinstance(registry, dict):
                apps = registry.get("apps", registry)
                if isinstance(apps, dict):
                    stats["live_apps"] = len(apps)
                    stats["app_list"] = list(apps.keys())
                elif isinstance(apps, list):
                    stats["live_apps"] = len(apps)
                    stats["app_list"] = [a.get("name", a) if isinstance(a, dict) else str(a) for a in apps]
        except Exception as e:
            logger.warning(f"Could not read registry.json: {e}")

    # Count agents from aether_runtime WEBHOOK_MAP
    runtime_path = FACTORY_DIR / "Project_Aether" / "aether_runtime.py"
    if runtime_path.exists():
        try:
            content = runtime_path.read_text(encoding="utf-8")
            webhook_matches = re.findall(r'"(\w[\w\s]*?)":\s*"https?://', content)
            if webhook_matches:
                stats["agents"] = len(webhook_matches)
                stats["agent_list"] = webhook_matches
        except Exception:
            pass

    # Fallback: count C-Suite agent configs
    if stats["agents"] == 0:
        csuite_dir = FACTORY_DIR / "Project_Aether" / "C-Suite_Agents"
        if csuite_dir.is_dir():
            configs = list(csuite_dir.glob("*.json"))
            stats["agents"] = max(len(configs), stats["agents"])

    # Also include Phantom QA as an agent
    phantom = FACTORY_DIR / "Project_Aether" / "C-Suite_Active_Logic" / "Phantom_QA" / "phantom_gate.py"
    if phantom.exists() and "Phantom" not in str(stats["agent_list"]):
        stats["agents"] += 1
        stats["agent_list"].append("Phantom QA")

    # Per-project endpoint counts
    stats["project_stats"] = {}
    for project in ["Resonance", "Sentinel_Bridge", "Alpha_V2_Genesis"]:
        proj_dir = FACTORY_DIR / project
        if proj_dir.is_dir():
            server_files = list(proj_dir.glob("server*.py")) + list(proj_dir.glob("*_server.py"))
            endpoint_count = 0
            for sf in server_files:
                try:
                    code = sf.read_text(encoding="utf-8")
                    endpoint_count += len(re.findall(r'@app\.(get|post|put|delete|patch)\(', code))
                except Exception:
                    pass
            py_count = len([f for f in proj_dir.rglob("*.py")
                          if "__pycache__" not in str(f) and "node_modules" not in str(f)])
            stats["project_stats"][project] = {
                "endpoints": endpoint_count,
                "python_files": py_count,
            }

    logger.info(f"Scan complete: {stats['python_files']} .py files, "
                f"{stats['live_apps']} apps, {stats['agents']} agents")

    return stats


# ═══════════════════════════════════════════════════════════
#  HTML PATCHER
# ═══════════════════════════════════════════════════════════

def _patch_cover_stat(html: str, label: str, new_value: str) -> str:
    """
    Patch a cover-stat value by matching its label.
    Pattern: <div class="val">X</div><div class="lbl">Label</div>
    """
    # Match the val div that is followed (possibly with whitespace) by a lbl div containing the label
    pattern = (
        r'(<div\s+class="val">)'       # Group 1: opening val tag
        r'[^<]*'                         # Old value text
        r'(</div>\s*<div\s+class="lbl">)' # Group 2: closing val + opening lbl
        + re.escape(label) +             # The exact label text
        r'(</div>)'                      # Group 3: closing lbl
    )
    replacement = rf'\g<1>{new_value}\g<2>{label}\g<3>'
    new_html, count = re.subn(pattern, replacement, html, flags=re.IGNORECASE)
    if count > 0:
        logger.info(f"  📊 Updated cover stat '{label}': → {new_value}")
    return new_html


def _patch_cover_badge_date(html: str, new_date: str) -> str:
    """Patch the date in cover-badge elements (e.g., 'MARCH 2026')."""
    # Match month patterns in cover-badge
    months = "|".join(["JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE",
                       "JULY", "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER"])
    pattern = rf'(<div\s+class="cover-badge">[^<]*?)({months})\s+\d{{4}}'
    new_html, count = re.subn(pattern, rf'\1{new_date}', html, flags=re.IGNORECASE)
    if count > 0:
        logger.info(f"  📅 Updated cover badge date → {new_date}")
    return new_html


def _patch_footer_date(html: str, new_date: str) -> str:
    """Patch date patterns inside cover-footer or manual-footer divs."""
    months = "|".join(["January", "February", "March", "April", "May", "June",
                       "July", "August", "September", "October", "November", "December"])
    # Pattern: Month YYYY (e.g., "March 2026")
    pattern = rf'({months})\s+\d{{4}}'
    # Only patch inside footer divs
    footer_pattern = r'(<div\s+class="(?:cover-footer|manual-footer)"[^>]*>)(.*?)(</div>)'

    def replace_footer(match):
        pre = match.group(1)
        content = match.group(2)
        post = match.group(3)
        updated = re.sub(pattern, new_date, content, flags=re.IGNORECASE)
        return pre + updated + post

    new_html, count = re.subn(footer_pattern, replace_footer, html, flags=re.DOTALL)
    if count > 0:
        logger.info(f"  📅 Updated footer date → {new_date}")
    return new_html


def _patch_meta_date(html: str, new_date: str) -> str:
    """Patch date in metadata paragraphs (e.g., '<strong>Date:</strong> March 23, 2026')."""
    months = "|".join(["January", "February", "March", "April", "May", "June",
                       "July", "August", "September", "October", "November", "December"])
    pattern = rf'(<strong>Date:</strong>\s*)({months})\s+\d{{1,2}},?\s*\d{{4}}'
    new_html, count = re.subn(pattern, rf'\1{new_date}', html, flags=re.IGNORECASE)
    if count > 0:
        logger.info(f"  📅 Updated meta date → {new_date}")
    return new_html


def _patch_footer_stats(html: str, stats: dict) -> str:
    """Patch inline stats in footer (e.g., 'Files: 258 | Apps: 6 | Agents: 19')."""
    # Files count
    html = re.sub(r'Files:\s*\d+', f"Files: {stats['python_files']}", html)
    # Apps count
    html = re.sub(r'Apps:\s*\d+', f"Apps: {stats['live_apps']}", html)
    # Agents count
    html = re.sub(r'Agents:\s*\d+', f"Agents: {stats['agents']}", html)
    return html


# ═══════════════════════════════════════════════════════════
#  PROJECT-SPECIFIC SYNC
# ═══════════════════════════════════════════════════════════

def sync_factory_html(html: str, stats: dict) -> str:
    """Sync Meta_App_Factory presentations."""
    html = _patch_cover_stat(html, "Python Files", str(stats["python_files"]))
    html = _patch_cover_stat(html, "Live Apps", str(stats["live_apps"]))
    html = _patch_cover_stat(html, "AI Agents", str(stats["agents"]))
    html = _patch_cover_stat(html, "Architecture", stats["architecture_version"])
    html = _patch_cover_badge_date(html, stats["month_year"].upper())
    html = _patch_footer_date(html, stats["month_year"])
    html = _patch_footer_stats(html, stats)
    return html


def sync_resonance_html(html: str, stats: dict) -> str:
    """Sync Resonance presentations."""
    proj = stats.get("project_stats", {}).get("Resonance", {})
    if proj.get("endpoints"):
        html = _patch_cover_stat(html, "API Endpoints", str(proj["endpoints"]))
    html = _patch_cover_stat(html, "Architecture", stats["architecture_version"])
    html = _patch_cover_badge_date(html, stats["month_year"].upper())
    html = _patch_footer_date(html, stats["month_year"])
    return html


def sync_sentinel_html(html: str, stats: dict) -> str:
    """Sync Sentinel presentations."""
    html = _patch_meta_date(html, stats["date_full"])
    proj = stats.get("project_stats", {}).get("Sentinel_Bridge", {})
    if proj.get("endpoints"):
        # Update endpoint count in text like "API Surface (20 Endpoints)"
        html = re.sub(r'API Surface \(\d+ Endpoints?\)',
                      f"API Surface ({proj['endpoints']} Endpoints)", html)
    return html


def sync_aether_html(html: str, stats: dict) -> str:
    """Sync Project Aether presentations."""
    html = _patch_cover_badge_date(html, stats["month_year"].upper())
    html = _patch_footer_date(html, stats["month_year"])
    html = _patch_meta_date(html, stats["date_full"])
    return html


def sync_venture_html(html: str, stats: dict) -> str:
    """Sync Venture Studio presentations (aggregate stats)."""
    html = _patch_cover_stat(html, "Python Files", str(stats["python_files"]))
    html = _patch_cover_stat(html, "Live Apps", str(stats["live_apps"]))
    html = _patch_cover_stat(html, "AI Agents", str(stats["agents"]))
    html = _patch_cover_badge_date(html, stats["month_year"].upper())
    html = _patch_footer_date(html, stats["month_year"])
    html = _patch_footer_stats(html, stats)
    return html


# ═══════════════════════════════════════════════════════════
#  MAIN SYNC
# ═══════════════════════════════════════════════════════════

# Map presentation folders to their sync functions
PROJECT_SYNC_MAP = {
    "Meta_App_Factory": sync_factory_html,
    "Resonance": sync_resonance_html,
    "Sentinel": sync_sentinel_html,
    "Project_Aether": sync_aether_html,
    "Venture_Studio": sync_venture_html,
}


def sync_all(dry_run: bool = False, project_filter: str = None) -> dict:
    """
    Sync all presentations with current codebase stats.

    Args:
        dry_run: If True, report changes without writing files
        project_filter: If set, only sync this project folder

    Returns:
        Summary dict with files processed and changes made
    """
    if not PRESENTATIONS_DIR.is_dir():
        logger.warning(f"Presentations directory not found: {PRESENTATIONS_DIR}")
        return {"error": "Presentations directory not found", "files": 0, "changes": 0}

    stats = scan_codebase()
    results = {"files_processed": 0, "files_changed": 0, "changes": [], "dry_run": dry_run}

    for folder_name in sorted(os.listdir(PRESENTATIONS_DIR)):
        folder_path = PRESENTATIONS_DIR / folder_name
        if not folder_path.is_dir():
            continue
        if project_filter and folder_name.lower() != project_filter.lower():
            continue

        sync_fn = PROJECT_SYNC_MAP.get(folder_name)
        if not sync_fn:
            logger.info(f"⏭️  No sync function for '{folder_name}' — skipping")
            continue

        logger.info(f"▶ Syncing {folder_name}/")

        for html_file in sorted(folder_path.glob("*.html")):
            results["files_processed"] += 1
            try:
                original = html_file.read_text(encoding="utf-8")
                patched = sync_fn(original, stats)

                if patched != original:
                    results["files_changed"] += 1
                    results["changes"].append(html_file.name)

                    if not dry_run:
                        html_file.write_text(patched, encoding="utf-8")
                        logger.info(f"  ✅ Updated: {html_file.name}")
                    else:
                        logger.info(f"  🔍 Would update: {html_file.name}")
                else:
                    logger.info(f"  ⏸️  No changes: {html_file.name}")

            except Exception as e:
                logger.error(f"  ❌ Error processing {html_file.name}: {e}")
                results["changes"].append(f"ERROR: {html_file.name}: {str(e)[:100]}")

    logger.info(f"\n{'='*55}")
    logger.info(f"  Presentation Sync Complete")
    logger.info(f"  Files processed: {results['files_processed']}")
    logger.info(f"  Files changed: {results['files_changed']}")
    if dry_run:
        logger.info(f"  Mode: DRY RUN (no files written)")
    logger.info(f"{'='*55}\n")

    return results


def sync_project(project_name: str, dry_run: bool = False) -> dict:
    """Sync presentations for a specific project only."""
    return sync_all(dry_run=dry_run, project_filter=project_name)


# ═══════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Presentation Sync — Auto-Update HTML Manuals")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing")
    parser.add_argument("--project", help="Sync specific project only (e.g., Resonance)")
    args = parser.parse_args()

    result = sync_all(dry_run=args.dry_run, project_filter=args.project)

    print(f"\n{'='*55}")
    print(f"  Presentation Sync {'(DRY RUN)' if args.dry_run else 'Complete'}")
    print(f"{'='*55}")
    print(f"  Files processed: {result['files_processed']}")
    print(f"  Files changed:   {result['files_changed']}")
    if result["changes"]:
        print(f"  Changed files:")
        for c in result["changes"]:
            print(f"    - {c}")
    print(f"{'='*55}\n")
