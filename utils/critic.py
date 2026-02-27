import requests
import time
import sys

class ArtisanCritic:
    """
    The Artisan Critic (formerly Inspector).
    Validates newly built apps before "official" handover.
    Global Quality Sync Component.
    """
    def __init__(self):
        pass

    def run_smoke_test(self, app_name, webhook_url):
        """Sends a test ping to the app's webhook."""
        print(f"--- Artisan Critic: Running Smoke Test for '{app_name}' ---")
        print(f"- Testing URL: {webhook_url}")
        
        test_payload = {
            "prompt": "PING_TEST",
            "context": "POST-BUILD_INSPECTION"
        }

        try:
            # Give N8N a moment to fully initialize the new workflow
            time.sleep(5)
            response = requests.post(webhook_url, json=test_payload, timeout=30)
            
            if response.status_code == 200:
                print(f"--- Artisan Critic: SUCCESS! App '{app_name}' is alive and responsive. ---", flush=True)
                return True
            else:
                print(f"--- Artisan Critic: WARNING! App '{app_name}' returned status {response.status_code}. ---", flush=True)
                if response.text:
                    print(f"- Feedback: {response.text[:100]}...", flush=True)
                return False
        except Exception as e:
            print(f"--- Artisan Critic: FAILED! Could not reach App '{app_name}'. Error: {e} ---", flush=True)
            return False

if __name__ == "__main__":
    # Test
    critic = ArtisanCritic()
    critic.run_smoke_test("TestApp", "https://httpbin.org/post")
