"""
aegis_agent.py — Aegis: Core Guardian & Collision Resolver
═══════════════════════════════════════════════════════════
Node #22 on the Antigravity System Map.

Responsibilities:
  1. resolve_collisions()  — Detect overlapping activities from n8n/Sentinel,
                              auto-merge when safe, flag priority tie-breakers.
  2. repair_quarantined()  — Fix malformed n8n payloads parked in quarantine
                              (date normalization, field completion).
  3. audit_schedule()      — Full schedule integrity check across all sources.

Usage:
    from agents.aegis_agent import AegisAgent
    aegis = AegisAgent()
    merged = aegis.resolve_collisions(activities_list)
    fixed  = aegis.repair_quarantined(quarantine_item)
"""

import os
import sys
import json
import hashlib
import logging
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

logger = logging.getLogger("v3.aegis")

FACTORY_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = FACTORY_DIR / "data"
QUARANTINE_FILE = DATA_DIR / "quarantine.json"


# ═══════════════════════════════════════════════════════════
#  DATE NORMALIZER — repairs common date format issues
# ═══════════════════════════════════════════════════════════

DATE_PATTERNS = [
    (r"(\d{1,2})/(\d{1,2})/(\d{4})",    lambda m: f"{m.group(3)}-{m.group(1).zfill(2)}-{m.group(2).zfill(2)}"),
    (r"(\d{1,2})/(\d{1,2})/(\d{2})",    lambda m: f"20{m.group(3)}-{m.group(1).zfill(2)}-{m.group(2).zfill(2)}"),
    (r"(\d{1,2})-(\d{1,2})-(\d{4})",    lambda m: f"{m.group(3)}-{m.group(1).zfill(2)}-{m.group(2).zfill(2)}"),
    (r"(\w+ \d{1,2},? \d{4})",          None),  # "March 15, 2026" — handled by dateutil
]


def _normalize_date(raw: str) -> str:
    """Attempt to normalize a date string to ISO format."""
    if not raw:
        return raw

    # Already ISO?
    if re.match(r"\d{4}-\d{2}-\d{2}", raw):
        return raw[:10]

    for pattern, converter in DATE_PATTERNS:
        match = re.search(pattern, raw)
        if match and converter:
            try:
                return converter(match)
            except Exception:
                continue

    # Try dateutil as fallback
    try:
        from dateutil import parser as dateparser
        dt = dateparser.parse(raw)
        return dt.strftime("%Y-%m-%d")
    except Exception:
        pass

    return raw  # Return as-is if nothing works


# ═══════════════════════════════════════════════════════════
#  AEGIS AGENT
# ═══════════════════════════════════════════════════════════

