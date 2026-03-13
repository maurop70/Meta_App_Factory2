"""
wisdom_accumulator.py — Institutional Memory Engine (Global Core)
═══════════════════════════════════════════════════════════════════
.system_core | Antigravity V3.0 | Venture Studio Inheritance Engine

After every successful "Persuasion" in the War Room (when the Socratic
Challenger verdict == "CONVINCED"), the winning logic is appended to
.system_core/global_wisdom.db — a JSON-lines knowledge base.

This creates a growing institutional memory of what arguments work,
which evidence patterns are strongest, and what categories of
objections the Commander has successfully addressed.

Usage:
    python wisdom_accumulator.py --stats
    python wisdom_accumulator.py --query "scalability"
    python wisdom_accumulator.py --recent 5
"""

import os
import sys
import json
import logging
from datetime import datetime
from typing import Optional, List

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FACTORY_DIR = os.path.normpath(os.path.join(SCRIPT_DIR, ".."))
sys.path.insert(0, FACTORY_DIR)

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

logger = logging.getLogger("system_core.wisdom_accumulator")

# Default location for the wisdom database
DEFAULT_WISDOM_DB = os.path.join(SCRIPT_DIR, "global_wisdom.db")


class WisdomAccumulator:
    """
    Institutional memory engine that captures winning persuasion logic
    from successful Socratic challenges.

    Usage:
        from system_core import WisdomAccumulator
        wisdom = WisdomAccumulator()
        wisdom.record_wisdom(challenge_id, proposal, reasoning, analysis)
        stats = wisdom.get_stats()
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or DEFAULT_WISDOM_DB
        logger.info("WisdomAccumulator initialized (db: %s)", self.db_path)

    # ── Record ───────────────────────────────────────────

    def record_wisdom(
        self,
        challenge_id: str,
        proposal: str,
        winning_reasoning: str,
        analysis: dict,
    ) -> dict:
        """
        Append a winning persuasion entry to global_wisdom.db.

        Args:
            challenge_id: The Socratic challenge ID (e.g. "CHG-0001")
            proposal: The original proposal text
            winning_reasoning: The Commander's successful argument
            analysis: The analysis dict from SocraticChallenger.analyze_response()

        Returns:
            The stored wisdom entry dict.
        """
        entry = {
            "ts": datetime.now().isoformat(),
            "challenge_id": challenge_id,
            "proposal": proposal[:500],  # Truncate for storage
            "winning_reasoning": winning_reasoning[:2000],
            "combined_score": analysis.get("combined_score", 0),
            "reasoning_score": analysis.get("reasoning_score", 0),
            "original_critic_score": analysis.get("original_critic_score", 0),
            "strong_signals": analysis.get("analysis", {}).get("strong_signals", 0),
            "weak_signals": analysis.get("analysis", {}).get("weak_signals", 0),
            "weaknesses_addressed": analysis.get("analysis", {}).get("weaknesses_addressed", "0/0"),
            "word_count": analysis.get("analysis", {}).get("word_count", 0),
        }

        try:
            with open(self.db_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, default=str) + "\n")
            logger.info(
                "Wisdom recorded: %s (score %.1f)",
                challenge_id,
                entry["combined_score"],
            )
        except Exception as e:
            logger.error("Failed to record wisdom: %s", e)

        return entry

    # ── Query ────────────────────────────────────────────

    def query_wisdom(self, keyword: str) -> List[dict]:
        """
        Search the accumulated wisdom for entries matching a keyword.
        Searches across proposal text, winning reasoning, and challenge IDs.
        """
        results = []
        keyword_lower = keyword.lower()

        for entry in self._load_all():
            searchable = " ".join([
                entry.get("proposal", ""),
                entry.get("winning_reasoning", ""),
                entry.get("challenge_id", ""),
            ]).lower()
            if keyword_lower in searchable:
                results.append(entry)

        return results

    def get_recent(self, n: int = 10) -> List[dict]:
        """Return the N most recent wisdom entries."""
        entries = self._load_all()
        return entries[-n:]

    # ── Stats ────────────────────────────────────────────

    def get_stats(self) -> dict:
        """
        Aggregate statistics from the wisdom database.
        Returns win rates, average scores, strongest signal types, etc.
        """
        entries = self._load_all()
        total = len(entries)

        if total == 0:
            return {
                "total_entries": 0,
                "message": "No wisdom recorded yet. Win some Socratic challenges!",
            }

        avg_combined = sum(e.get("combined_score", 0) for e in entries) / total
        avg_reasoning = sum(e.get("reasoning_score", 0) for e in entries) / total
        avg_critic = sum(e.get("original_critic_score", 0) for e in entries) / total
        avg_strong = sum(e.get("strong_signals", 0) for e in entries) / total
        avg_weak = sum(e.get("weak_signals", 0) for e in entries) / total
        avg_words = sum(e.get("word_count", 0) for e in entries) / total

        # Coverage analysis
        full_coverage = 0
        for e in entries:
            addressed = e.get("weaknesses_addressed", "0/0")
            parts = addressed.split("/")
            if len(parts) == 2 and parts[0] == parts[1] and parts[0] != "0":
                full_coverage += 1

        return {
            "total_entries": total,
            "avg_combined_score": round(avg_combined, 1),
            "avg_reasoning_score": round(avg_reasoning, 1),
            "avg_original_critic_score": round(avg_critic, 1),
            "avg_strong_signals": round(avg_strong, 1),
            "avg_weak_signals": round(avg_weak, 1),
            "avg_word_count": round(avg_words, 0),
            "full_coverage_rate": f"{full_coverage}/{total} ({round(full_coverage/total*100)}%)",
            "first_entry": entries[0].get("ts", "N/A"),
            "latest_entry": entries[-1].get("ts", "N/A"),
        }

    # ── Hook ─────────────────────────────────────────────

    def hook_into_socratic(self, challenger=None):
        """
        Monkey-patch the SocraticChallenger's analyze_response() method
        to automatically record wisdom on every CONVINCED verdict.

        Call once at startup to enable automatic wisdom capture.

        Usage:
            from system_core import WisdomAccumulator
            from socratic_challenger import get_challenger
            wisdom = WisdomAccumulator()
            wisdom.hook_into_socratic(get_challenger())
        """
        if challenger is None:
            try:
                from socratic_challenger import get_challenger
                challenger = get_challenger()
            except ImportError:
                logger.warning("Could not import SocraticChallenger for hook.")
                return False

        original_analyze = challenger.analyze_response
        accumulator = self

        def _hooked_analyze(challenge_id: str, user_reasoning: str):
            result = original_analyze(challenge_id, user_reasoning)

            # On successful persuasion, record the wisdom
            if result.get("verdict") == "CONVINCED":
                challenge = challenger._active_challenges.get(challenge_id, {})
                proposal = challenge.get("proposal_preview", "")
                accumulator.record_wisdom(
                    challenge_id=challenge_id,
                    proposal=proposal,
                    winning_reasoning=user_reasoning,
                    analysis=result,
                )
                logger.info(
                    "🧠 Wisdom captured for %s (score: %.1f)",
                    challenge_id,
                    result.get("combined_score", 0),
                )

            return result

        challenger.analyze_response = _hooked_analyze
        logger.info("✅ Wisdom Accumulator hooked into SocraticChallenger")
        return True

    # ── Internal ─────────────────────────────────────────

    def _load_all(self) -> List[dict]:
        """Load all entries from the JSON-lines database."""
        entries = []
        if not os.path.exists(self.db_path):
            return entries

        try:
            with open(self.db_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            entries.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            logger.error("Failed to read wisdom DB: %s", e)

        return entries


# ── Module-level singleton ───────────────────────────────
_accumulator = WisdomAccumulator()


def get_accumulator() -> WisdomAccumulator:
    """Get the module-level WisdomAccumulator instance."""
    return _accumulator


# ── CLI ──────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Wisdom Accumulator — Institutional Memory Engine"
    )
    parser.add_argument("--stats", action="store_true", help="Show accumulated wisdom statistics")
    parser.add_argument("--query", type=str, default=None, help="Search wisdom by keyword")
    parser.add_argument("--recent", type=int, default=None, help="Show N most recent entries")
    parser.add_argument("--db", type=str, default=None, help="Path to wisdom database file")
    args = parser.parse_args()

    acc = WisdomAccumulator(db_path=args.db) if args.db else WisdomAccumulator()

    print(f"\n{'='*60}")
    print(f"  🧠 Wisdom Accumulator — Institutional Memory")
    print(f"{'='*60}\n")

    if args.stats:
        stats = acc.get_stats()
        print(f"  📊 Wisdom Database Statistics")
        print(f"  {'─'*40}")
        for key, val in stats.items():
            label = key.replace("_", " ").title()
            print(f"  {label}: {val}")

    elif args.query:
        results = acc.query_wisdom(args.query)
        print(f"  🔍 Query: \"{args.query}\"")
        print(f"  Found {len(results)} matching entries\n")
        for i, entry in enumerate(results[:10], 1):
            print(f"  {i}. [{entry.get('challenge_id')}] Score: {entry.get('combined_score')}")
            print(f"     {entry.get('winning_reasoning', '')[:100]}...")
            print()

    elif args.recent is not None:
        entries = acc.get_recent(args.recent)
        print(f"  📋 Recent {len(entries)} Wisdom Entries\n")
        for i, entry in enumerate(entries, 1):
            print(f"  {i}. [{entry.get('challenge_id')}] {entry.get('ts', 'N/A')}")
            print(f"     Score: {entry.get('combined_score')} | "
                  f"Signals: +{entry.get('strong_signals', 0)} / -{entry.get('weak_signals', 0)}")
            print(f"     {entry.get('winning_reasoning', '')[:80]}...")
            print()

    else:
        parser.print_help()

    print(f"\n{'='*60}\n")
