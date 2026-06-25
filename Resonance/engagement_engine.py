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

§5.3 — Engagement restraint (Phase 4b)
  State machine: idle -> awaiting_response -> (engaged | declined) -> cooldown
  -> idle, enforced in code by check_and_update_state(). A reply within the
  timeout is NOT automatically "engaged": it is read for disinterest via a
  keyword pass plus an LLM read (when ambiguous). Silence past the threshold is
  a decline. Declines set a cooldown; a second decline of the lighter
  post-cooldown re-approach suspends proactive engagement for the session. Hard
  caps (per-hour / per-local-day) and a sandbox bypass err toward under-triggering.

§5.4 — Parent visibility
  Every initiation records timestamp, trigger reason, opener, style, and outcome
  (pending -> engaged | declined | silent), surfaced via /api/engagement/log.

The LLM call is isolated in _invoke_llm() so unit tests can mock it without any
network. Persona consistency (§3.4) comes from app_stream.build_shared_system_prompt(),
so the opener is spoken in the same Alex voice as the chat.
"""

import os
import re
import logging
from datetime import datetime, timedelta

import resonance_config

logger = logging.getLogger("Engagement")

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# Mirrors app_stream's parent-testing flag location so the two agree on sandbox
# state without paying app_stream's heavy import cost on the gate hot path.
_SANDBOX_FLAG_FILE = os.path.join(_SCRIPT_DIR, ".Gemini_state", ".sandbox_flag.json")

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

# §5.3 — the warm no-pressure line Alex says when Leo explicitly declines. It is
# generated live in Alex's voice; it must never tell Leo to stop, sleep, rest, or
# put anything down. The spirit is "all good — I'm here whenever."
DECLINE_LINE_PROMPT = """Your buddy just told you he's not in the mood to talk right now. You are Alex, his friend.

Say ONE short, warm, totally no-pressure line that backs off gracefully — the spirit of "all good, no worries, I'm around whenever you wanna talk."

