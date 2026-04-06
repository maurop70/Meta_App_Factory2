import os
import ngrok
import time
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("expose_localhost")

def expose_service(port: int = 5041, domain: str = None):
    """
    Exposes a local port via Ngrok using fully in-code Traffic Policies for Zero-Trust.
    Requires NGROK_AUTH_TOKEN in the environment.
    """
    ngrok_token = os.getenv("NGROK_AUTH_TOKEN")
    if not ngrok_token:
        logger.error("NGROK_AUTH_TOKEN is missing. Cannot expose service.")
        return None

    logger.info(f"Initiating Ngrok Tunnel for port {port} (Region: US)...")

    # In-code Zero-Trust Traffic Policy
    # 1. Google OAuth/OIDC for general user access authentication.
    # 2. Strict Header validation to ensure only 'Phantom QA Elite' or 'Commander' can bypass or access programmatically.
    traffic_policy = {
        "on_http_request": [
            {
                "name": "Enforce Identity Signature",
                "actions": [
                    {
                        "type": "deny",
                        "config": {
                            "status_code": 403,
                            "content": "Access Denied: Invalid Pod Identity Signature. Only Phantom QA Elite or Commander allowed."
                        }
                    }
                ],
                "expressions": [
                    "req.Headers['X-Antigravity-Signature'] != 'Phantom QA Elite' && req.Headers['X-Antigravity-Signature'] != 'Commander'"
                ]
            },
            {
                "name": "Google OAuth",
                "actions": [
                    {
                        "type": "oauth",
                        "config": {
                            "provider": "google"
                        }
                    }
                ]
            }
        ]
    }

    try:
        # Define the listener with the policy
        listener = ngrok.forward(
            addr=f"localhost:{port}",
            authtoken=ngrok_token,
            region="us",
            domain=domain,
            policy=traffic_policy
        )
        
        url = listener.url()
        logger.info(f"✅ Service securely exposed at: {url}")
        logger.info(f"🔒 Traffic Policy Active: Google OAuth + Identity Signature validation")
        
        return listener
        
    except Exception as e:
        logger.error(f"Failed to expose service: {e}")
        return None

if __name__ == "__main__":
    from dotenv import load_dotenv
    # Load .env relative to this file
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    if os.path.exists(env_path):
        load_dotenv(env_path)
    
    print("\n🚀 Autonomous Service Exposure Skill")
    print("Binding port 5041 (CFO Ultimate Excel Architect). Press Ctrl+C to exit.\n")
    
    tunnel = expose_service(port=5041)
    if tunnel:
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down tunnel...")
