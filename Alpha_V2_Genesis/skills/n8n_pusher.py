import requests
import json
import logging

# Configuration
# Webhook URL for the "Alpha Phase 3 Logic (Push Mode)" workflow
# In production, this matches the path 'alpha-decision' configured in the Webhook Node.
N8N_WEBHOOK_URL = "https://humanresource.app.n8n.cloud/webhook/alpha-decision"

logger = logging.getLogger("n8n_pusher")

def push_decision(decision_data):
    """
    Pushes the decision payload to the n8n webhook.
    """
    try:
        # BUDGET GUARD: Limit N8N executions to Mon-Tue, 9am-4pm
        import datetime
        now = datetime.datetime.now()
        is_window = (now.weekday() < 2) and (9 <= now.hour < 16)
        
        if not is_window:
            logger.info("Outside N8N Window (Mon-Tue, 9am-4pm). Skipping decision push.")
            return True # Return true to avoid error loops
            
        # Extract relevant fields for the Mauro Gate check
        payload = {
            "verdict": decision_data.get('loki_proposal', {}).get('strategy', 'UNKNOWN'),
            "rationale": decision_data.get('loki_proposal', {}).get('rationale', ''),
            "hold_value": decision_data.get('expert_opinions', {}).get('defense', {}).get('financials', {}).get('debit_close', 0.0),
            "roll_value": decision_data.get('expert_opinions', {}).get('defense', {}).get('financials', {}).get('credit_open', 0.0),
            "mmm": decision_data.get('expert_opinions', {}).get('new_trade', {}).get('mmm', 0.0),
            "timestamp": decision_data.get('market_snapshot', {}).get('timestamp', 0)
        }
        
        logger.info(f"Pushing decision to n8n: {N8N_WEBHOOK_URL}")
        response = requests.post(N8N_WEBHOOK_URL, json=payload, timeout=5)
        
        if response.status_code == 200:
            logger.info("Successfully pushed to n8n.")
            return True
        else:
            logger.error(f"Failed to push to n8n. Status: {response.status_code}")
            return False
            
    except Exception as e:
        logger.error(f"Error pushing to n8n: {e}")
        return False

if __name__ == "__main__":
    # Test Payload
    test_data = {
        "loki_proposal": {"strategy": "TEST_HOLD", "rationale": "Testing Push"},
        "expert_opinions": {
            "defense": {
                "financials": {"debit_close": 1.54, "credit_open": 1.22}
            }
        }
    }
    push_decision(test_data)