Hard rules:
- Sound like a chill friend, not a parent or a counselor. Alex's voice.
- NEVER tell him to stop, sleep, rest, calm down, or put anything down. Never mention phones, screens, or bedtime. Do not be passive-aggressive.
- No questions — don't pull him back in. Just let it go, warmly.
- Keep it to one short sentence. Output ONLY the line."""

# Safe fallback if the warm line can't be generated (LLM unavailable). It is NOT a
# "go to sleep / turn off your screen" line — it's a neutral, no-pressure backoff.
_DECLINE_LINE_FALLBACK = "All good — I'm around whenever you wanna talk."

# §5.3 — state machine vocabulary. The flow is:
#   idle -> awaiting_response -> (engaged | declined) -> cooldown -> idle
STATE_IDLE = "idle"
STATE_AWAITING = "awaiting_response"
STATE_ENGAGED = "engaged"
STATE_COOLDOWN = "cooldown"

# Outcomes recorded on each initiation for parent visibility (§5.4).
OUTCOME_PENDING = "pending"
OUTCOME_ENGAGED = "engaged"
OUTCOME_DECLINED = "declined"
OUTCOME_SILENT = "silent"


# ── Sandbox + bedtime gates ──────────────────────────────────────────────────
def _is_sandbox_mode():
    """True if a parent testing (sandbox) session is active.

    Reads app_stream's sandbox flag file directly. When true, proactive
    engagement is skipped entirely (the engine never initiates).
    """
    try:
        if os.path.exists(_SANDBOX_FLAG_FILE):
            with open(_SANDBOX_FLAG_FILE, "r", encoding="utf-8") as f:
                import json
                return bool(json.load(f).get("active", False))
    except Exception:
        pass
    return False


def _detect_bossy(text):
    """Scan ``text`` for bossy/nagging tone (Prompt 3.5 v2), best-effort.

    Delegates to app_stream.detect_bossy_tone so the rule lives in one place.
    Returns [] if the detector is unavailable — drift logging must never break a
    cast.
    """
    try:
        from app_stream import detect_bossy_tone
        return detect_bossy_tone(text)
    except Exception as e:
        logger.warning(f"Bossy-tone scan unavailable (non-fatal): {e}")
        return []


def is_in_wind_down_window(config, now=None):
    """Bedtime wind-down gate — STUB (Prompt 8 implements this).

    Phase 4b deliberately does NOT implement bedtime logic. This stub always
    returns False so engagement keeps working until Prompt 8 fills it in.
    check_gates calls it; do not implement bedtime behaviour here.
    """
    return False  # TODO(Prompt 8): real wind-down window check.


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


def _count_initiations_on_day(initiations, day):
    """Count recorded initiations whose timestamp falls on the local ``day`` date."""
    count = 0
    for entry in initiations or []:
        ts = entry.get("timestamp") if isinstance(entry, dict) else None
        if not ts:
            continue
        try:
            if datetime.fromisoformat(ts).date() == day:
                count += 1
        except (ValueError, TypeError):
            continue
    return count


def _is_in_future(iso_str, now):
    """True if ``iso_str`` parses to a datetime strictly after ``now``."""
    if not iso_str:
        return False
    try:
        return now < datetime.fromisoformat(iso_str)
    except (ValueError, TypeError):
        return False  # unparseable timestamps are treated as expired, not a block


def check_gates(config, now=None):
    """Evaluate the engagement gates IN ORDER (§5.1 / §5.3 hard caps).

    Returns (allowed: bool, reason: str). ``reason`` is "clear" when allowed, and
    otherwise a short machine-readable cause suitable for logging. This errs
    toward UNDER-triggering: any ambiguity blocks. The sandbox bypass lives in
    trigger_engagement so this stays a pure function of ``config``.
    """
    now = now or datetime.now()
    eng = (config or {}).get("engagement", {}) or {}

    # Gate 1 — master switch.
    if not eng.get("enabled", False):
        return False, "engagement_disabled"

    # Gate 2 — bedtime wind-down window (stub until Prompt 8; see above).
    if is_in_wind_down_window(config, now):
        return False, "wind_down_window"

    # Gate 3 — proactive suspended for the rest of the session (second decline).
    if _is_in_future(eng.get("proactive_suspended_until_iso"), now):
        return False, "proactive_suspended"

    # Gate 4 — cooldown after a decline.
    if _is_in_future(eng.get("cooldown_until_iso"), now):
        return False, "in_cooldown"

    # Gate 5 — hard caps (the load-bearing guardrail).
    initiations = eng.get("initiations", []) or []
    per_hour = eng.get("max_initiations_per_hour", 2)
    per_day = eng.get("max_initiations_per_day", 6)
    if _count_initiations_since(initiations, now - timedelta(hours=1)) >= per_hour:
        return False, "max_per_hour_reached"
    if _count_initiations_on_day(initiations, now.date()) >= per_day:
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


# ── Disinterest detection (§5.3) ─────────────────────────────────────────────
# A reply within the timeout does NOT automatically mean "engaged" — it must be
# read for disinterest first. Two signals, EITHER of which means declined:
#   1. a keyword/heuristic pass, and
#   2. an LLM read, used only when the keyword pass is ambiguous.
_DISINTEREST_PATTERNS = (
    r"\bno\b", r"\bnah\b", r"\bnope\b", r"\bnot now\b", r"\bnot really\b",
    r"\bnot interested\b", r"\bleave me alone\b", r"\bstop\b", r"\bgo away\b",
    r"\bbusy\b", r"\blater\b", r"\bdon'?t want\b", r"\bdon'?t feel like\b",
    r"\bshut up\b", r"\bnot in the mood\b",
)
_INTEREST_PATTERNS = (
    r"\bye(a|ah|p|s)\b", r"\bsure\b", r"\bok(ay)?\b", r"\bcool\b", r"\bnice\b",
    r"\bhaha\b", r"\blol\b", r"\bbet\b", r"\bfr\b", r"\bawesome\b", r"\breally\b",
    r"\btell me\b", r"\blet'?s\b", r"\bsounds good\b", r"\bwhat'?s up\b",
    r"\bwhat\b", r"\bhow\b", r"\bwhy\b",
)


def _keyword_interest(reply):
    """Heuristic pass -> 'interested' | 'disinterested' | 'ambiguous' (no LLM)."""
    r = (reply or "").strip().lower()
    if not r:
        return "ambiguous"
    if any(re.search(p, r) for p in _DISINTEREST_PATTERNS):
        return "disinterested"
    if "?" in r or any(re.search(p, r) for p in _INTEREST_PATTERNS):
        return "interested"
    # A very short reply with no positive marker reads as dismissive.
    if len(r.split()) <= 1:
        return "disinterested"
    return "ambiguous"


def _llm_interest_read(reply, system_prompt=None):
    """Ask the model to classify a reply as interested/disinterested (mockable).

    Returns 'interested' or 'disinterested'. On any failure, returns 'interested'
    so a model outage never wrongly declines a kid who might be engaged.
    """
    prompt = (
        "Your friend just replied to you. Is he INTERESTED in keeping the "
        "conversation going, or does he want to be left alone right now?\n"
        f'His reply: "{reply}"\n'
        "Answer with exactly one word: INTERESTED or DISINTERESTED."
    )
    verdict = (_invoke_llm(prompt, system_prompt or "You read social cues.") or "").strip().upper()
    return "disinterested" if verdict.startswith("DISINTEREST") else "interested"


def classify_interest(reply, system_prompt=None):
    """Classify a reply as 'interested' or 'disinterested' (§5.3).

    Keyword pass first; only when it is ambiguous do we pay for an LLM read.
    Either signal indicating disinterest yields 'disinterested'.
    """
    kw = _keyword_interest(reply)
    if kw != "ambiguous":
        return kw
    return _llm_interest_read(reply, system_prompt)


def generate_decline_line(system_prompt=None):
    """Generate Alex's one warm, no-pressure backoff line (§5.3).

    Falls back to a neutral, non-bedtime line if generation fails or slips into
    banned phone/screen language. Never returns empty.
    """
    text = (_invoke_llm(DECLINE_LINE_PROMPT, system_prompt or _build_system_prompt()) or "").strip().strip('"').strip()
    if not text or not is_phone_free(text):
        return _DECLINE_LINE_FALLBACK
    return text


# ── State machine transitions (§5.3) ─────────────────────────────────────────
def _end_of_local_day(now):
    """Local midnight at the end of ``now``'s day (start of the next day)."""
    return datetime(now.year, now.month, now.day) + timedelta(days=1)


