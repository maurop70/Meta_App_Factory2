"""
leak_monitor.py — ntfy Security Watchdog
==========================================
Project Aether | C-Suite | Antigravity-AI

Real-time security alerting via ntfy.sh push notifications.
Monitors for two event types:

1. LEAK INTERCEPTION: Agent attempts to export proprietary logic
2. IP MILESTONE: App confidence score exceeds 80% threshold

Every alert is mirrored as a permanent entry in LEDGER.md under
## SECURITY_INTERCEPTIONS.

Configuration:
    Environment Variables:
        NTFY_TOPIC      — ntfy topic name (default: antigravity-security)
        NTFY_SERVER     — ntfy server URL (default: https://ntfy.sh)
        NTFY_PRIORITY   — default priority: 4 (high)

Usage:
    from c_suite.leak_monitor import on_leak_intercepted, on_ip_milestone

    # When a leak is blocked
    on_leak_intercepted("Deep_Crawler", "TRADE_SECRET")

    # When IP milestone is hit
    on_ip_milestone("Resonance", 0.85, "patent")
"""

import os
import json
import httpx
from datetime import datetime
from typing import Optional


# ── Config ─────────────────────────────────────────

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
AETHER_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
FACTORY_ROOT = os.path.abspath(os.path.join(AETHER_DIR, ".."))
LEDGER_PATH = os.path.join(FACTORY_ROOT, "LEDGER.md")

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(FACTORY_ROOT, ".env"))
except ImportError:
    pass

NTFY_TOPIC = os.getenv("NTFY_TOPIC", "antigravity-security")
NTFY_SERVER = os.getenv("NTFY_SERVER", "https://ntfy.sh")
NTFY_DEFAULT_PRIORITY = int(os.getenv("NTFY_PRIORITY", "4"))  # 1-5, 4=high


# ══════════════════════════════════════════════════
#  CORE: ntfy PUSH NOTIFICATION
# ══════════════════════════════════════════════════

# Factory UI base URL for deep-linking
FACTORY_UI_BASE = os.getenv("FACTORY_UI_URL", "http://localhost:5173")


