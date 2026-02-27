import sys
import os

# Set up paths to import bridge
BRIDGE_PATH = r"c:\Users\mpetr\My Drive (maurotgs@gmail.com)\Antigravity-AI Agents\Meta_App_Factory\Adv_Autonomous_Agent"
sys.path.append(BRIDGE_PATH)

import bridge

print(f"Current Webhook URL: {bridge.WEBHOOK_URL}")
print("\n--- TEST: Running Sentry Level 2 Healing Protocol ---")

# Run the protocol
# It should find the workflow and potentially update the URL (or keep it if it matches the ID logic)
# Note: Our current URL is the simplified one. The logic updates to the ID-based one.
# So we expect it to say "RE-ALIGNING SATELLITES" and update the URL.

try:
    healed = bridge._healing_protocol()
    print(f"\nHealing Result: {healed}")
    print(f"New Webhook URL: {bridge.WEBHOOK_URL}")
except Exception as e:
    print(f"Test Failed: {e}")
