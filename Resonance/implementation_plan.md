# Resonance Project — Implementation Plan v2 (Architect Approved)

This plan integrates the V3 auto-heal repairs, intelligent model routing, LAN-based Google Home casting, and the interactive engagement state machine.

## User Review Required

> [!WARNING]
> - **Age Correction**: The previous draft mistakenly listed Leo's age as 9. **Leo is 16 years old** (with APD and speech delays). The persona prompts and complexity levels must be tailored to a teenager, not a young child, to avoid patronizing him.
> - **Anthropic Model**: We will target the official `claude-3-5-sonnet-latest` (or `claude-3-5-sonnet-20241022`) rather than speculative future model aliases.
> - **Chromecast HTTP Requirement**: Chromecast cannot stream raw bytes directly from Python. We must save TTS output to a temporary cache file (e.g. `uploads/tts_cache/`) and serve it via a local FastAPI HTTP server using the host's LAN IP address.

---

## 0. Build & Deploy Phases

1. **Phase 1 — Dr. Aris safe_post regression fix**: Defensively parse candidates, status codes, and safety flags to prevent any `KeyError`.
2. **Phase 2 — Model Routing & Claude Client**: Setup the classifier pass to route complex deconstruction tasks to Claude.
3. **Phase 3 — Google Home Casting (Audio Infra)**: Integrate `pychromecast` with a local TTS file server and secure endpoints.
4. **Phase 4 — Engagement Engine & Bedtime**: Deploy the initiation state machine, bedtime wind-down rules, and parent visibility logs.

---

## 1. Schema: parent_config.json

```json
{
  "pin": "1234",
  "instructions": "",
  "focus_topics": ["Math - Quadratics", "biology"],
  "vocabulary": [],
  "progress_log": [],
  "student_profile": {
    "name": "Leo",
    "age": 16,
    "hobbies_interests": ["Music", "Social Media", "telephone towers", "guitar", "drive through-fast foods"],
    "social_level": "social",
    "academic_weak_areas": [],
    "stress_indicators": [],
    "learning_style_preferences": []
  },
  "bedtime": {
    "scheduled_time": "21:30",
    "wind_down_minutes": 30,
    "child_stated_time": null,
    "last_asked_iso": null,
    "parent_hard_cap": "22:00"
  },
  "engagement": {
    "enabled": true,
    "max_initiations_per_hour": 2,
    "max_initiations_per_day": 6,
    "cooldown_after_decline_minutes": 30,
    "silence_is_decline_after_minutes": 4,
    "state": "idle",
    "cooldown_until_iso": null,
    "initiations": []
  },
  "cognitive_metrics": {
    "rolling_average_sentence_length": 0.0,
    "active_vocabulary_retention_score": 0.0,
    "quiz_accuracy_streak": 0,
    "current_conversational_level": 1,
    "level_min": 1,
    "level_max": 5,
    "parent_level_cap": 5,
    "parent_level_override": null,
    "last_level_change_iso": null,
    "level_change_cooldown_hours": 48
  }
}
```

---

## 2. Phase 1 — Dr. Aris safe_post Fix

* **The Fix**: Add `safe_post_with_response(...)` in `dr_aris_engine.py` (or as a factory wrapper) returning the raw `requests.Response`.
* **Defensive Parsing**:
  ```python
  def parse_gemini_response(response) -> dict:
      if response.status_code != 200:
          return {"status": "error", "error": f"HTTP {response.status_code}"}
      try:
          data = response.json()
      except ValueError:
          return {"status": "error", "error": "Invalid JSON"}
      
      # Safety check
      if "promptFeedback" in data and "blockReason" in data["promptFeedback"]:
          return {"status": "blocked", "reason": data["promptFeedback"]["blockReason"]}
          
      candidates = data.get("candidates", [])
      if not candidates:
          return {"status": "empty"}
          
      # Extract text
      parts = candidates[0].get("content", {}).get("parts", [])
      text = "".join(p.get("text", "") for p in parts)
      return {"status": "success", "text": text}
  ```

---

## 3. Phase 2 — Model Routing & Persona Consistency

### 3.1 Cheap Classifier Pass
* Run a fast, lightweight classifier pass on the incoming user query using the cheap `gemini-2.5-flash` model before processing:
  * *"Does answering this query require step-by-step mathematical logic or scientific deconstruction? Respond ONLY with YES or NO."*
  * If `YES` -> Route to `claude-3-5-sonnet`.
  * If `NO` -> Route to `gemini-2.5-flash`.

### 3.2 Complexity Injection
* Keep the Alex persona consistent on both models. Inject the complexity constraint dynamically:
  ```
  CONVERSATIONAL COMPLEXITY LEVEL: {level} of 5.
  Level 1 = short, simple sentences, common words.
  Level 5 = rich vocabulary, compound multi-clause sentences.
  Remain warm, encouraging, and friend-like.
  ```

---

## 4. Phase 3 — Google Home Casting (Infra)

* **TTS Cache Server**:
  * Use `gTTS` to generate speech `.mp3`.
  * Save to `uploads/tts_cache/<hash>.mp3`.
  * Expose via FastAPI: `http://<host-lan-ip>:5006/static/tts_cache/<hash>.mp3`.
* **Endpoint Authentication**:
  * Protect `/api/telemetry/screen-time` and `/api/google-home/cast` with an API token header (`X-Resonance-Token`) matched against the environment.

---

## 5. Phase 4 — Engagement Engine State Machine

* **States**: `idle` -> `awaiting_response` -> (`engaged` | `declined`) -> `cooldown` -> `idle`
* **Phone Intervention Trigger**:
  - Exclude any phone/screen time language from the prompt.
  - Alex initiates by asking about a topic Leo is interested in (from `interest_store`) or suggesting a guitar jam session.
  - If no response within 4 minutes, trigger the `declined` state and apply cooldown limits.

---

## Verification Plan

* **Automated**:
  - Run regression suites: `phantom_agent.py --app Resonance`
  - Unit test `parse_gemini_response` with mock blocked/error payloads.
* **Manual**:
  - Call `/api/telemetry/screen-time` using `Invoke-RestMethod` carrying the authorization token.
