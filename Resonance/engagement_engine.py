"""
engagement_engine.py — Plan v2 §5.1 / §5.2: intent-based engagement trigger.

The screen-time hook carries NO words. It fires this engine with context + a
goal ("start a friendly conversation right now"); Alex generates the opener live.

§5.1 — Gate logic + state machine
  On a trigger the engine checks gates IN ORDER and does nothing (logging why)
  if any fails:
    1. engagement.enabled?
    2. bedtime wind-down window?  (TODO — Prompt 8's is_in_wind_down_window())
    3. in cooldown?  (engagement.cooldown_until_iso)
    4. over max_initiations_per_hour / per_day?
  If clear it assembles 1-2 interest topics + 1 recent callback from
  interest_store, picks a ROTATING opener style, generates the opener, casts it
  via speak_to_room, records the initiation, and sets state to awaiting_response.

§5.2 — Opener generation
  The opener is generated live from OPENER_PROMPT_TEMPLATE. It must NEVER mention
  phones, screens, or screen time, and the STYLE rotates (not just the words).

The LLM call is isolated in _invoke_llm() so unit tests can mock it without any
network. Persona consistency (§3.4) comes from app_stream.build_shared_system_prompt(),
so the opener is spoken in the same Alex voice as the chat.
"""

import logging
from datetime import datetime, timedelta

import resonance_config

logger = logging.getLogger("Engagement")

# §5.2 — rotating opener styles. The STYLE rotates per initiation, not just the
# wording, so Alex never feels like a stuck script.
OPENER_STYLES = [
    "curious_question",
    "i_was_thinking",
    "callback",
    "joke_or_dare",
    "cool_fact",
]

_STYLE_HINTS = {
    "curious_question": "ask him something you're genuinely curious about, tied to what he's into",
    "i_was_thinking": "open with a thought that just popped into your head, like 'yo I was just thinking...'",
    "callback": "pick back up something you two talked about recently",
    "joke_or_dare": "open with a light joke, a playful dare, or a silly little challenge",
    "cool_fact": "drop one surprising, cool fact tied to something he likes",
}

# Defensive guard: an opener must never reference phones / screens / screen time.
# Used both as an instruction in the prompt and as a post-generation check.
_BANNED_SUBSTRINGS = (
    "phone", "screen", "screen time", "screen-time", "device", "scroll",
    "get off your", "put it down", "too much time",
)

# §5.2 — the EXACT opener-generation prompt. {style}/{style_hint} rotate; the
# topics/callback are woven in only where they fit. Phones are hard-banned.
OPENER_PROMPT_TEMPLATE = """You are Alex, texting your 16-year-old buddy out of the blue, right now, because you genuinely feel like talking to him — like a real friend reaching out. You are NOT a teacher, a tutor, an app, or a reminder.

Write exactly ONE short opener (1-2 sentences, max) to kick off a conversation.

Opener style for THIS message: {style} — {style_hint}.

Things you can pull from (use what fits naturally — do NOT force all of it in):
- Stuff he's into: {topics}
- Something you two talked about recently you could call back to: {callback}

Hard rules:
- Sound like a real friend texting. Warm, casual, Alex's voice. Energy is good.
- NEVER mention phones, screens, screen time, scrolling, devices, or "getting off" anything. Not even subtly. This is non-negotiable.
- Don't sound like a lesson or a check-in. No "how's studying going", no "let's get back to work".
- Keep it SHORT and punchy. One thought.
- Output ONLY the opener text itself — no quotes, no labels, no explanation."""


# ── Material assembly ────────────────────────────────────────────────────────
def _coerce_topic(entry):
    """Normalize an interest_store topic entry (str or dict) to a clean string."""
    if isinstance(entry, str):
        return entry.strip()
    if isinstance(entry, dict):
        for key in ("topic", "name", "title", "text"):
            val = entry.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
    return str(entry).strip()


