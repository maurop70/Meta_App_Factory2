import requests
import sys
import json

WEBHOOK_URL = "https://humanresource.app.n8n.cloud/webhook/Resonance4-webhook"

def call_app(payload):
    try:
        response = requests.post(WEBHOOK_URL, json=payload, timeout=30)
        response.raise_for_status()
        try: return response.json()
        except: return response.text
    except Exception as e: return f"Error: {e}"

if __name__ == "__main__":
    print(call_app({"prompt": "Hello"}))
