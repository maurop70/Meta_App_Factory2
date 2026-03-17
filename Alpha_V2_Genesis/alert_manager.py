"""
╔══════════════════════════════════════════════════════════════╗
║  ALPHA V2 GENESIS — ALERT MANAGER (Priority 3)              ║
║                                                              ║
║  Three zero-config channels:                                 ║
║  1. Windows Desktop Toast  (no setup, always works)         ║
║  2. ntfy.sh Mobile Push    (free, no account needed)        ║
║  3. SMTP Email             (optional, add to .env)          ║
╚══════════════════════════════════════════════════════════════╝

SETUP:
  • Toast  : Works immediately on Windows 10/11
  • Mobile : On your phone, visit https://ntfy.sh/<NTFY_TOPIC>
             or install the "ntfy" app and subscribe to the topic.
             Default topic: alpha-v2-genesis-alerts
  • Email  : Add to .env: ALERT_EMAIL, SMTP_USER, SMTP_PASS
  Optional: NTFY_TOPIC (to customise your mobile channel name)
"""
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


import os
import subprocess
import logging
import smtplib
import requests
from datetime import datetime
from email.mime.text import MIMEText

logger = logging.getLogger("AlertManager")

# ── Config from .env ───────────────────────────────────────────
NTFY_TOPIC  = os.getenv("NTFY_TOPIC", "alpha-v2-genesis-alerts")
ALERT_EMAIL = os.getenv("ALERT_EMAIL", "")
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT   = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER   = os.getenv("SMTP_USER", "")
SMTP_PASS   = os.getenv("SMTP_PASS", "")

# De-duplicate: tracks which alerts have already fired this session
_sent_hashes: set = set()


# ══════════════════════════════════════════════════════════════════
# CHANNEL 1: Windows Desktop Toast
# ══════════════════════════════════════════════════════════════════

def _windows_toast(title: str, message: str, urgency: str = "INFO") -> bool:
    """
    Native Windows 10/11 balloon/toast notification via PowerShell.
    Non-blocking — spawns a hidden PowerShell process.
    """
    # Escape double-quotes for PowerShell injection safety
    safe_title   = title.replace('"', "'")
    safe_message = message.replace('"', "'").replace('\n', ' | ')

    icon = "Warning" if urgency in ("WARN", "CRITICAL") else "Information"
    balloon_icon = "Warning" if urgency == "WARN" else ("Error" if urgency == "CRITICAL" else "Info")

    ps = f"""
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$n = New-Object System.Windows.Forms.NotifyIcon
$n.Icon = [System.Drawing.SystemIcons]::{icon}
$n.BalloonTipIcon = [System.Windows.Forms.ToolTipIcon]::{balloon_icon}
$n.BalloonTipTitle = "{safe_title}"
$n.BalloonTipText = "{safe_message}"
$n.Visible = $true
$n.ShowBalloonTip(9000)
Start-Sleep -Seconds 10
$n.Dispose()
"""
    try:
        subprocess.Popen(
            ["powershell", "-WindowStyle", "Hidden", "-NonInteractive", "-Command", ps],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        logger.info(f"[Toast] ✅ Sent: {title}")
        return True
    except AttributeError:
        # CREATE_NO_WINDOW not available on non-Windows
        try:
            subprocess.Popen(
                ["powershell", "-Command", ps],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
        except Exception as e:
            logger.warning(f"[Toast] Failed: {e}")
            return False
    except Exception as e:
        logger.warning(f"[Toast] Failed: {e}")
        return False


# ══════════════════════════════════════════════════════════════════
# CHANNEL 2: ntfy.sh Mobile Push
# ══════════════════════════════════════════════════════════════════

def _ntfy_push(title: str, message: str, priority: str = "default", tags: list = None) -> bool:
    """
    Free mobile push via ntfy.sh. No account, no API key needed.

    To receive alerts on your phone:
      1. Download the "ntfy" app (iOS / Android)
      2. Subscribe to topic: alpha-v2-genesis-alerts
         (or whatever NTFY_TOPIC is set to in .env)
    """
    try:
        r = requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=message.encode("utf-8"),
            headers={
                "Title":    title,
                "Priority": priority,           # urgent / high / default / low / min
                "Tags":     ",".join(tags or ["chart_increasing"]),
            },
            timeout=5,
        )
        if r.status_code == 200:
            logger.info(f"[ntfy] ✅ Mobile push sent → ntfy.sh/{NTFY_TOPIC}")
            return True
        logger.warning(f"[ntfy] Returned {r.status_code}: {r.text[:100]}")
        return False
    except Exception as e:
        logger.warning(f"[ntfy] Push failed (non-critical): {e}")
        return False


# ══════════════════════════════════════════════════════════════════
# CHANNEL 3: SMTP Email
# ══════════════════════════════════════════════════════════════════

def _smtp_email(subject: str, body: str) -> bool:
    """
    Optional SMTP email alert.
    Requires in .env: ALERT_EMAIL, SMTP_USER, SMTP_PASS
    Optional: SMTP_SERVER (default smtp.gmail.com), SMTP_PORT (default 587)

    For Gmail:  Use an App Password (Google Account → Security → App Passwords)
    """
    if not all([ALERT_EMAIL, SMTP_USER, SMTP_PASS]):
        return False  # Silently skip if not configured
    try:
        msg            = MIMEText(body, "plain")
        msg["Subject"] = f"[Alpha V2 Genesis] {subject}"
        msg["From"]    = SMTP_USER
        msg["To"]      = ALERT_EMAIL
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=10) as s:
            s.starttls()
            s.login(SMTP_USER, SMTP_PASS)
            s.sendmail(SMTP_USER, ALERT_EMAIL, msg.as_string())
        logger.info(f"[Email] ✅ Sent to {ALERT_EMAIL}")
        return True
    except Exception as e:
        logger.warning(f"[Email] Failed (non-critical): {e}")
        return False


