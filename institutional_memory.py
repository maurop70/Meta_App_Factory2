"""
institutional_memory.py — Factory-wide Learning Engine
═══════════════════════════════════════════════════════════
Captures every correction, feedback, debate outcome, and self-heal cycle
as persistent "lessons" that are inherited by all child apps at build time.

Storage: projects/_shared/lessons.json (global) + projects/{project}/lessons.json (per-project)
"""

import os
import json
import logging
from datetime import datetime, timezone

logger = logging.getLogger("InstitutionalMemory")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SHARED_DIR = os.path.join(SCRIPT_DIR, "projects", "_shared")
SHARED_LESSONS = os.path.join(SHARED_DIR, "lessons.json")


def _ensure_dirs():
    os.makedirs(SHARED_DIR, exist_ok=True)


def _load_lessons(path: str) -> list:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _save_lessons(path: str, lessons: list):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(lessons, f, indent=2, default=str)


# ── Lesson Categories ────────────────────────────────────────────

CATEGORIES = {
    "user_feedback":     "Direct feedback or correction from the user",
    "critic_rejection":  "A deliverable rejected by the Critic agent",
    "self_heal":         "A bug caught and fixed by the self-healing loop",
    "debate_consensus":  "A strategic decision reached through C-Suite debate",
    "override":          "A user override that bypassed the Critic",
    "build_failure":     "A build or deploy failure with root cause",
    "quality_gate":      "A Phantom QA score below threshold",
    "architecture":      "An architectural pattern or anti-pattern discovered",
}


def record_lesson(
    category: str,
    summary: str,
    details: str = "",
    project_name: str = None,
    source_agent: str = "SYSTEM",
    severity: str = "normal",
    tags: list = None,
) -> dict:
    """
    Record a lesson learned. Saved to both global and per-project stores.
    
    Args:
        category: One of CATEGORIES keys
        summary: One-line lesson (e.g., "Always validate JSON before parsing")
        details: Extended context (error trace, debate log, etc.)
        project_name: If set, also saved to the project-specific store
        source_agent: Which agent/system generated this lesson
        severity: "low" | "normal" | "high" | "critical"
        tags: Searchable tags for retrieval
    """
    _ensure_dirs()

    lesson = {
        "id": f"L-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{hash(summary) % 10000:04d}",
        "category": category,
        "summary": summary,
        "details": details[:5000],  # Cap to avoid bloat
        "source_agent": source_agent,
        "severity": severity,
        "tags": tags or [],
        "project": project_name or "_global",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    # Save to global shared lessons
    global_lessons = _load_lessons(SHARED_LESSONS)
    global_lessons.append(lesson)
    # Keep only last 1000 lessons globally
    if len(global_lessons) > 1000:
        global_lessons = global_lessons[-1000:]
    _save_lessons(SHARED_LESSONS, global_lessons)

    # Also save to per-project lessons if applicable
    if project_name:
        project_path = os.path.join(SCRIPT_DIR, "projects", project_name, "lessons.json")
        project_lessons = _load_lessons(project_path)
        project_lessons.append(lesson)
        if len(project_lessons) > 500:
            project_lessons = project_lessons[-500:]
        _save_lessons(project_path, project_lessons)

    logger.info(f"[Memory] Lesson recorded: [{category}] {summary[:80]}...")
    return lesson


def get_lessons(
    project_name: str = None,
    category: str = None,
    limit: int = 50,
    include_global: bool = True,
) -> list:
    """
    Retrieve lessons, optionally filtered by project and/or category.
    If include_global=True, merges global lessons with project-specific ones.
    """
    lessons = []

    if include_global:
        lessons.extend(_load_lessons(SHARED_LESSONS))

    if project_name:
        project_path = os.path.join(SCRIPT_DIR, "projects", project_name, "lessons.json")
        project_lessons = _load_lessons(project_path)
        # Deduplicate by ID
        existing_ids = {l["id"] for l in lessons}
        for pl in project_lessons:
            if pl["id"] not in existing_ids:
                lessons.append(pl)

    if category:
        lessons = [l for l in lessons if l.get("category") == category]

    # Sort by creation date descending
    lessons.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return lessons[:limit]


def get_lessons_for_build(project_name: str = None) -> str:
    """
    Generate a context block of relevant lessons to inject into child app builds.
    This is the knowledge inheritance mechanism — every app built by Factory
    starts with the accumulated wisdom of all past projects.
    """
    lessons = get_lessons(project_name=project_name, limit=100, include_global=True)

    if not lessons:
        return ""

    # Group by category
    grouped = {}
    for l in lessons:
        cat = l.get("category", "other")
        if cat not in grouped:
            grouped[cat] = []
        grouped[cat].append(l)

    lines = ["# Factory Institutional Memory — Lessons Learned", ""]
    lines.append(f"*{len(lessons)} lessons from {len(set(l.get('project', '') for l in lessons))} projects*\n")

    for cat, items in grouped.items():
        cat_label = CATEGORIES.get(cat, cat)
        lines.append(f"## {cat.replace('_', ' ').title()} ({len(items)} lessons)")
        lines.append(f"*{cat_label}*\n")
        for item in items[:10]:  # Max 10 per category to keep context manageable
            severity_icon = {"critical": "🔴", "high": "🟠", "normal": "🟡", "low": "⚪"}.get(item.get("severity"), "🟡")
            lines.append(f"- {severity_icon} **{item['summary']}**")
            if item.get("details"):
                lines.append(f"  _{item['details'][:200]}_")
        lines.append("")

    return "\n".join(lines)


def search_lessons(query: str, limit: int = 20) -> list:
    """Full-text search across all lessons."""
    all_lessons = _load_lessons(SHARED_LESSONS)
    q = query.lower()
    matches = []
    for l in all_lessons:
        searchable = f"{l.get('summary', '')} {l.get('details', '')} {' '.join(l.get('tags', []))}".lower()
        if q in searchable:
            matches.append(l)
    matches.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return matches[:limit]


if __name__ == "__main__":
    # Demo
    record_lesson(
        category="architecture",
        summary="Always use per-project state isolation, never global singletons",
        details="The EOSContext was originally a global singleton which caused cross-project data leakage",
        project_name="Aether",
        source_agent="Master Architect",
        severity="high",
        tags=["architecture", "state-management", "isolation"],
    )
    print(get_lessons_for_build("Aether"))
