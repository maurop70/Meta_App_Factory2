"""
CMO Agent — Marketing Memory Store
═══════════════════════════════════
SQLite-based persistent memory for cross-module intelligence.
When the Brand Studio creates an identity, the Campaign Hub
remembers those colors and tone constraints automatically.
"""

import sqlite3
import json
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "marketing_memory.db")


def get_db():
    """Get a database connection, creating tables if needed."""
    db_path = os.path.normpath(DB_PATH)
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    _init_tables(conn)
    return conn


def _init_tables(conn):
    """Create tables if they don't exist."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            display_name TEXT NOT NULL,
            description TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            status TEXT DEFAULT 'active',
            thumbnail TEXT
        );

        CREATE TABLE IF NOT EXISTS analyses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            module TEXT NOT NULL,
            project_name TEXT,
            input_summary TEXT,
            result_json TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            tags TEXT
        );
        
        CREATE TABLE IF NOT EXISTS brand_identities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_name TEXT NOT NULL,
            company_name TEXT,
            colors_json TEXT,
            fonts_json TEXT,
            tone_json TEXT,
            full_identity_json TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            is_active INTEGER NOT NULL DEFAULT 1
        );
        
        CREATE TABLE IF NOT EXISTS personas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_name TEXT NOT NULL,
            persona_name TEXT,
            persona_title TEXT,
            persona_json TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        
        CREATE TABLE IF NOT EXISTS campaigns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_name TEXT NOT NULL,
            campaign_name TEXT,
            campaign_json TEXT NOT NULL,
            status TEXT DEFAULT 'draft',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        
        CREATE TABLE IF NOT EXISTS market_research (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_name TEXT NOT NULL,
            company_name TEXT,
            research_json TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        
        CREATE INDEX IF NOT EXISTS idx_analyses_module ON analyses(module);
        CREATE INDEX IF NOT EXISTS idx_brand_project ON brand_identities(project_name);
        CREATE INDEX IF NOT EXISTS idx_personas_project ON personas(project_name);
        CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status);
    """)
    conn.commit()


# ── Generic Analysis Storage ────────────────────────────────

def save_analysis(module: str, result: dict, project_name: str = "", input_summary: str = "", tags: str = ""):
    """Save any analysis result and ensure the project exists."""
    conn = get_db()
    # Auto-create project if it doesn't exist
    if project_name:
        _ensure_project(conn, project_name, input_summary)
    conn.execute(
        "INSERT INTO analyses (module, project_name, input_summary, result_json, tags) VALUES (?, ?, ?, ?, ?)",
        (module, project_name, input_summary, json.dumps(result), tags)
    )
    # Update project timestamp
    if project_name:
        conn.execute("UPDATE projects SET updated_at = datetime('now') WHERE name = ?", (project_name,))
    conn.commit()
    conn.close()


def get_recent_analyses(module: str = None, project_name: str = None, limit: int = 10) -> list:
    """Get recent analyses, optionally filtered by module or project."""
    conn = get_db()
    query = "SELECT * FROM analyses WHERE 1=1"
    params = []
    if module:
        query += " AND module = ?"
        params.append(module)
    if project_name:
        query += " AND project_name = ?"
        params.append(project_name)
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    
    rows = conn.execute(query, params).fetchall()
    conn.close()
    
    results = []
    for row in rows:
        r = dict(row)
        try:
            r["result"] = json.loads(r.pop("result_json"))
        except (json.JSONDecodeError, KeyError):
            pass
        results.append(r)
    return results


# ── Brand Identity Storage ──────────────────────────────────

def save_brand_identity(project_name: str, identity: dict):
    """Save a brand identity and extract key fields for cross-module use."""
    conn = get_db()
    
    colors = identity.get("visual_identity", {}).get("color_palette", {})
    fonts = identity.get("visual_identity", {}).get("typography", {})
    tone = identity.get("tone_of_voice", {})
    company = identity.get("company_name", "")
    
    # Deactivate previous identities for this project
    conn.execute("UPDATE brand_identities SET is_active = 0 WHERE project_name = ?", (project_name,))
    
    conn.execute(
        """INSERT INTO brand_identities 
           (project_name, company_name, colors_json, fonts_json, tone_json, full_identity_json) 
           VALUES (?, ?, ?, ?, ?, ?)""",
        (project_name, company, json.dumps(colors), json.dumps(fonts), json.dumps(tone), json.dumps(identity))
    )
    conn.commit()
    conn.close()