class AegisAgent:
    """Core Guardian — collision resolution, data repair, schedule auditing."""

    VERSION = "1.0.0"
    AGENT_ID = "aegis_agent"
    NODE_NUMBER = 22

    def __init__(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)

    def info(self) -> dict:
        return {
            "agent": self.AGENT_ID,
            "version": self.VERSION,
            "node": self.NODE_NUMBER,
            "capabilities": [
                "resolve_collisions",
                "repair_quarantined",
                "audit_schedule",
            ],
            "quarantine_file": str(QUARANTINE_FILE),
        }

    # ─── Collision Resolution ────────────────────────────

    def resolve_collisions(self, activities: list[dict]) -> dict:
        """
        Detect and resolve overlapping activities.

        Each activity dict should have at minimum:
            - "activity": str
            - "time" or "due_date": str (ISO date or datetime)
            - "source": str (e.g., "sentinel", "n8n", "calendar")
            - "priority": str ("high", "normal", "low")
            - "category": str

        Returns:
            {
                "merged": [...],        # activities that were auto-merged
                "conflicts": [...],     # unresolvable priority ties flagged
                "clean": [...],         # activities with no collisions
                "total_input": int,
                "total_output": int,
            }
        """
        if not activities:
            return {"merged": [], "conflicts": [], "clean": [], "total_input": 0, "total_output": 0}

        # Normalize all dates
        for act in activities:
            date_field = act.get("due_date") or act.get("time") or ""
            act["_normalized_date"] = _normalize_date(str(date_field))[:10] if date_field else ""

        # Group by date
        by_date: dict[str, list[dict]] = {}
        no_date = []
        for act in activities:
            d = act["_normalized_date"]
            if d:
                by_date.setdefault(d, []).append(act)
            else:
                no_date.append(act)

        merged = []
        conflicts = []
        clean = list(no_date)  # No-date items are always clean

        for date, group in by_date.items():
            if len(group) == 1:
                clean.append(group[0])
                continue

            # Multiple activities on same date — check for duplicates and conflicts
            seen = {}
            for act in group:
                sig = self._activity_signature(act)
                if sig in seen:
                    # Duplicate — merge (keep higher priority)
                    existing = seen[sig]
                    winner = self._priority_winner(existing, act)
                    seen[sig] = winner
                    merged.append({
                        "kept": winner.get("activity", ""),
                        "dropped": (act if winner is existing else existing).get("activity", ""),
                        "date": date,
                        "reason": "duplicate_merged",
                    })
                else:
                    seen[sig] = act

            # Check remaining for time-slot conflicts
            remaining = list(seen.values())
            if len(remaining) > 1:
                # Group by exact time (hour-level)
                by_hour = {}
                for act in remaining:
                    h = self._extract_hour(act)
                    by_hour.setdefault(h, []).append(act)

                for hour, hour_group in by_hour.items():
                    if len(hour_group) == 1:
                        clean.append(hour_group[0])
                    elif self._can_auto_resolve(hour_group):
                        winner = self._priority_winner(*hour_group[:2])
                        clean.append(winner)
                        for loser in hour_group:
                            if loser is not winner:
                                merged.append({
                                    "kept": winner.get("activity", ""),
                                    "dropped": loser.get("activity", ""),
                                    "date": date,
                                    "hour": hour,
                                    "reason": "priority_auto_resolved",
                                })
                    else:
                        # True conflict — flag for human review
                        conflicts.append({
                            "date": date,
                            "hour": hour,
                            "activities": [a.get("activity", "") for a in hour_group],
                            "sources": [a.get("source", "") for a in hour_group],
                            "priorities": [a.get("priority", "normal") for a in hour_group],
                            "reason": "priority_tie",
                        })
                        clean.extend(hour_group)  # Keep both, flagged
            else:
                clean.extend(remaining)

        # Cleanup internal fields
        for act in clean:
            act.pop("_normalized_date", None)

        result = {
            "merged": merged,
            "conflicts": conflicts,
            "clean": clean,
            "total_input": len(activities),
            "total_output": len(clean),
        }

        if conflicts:
            logger.warning(f"[Aegis] {len(conflicts)} collision(s) flagged for review")
        if merged:
            logger.info(f"[Aegis] Auto-merged {len(merged)} duplicate(s)")

        return result

    def _activity_signature(self, act: dict) -> str:
        """Generate a dedup signature from activity content."""
        text = (act.get("activity", "") + act.get("description", "")).lower().strip()
        return hashlib.md5(text.encode()).hexdigest()[:12]

    def _extract_hour(self, act: dict) -> str:
        """Extract hour from time field, or 'all_day'."""
        time_str = act.get("time") or act.get("due_date") or ""
        if "T" in str(time_str) and ":" in str(time_str):
            try:
                return str(time_str).split("T")[1][:2]
            except Exception:
                pass
        return "all_day"

    def _can_auto_resolve(self, group: list[dict]) -> bool:
        """Can we auto-resolve? Yes if there's a clear priority winner."""
        priorities = [a.get("priority", "normal") for a in group]
        if priorities.count("high") == 1:
            return True
        if len(set(priorities)) > 1:
            return True  # Different priorities = resolvable
        return False  # All same priority = tie

    def _priority_winner(self, a: dict, b: dict) -> dict:
        """Return the higher-priority activity."""
        rank = {"high": 3, "normal": 2, "low": 1}
        ra = rank.get(a.get("priority", "normal"), 2)
        rb = rank.get(b.get("priority", "normal"), 2)
        return a if ra >= rb else b

    # ─── Quarantine Repair ───────────────────────────────

    def repair_quarantined(self, item: dict) -> dict:
        """
        Attempt to repair a quarantined n8n payload.

        Fixes:
          - Date format normalization
          - Missing required fields (fills defaults)
          - Category validation
          - Priority normalization

        Returns the repaired item with a `_repair_log` field.
        """
        repairs = []

        # 1. Date normalization
        for date_field in ("due_date", "time", "date", "deadline"):
            if date_field in item:
                original = str(item[date_field])
                normalized = _normalize_date(original)
                if normalized != original:
                    item[date_field] = normalized
                    repairs.append(f"date:{date_field} '{original}' → '{normalized}'")

        # 2. Required field defaults
        defaults = {
            "activity": "Untitled Activity",
            "category": "Other",
            "priority": "normal",
            "status": "pending",
            "source": "n8n_repaired",
        }
        for field, default in defaults.items():
            if not item.get(field):
                item[field] = default
                repairs.append(f"field:{field} set to '{default}'")

        # 3. Priority normalization
        valid_priorities = {"high", "normal", "low"}
        if item.get("priority") not in valid_priorities:
            old = item["priority"]
            item["priority"] = "normal"
            repairs.append(f"priority:'{old}' → 'normal'")

        # 4. Category validation
        valid_cats = {"Legal", "Finance", "Ops", "Medical", "Technical", "AI", "Other"}
        if item.get("category") not in valid_cats:
            old = item.get("category", "")
            item["category"] = "Other"
            repairs.append(f"category:'{old}' → 'Other'")

        item["_repair_log"] = repairs
        item["_repaired_at"] = datetime.now(timezone.utc).isoformat()
        item["_repaired_by"] = "aegis_agent"

        logger.info(f"[Aegis] Repaired quarantined item: {len(repairs)} fixes applied")
        return item

    def process_quarantine(self) -> dict:
        """
        Process all items in quarantine.json — repair each, return stats.
        """
        if not QUARANTINE_FILE.exists():
            return {"processed": 0, "repaired": 0, "failed": 0}

        try:
            with open(QUARANTINE_FILE, "r", encoding="utf-8") as f:
                items = json.load(f)
        except Exception as e:
            logger.error(f"[Aegis] Failed to read quarantine: {e}")
            return {"processed": 0, "repaired": 0, "failed": 0, "error": str(e)}

        repaired = []
        failed = []
        for item in items:
            if item.get("_repaired_at"):
                continue  # Already processed
            try:
                fixed = self.repair_quarantined(item)
                repaired.append(fixed)
            except Exception as e:
                item["_repair_error"] = str(e)
                failed.append(item)

        # Save back
        try:
            all_items = repaired + failed
            with open(QUARANTINE_FILE, "w", encoding="utf-8") as f:
                json.dump(all_items, f, indent=2, default=str)
        except Exception:
            pass

        return {
            "processed": len(repaired) + len(failed),
            "repaired": len(repaired),
            "failed": len(failed),
        }

    # ─── Schedule Audit ──────────────────────────────────

    def audit_schedule(self, reminders: list[dict]) -> dict:
        """
        Run a full integrity check on a reminder list.
        Returns stats and any issues found.
        """
        issues = []
        stats = {"total": len(reminders), "missing_date": 0, "past_due": 0, "duplicates": 0}
        now = datetime.now(timezone.utc)
        sigs = set()

        for r in reminders:
            # Missing date
            date_str = r.get("time") or r.get("due_date")
            if not date_str:
                stats["missing_date"] += 1
                issues.append({"id": r.get("id"), "issue": "missing_date"})
                continue

            # Past due
            try:
                dt = datetime.fromisoformat(str(date_str).replace("Z", "+00:00"))
                if dt < now - timedelta(days=7):
                    stats["past_due"] += 1
                    issues.append({"id": r.get("id"), "issue": "past_due", "date": str(date_str)})
            except Exception:
                pass

            # Duplicates
            sig = self._activity_signature(r)
            if sig in sigs:
                stats["duplicates"] += 1
                issues.append({"id": r.get("id"), "issue": "duplicate", "sig": sig})
            sigs.add(sig)

        return {"stats": stats, "issues": issues, "healthy": len(issues) == 0}


# ═══════════════════════════════════════════════════════════
#  __init__.py auto-export
# ═══════════════════════════════════════════════════════════

__all__ = ["AegisAgent"]


# ═══════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    aegis = AegisAgent()
    print(json.dumps(aegis.info(), indent=2))

    # Process quarantine if it exists
    result = aegis.process_quarantine()
    print(f"\nQuarantine: {json.dumps(result, indent=2)}")

