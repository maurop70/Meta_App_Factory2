"""
phantom_ui_pathfinder.py — Phase 6: Native Phantom UI-First Auditor
═════════════════════════════════════════════════════════════════════
Replaces the legacy Phantom QA Elite n8n workflow.
Uses Playwright to stress-test the local factory UI (React).
Protected by the V3 Resilience Core.
"""
import time
import logging
from playwright.sync_api import sync_playwright
sys_path_added = False
import sys, os
if os.path.dirname(os.path.abspath(__file__)) not in sys.path:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from auto_heal import _log_heal_event

logger = logging.getLogger("PhantomUIPathfinder")

class PhantomUIPathfinder:
    def __init__(self, project_id: str, base_url="http://localhost:5173"):
        self.project_id = project_id
        self.base_url = base_url

    def run_audit(self) -> dict:
        """Runs the headless UI walkthrough, network sniffer, and stress test."""
        logger.info(f"PhantomUIPathfinder initiating simulated session for: {self.project_id}")
        
        results = {
            "verdict": "FAIL",
            "score": 0,
            "errors": [],
            "duration_seconds": 0
        }
        
        start_time = time.time()
        
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                
                # ── V3 Network Sniffer ──────────────────────────────────────────
                network_errors = []
                def _check_network_health(response):
                    if response.status >= 400 and not response.url.endswith("favicon.ico") and not response.url.endswith(".map"):
                        network_errors.append(f"Network Fault: {response.url} returned HTTP {response.status}")
                        _log_heal_event("UI_NETWORK_FAULT", f"HTTP {response.status} on {response.url}", {}, "network_error")
                
                page.on("response", _check_network_health)
                
                try:
                    # 1. Target Validation: Context-Aware Navigation
                    target_url = f"{self.base_url}/?project={self.project_id}"
                    logger.info(f"Navigating to {target_url}")
                    page.goto(target_url, timeout=4000)
                    
                    # 2. Latency Watchdog: Wait for project view to render
                    page.wait_for_load_state("networkidle", timeout=3000)
                    
                    # Target specific War Room elements if present
                    try:
                        page.wait_for_selector(".war-room-container, .dashboard", timeout=2000)
                    except Exception:
                        logger.warning("Main container selector not found within 2s, continuing strictly.")
                    
                    # 3. The "Human-Centric" Stress Test
                    # Find any inputs/textareas to break the layout
                    inputs = page.locator("input, textarea").all()
                    for inp in inputs:
                        if inp.is_visible():
                            try:
                                inp.fill("A" * 5000)
                            except Exception:
                                pass
                                
                    # Simulated Clicks
                    buttons = page.locator("button").all()
                    clicked = 0
                    for btn in buttons:
                        if clicked >= 3:
                            break
                        if btn.is_visible() and not btn.is_disabled():
                            try:
                                btn.click(timeout=1000)
                                clicked += 1
                                time.sleep(0.5)
                            except Exception:
                                continue
                                
                except Exception as e:
                    raise Exception(f"Latency Watchdog Tripped or Navigation failed: {str(e)}")
                finally:
                    browser.close()
                
                # ── Phase 4: Verification ────────────────────────────
                if network_errors:
                    results["errors"].extend(network_errors)
                    raise Exception(f"Caught {len(network_errors)} DOM Network Errors during session.")
                
                results["verdict"] = "COMMERCIALLY READY"
                results["score"] = 95
                
        except Exception as e:
            # ── V3 Feedback Loop ──────────────────────────────────
            _log_heal_event("UI_PATHFINDER_FAILURE", "UI Stress Test Failed", {"error": str(e)}, "qa_gate_failure")
            results["errors"].append(str(e))
            results["verdict"] = "FAIL"
            results["score"] = 0
            
        results["duration_seconds"] = round(time.time() - start_time, 2)
        return results

# Hook
def run_ui_audit(project_id: str) -> dict:
    pathfinder = PhantomUIPathfinder(project_id)
    return pathfinder.run_audit()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Testing Phantom UI Pathfinder...")
    res = run_ui_audit("Aether")
    print(res)