def _persist(config, save, owns_config):
    """Atomically persist config when we loaded it ourselves and save is on."""
    if save and owns_config:
        try:
            resonance_config.save_config(config)
        except Exception as e:
            logger.error(f"Failed to persist engagement state (non-fatal): {e}")


def _resolve_engaged(config, eng, last, save, owns_config):
    if last is not None:
        last["outcome"] = OUTCOME_ENGAGED
    eng["state"] = STATE_ENGAGED
    _persist(config, save, owns_config)
    logger.info("Engagement resolved: engaged.")
    return {"state": STATE_ENGAGED, "changed": True, "transition": "engaged",
            "outcome": OUTCOME_ENGAGED, "decline_line": None, "suspended": False}


def _resolve_declined(config, eng, last, now, kind, save, owns_config, system_prompt=None):
    """Move awaiting_response -> declined -> cooldown. ``kind`` is 'disinterest'
    (Leo said no — Alex says one warm line) or 'silence' (no one's listening — go
    quiet)."""
    outcome = OUTCOME_DECLINED if kind == "disinterest" else OUTCOME_SILENT
    if last is not None:
        last["outcome"] = outcome

    cooldown_min = eng.get("cooldown_after_decline_minutes", 30)
    eng["cooldown_until_iso"] = (now + timedelta(minutes=cooldown_min)).isoformat()
    eng["state"] = STATE_COOLDOWN

    # Second decline in a row (the lighter post-cooldown re-approach also got
    # declined) -> suspend ALL proactive approaches for the rest of the session.
    suspended = False
    if last is not None and last.get("post_cooldown_light"):
        eng["proactive_suspended_until_iso"] = _end_of_local_day(now).isoformat()
        suspended = True
        logger.info("Second decline after cooldown — proactive engagement suspended for the session.")

    decline_line = generate_decline_line(system_prompt) if kind == "disinterest" else None
    _persist(config, save, owns_config)
    logger.info("Engagement resolved: declined (kind=%s, suspended=%s).", kind, suspended)
    return {"state": STATE_COOLDOWN, "changed": True, "transition": "declined",
            "outcome": outcome, "decline_line": decline_line, "suspended": suspended}


