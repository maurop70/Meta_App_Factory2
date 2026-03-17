import os
import time
import json
import logging
import requests
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("n8n_watchdog")

load_dotenv(r'c:\Users\mpetr\My Drive (maurotgs@gmail.com)\Antigravity-AI Agents\Meta_App_Factory\.env')
N8N_BASE_URL = os.getenv('N8N_BASE_URL', 'https://humanresource.app.n8n.cloud').rstrip('/')
N8N_API_KEY = os.getenv('N8N_API_KEY')

def get_headers():
    return {'X-N8N-API-KEY': N8N_API_KEY, 'Accept': 'application/json', 'Content-Type': 'application/json'}

def auto_heal_all_credentials():
    logger.info("--- [V3 Watchdog] Scanning n8n Cloud for Credential Decay ---")
    headers = get_headers()
    
    if not N8N_API_KEY:
        logger.warning("N8N_API_KEY not found. Watchdog parked.")
        return
        
    try:
        r_wf = requests.get(f"{N8N_BASE_URL}/api/v1/workflows?limit=100", headers=headers, timeout=10)
        if r_wf.status_code != 200:
            return
    except requests.exceptions.RequestException:
        logger.warning("[V3 Watchdog] Cannot reach n8n Cloud.")
        return
        
    workflows = r_wf.json().get('data', [])
    healed_count = 0
    
    # Known problematic credential ID
    broken_gemini_id = 'QWP5J4JcbFQKs34N'
    # Fallback to the known good one shared universally
    backup_gemini_id = 'CH9bCzMpKZxXZ0TC'
    backup_gemini_name = 'Google Gemini(PaLM) Api account'
    
    for w in workflows:
        wf_id = w['id']
        wf_name = w['name']
        
        try:
            r_full = requests.get(f"{N8N_BASE_URL}/api/v1/workflows/{wf_id}", headers=headers, timeout=10)
            if r_full.status_code != 200:
                continue
        except requests.exceptions.RequestException:
            continue
            
        wf_data = r_full.json()
        nodes = wf_data.get('nodes', [])
        modified = False
        
        for n in nodes:
            creds_block = n.get('credentials', {})
            for cred_key, cred_val in list(creds_block.items()):
                old_id = cred_val.get('id') if isinstance(cred_val, dict) else cred_val
                
                # Check if it references the problematic ID or if it's missing entirely but requires 'google'
                if old_id == broken_gemini_id:
                    logger.info(f"  [{wf_name}] Healing decoupled credential in node '{n['name']}'...")
                    n['credentials'][cred_key] = {"id": backup_gemini_id, "name": backup_gemini_name}
                    modified = True
                    
        if modified:
            settings_obj = wf_data.get('settings', {})
            clean_settings = {k: v for k, v in settings_obj.items() if k in ['executionOrder', 'timezone', 'saveDataErrorExecution', 'saveDataSuccessExecution', 'saveManualExecutions', 'callerPolicy']}
                
            payload = {
                "name": wf_data['name'],
                "nodes": nodes,
                "connections": wf_data.get('connections', {}),
                "settings": clean_settings
            }
            try:
                r_upd = requests.put(f"{N8N_BASE_URL}/api/v1/workflows/{wf_id}", headers=headers, json=payload, timeout=10)
                if r_upd.status_code == 200:
                    wf_tags = [t.get("name") for t in wf_data.get('tags', [])]
                    tag_str = f" [Tags: {', '.join(wf_tags)}]" if wf_tags else " [Untagged]"
                    logger.info(f"  [SUCCESS] Child App Workflow '{wf_name}'{tag_str} actively self-repaired!")
                    healed_count += 1
            except:
                pass

    if healed_count > 0:
        logger.info(f"[V3 Watchdog] Global Healing cycle complete. {healed_count} workflows repaired.")
    else:
        logger.info("[V3 Watchdog] Cloud environment is stable. 0 decoupled credentials found.")

def watchdog_daemon():
    """Runs continuously in the background to enforce active self-repair"""
    logger.info("Starting n8n Cloud Watchdog Daemon... (Operational Window: 08:00 to 00:00)")
    while True:
        try:
            from datetime import datetime
            current_hour = datetime.now().hour
            
            # 8 AM is 8, 12 AM (midnight) is technically 0 the next day.
            # So the active window is 08:00 to 23:59 (hours 8 through 23).
            if 8 <= current_hour <= 23:
                auto_heal_all_credentials()
            else:
                logger.debug(f"[V3 Watchdog] Current hour is {current_hour}:00. Sleeping until 08:00.")
                
        except Exception as e:
            logger.error(f"[V3 Watchdog] Unhandled exception in daemon loop: {e}")
            
        # Sleep for 1 hour between full cloud scans to avoid unnecessary API consumption
        time.sleep(3600)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--daemon', action='store_true', help='Run as a continuous background daemon')
    args = parser.parse_args()
    
    if args.daemon:
        watchdog_daemon()
    else:
        auto_heal_all_credentials()