def send_ntfy_alert(
    title: str,
    message: str,
    priority: int = 0,
    tags: Optional[list] = None,
    topic: Optional[str] = None,
    click_url: Optional[str] = None,
) -> dict:
    """
    Send a push notification via ntfy.sh.

    Args:
        title: Alert title (shown as notification header)
        message: Alert body text
        priority: 1 (min) to 5 (max), 0 = use default
        tags: ntfy tag emojis (e.g., ["warning", "lock"])
        topic: Override default topic
        click_url: Optional URL opened when notification is tapped (ntfy Click header)

    Returns:
        dict with status and response info
    """
    target_topic = topic or NTFY_TOPIC
    url = f"{NTFY_SERVER}/{target_topic}"
    prio = priority or NTFY_DEFAULT_PRIORITY

    headers = {
        "Title": title,
        "Priority": str(prio),
    }

    if tags:
        headers["Tags"] = ",".join(tags)

    if click_url:
        headers["Click"] = click_url

    try:
        resp = httpx.post(url, content=message, headers=headers, timeout=10.0)
        return {
            "status": "sent" if resp.status_code == 200 else "error",
            "http_status": resp.status_code,
            "http_body": resp.text[:200] if resp.status_code != 200 else "",
            "topic": target_topic,
            "server": NTFY_SERVER,
            "click_url": click_url or "",
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
    except httpx.ConnectError:
        return {
            "status": "connection_failed",
            "detail": f"Could not connect to {NTFY_SERVER}",
            "click_url": click_url or "",  # always echo so callers can verify deep-link
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
    except Exception as e:
        return {
            "status": "error",
            "detail": str(e)[:200],
            "click_url": click_url or "",  # always echo
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }


# ══════════════════════════════════════════════════
#  EVENT: LEAK INTERCEPTED
# ══════════════════════════════════════════════════

def on_leak_intercepted(
    agent_name: str,
    leak_type: str,
    detail: str = "",
    severity: str = "HIGH",
) -> dict:
    """
    Called when a C-Suite agent attempts to export proprietary logic.

    Sends ntfy alert:  ⚠️ LEAK BLOCKED: {agent_name} attempted to export {type}
    Mirrors to:        LEDGER.md under ## SECURITY_INTERCEPTIONS

    Args:
        agent_name: Agent that triggered the leak (e.g., "Deep_Crawler")
        leak_type: Type of leak — "TRADE_SECRET", "PATENTABLE", "PROPRIETARY", "CONFIDENTIAL"
        detail: Additional context
        severity: "LOW", "MEDIUM", "HIGH", "CRITICAL"

    Returns:
        dict with ntfy_result and ledger_result
    """
    # Build deep-link URL for one-tap review
    review_url = f"{FACTORY_UI_BASE}/?view=sop&app=LEAK_{agent_name}&score=0"

    title = f"⚠️ LEAK BLOCKED — {agent_name}"
    message = (
        f"Agent: {agent_name}\n"
        f"Type: {leak_type}\n"
        f"Severity: {severity}\n"
        f"Time: {datetime.utcnow().isoformat()}Z\n"
    )
    if detail:
        message += f"Detail: {detail}\n"
    message += "\nTap to review in Meta App Factory SOP."

    # Priority mapping
    prio_map = {"LOW": 2, "MEDIUM": 3, "HIGH": 4, "CRITICAL": 5}
    priority = prio_map.get(severity, 4)

    # Send ntfy with Click deep-link
    ntfy_result = send_ntfy_alert(
        title=title,
        message=message,
        priority=priority,
        tags=["warning", "lock", "rotating_light"],
        click_url=review_url,
    )

    # Mirror to LEDGER.md with SOP link
    ledger_entry = (
        f"[{datetime.utcnow().isoformat()}Z] | LEAK_MONITOR | "
        f"ACTION: LEAK_BLOCKED | AGENT: {agent_name} | "
        f"TYPE: {leak_type} | SEVERITY: {severity}"
    )
    if detail:
        ledger_entry += f" | DETAIL: {detail}"
    ledger_entry += f" | REVIEW: {review_url}"

    ledger_result = mirror_to_ledger("SECURITY_INTERCEPTIONS", ledger_entry)

    return {
        "event": "leak_intercepted",
        "agent": agent_name,
        "leak_type": leak_type,
        "severity": severity,
        "ntfy": ntfy_result,
        "ledger": ledger_result,
    }


# ══════════════════════════════════════════════════
#  EVENT: IP MILESTONE HIT
# ══════════════════════════════════════════════════

def on_ip_milestone(
    app_name: str,
    confidence: float,
    ip_type: str = "patent",
    detail: str = "",
) -> dict:
    """
    Called when an app's IP confidence score exceeds 80%.

    Sends ntfy alert:  🛡️ IP ALERT: {app_name} reached >80% confidence for {patent/trademark}
    Mirrors to:        LEDGER.md under ## SECURITY_INTERCEPTIONS

    Args:
        app_name: Application name
        confidence: Confidence score (0.0-1.0)
        ip_type: "patent" or "trademark"
        detail: Additional context

    Returns:
        dict with ntfy_result and ledger_result
    """
    pct = f"{confidence * 100:.1f}%"
    score_int = int(confidence * 100)

    # Build deep-link — tapping the notification opens SOP modal in Factory UI
    sop_url = f"{FACTORY_UI_BASE}/?view=sop&app={app_name}&score={score_int}"

    title = f"🛡️ IP ALERT — {app_name}"
    message = f"🛡️ IP ALERT: {app_name} ({pct}). Click to open SOP and review claims."
    if detail:
        message += f"\n{detail}"

    # Send ntfy WITH Click deep-link header
    ntfy_result = send_ntfy_alert(
        title=title,
        message=message,
        priority=4,
        tags=["shield", "bulb", "chart_with_upwards_trend"],
        click_url=sop_url,
    )

    # Mirror to LEDGER.md with SOP deep-link
    ledger_entry = (
        f"[{datetime.utcnow().isoformat()}Z] | LEAK_MONITOR | "
        f"ACTION: IP_MILESTONE | APP: {app_name} | "
        f"TYPE: {ip_type.upper()} | CONFIDENCE: {pct} | SOP: {sop_url}"
    )
    if detail:
        ledger_entry += f" | DETAIL: {detail}"

    ledger_result = mirror_to_ledger("SECURITY_INTERCEPTIONS", ledger_entry)

    return {
        "event": "ip_milestone",
        "app_name": app_name,
        "confidence": confidence,
        "ip_type": ip_type,
        "ntfy": ntfy_result,
        "ledger": ledger_result,
    }


# ══════════════════════════════════════════════════
#  LEDGER MIRROR
# ══════════════════════════════════════════════════

def mirror_to_ledger(
    section: str,
    entry_text: str,
    ledger_path: Optional[str] = None,
) -> dict:
    """
    Append a timestamped entry to LEDGER.md under a specific section heading.

    If the section heading doesn't exist, it's created at the end of the file.

    Args:
        section: Section name (e.g., "SECURITY_INTERCEPTIONS")
        entry_text: The raw text line to append
        ledger_path: Override default ledger path

    Returns:
        dict with status
    """
    path = ledger_path or LEDGER_PATH

    try:
        # Read existing content
        content = ""
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()

        section_header = f"## {section}"

        if section_header in content:
            # Insert entry after the section header
            idx = content.index(section_header) + len(section_header)
            # Find the end of the header line
            newline_idx = content.index("\n", idx) if "\n" in content[idx:] else len(content)
            content = content[:newline_idx + 1] + entry_text + "\n" + content[newline_idx + 1:]
        else:
            # Add section at the end
            content += f"\n{section_header}\n{entry_text}\n"

        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

        return {"status": "written", "section": section, "path": path}

    except OSError as e:
        return {"status": "error", "detail": str(e)[:200]}


# ══════════════════════════════════════════════════
#  MODULE INFO
# ══════════════════════════════════════════════════

def get_info() -> dict:
    """Return leak monitor module metadata."""
    return {
        "name": "Leak Monitor — ntfy Security Watchdog",
        "version": "1.1.0",
        "ntfy_topic": NTFY_TOPIC,
        "ntfy_server": NTFY_SERVER,
        "factory_ui": FACTORY_UI_BASE,
        "ledger_path": LEDGER_PATH,
        "events": ["leak_intercepted", "ip_milestone"],
        "deep_linking": True,
        "sop_url_format": f"{FACTORY_UI_BASE}/?view=sop&app={{app_name}}&score={{score}}",
        "status": "operational",
    }


# ══════════════════════════════════════════════════
#  STANDALONE TEST
# ══════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Leak Monitor — ntfy Security Watchdog")
    parser.add_argument("--test-leak", action="store_true", help="Send a test leak alert")
    parser.add_argument("--test-ip", action="store_true", help="Send a test IP milestone alert")
    parser.add_argument("--info", action="store_true", help="Show module info")
    args = parser.parse_args()

    if args.info:
        print(json.dumps(get_info(), indent=2))

    elif args.test_leak:
        print("\n⚠️ Sending test LEAK alert...")
        result = on_leak_intercepted(
            agent_name="Deep_Crawler",
            leak_type="TRADE_SECRET",
            detail="Test alert — no actual leak detected",
            severity="MEDIUM",
        )
        print(json.dumps(result, indent=2))

    elif args.test_ip:
        print("\n🛡️ Sending test IP MILESTONE alert...")
        result = on_ip_milestone(
            app_name="Resonance",
            confidence=0.85,
            ip_type="patent",
            detail="Test alert — confidence threshold exceeded",
        )
        print(json.dumps(result, indent=2))

    else:
        info = get_info()
        print(f"\n🔒 Leak Monitor v{info['version']}")
        print(f"   ntfy topic: {info['ntfy_topic']}")
        print(f"   ntfy server: {info['ntfy_server']}")
        print(f"   LEDGER: {info['ledger_path']}")
        print(f"\nUsage:")
        print(f"  --test-leak   Send test leak interception alert")
        print(f"  --test-ip     Send test IP milestone alert")
        print(f"  --info        Show module metadata")