def get_active_brand(project_name: str) -> dict | None:
    """Get the active brand identity for a project."""
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM brand_identities WHERE project_name = ? AND is_active = 1 ORDER BY created_at DESC LIMIT 1",
        (project_name,)
    ).fetchone()
    conn.close()
    
    if not row:
        return None
    
    r = dict(row)
    try:
        r["full_identity"] = json.loads(r.pop("full_identity_json"))
        r["colors"] = json.loads(r.pop("colors_json"))
        r["fonts"] = json.loads(r.pop("fonts_json"))
        r["tone"] = json.loads(r.pop("tone_json"))
    except (json.JSONDecodeError, KeyError):
        pass
    return r


# ── Persona Storage ─────────────────────────────────────────

def save_personas(project_name: str, personas_data: dict):
    """Save generated personas."""
    conn = get_db()
    personas = personas_data.get("personas", [])
    for p in personas:
        conn.execute(
            "INSERT INTO personas (project_name, persona_name, persona_title, persona_json) VALUES (?, ?, ?, ?)",
            (project_name, p.get("name", ""), p.get("title", ""), json.dumps(p))
        )
    conn.commit()
    conn.close()


def get_personas(project_name: str) -> list:
    """Get all personas for a project."""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM personas WHERE project_name = ? ORDER BY created_at DESC", (project_name,)
    ).fetchall()
    conn.close()
    
    results = []
    for row in rows:
        r = dict(row)
        try:
            r["persona"] = json.loads(r.pop("persona_json"))
        except (json.JSONDecodeError, KeyError):
            pass
        results.append(r)
    return results


# ── Campaign Storage ────────────────────────────────────────

def save_campaign(project_name: str, campaign: dict):
    """Save a campaign plan."""
    conn = get_db()
    conn.execute(
        "INSERT INTO campaigns (project_name, campaign_name, campaign_json) VALUES (?, ?, ?)",
        (project_name, campaign.get("campaign_name", ""), json.dumps(campaign))
    )
    conn.commit()
    conn.close()


def get_campaigns(project_name: str) -> list:
    """Get all campaigns for a project."""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM campaigns WHERE project_name = ? ORDER BY created_at DESC", (project_name,)
    ).fetchall()
    conn.close()
    
    results = []
    for row in rows:
        r = dict(row)
        try:
            r["campaign"] = json.loads(r.pop("campaign_json"))
        except (json.JSONDecodeError, KeyError):
            pass
        results.append(r)
    return results


# ── Cross-Module Context Builder ────────────────────────────

def get_project_context(project_name: str) -> str:
    """
    Build a context string from all stored data for a project.
    This is injected into engine prompts so the CMO "remembers" everything.
    """
    parts = []
    
    # Brand identity
    brand = get_active_brand(project_name)
    if brand:
        parts.append(f"ACTIVE BRAND IDENTITY: {json.dumps(brand.get('full_identity', {}), indent=0)[:1500]}")
    
    # Recent personas
    personas = get_personas(project_name)[:3]
    if personas:
        names = [f"{p.get('persona', {}).get('name', '?')} ({p.get('persona', {}).get('title', '')})" for p in personas]
        parts.append(f"KNOWN PERSONAS: {', '.join(names)}")
    
    # Recent campaigns
    campaigns = get_campaigns(project_name)[:2]
    if campaigns:
        names = [c.get('campaign', {}).get('campaign_name', '?') for c in campaigns]
        parts.append(f"ACTIVE CAMPAIGNS: {', '.join(names)}")
    
    # Recent research
    research = get_recent_analyses("market_research", project_name, limit=2)
    if research:
        for r in research:
            summary = r.get("result", {}).get("executive_summary", "")
            if summary:
                parts.append(f"PRIOR RESEARCH: {summary}")
    
    return "\n".join(parts) if parts else ""


# ── Dashboard Stats ─────────────────────────────────────────

def get_dashboard_stats() -> dict:
    """Get aggregate stats for the dashboard."""
    conn = get_db()
    
    total_analyses = conn.execute("SELECT COUNT(*) FROM analyses").fetchone()[0]
    total_brands = conn.execute("SELECT COUNT(*) FROM brand_identities").fetchone()[0]
    total_personas = conn.execute("SELECT COUNT(*) FROM personas").fetchone()[0]
    total_campaigns = conn.execute("SELECT COUNT(*) FROM campaigns").fetchone()[0]
    
    # Unique projects from projects table
    project_rows = conn.execute("SELECT name FROM projects WHERE status = 'active' ORDER BY updated_at DESC").fetchall()
    projects = [r[0] for r in project_rows]
    
    # Also check for orphaned project names not yet in projects table
    for table in ["analyses", "brand_identities", "personas", "campaigns"]:
        rows = conn.execute(f"SELECT DISTINCT project_name FROM {table} WHERE project_name != ''").fetchall()
        for row in rows:
            if row[0] not in projects:
                projects.append(row[0])
    
    conn.close()
    
    return {
        "total_analyses": total_analyses,
        "total_brands": total_brands,
        "total_personas": total_personas,
        "total_campaigns": total_campaigns,
        "total_projects": len(projects),
        "projects": projects
    }