def _select_material(interest_store):
    """Assemble 1-2 topics + 1 recent callback from interest_store.

    Takes the most recent entries (tail of each list). Returns (topics, callback)
    where topics is a list of up to 2 strings and callback is a string or None.
    """
    interest_store = interest_store or {}
    raw_topics = interest_store.get("topics") or []
    topics = [t for t in (_coerce_topic(t) for t in raw_topics[-2:]) if t]

    raw_callbacks = interest_store.get("recent_callbacks") or []
    callback = None
    for entry in reversed(raw_callbacks):
        candidate = _coerce_topic(entry)
        if candidate:
            callback = candidate
            break
    return topics, callback


# ── Gate logic (§5.1) ────────────────────────────────────────────────────────
def _count_initiations_since(initiations, cutoff):
    """Count recorded initiations whose timestamp is at or after ``cutoff``."""
    count = 0
    for entry in initiations or []:
        ts = entry.get("timestamp") if isinstance(entry, dict) else None
        if not ts:
            continue
        try:
            if datetime.fromisoformat(ts) >= cutoff:
                count += 1
        except (ValueError, TypeError):
            continue
    return count


def check_gates(config, now=None):
    """Evaluate the engagement gates IN ORDER (§5.1).

    Returns (allowed: bool, reason: str). ``reason`` is "clear" when allowed, and
    otherwise a short machine-readable cause suitable for logging.
    """
    now = now or datetime.now()
    eng = (config or {}).get("engagement", {}) or {}

    # Gate 1 — master switch.
    if not eng.get("enabled", False):
        return False, "engagement_disabled"

    # Gate 2 — bedtime wind-down window.
    # TODO(Prompt 8): once the bedtime module lands is_in_wind_down_window(),
    # gate here, e.g.:
    #     from bedtime import is_in_wind_down_window
    #     if is_in_wind_down_window(config, now):
    #         return False, "wind_down_window"
    # Until then this gate is a no-op so engagement still works pre-Prompt-8.

    # Gate 3 — cooldown after a decline.
    cooldown_until = eng.get("cooldown_until_iso")
    if cooldown_until:
        try:
            if now < datetime.fromisoformat(cooldown_until):
                return False, "in_cooldown"
        except (ValueError, TypeError):
            pass  # unparseable cooldown is treated as expired, not a hard block

    # Gate 4 — rate limits (rolling windows).
    initiations = eng.get("initiations", []) or []
    per_hour = eng.get("max_initiations_per_hour", 2)
    per_day = eng.get("max_initiations_per_day", 6)
    if _count_initiations_since(initiations, now - timedelta(hours=1)) >= per_hour:
        return False, "max_per_hour_reached"
    if _count_initiations_since(initiations, now - timedelta(days=1)) >= per_day:
        return False, "max_per_day_reached"

    return True, "clear"


def select_opener_style(initiation_count):
    """Pick the rotating opener style based on how many initiations came before."""
    return OPENER_STYLES[initiation_count % len(OPENER_STYLES)]


def is_phone_free(text):
    """True if ``text`` is free of any phone / screen-time language (§5.2)."""
    if not text:
        return False
    lowered = text.lower()
    return not any(banned in lowered for banned in _BANNED_SUBSTRINGS)


# ── Opener generation (§5.2) ─────────────────────────────────────────────────
def _invoke_llm(user_prompt, system_prompt):
    """Generate text from Claude (non-streaming join). Isolated for mockability.

    Reuses the shared Anthropic client + secret resolution so the opener is spoken
    in the exact same Alex voice as the chat. Returns the text, or "" on failure.
    """
    try:
        import app_stream
        from model_router_v3 import IntelligentModelRouter

        api_key = IntelligentModelRouter._get_secret("ANTHROPIC_API_KEY")
        if not api_key:
            logger.warning("No ANTHROPIC_API_KEY available; cannot generate opener.")
            return ""
        model = IntelligentModelRouter._resolve_deep_model()
        chunks = list(
            app_stream.stream_anthropic(
                user_prompt, system_prompt, [], model, api_key, max_tokens=120
            )
        )
        return "".join(chunks).strip()
    except Exception as e:  # network / auth / import — never raise into the engine
        logger.error(f"Opener LLM call failed: {e}")
        return ""


