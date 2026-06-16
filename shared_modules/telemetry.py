"""Centralized cost-tracking telemetry for the MAF ecosystem.

Records LLM token usage to a local SQLite DB (data/maf_telemetry.db) and exposes
aggregate statistics. Self-contained: importing this module ensures the schema
exists, so api.py only needs to import it and expose the HTTP endpoints.
"""
import os
import sqlite3
import asyncio
import functools
from contextlib import closing

_DIR = os.path.dirname(os.path.abspath(__file__))
_DATA_DIR = os.path.join(os.path.dirname(_DIR), "data")
DB_PATH = os.path.join(_DATA_DIR, "maf_telemetry.db")

# Per-model price in USD per 1,000 tokens as (input, output). Unknown -> (0, 0).
# Estimates only; tokens in the DB are the source of truth.
PRICING = {
    "gemini-2.5-pro":    (0.00125, 0.01000),
    "gemini-2.5-flash":  (0.00030, 0.00250),
    "claude-opus-4-8":   (0.00500, 0.02500),
    "claude-sonnet-4-6": (0.00300, 0.01500),
    "claude-haiku-4-5":  (0.00100, 0.00500),
}


def _connect():
    os.makedirs(_DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create the token_usage table if it does not exist (idempotent)."""
    with closing(_connect()) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS token_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                app_id VARCHAR NOT NULL,
                model_name VARCHAR NOT NULL,
                input_tokens INTEGER NOT NULL,
                output_tokens INTEGER NOT NULL,
                total_tokens INTEGER NOT NULL
            )
            """
        )
        conn.commit()


def _cost(model_name, input_tokens, output_tokens):
    pin, pout = PRICING.get(model_name, (0.0, 0.0))
    return round((input_tokens / 1000.0) * pin + (output_tokens / 1000.0) * pout, 6)


def record_usage(app_id, model_name, input_tokens, output_tokens):
    """Persist one usage record. Returns the stored row plus an estimated cost."""
    input_tokens = int(input_tokens or 0)
    output_tokens = int(output_tokens or 0)
    total = input_tokens + output_tokens
    with closing(_connect()) as conn:
        conn.execute(
            "INSERT INTO token_usage (app_id, model_name, input_tokens, output_tokens, total_tokens) "
            "VALUES (?, ?, ?, ?, ?)",
            (str(app_id or "unknown"), str(model_name or "unknown"),
             input_tokens, output_tokens, total),
        )
        conn.commit()
    return {
        "app_id": str(app_id or "unknown"),
        "model_name": str(model_name or "unknown"),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total,
        "cost_usd": _cost(model_name, input_tokens, output_tokens),
    }


def get_stats():
    """Aggregate usage by app and by model, with estimated cost and totals."""
    with closing(_connect()) as conn:
        rows = conn.execute(
            "SELECT app_id, model_name, "
            "SUM(input_tokens) AS i, SUM(output_tokens) AS o, "
            "SUM(total_tokens) AS t, COUNT(*) AS n "
            "FROM token_usage GROUP BY app_id, model_name"
        ).fetchall()

    by_app, by_model = {}, {}
    totals = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "cost_usd": 0.0, "calls": 0}

    def _bump(bucket, key, r, cost):
        b = bucket.setdefault(key, {"input_tokens": 0, "output_tokens": 0,
                                    "total_tokens": 0, "cost_usd": 0.0, "calls": 0})
        b["input_tokens"] += r["i"]
        b["output_tokens"] += r["o"]
        b["total_tokens"] += r["t"]
        b["cost_usd"] = round(b["cost_usd"] + cost, 6)
        b["calls"] += r["n"]

    for r in rows:
        cost = _cost(r["model_name"], r["i"], r["o"])
        _bump(by_app, r["app_id"], r, cost)
        _bump(by_model, r["model_name"], r, cost)
        totals["input_tokens"] += r["i"]
        totals["output_tokens"] += r["o"]
        totals["total_tokens"] += r["t"]
        totals["cost_usd"] = round(totals["cost_usd"] + cost, 6)
        totals["calls"] += r["n"]

    def _flatten(bucket):
        return [dict(name=k, **v) for k, v in
                sorted(bucket.items(), key=lambda kv: kv[1]["total_tokens"], reverse=True)]

    return {"by_app": _flatten(by_app), "by_model": _flatten(by_model), "totals": totals}


def _extract_usage(result):
    """Best-effort token extraction from common LLM response shapes."""
    um = getattr(result, "usage_metadata", None)  # google.generativeai
    if um is not None:
        return (int(getattr(um, "prompt_token_count", 0) or 0),
                int(getattr(um, "candidates_token_count", 0) or 0))
    usage = getattr(result, "usage", None)  # anthropic-style
    if usage is not None:
        return (int(getattr(usage, "input_tokens", 0) or 0),
                int(getattr(usage, "output_tokens", 0) or 0))
    if isinstance(result, dict):
        u = result.get("usage") or result.get("usage_metadata") or {}
        return (int(u.get("input_tokens") or u.get("prompt_token_count") or 0),
                int(u.get("output_tokens") or u.get("candidates_token_count") or 0))
    return (0, 0)


def _extract_model(result, default="unknown"):
    m = getattr(result, "model", None)
    if not m and isinstance(result, dict):
        m = result.get("model")
    return m or default


def track_operational_cost(app_id, model_name=None):
    """Decorator that records the token usage of a wrapped LLM call.

    Wraps a function that returns an LLM response; after it returns, the
    input/output tokens and model name are extracted (Gemini ``usage_metadata``
    or Anthropic ``usage``) and written to maf_telemetry.db. Recording failures
    never break the wrapped call. For full control, call ``record_usage()``
    directly. Works on both sync and async functions.
    """
    def decorator(fn):
        @functools.wraps(fn)
        def sync_wrapper(*args, **kwargs):
            result = fn(*args, **kwargs)
            try:
                i, o = _extract_usage(result)
                if i or o:
                    record_usage(app_id, model_name or _extract_model(result), i, o)
            except Exception:
                pass
            return result

        @functools.wraps(fn)
        async def async_wrapper(*args, **kwargs):
            result = await fn(*args, **kwargs)
            try:
                i, o = _extract_usage(result)
                if i or o:
                    record_usage(app_id, model_name or _extract_model(result), i, o)
            except Exception:
                pass
            return result

        return async_wrapper if asyncio.iscoroutinefunction(fn) else sync_wrapper

    return decorator


# Ensure the schema exists as soon as the module is imported.
try:
    init_db()
except Exception:
    pass