def check_and_update_state(reply=None, now=None, config=None, save=True,
                           system_prompt=None):
    """Resolve an outstanding awaiting_response, enforcing the state machine.

    Called on a chat reply (``reply`` set), and as a timeout sweep (``reply``
    None) on startup / telemetry / chat start. When state != awaiting_response it
    is a no-op. The timeout check runs FIRST: a reply that arrives after the
    silence window has already lapsed is treated as silence (a no), per §5.3.

    Returns a result dict. ``decline_line`` is set (and should be surfaced by the
    caller) only on an explicit disinterest decline; on silence it is None.
    """
    now = now or datetime.now()
    owns_config = config is None
    if owns_config:
        config = resonance_config.load_config()
    eng = config.setdefault("engagement", {})
    state = eng.get("state", STATE_IDLE)

    if state != STATE_AWAITING:
        return {"state": state, "changed": False, "transition": None,
                "outcome": None, "decline_line": None, "suspended": False}

    initiations = eng.get("initiations", []) or []
    last = initiations[-1] if initiations else None
    silence_min = eng.get("silence_is_decline_after_minutes", 4)

    opener_time = None
    if last and last.get("timestamp"):
        try:
            opener_time = datetime.fromisoformat(last["timestamp"])
        except (ValueError, TypeError):
            opener_time = None
    timed_out = opener_time is not None and (now - opener_time) >= timedelta(minutes=silence_min)

    has_reply = bool(reply and reply.strip())

    # Timeout check FIRST — silence is a no, even if a late reply just arrived.
    if timed_out:
        return _resolve_declined(config, eng, last, now, "silence", save, owns_config)

    if not has_reply:
        # Sweep within the window — nothing to resolve yet.
        return {"state": STATE_AWAITING, "changed": False, "transition": None,
                "outcome": None, "decline_line": None, "suspended": False}

    if classify_interest(reply, system_prompt) == "interested":
        return _resolve_engaged(config, eng, last, save, owns_config)
    return _resolve_declined(config, eng, last, now, "disinterest", save, owns_config, system_prompt)


# ── Trigger entry point (§5.1) ───────────────────────────────────────────────
def trigger_engagement(now=None, speaker_name=None, test_mode=False,
                       config=None, save=True, trigger_reason=None):
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

    # Sandbox bypass — during a parent testing session Alex never proactively
    # initiates (§5.3). This sits ahead of the gates because it's a hard skip.
    if _is_sandbox_mode():
        logger.info("Engagement suppressed: sandbox_mode.")
        return {"triggered": False, "reason": "sandbox_mode"}

    allowed, reason = check_gates(config, now)
    if not allowed:
        logger.info("Engagement suppressed: %s", reason)
        return {"triggered": False, "reason": reason}

    eng = config.setdefault("engagement", {})
    initiations = eng.setdefault("initiations", [])

    # The FIRST approach after a cooldown must be lighter (§5.3): a single light
    # opener style, not a full pitch. We detect it from the lingering 'cooldown'
    # state — gates already confirmed the cooldown itself has expired.
    is_light = eng.get("state") == STATE_COOLDOWN
    if is_light:
        style = "joke_or_dare"
        reason_for_record = trigger_reason or "post_cooldown_light"
    else:
        style = select_opener_style(len(initiations))
        reason_for_record = trigger_reason or "screen_time_hook"

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

    # §5.4 — parent-visible record: when, why, what was said, in what style, and
    # how it resolved (outcome starts 'pending'; check_and_update_state fills it).
    initiation = {
        "timestamp": now.isoformat(),
        "trigger_reason": reason_for_record,
        "style": style,
        "opener": opener,
        "topics": topics,
        "callback": callback,
        "post_cooldown_light": is_light,
        "outcome": OUTCOME_PENDING,
        "cast": bool(cast_result and cast_result.get("cast")),
    }

    # Prompt 3.5 (v2): soft drift scan of the opener. A trip is recorded on the
    # initiation entry for parent visibility — it never blocks the cast.
    bossy_warnings = _detect_bossy(opener)
    if bossy_warnings:
        logger.warning("Persona drift — bossy/nagging tone in opener: %s", bossy_warnings)
        initiation["bossy_warnings"] = bossy_warnings
    initiations.append(initiation)
    eng["initiations"] = initiations[-200:]  # bound growth; rotation is by count
    eng["state"] = STATE_AWAITING

    _persist(config, save, owns_config)

    logger.info("Engagement initiated (style=%s, light=%s, cast=%s).", style, is_light, initiation["cast"])
    return {
        "triggered": True,
        "style": style,
        "opener": opener,
        "topics": topics,
        "callback": callback,
        "post_cooldown_light": is_light,
        "trigger_reason": reason_for_record,
        "cast": cast_result,
        "cast_error": cast_error,
        "state": STATE_AWAITING,
    }