def _build_system_prompt():
    """Build the shared Alex persona system prompt (best-effort)."""
    try:
        import app_stream
        return app_stream.build_shared_system_prompt()
    except Exception as e:
        logger.warning(f"Falling back to bare persona for opener ({e}).")
        return "You are Alex, a warm, upbeat 16-year-old friend. Never break character."


def generate_opener(style, topics, callback, system_prompt=None):
    """Render OPENER_PROMPT_TEMPLATE for ``style`` and generate the opener text.

    Returns the opener string, or "" if generation fails or yields phone language.
    """
    style_hint = _STYLE_HINTS.get(style, _STYLE_HINTS["curious_question"])
    topics_str = ", ".join(topics) if topics else "(nothing specific — keep it open and friendly)"
    callback_str = callback or "(nothing recent — skip the callback)"

    user_prompt = OPENER_PROMPT_TEMPLATE.format(
        style=style, style_hint=style_hint, topics=topics_str, callback=callback_str
    )
    if system_prompt is None:
        system_prompt = _build_system_prompt()

    text = (_invoke_llm(user_prompt, system_prompt) or "").strip().strip('"').strip()
    if not text:
        logger.warning("Opener generation returned empty text.")
        return ""
    if not is_phone_free(text):
        # The prompt hard-bans this, but never cast an opener that slipped through.
        logger.warning("Opener mentioned phones/screens; discarding (style=%s).", style)
        return ""
    return text


# ── Trigger entry point (§5.1) ───────────────────────────────────────────────
def trigger_engagement(now=None, speaker_name=None, test_mode=False,
                       config=None, save=True):
    """Fire the engagement engine. This is the body behind the screen-time hook.

    Checks the gates in order; if clear, generates a rotating friend-style opener,
    casts it via speak_to_room, records the initiation, and moves the state machine
    to ``awaiting_response``.

    Returns a result dict; ``triggered`` is False (with a ``reason``) when a gate
    blocks or generation fails.
    """
    now = now or datetime.now()
    owns_config = config is None
    if owns_config:
        config = resonance_config.load_config()

    allowed, reason = check_gates(config, now)
    if not allowed:
        logger.info("Engagement suppressed: %s", reason)
        return {"triggered": False, "reason": reason}

    eng = config.setdefault("engagement", {})
    initiations = eng.setdefault("initiations", [])

    style = select_opener_style(len(initiations))
    topics, callback = _select_material(config.get("interest_store"))

    opener = generate_opener(style, topics, callback)
    if not opener:
        logger.info("Engagement aborted: opener generation produced no usable text.")
        return {"triggered": False, "reason": "opener_generation_failed", "style": style}

    # Cast the opener. A cast failure must not lose the recorded initiation, so we
    # record either way but report the cast outcome.
    cast_result = None
    cast_error = None
    try:
        import google_home_client as ghc
        cast_result = ghc.speak_to_room(opener, speaker_name, test_mode=test_mode)
    except Exception as e:
        cast_error = str(e)
        logger.error(f"Engagement cast failed (initiation still recorded): {e}")

    initiation = {
        "timestamp": now.isoformat(),
        "style": style,
        "opener": opener,
        "topics": topics,
        "callback": callback,
        "cast": bool(cast_result and cast_result.get("cast")),
    }
    initiations.append(initiation)
    eng["initiations"] = initiations[-200:]  # bound growth; rotation is by count
    eng["state"] = "awaiting_response"

    if save and owns_config:
        try:
            resonance_config.save_config(config)
        except Exception as e:
            logger.error(f"Failed to persist engagement state (non-fatal): {e}")

    logger.info("Engagement initiated (style=%s, cast=%s).", style, initiation["cast"])
    return {
        "triggered": True,
        "style": style,
        "opener": opener,
        "topics": topics,
        "callback": callback,
        "cast": cast_result,
        "cast_error": cast_error,
        "state": "awaiting_response",
    }
