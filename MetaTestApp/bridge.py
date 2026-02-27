import requests
import sys
import json

# META APP: MetaTestApp
# Blueprint: gemini_reasoner
WEBHOOK_URL = "https://humanresource.app.n8n.cloud/webhook/MetaTestApp-webhook"

def call_app(payload):
    """
    Calls the N8N webhook for MetaTestApp.
    Payload should match the expectations of the gemini_reasoner blueprint.
    """
    try:
        response = requests.post(WEBHOOK_URL, json=payload, timeout=30)
        response.raise_for_status()
        # N8N might return JSON or raw text depending on 'Response Mode'
        try:
            return response.json()
        except:
            return response.text
    except Exception as e:
        print(f"Error calling MetaTestApp: {e}", file=sys.stderr)
        return None

if __name__ == "__main__":
    # Example usage for gemini_reasoner
    test_payload = {"prompt": "Hello from Meta App Factory!", "context": "Testing bridge generation"}
    print(f"Calling MetaTestApp...")
    result = call_app(test_payload)
    print(f"Result: {result}")
