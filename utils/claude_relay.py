import requests
import sys
import json
import logging
import sentry_sdk
from sentry_sdk.integrations.logging import LoggingIntegration

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('ClaudeRelay')

class ClaudeRelay:
    def __init__(self, webhook_url, sentry_dsn=None):
        self.webhook_url = webhook_url
        
        # Initialize Sentry if DSN is provided
        if sentry_dsn:
            sentry_logging = LoggingIntegration(
                level=logging.INFO,        # Capture info and above as breadcrumbs
                event_level=logging.ERROR  # Send errors as events
            )
            sentry_sdk.init(
                dsn=sentry_dsn,
                integrations=[sentry_logging],
                traces_sample_rate=1.0,
                environment="production"
            )
            logger.info("Sentry integration enabled.")

    def send_task(self, task):
        """
        Sends a task command to the n8n webhook.
        """
        payload = {"task": task}
        
        try:
            logger.info(f"Sending task to n8n: {task}")
            with sentry_sdk.start_transaction(op="task", name=f"run_claude_{task[:20]}"):
                response = requests.post(self.webhook_url, json=payload)
                response.raise_for_status()
                
                # Check for logic errors in response (schema dependent)
                result = response.json()
                logger.info(f"Received response: {result}")
                
                return {
                    "success": True, 
                    "data": result,
                    "trace_id": sentry_sdk.Hub.current.scope.transaction.trace_id if sentry_sdk.Hub.current.scope.transaction else None
                }

        except Exception as e:
            logger.error(f"Failed to execute task: {e}")
            # Capture exception explicitly if not handled by logging integration
            sentry_sdk.capture_exception(e)
            return {
                "success": False, 
                "error": str(e),
                "last_event_id": sentry_sdk.last_event_id()
            }

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python claude_relay.py <WEBHOOK_URL> <TASK>")
        sys.exit(1)
        
    url = sys.argv[1]
    task_input = sys.argv[2]
    
    relay = ClaudeRelay(url) # Add DSN here if hardcoding required
    print(relay.send_task(task_input))