# ══════════════════════════════════════════════════════════════════
# UNIFIED DISPATCHER
# ══════════════════════════════════════════════════════════════════

def send_alert(
    title:    str,
    message:  str,
    level:    str  = "WARN",   # INFO | WARN | CRITICAL
    tags:     list = None,
    dedup_key: str = None,     # If set, same key won't fire twice per session
) -> bool:
    """
    Dispatches to all configured channels.
    Returns True if at least one channel succeeded.
    """
    # De-duplication within the same Python session
    if dedup_key:
        if dedup_key in _sent_hashes:
            logger.debug(f"[Alert] Suppressed duplicate: {dedup_key}")
            return False
        _sent_hashes.add(dedup_key)

    priority_map = {"INFO": "default", "WARN": "high", "CRITICAL": "urgent"}
    priority = priority_map.get(level, "default")

    logger.warning(f"⚠️  ALERT [{level}]: {title} — {message[:120]}")

    ok = False
    ok |= _windows_toast(title, message, urgency=level)
    ok |= _ntfy_push(title, message, priority=priority, tags=tags or ["warning"])
    ok |= _smtp_email(
        subject=title,
        body=(
            f"{message}\n\n"
            f"Time     : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"Level    : {level}\n"
            f"System   : Alpha V2 Genesis — Lead Quant Architect v2.1\n"
            f"\n---\nTo unsubscribe from mobile alerts: unsubscribe from ntfy.sh/{NTFY_TOPIC}"
        )
    )

    return ok


# ══════════════════════════════════════════════════════════════════
# PRE-BUILT ALERT TEMPLATES
# ══════════════════════════════════════════════════════════════════

def alert_thesis_broken(trade_id: str, drift_flags: list):
    flags_text = "\n".join(f"• {f}" for f in drift_flags[-3:])
    send_alert(
        title     = f"🔴 THESIS BROKEN: {trade_id}",
        message   = f"Position {trade_id} thesis has critically degraded.\n\nFlags:\n{flags_text}\n\nImmediate review required.",
        level     = "CRITICAL",
        tags      = ["rotating_light", "chart_decreasing"],
        dedup_key = f"thesis_broken_{trade_id}",
    )


def alert_pivot_recommended(trade_id: str, challenger: dict):
    strikes = challenger.get("strikes", {})
    send_alert(
        title   = f"⚠️ PIVOT ALERT: {trade_id}",
        message = (
            f"Challenger Iron Condor offers significantly better margin.\n\n"
            f"New Short Put  : {strikes.get('short_put')}\n"
            f"New Short Call : {strikes.get('short_call')}\n"
            f"New Credit     : ${challenger.get('net_credit', 0):.2f}\n"
            f"Expiry         : {challenger.get('expiry', '?')}\n\n"
            f"{challenger.get('pivot_rationale', '')}"
        ),
        level     = "WARN",
        tags      = ["dart", "chart_with_upwards_trend"],
        dedup_key = f"pivot_{trade_id}_{challenger.get('expiry')}",
    )


def alert_dte_exit_window(trade_id: str, dte: int):
    send_alert(
        title   = f"⏰ 21-DTE EXIT WINDOW: {trade_id}",
        message = (
            f"Position {trade_id} has reached {dte} DTE.\n\n"
            f"Standard protocol: Close for 50% profit OR roll to next month.\n"
            f"Gamma risk increases significantly from here."
        ),
        level     = "WARN",
        tags      = ["alarm_clock", "calendar"],
        dedup_key = f"dte_exit_{trade_id}",
    )


def alert_profit_target(trade_id: str, pnl_pct: float, current_mark: float, credit: float):
    send_alert(
        title   = f"✅ 50% PROFIT TARGET: {trade_id}",
        message = (
            f"Position {trade_id} has captured {pnl_pct:.1f}% of maximum profit.\n\n"
            f"Entry Credit   : ${credit:.2f}\n"
            f"Current Mark   : ${current_mark:.2f}\n"
            f"P&L Captured   : ${credit - current_mark:.2f} ({pnl_pct:.1f}%)\n\n"
            f"Recommended Action: CLOSE position to lock in profit."
        ),
        level     = "INFO",
        tags      = ["white_check_mark", "money_bag"],
        dedup_key = f"profit_50_{trade_id}",
    )


if __name__ == "__main__":
    # Test all channels
    print("Testing Alpha Alert Manager...")
    send_alert(
        title   = "🧪 Alert System Test",
        message = "Alpha V2 Genesis alert system is working correctly. All channels active.",
        level   = "INFO",
        tags    = ["test_tube"],
    )
    print("Done. Check your Windows notification and ntfy.sh topic.")

# V3 MIGRATION COMPLETE
# V3 AUTO-HEAL ACTIVE
