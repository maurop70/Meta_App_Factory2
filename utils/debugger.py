# ── V3.0 Resilience Integration ──────────────────────────
import os as _os, sys as _sys
_FACTORY_DIR = _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
_sys.path.insert(0, _FACTORY_DIR)
try:
    from factory import safe_post
    from local_state_manager import StateManager as _StateManager
    _v3_sm = _StateManager()
    _V3_AVAILABLE = True
except ImportError:
    _V3_AVAILABLE = False
# ── End V3 Integration ──────────────────────────────────

from auto_heal import healed_post, auto_heal, diagnose

def _v3_preflight():
    """V3: Ping Resonance_Watchdog_V3 before execution."""
    if not _V3_AVAILABLE:
        return True
    try:
        import json as _j
        _cfg_path = _os.path.join(_FACTORY_DIR, "resilience_config.json")
        if not _os.path.exists(_cfg_path):
            return True
        with open(_cfg_path) as _f:
            _cfg = _j.load(_f)
        _url = _cfg.get("cloud_health", {}).get("watchdog_url", "")
        if not _url:
            return True
        import requests as _rq
        _r = _rq.get(_url, timeout=5)
        return _r.status_code == 200
    except Exception:
        return False


import requests
import logging
import os

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('SentryDebugger')

class SentryDebugger:
    def __init__(self, auth_token=None, organization_slug=None, project_slug=None):
        self.auth_token = auth_token or os.getenv("SENTRY_AUTH_TOKEN")
        self.organization_slug = organization_slug or os.getenv("SENTRY_ORG_SLUG")
        self.project_slug = project_slug or os.getenv("SENTRY_PROJECT_SLUG")
        self.base_url = "https://sentry.io/api/0"

    def get_issue_summary(self, issue_id):
        """
        Retrieves the issue summary from Sentry/Seer for a given issue ID.
        In a real integration, this would query the Sentry API or the Seer service.
        """
        if not self.auth_token:
            logger.warning("Sentry Auth Token not provided. Cannot fetch issue summary.")
            return "Sentry Debugger: Auth Token missing. Unable to fetch remote summary."

        headers = {
            "Authorization": f"Bearer {self.auth_token}",
            "Content-Type": "application/json"
        }

        try:
            # Hypothetical endpoint for retrieving an issue's AI summary or details
            # Using the standard issues endpoint for now
            # Issues endpoint: https://docs.sentry.io/api/events/retrieve-an-event-for-a-project/
            # If issue_id is actually an event_id (which it is from capture_exception), we need a different endpoint or logic.
            # However, for now, we will try to fetch the issue details assuming issue_id is the Issue ID (group ID).
            # If it's an Event ID, we might need to resolve it to an Issue ID first, or use the Events endpoint.
            
            # NOTE: sentry_sdk.last_event_id() returns the EVENT ID (hex string), not the Issue ID (integer-like usually).
            # Retrieving event details requires Organization Slug and Project Slug.
            
            if len(str(issue_id)) == 32: # Likely an Event ID (Hex)
                if not self.organization_slug or not self.project_slug:
                     # Try to infer or fallback? 
                     # Use the "Retrieve an Event" endpoint which needs org/project
                     # GET /api/0/projects/{organization_slug}/{project_slug}/events/{event_id}/
                     if self.organization_slug and self.project_slug:
                         url = f"{self.base_url}/projects/{self.organization_slug}/{self.project_slug}/events/{issue_id}/"
                     else:
                         # Without slugs, we can't easily fetch event details via API without more discovery.
                         # Fallback to just reporting the ID.
                         return f"Event ID: {issue_id} (Configure SENTRY_ORG_SLUG and SENTRY_PROJECT_SLUG to fetch details)"
            else:
                # Assume Issue ID
                url = f"{self.base_url}/issues/{issue_id}/"

            response = requests.get(url, headers=headers)
            
            if response.status_code == 403:
                return f"Sentry Permission Denied (403). Check Auth Token scopes (need 'event:read', 'org:read'). ID: {issue_id}"
            
            response.raise_for_status()
            
            data = response.json()
            title = data.get("title", "Unknown Error")
            # culprits or location
            location = data.get("culprit") or data.get("location", "Unknown Location")
            
            summary = f"Issue: {title}\nLocation: {location}\nMessage: {data.get('message', '')}"
            return summary

        except Exception as e:
            logger.error(f"Failed to fetch issue summary: {e}")
            return f"Error fetching summary for Issue {issue_id}: {str(e)}"

# Example usage
if __name__ == "__main__":
    debugger = SentryDebugger(auth_token="PLACEHOLDER_TOKEN", organization_slug="org", project_slug="proj")
    print(debugger.get_issue_summary("12345"))
# V3 AUTO-HEAL ACTIVE
