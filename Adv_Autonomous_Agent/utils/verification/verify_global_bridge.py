import sys
import os

# Set up paths to import global bridge
BRIDGE_PATH = r"c:\Users\mpetr\My Drive (maurotgs@gmail.com)\Antigravity-AI Agents\gemini-n8n"
sys.path.append(BRIDGE_PATH)

import bridge

print(f"Default Webhook URL: {bridge.N8N_WEBHOOK_URL}")
print("\n--- TEST: Running Global Bridge Healing Protocol ---")

try:
    # Trigger healing
    healed = bridge._healing_protocol()
    print(f"\nHealing Result: {healed}")
    print(f"New Webhook URL: {bridge.N8N_WEBHOOK_URL}")
except Exception as e:
    print(f"Test Failed: {e}")
