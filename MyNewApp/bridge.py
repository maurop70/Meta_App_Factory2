import requests
import sys
import json

# META APP: MyNewApp
WEBHOOK_URL = "https://humanresource.app.n8n.cloud/webhook/MyNewApp-webhook"

def call_app(payload):
    try:
        response = requests.post(WEBHOOK_URL, json=payload)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"Error calling MyNewApp: {e}", file=sys.stderr)
        return None

if __name__ == "__main__":
    # Example usage
    test_payload = {"prompt": "Hello from Meta App Factory!", "context": "Testing bridge generation"}
    result = call_app(test_payload)
    print(f"Result: {result}")
