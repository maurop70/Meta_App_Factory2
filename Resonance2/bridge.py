from auto_heal import healed_post, auto_heal, diagnose

import requests
import sys
import json

WEBHOOK_URL = "https://humanresource.app.n8n.cloud/webhook/Resonance2-webhook"

def call_app(payload):
    try:
        _v3_status = healed_post(WEBHOOK_URL, payload)

        response = type("Resp", (), {"status_code": 200 if _v3_status == "sent" else 503, "ok": _v3_status == "sent", "text": _v3_status, "json": lambda: {"status": _v3_status}})()
        response.raise_for_status()
        try: return response.json()
        except: return response.text
    except Exception as e: return f"Error: {e}"

if __name__ == "__main__":
    print(call_app({"prompt": "Hello"}))

# V3 MIGRATION COMPLETE
# V3 AUTO-HEAL ACTIVE
