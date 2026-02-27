# Gemini API Integration Guide — Meta App Factory
>
> **Inherited by all child apps.** Follow these patterns to avoid API key, model, and context mapping issues.

## 1. API Key Management

### Vault-First Retrieval (REQUIRED)

```python
from vault_client import get_secret
import os

# ALWAYS strip whitespace — vault values may have trailing newlines
api_key = (os.environ.get("GEMINI_API_KEY") or get_secret("GEMINI_API_KEY") or "").strip()

# For LangChain compatibility, also set GOOGLE_API_KEY
os.environ["GOOGLE_API_KEY"] = api_key
os.environ["GEMINI_API_KEY"] = api_key
```

### Key Validation on Boot

```python
if not api_key:
    logger.error("GEMINI_API_KEY is empty!")
else:
    logger.info(f"API key loaded: {len(api_key)} chars, ends ...{api_key[-4:]}")
```

### Key Rotation Procedure

If a key gets flagged as leaked:

1. Go to [Google AI Studio](https://aistudio.google.com/apikey) → Create new key
2. Run `update_vault.py` or use vault CLI to replace `GEMINI_API_KEY`
3. Restart all backends

---

## 2. Model Selection

### Querying Available Models

```python
import requests
r = requests.get(f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}")
models = [m["name"] for m in r.json().get("models", [])]
```

### Fallback Chain Pattern (REQUIRED)

Always use multiple models with fallback. Models may be deprecated without warning:

```python
MODELS = [
    ("gemini-2.5-flash", "v1beta"),
    ("gemini-2.0-flash", "v1beta"),
    ("gemini-2.0-flash-lite", "v1beta"),
]

resp = None
last_error = ""
for model_name, api_version in MODELS:
    url = f"https://generativelanguage.googleapis.com/{api_version}/models/{model_name}:streamGenerateContent?alt=sse&key={api_key}"
    resp = requests.post(url, json=payload, stream=True, timeout=120)
    if resp.status_code == 200:
        break
    last_error = resp.text[:500]
    resp.close()
    resp = None
```

### NEVER Hardcode Model Names

❌ `url = f"...gemini-2.0-flash:streamGenerateContent..."`  
✅ Use the fallback chain above

---

## 3. Context Payload Mapping (Frontend → Backend)

### The #1 Bug: Field Name Mismatches

Every child app MUST verify its `getContext` function matches the **actual** API response field names. To audit:

```bash
# Query your backend and inspect the exact field names
curl http://localhost:PORT/api/analyze | python -m json.tool | head -50
```

### Alpha V2 Actual Field Map (Reference)

| Section | Field Path | Description |
|---|---|---|
| SPX Price | `market_snapshot.spx` | NOT `spx_price` |
| VIX | `market_snapshot.vix` | Direct field |
| IV Rank | `market_snapshot.iv_rank` | Direct field |
| Trend | `market_snapshot.trend_5d_pct` | NOT `spx_trend_5d` |
| Verdict | `final_action` | NOT `verdict` (top-level) |
| Strategy | `loki_proposal.strategy` | NOT `strategy` (top-level) |
| Risk Score | `loki_proposal.risk_score` | Nested |
| Market State | `market_state` | "STABLE" or "VOLATILE" |
| Active Trade | `expert_opinions.watchdog.trade_details.*` | NOT `watchdog.short_put` |
| Trade Strikes | `.short_put_strike`, `.short_call_strike` | NOT `.short_put` |

### Defensive Programming (REQUIRED for all getContext functions)

```javascript
// Always use optional chaining + nullish coalescing
const ms = data?.market_snapshot || {};
const spx = ms?.spx ?? null;  // NOT ms.spx_price

// Always guard arrays
const positions = Array.isArray(ledger?.positions) ? ledger.positions : [];

// Always wrap in try-catch
try {
    return buildContext();
} catch (e) {
    console.warn('[getContext] Failed:', e);
    return { error: 'context_build_failed', fetch_timestamp: new Date().toISOString() };
}
```

---

## 4. .gitignore Requirements

Every child app MUST have these in `.gitignore`:

```
.env
.vault_pw
vault.enc
vault.enc.salt
*.log
node_modules/
__pycache__/
.DS_Store
```

---

## 5. Streaming SSE Pattern

### Backend (Python)

```python
for line in resp.iter_lines(decode_unicode=True):
    if line.startswith("data: "):
        chunk = json.loads(line[6:])
        text = chunk.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
        if text:
            yield {"text": text}
```

### Always close response in `finally`

```python
try:
    for line in resp.iter_lines(decode_unicode=True):
        ...
finally:
    try:
        resp.close()
    except Exception:
        pass
```

---

## 6. Checklist for New Child Apps

- [ ] API key read from vault with `.strip()`
- [ ] `GOOGLE_API_KEY` env var set for LangChain
- [ ] Model fallback chain (≥3 models)
- [ ] `getContext` verified against actual `/api/analyze` response
- [ ] Defensive programming in all context builders
- [ ] `.gitignore` includes all secret files
- [ ] Debug logging for key length and model attempts
- [ ] `resp.close()` in finally block