# ═══════════════════════════════════════════════════════════
#  PROJECT MANAGEMENT
# ═══════════════════════════════════════════════════════════

def _slugify(text: str) -> str:
    """Create a URL-friendly project slug from text."""
    import re
    slug = text.lower().strip()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'[\s-]+', '-', slug)
    return slug[:50].strip('-')


def _ensure_project(conn, project_name: str, input_summary: str = ""):
    """Ensure a project row exists. Auto-create if missing."""
    row = conn.execute("SELECT id FROM projects WHERE name = ?", (project_name,)).fetchone()
    if not row:
        display = project_name.replace('-', ' ').replace('_', ' ').title()
        desc = input_summary[:200] if input_summary else ''
        conn.execute(
            "INSERT OR IGNORE INTO projects (name, display_name, description) VALUES (?, ?, ?)",
            (project_name, display, desc)
        )


def create_project(name: str, display_name: str = "", description: str = "") -> dict:
    """Create a new project."""
    conn = get_db()
    slug = _slugify(name) if name else "project"
    display = display_name or name.replace('-', ' ').replace('_', ' ').title()
    
    # Ensure unique slug
    base_slug = slug
    counter = 1
    while conn.execute("SELECT id FROM projects WHERE name = ?", (slug,)).fetchone():
        slug = f"{base_slug}-{counter}"
        counter += 1
    
    conn.execute(
        "INSERT INTO projects (name, display_name, description) VALUES (?, ?, ?)",
        (slug, display, description)
    )
    conn.commit()
    project = conn.execute("SELECT * FROM projects WHERE name = ?", (slug,)).fetchone()
    conn.close()
    return dict(project)


def list_projects(status: str = "active") -> list:
    """List all projects with summary stats."""
    conn = get_db()
    
    if status == "all":
        rows = conn.execute("SELECT * FROM projects ORDER BY updated_at DESC").fetchall()
    else:
        rows = conn.execute("SELECT * FROM projects WHERE status = ? ORDER BY updated_at DESC", (status,)).fetchall()
    
    projects = []
    for row in rows:
        p = dict(row)
        name = p["name"]
        
        # Aggregate stats for this project
        p["analysis_count"] = conn.execute(
            "SELECT COUNT(*) FROM analyses WHERE project_name = ?", (name,)
        ).fetchone()[0]
        
        # Engines used
        modules = conn.execute(
            "SELECT DISTINCT module FROM analyses WHERE project_name = ?", (name,)
        ).fetchall()
        p["engines_used"] = [m[0] for m in modules]
        
        # Active brand
        brand = conn.execute(
            "SELECT company_name FROM brand_identities WHERE project_name = ? AND is_active = 1 ORDER BY created_at DESC LIMIT 1",
            (name,)
        ).fetchone()
        p["brand_name"] = brand[0] if brand else None
        
        # Persona count
        p["persona_count"] = conn.execute(
            "SELECT COUNT(*) FROM personas WHERE project_name = ?", (name,)
        ).fetchone()[0]
        
        # Campaign count
        p["campaign_count"] = conn.execute(
            "SELECT COUNT(*) FROM campaigns WHERE project_name = ?", (name,)
        ).fetchone()[0]
        
        projects.append(p)
    
    conn.close()
    return projects


def get_project_detail(name: str) -> dict:
    """Get full project detail with all engine results."""
    conn = get_db()
    
    project = conn.execute("SELECT * FROM projects WHERE name = ?", (name,)).fetchone()
    if not project:
        conn.close()
        return None
    
    detail = dict(project)
    
    # All analyses for this project (chronological)
    analyses = conn.execute(
        "SELECT id, module, input_summary, result_json, created_at FROM analyses WHERE project_name = ? ORDER BY created_at ASC",
        (name,)
    ).fetchall()
    detail["history"] = []
    for a in analyses:
        entry = dict(a)
        try:
            entry["result"] = json.loads(entry.pop("result_json"))
        except (json.JSONDecodeError, KeyError):
            pass
        detail["history"].append(entry)
    
    # Active brand
    brand = get_active_brand(name)
    detail["brand"] = brand
    
    # Personas
    detail["personas"] = get_personas(name)
    
    # Campaigns
    detail["campaigns"] = get_campaigns(name)
    
    conn.close()
    return detail


