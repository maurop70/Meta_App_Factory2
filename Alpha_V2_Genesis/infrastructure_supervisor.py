"""
Infrastructure Supervisor — Alpha V2 Genesis
Watches:
  1. N8N Cloud health (every 5 minutes, during execution window)
  2. Alpha Server local health (every 5 minutes, always)
  3. portfolio.json — triggers Strategy Ledger on new OPEN positions (NEW)
  4. Daily 09:15 EST ledger recalibration cron (NEW)
"""
import os, sys, time, json, requests, logging, subprocess, threading
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - Infrastructure - %(levelname)s - %(message)s"
)
logger = logging.getLogger("Supervisor")

# ── Config ──────────────────────────────────────────────────────
PORTFOLIO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Alpha_Data", "portfolio.json")
SCRIPT_DIR     = os.path.dirname(os.path.abspath(__file__))


def check_n8n():
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    try:
        sys.path.insert(0, SCRIPT_DIR)
        from vault_client import get_secret
        api_key = get_secret("N8N_API_KEY")
    except ImportError:
        api_key = os.getenv("N8N_API_KEY")
    if not api_key:
        api_key = os.getenv("N8N_API_KEY")
    if not api_key:
        logger.warning("N8N_API_KEY not found in vault/.env. Skipping N8N health check.")
        return False
    url     = "https://humanresource.app.n8n.cloud/api/v1/workflows"
    headers = {"X-N8N-API-KEY": api_key}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            logger.info("N8N Connectivity: ONLINE")
            return True
        else:
            logger.error(f"N8N Connectivity: FAILED ({resp.status_code})")
            return False
    except Exception as e:
        logger.error(f"N8N Connectivity: ERROR ({e})")
        return False


def check_server():
    try:
        resp = requests.get("http://localhost:5005/", timeout=5)
        if resp.status_code == 200:
            logger.info("Alpha Server: RESPONDING")
            return True
        else:
            logger.warning(f"Alpha Server: UNHEALTHY ({resp.status_code})")
            return False
    except Exception:
        logger.error("Alpha Server: DOWN")
        return False


def get_open_position_ids():
    """Returns a set of IDs of currently OPEN positions."""
    try:
        with open(PORTFOLIO_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {p["id"] for p in data.get("positions", []) if p.get("status") == "OPEN"}
    except Exception:
        return set()


def trigger_ledger(force=False):
    """Runs strategy_ledger.py as a subprocess."""
    ledger_path = os.path.join(SCRIPT_DIR, "strategy_ledger.py")
    if not os.path.exists(ledger_path):
        logger.warning("strategy_ledger.py not found — skipping ledger trigger.")
        return
    cmd = [sys.executable, ledger_path]
    if force:
        cmd.append("--force")
    try:
        logger.info(f"Triggering Strategy Ledger {'(FORCE)' if force else ''}...")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120, cwd=SCRIPT_DIR)
        if result.returncode == 0:
            logger.info("Strategy Ledger completed successfully.")
        else:
            logger.error(f"Strategy Ledger error: {result.stderr[-300:]}")
    except subprocess.TimeoutExpired:
        logger.warning("Strategy Ledger timed out (120s) — skipping this cycle.")
    except Exception as e:
        logger.error(f"Failed to trigger ledger: {e}")


def monitor_loop():
    logger.info("Infrastructure Supervisor Active (v2 — with Ledger Watchdog).")

    known_open_ids = get_open_position_ids()
    last_daily_run = None

    # Trigger initial ledger run on startup (force to capture entry conditions)
    threading.Thread(target=trigger_ledger, kwargs={"force": True}, daemon=True).start()

    while True:
        now     = datetime.now()
        is_window = (now.weekday() < 2) and (9 <= now.hour < 16)

        # ── 1. N8N Health (execution window only) ─────────────────
        if is_window:
            check_n8n()
        else:
            logger.info("Outside Mon-Tue 9a-4p window. Skipping N8N ping.")

        # ── 2. Server Health ───────────────────────────────────────
        check_server()

        # ── 3. Portfolio Watcher — detect new open positions ───────
        current_ids = get_open_position_ids()
        new_ids = current_ids - known_open_ids

        if new_ids:
            logger.info(f"NEW POSITION(S) DETECTED: {new_ids} — Triggering ledger entry report!")
            threading.Thread(target=trigger_ledger, kwargs={"force": True}, daemon=True).start()
            known_open_ids = current_ids
        else:
            known_open_ids = current_ids

        # ── 4. Daily Recalibration at 09:15 EST ───────────────────
        today_str = now.strftime("%Y-%m-%d")
        if now.hour == 9 and now.minute >= 15 and last_daily_run != today_str:
            logger.info("Daily recalibration window (09:15 EST). Running ledger update...")
            threading.Thread(target=trigger_ledger, daemon=True).start()
            last_daily_run = today_str

        time.sleep(300)  # 5-minute ping cycle


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    monitor_loop()
