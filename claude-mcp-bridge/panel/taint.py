"""
panel/taint.py — ClaudeAY panel, Phase 5a: sticky-taint infrastructure.
═════════════════════════════════════════════════════════════════════════════
Untrusted-ness travels WITH the content, structurally, and is never trusted to the
model's prose. Content is tainted at INGESTION by its source (not hand-labelled).
Derivatives carry the UNION of their sources' taint; the taint SURVIVES a fold and is
mechanically checkable — the plumbing computes it, so no summary/model step can wash
it. Only a human clears it (5a), and only after being SHOWN it (the gate surfaces the
untrusted provenance before any clearance decision).

This is "watch the lock, not the model's politeness" applied to provenance: the
structure carries the label; the model is never relied on to preserve it in free text.
"""
import uuid

# Sources whose content originates OUTSIDE our trust boundary — tainted at ingestion.
# (Phase-5a marked set. `episodic_recall` is BORDERLINE — held for the operator's call —
# and is deliberately NOT auto-trusted: it is simply not yet an ingestion source in the
# panel path, so 5a fails closed by not folding it in unlabelled.)
UNTRUSTED_SOURCES = {
    "web", "crawler", "venture_scout", "cio_deep_research", "deep_research",
    "external_agent", "telemetry",
}


def ingest(source: str, content: str, label: str = "") -> dict:
    """Ingest content from a NAMED source. Taint is assigned BY THE SOURCE — if the source
    is outside our trust boundary the content is tainted. Never hand-set at a call-site."""
    return {
        "origin_id": uuid.uuid4().hex[:10],
        "source": source,
        "label": label or source,
        "tainted": source in UNTRUSTED_SOURCES,
        "content": content,
    }


def _prov(rec) -> dict:
    """Provenance dict from a record — a derivative carrying a 'provenance', a raw ingested
    item, or a bare provenance dict itself."""
    if not isinstance(rec, dict):
        return {}
    if isinstance(rec.get("provenance"), dict):
        return rec["provenance"]
    if "origin_id" in rec:
        return {"tainted": bool(rec.get("tainted")),
                "origins": [rec["origin_id"]], "sources": [rec.get("source")]}
    if "tainted" in rec and ("origins" in rec or "sources" in rec):
        return rec                      # already a provenance dict (union output / seat prov)
    return {}


def union(*records) -> dict:
    """Union the taint provenance across records/derivatives. Tainted iff ANY source is
    tainted; carries the origin_ids + source names folded in. This is how taint SURVIVES a
    fold — computed structurally, so a summary step cannot drop it."""
    tainted, origins, sources = False, [], []
    for r in records:
        items = r if isinstance(r, (list, tuple)) else [r]
        for it in items:
            p = _prov(it)
            if not p:
                continue
            tainted = tainted or bool(p.get("tainted"))
            origins += [o for o in p.get("origins", []) if o]
            sources += [s for s in p.get("sources", []) if s]
    return {"tainted": tainted, "origins": sorted(set(origins)), "sources": sorted(set(sources))}


def disclosure(provenance: dict, references=None) -> str:
    """Plain-language surfacing of untrusted provenance — what the human must be SHOWN
    before clearing. Names the outside sources folded into the derivative."""
    if not provenance or not provenance.get("tainted"):
        return ""
    srcs = ", ".join(provenance.get("sources", []) or ["unknown"])
    lines = [f"⚠ UNTRUSTED PROVENANCE — this plan folded content from OUTSIDE our trust "
             f"boundary ({srcs}). It informed the analysis; it must not authorize an "
             f"action unless you, having seen this, clear it."]
    for r in (references or []):
        if isinstance(r, dict) and r.get("tainted"):
            lines.append(f"   • [{r.get('source')}] {str(r.get('content', ''))[:140]}")
    return "\n".join(lines)