def rename_project(old_name: str, new_name: str = None, display_name: str = None) -> dict:
    """Rename a project's slug and/or display name."""
    conn = get_db()
    
    if new_name:
        slug = _slugify(new_name)
        # Update all references
        for table in ["analyses", "brand_identities", "personas", "campaigns"]:
            conn.execute(f"UPDATE {table} SET project_name = ? WHERE project_name = ?", (slug, old_name))
        conn.execute("UPDATE projects SET name = ? WHERE name = ?", (slug, old_name))
    
    if display_name:
        target = new_name and _slugify(new_name) or old_name
        conn.execute("UPDATE projects SET display_name = ?, updated_at = datetime('now') WHERE name = ?", (display_name, target))
    
    conn.commit()
    target_name = (new_name and _slugify(new_name)) or old_name
    project = conn.execute("SELECT * FROM projects WHERE name = ?", (target_name,)).fetchone()
    conn.close()
    return dict(project) if project else {}


def archive_project(name: str) -> bool:
    """Archive a project (soft delete)."""
    conn = get_db()
    conn.execute("UPDATE projects SET status = 'archived', updated_at = datetime('now') WHERE name = ?", (name,))
    conn.commit()
    conn.close()
    return True


def get_project_history(name: str, limit: int = 50) -> list:
    """Get paginated history of all engine runs for a project."""
    conn = get_db()
    rows = conn.execute(
        "SELECT id, module, input_summary, result_json, created_at FROM analyses WHERE project_name = ? ORDER BY created_at DESC LIMIT ?",
        (name, limit)
    ).fetchall()
    conn.close()
    
    results = []
    for row in rows:
        r = dict(row)
        try:
            r["result"] = json.loads(r.pop("result_json"))
        except (json.JSONDecodeError, KeyError):
            pass
        results.append(r)
    return results


def duplicate_project(source_name: str, new_display_name: str = "") -> dict:
    """Deep-copy a project and all its data to a new project."""
    conn = get_db()

    # Verify source exists
    source = conn.execute("SELECT * FROM projects WHERE name = ?", (source_name,)).fetchone()
    if not source:
        conn.close()
        return None

    source = dict(source)

    # Generate unique slug
    base_slug = _slugify(new_display_name or f"{source['display_name']} Copy")
    slug = base_slug
    counter = 1
    while conn.execute("SELECT id FROM projects WHERE name = ?", (slug,)).fetchone():
        slug = f"{base_slug}-{counter}"
        counter += 1

    display = new_display_name or f"{source['display_name']} (Copy)"

    # Create new project row
    conn.execute(
        "INSERT INTO projects (name, display_name, description, status) VALUES (?, ?, ?, 'active')",
        (slug, display, source.get("description", ""))
    )

    # Copy analyses
    rows = conn.execute(
        "SELECT module, input_summary, result_json, tags FROM analyses WHERE project_name = ?",
        (source_name,)
    ).fetchall()
    for r in rows:
        conn.execute(
            "INSERT INTO analyses (module, project_name, input_summary, result_json, tags) VALUES (?, ?, ?, ?, ?)",
            (r[0], slug, r[1], r[2], r[3])
        )

    # Copy brand identities
    rows = conn.execute(
        "SELECT company_name, colors_json, fonts_json, tone_json, full_identity_json, is_active FROM brand_identities WHERE project_name = ?",
        (source_name,)
    ).fetchall()
    for r in rows:
        conn.execute(
            "INSERT INTO brand_identities (project_name, company_name, colors_json, fonts_json, tone_json, full_identity_json, is_active) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (slug, r[0], r[1], r[2], r[3], r[4], r[5])
        )

    # Copy personas
    rows = conn.execute(
        "SELECT persona_name, persona_title, persona_json FROM personas WHERE project_name = ?",
        (source_name,)
    ).fetchall()
    for r in rows:
        conn.execute(
            "INSERT INTO personas (project_name, persona_name, persona_title, persona_json) VALUES (?, ?, ?, ?)",
            (slug, r[0], r[1], r[2])
        )

    # Copy campaigns
    rows = conn.execute(
        "SELECT campaign_name, campaign_json, status FROM campaigns WHERE project_name = ?",
        (source_name,)
    ).fetchall()
    for r in rows:
        conn.execute(
            "INSERT INTO campaigns (project_name, campaign_name, campaign_json, status) VALUES (?, ?, ?, ?)",
            (slug, r[0], r[1], r[2])
        )

    conn.commit()
    new_project = conn.execute("SELECT * FROM projects WHERE name = ?", (slug,)).fetchone()
    conn.close()
    return dict(new_project) if new_project else {}
