"""
ux_simulator.py — Native Triad Module 3
════════════════════════════════════════
Uses Playwright for Deep Audits. Clicks every button in the Auditor's Desk 
and verifies that no console errors (400/500) occur during state transitions.
Wrapped by the 500MB memory guard (via native watchdog).
"""
import time
import logging
from playwright.sync_api import sync_playwright
import sys, os

if os.path.dirname(os.path.abspath(__file__)) not in sys.path:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from auto_heal import _log_heal_event
except ImportError:
    def _log_heal_event(*args, **kwargs): pass

logger = logging.getLogger("UXSimulator")

class UXSimulator:
    def __init__(self, project_id: str, base_url="http://localhost:5173"):
        self.project_id = project_id
        self.base_url = base_url

    def run_deep_audit(self) -> dict:
        logger.info(f"[UXSimulator] Deep audit for: {self.project_id}")
        
        results = {"verdict": "FAIL", "score": 0, "errors": [], "duration_seconds": 0}
        start_time = time.time()
        
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                
                # ── 400/500 Network Sniffer ─────────────────────────
                network_errors = []
                def _check_network_health(response):
                    # Flag 4xx and 5xx errors directly
                    if response.status >= 400 and "favicon.ico" not in response.url and ".map" not in response.url:
                        err_msg = f"HTTP {response.status} Error on {response.url}"
                        network_errors.append(err_msg)
                        _log_heal_event("UI_SIMULATOR_FAULT", err_msg, {}, "network_error")
                
                page.on("response", _check_network_health)
                
                # Console error listener
                def _log_console(msg):
                    if msg.type == "error":
                        err_msg = f"Console Error: {msg.text}"
                        network_errors.append(err_msg)
                        _log_heal_event("UI_SIMULATOR_FAULT", err_msg, {}, "console_error")
                        
                page.on("console", _log_console)

                try:
                    # 1. Navigation
                    target_url = f"{self.base_url}/?project={self.project_id}"
                    page.goto(target_url, timeout=4000)
                    page.wait_for_load_state("networkidle", timeout=3000)
                    
                    try:
                        page.wait_for_selector(".dashboard", timeout=2000)
                    except Exception:
                        pass
                    
                    # 3. Deep Audit: Click EVERY interactive element
                    buttons = page.locator("button, [role='button'], .btn, a").all()
                    
                    for idx, btn in enumerate(buttons):
                        if btn.is_visible() and not btn.is_disabled():
                            try:
                                btn.click(timeout=1000)
                                time.sleep(0.3)  # Wait for state transitions
                            except Exception:
                                continue
                                
                except Exception as e:
                    raise Exception(f"Navigation/Click Failure: {str(e)}")
                finally:
                    browser.close()
                
                # ── Verification ───────────────────────
                if network_errors:
                    results["errors"].extend(network_errors)
                    score = max(0, 100 - (len(network_errors)*20))
                    results["score"] = score
                    results["verdict"] = "WARN" if score >= 80 else "FAIL"
                else:
                    results["verdict"] = "PASS"
                    results["score"] = 100
                
        except Exception as e:
            _log_heal_event("UI_SIMULATOR_FAILURE", "Deep Audit Failed", {"error": str(e)}, "qa_gate_failure")
            results["errors"].append(str(e))
            results["verdict"] = "FAIL"
            results["score"] = 0
            
        results["duration_seconds"] = round(time.time() - start_time, 2)
        return results
