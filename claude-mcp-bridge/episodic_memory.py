"""
Episodic Memory — CLAUDE_RULES.md §13.4
----------------------------------------
Records every loop run as an episode (mandate → outcome → resolution)
and retrieves similar past episodes for injection into new mandates,
so the Architect's first hypothesis on a repeat failure is the past fix.

Store: logs/episodes.jsonl — append-only, one JSON object per line:
  {ts, trace_id, instruction, status, summary, files_changed,
   resolution, tags}

Retrieval: token-overlap scoring (IDF-weighted) over instruction +
summary + tags. Deliberately dependency-free — no embeddings service
to keep alive; at this corpus size lexical scoring is competitive.
"""

import json
import math
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

EPISODES_LOG = Path(__file__).parent / "logs" / "episodes.jsonl"

_TOKEN_RE = re.compile(r"[a-z0-9_.]{3,}")
_STOPWORDS = frozenset(
    "the and for with that this from into are was were has have had not "
    "you your our their then than when what which while where been being "
    "all any can could should would must may might will shall its per via".split()
)


def _tokens(text: str) -> list[str]:
    return [t for t in _TOKEN_RE.findall((text or "").lower())
            if t not in _STOPWORDS]


def record_episode(trace_id: str, instruction: str, status: str,
                   summary: str, files_changed: list | None = None,
                   resolution: str = "", tags: list | None = None) -> None:
    """Append one episode. Never raises — memory must not break the loop."""
    try:
        EPISODES_LOG.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "trace_id": trace_id,
            "instruction": (instruction or "")[:500],
            "status": status,
            "summary": (summary or "")[:500],
            "files_changed": (files_changed or [])[:20],
            "resolution": (resolution or "")[:500],
            "tags": tags or [],
        }
        with open(EPISODES_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass


def _load_episodes(max_episodes: int = 2000) -> list[dict]:
    if not EPISODES_LOG.exists():
        return []
    episodes = []
    try:
        for line in EPISODES_LOG.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    episodes.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except Exception:
        return []
    return episodes[-max_episodes:]


def recall_similar(instruction: str, k: int = 3,
                   min_score: float = 0.15) -> list[dict]:
    """
    Return up to k past episodes most similar to the instruction.
    Scoring: IDF-weighted token overlap, normalized by query weight.
    """
    query = set(_tokens(instruction))
    if not query:
        return []
    episodes = _load_episodes()
    if not episodes:
        return []

    # Document frequency over the corpus
    df: Counter = Counter()
    docs: list[set] = []
    for ep in episodes:
        toks = set(_tokens(
            f"{ep.get('instruction','')} {ep.get('summary','')} "
            f"{' '.join(ep.get('tags', []))}"
        ))
        docs.append(toks)
        df.update(toks)

    n = len(episodes)
    def idf(t: str) -> float:
        return math.log(1 + n / (1 + df[t]))

    query_weight = sum(idf(t) for t in query) or 1.0
    scored = []
    for ep, toks in zip(episodes, docs):
        overlap = query & toks
        if not overlap:
            continue
        score = sum(idf(t) for t in overlap) / query_weight
        if score >= min_score:
            scored.append((score, ep))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [dict(ep, _score=round(score, 3)) for score, ep in scored[:k]]


def format_recall_block(episodes: list[dict]) -> str:
    """Render recalled episodes as a mandate context block."""
    if not episodes:
        return ""
    lines = ["<PAST_EPISODES note='Similar past runs — check these resolutions "
             "before re-diagnosing from scratch'>"]
    for ep in episodes:
        lines.append(json.dumps({
            "when": ep.get("ts", "")[:10],
            "instruction": ep.get("instruction", "")[:160],
            "outcome": ep.get("status", ""),
            "summary": ep.get("summary", "")[:160],
            "resolution": ep.get("resolution", "")[:200],
        }))
    lines.append("</PAST_EPISODES>")
    return "\n".join(lines)


if __name__ == "__main__":
    import tempfile, os
    # Isolated self-test against a temp store
    _orig = EPISODES_LOG
    tmp = Path(tempfile.mkdtemp()) / "episodes.jsonl"
    EPISODES_LOG = tmp  # noqa: F811
    record_episode("t1", "Fix ImportError in loop_engine.py", "complete",
                   "Stale __pycache__ — cleared and reran", resolution="clear pycache")
    record_episode("t2", "Deploy ERP to production", "escalate",
                   "Tier 3 gate", resolution="operator approved")
    record_episode("t3", "Build SKU search endpoint", "complete",
                   "Added /api/inventory/skus/search route")
    hits = recall_similar("There is an ImportError in loop_engine when starting")
    ok1 = bool(hits) and "ImportError" in hits[0]["instruction"]
    print(f"  [{'PASS' if ok1 else 'FAIL'}] recall finds ImportError episode first")
    hits2 = recall_similar("completely unrelated quantum blockchain topic")
    ok2 = all("ImportError" not in h.get("instruction", "") or h["_score"] < 0.5 for h in hits2)
    print(f"  [{'PASS' if ok2 else 'FAIL'}] unrelated query scores low/empty ({len(hits2)} hits)")
    block = format_recall_block(hits)
    ok3 = block.startswith("<PAST_EPISODES") and "resolution" in block
    print(f"  [{'PASS' if ok3 else 'FAIL'}] recall block renders")
    print(f"\n{sum([ok1, ok2, ok3])}/3 passed")
