from auto_heal import healed_post, auto_heal, diagnose

"""
document_router.py — App-Specific Document Routing
═══════════════════════════════════════════════════════
Routes parsed document results to the appropriate destination
based on source app and document category.

Routing Table:
  Sentinel_Bridge  + Any      → Reminders API
  *                + Finance  → CFO Agent
  *                + Legal    → Compliance Officer Agent
  *                + Medical  → Dr. Aris Agent
  *                + Other    → MASTER_INDEX only (no routing)

Part of the Meta_App_Factory V3 infrastructure.
"""

import os
import sys
import json
import logging
import requests
from typing import Optional

FACTORY_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, FACTORY_DIR)

logger = logging.getLogger("DocumentRouter")

# ── Endpoint Configuration ────────────────────────────────
AETHER_SKILLS_BASE = "http://localhost:8001"
SENTINEL_API_BASE = "http://localhost:5010"

# ── Routing Rules ─────────────────────────────────────────
# Priority: App-specific rules first, then category-based fallbacks

APP_ROUTES = {
    "Sentinel_Bridge": {
        "destination": "sentinel_reminders",
        "endpoint": f"{SENTINEL_API_BASE}/api/reminders",
        "method": "POST",
        "transform": "_transform_to_reminder",
    },
}

CATEGORY_ROUTES = {
    "Finance": {
        "destination": "cfo",
        "endpoint": f"{AETHER_SKILLS_BASE}/agent/cfo",
        "method": "POST",
        "transform": "_transform_to_agent_skill",
    },
    "Legal": {
        "destination": "compliance-officer",
        "endpoint": f"{AETHER_SKILLS_BASE}/agent/compliance-officer",
        "method": "POST",
        "transform": "_transform_to_agent_skill",
    },
    "Medical": {
        "destination": "dr-aris",
        "endpoint": f"{AETHER_SKILLS_BASE}/agent/dr-aris",
        "method": "POST",
        "transform": "_transform_to_agent_skill",
    },
    "Technical": {
        "destination": "cto",
        "endpoint": f"{AETHER_SKILLS_BASE}/agent/cto",
        "method": "POST",
        "transform": "_transform_to_agent_skill",
    },
    "Ops": {
        "destination": "ceo",
        "endpoint": f"{AETHER_SKILLS_BASE}/agent/ceo",
        "method": "POST",
        "transform": "_transform_to_agent_skill",
    },
}


class DocumentRouter:
    """
    Routes parsed document results to the appropriate service.
    """

    def route(self, parse_result: dict) -> dict:
        """
        Route a parsed document result to the correct destination.

        Args:
            parse_result: Output from DocumentParserService.parse()

        Returns:
            Updated parse_result with routing info filled in
        """
        if parse_result.get("status") != "parsed":
            return parse_result

        source_app = parse_result.get("source_app", "unknown")
        category = parse_result.get("category", "Other")

        # Priority 1: App-specific route
        route = APP_ROUTES.get(source_app)

        # Priority 2: Category-based route
        if not route:
            route = CATEGORY_ROUTES.get(category)

        if not route:
            # No route — log only
            parse_result["routing"] = {
                "destination": "master_index_only",
                "endpoint": None,
                "status": "logged",
            }
            logger.info(f"[{parse_result['parse_id'][:8]}] No route — logged to index only")
            return parse_result

        # Execute routing
        destination = route["destination"]
        endpoint = route["endpoint"]
        transform_fn = getattr(self, route["transform"], None)

        parse_result["routing"]["destination"] = destination
        parse_result["routing"]["endpoint"] = endpoint

        # Transform payload for the destination
        payload = transform_fn(parse_result) if transform_fn else parse_result

        # Attempt delivery
        try:
            r = requests.post(endpoint, json=payload, timeout=15)
            if r.status_code in (200, 201):
                parse_result["routing"]["status"] = "delivered"
                logger.info(f"[{parse_result['parse_id'][:8]}] Delivered to {destination} ({r.status_code})")
            else:
                parse_result["routing"]["status"] = "delivery_failed"
                parse_result["routing"]["error"] = f"HTTP {r.status_code}"
                logger.warning(f"[{parse_result['parse_id'][:8]}] Delivery failed: {destination} → {r.status_code}")
        except requests.ConnectionError:
            parse_result["routing"]["status"] = "offline"
            parse_result["routing"]["error"] = f"{destination} is not reachable"
            logger.warning(f"[{parse_result['parse_id'][:8]}] {destination} offline — queued for retry")
        except Exception as e:
            parse_result["routing"]["status"] = "error"
            parse_result["routing"]["error"] = str(e)
            logger.error(f"[{parse_result['parse_id'][:8]}] Routing error: {e}")

        return parse_result

    # ═══════════════════════════════════════════════════════
    #  PAYLOAD TRANSFORMERS
    # ═══════════════════════════════════════════════════════

    def _transform_to_reminder(self, result: dict) -> dict:
        """Transform parse result into a Sentinel_Bridge reminder payload."""
        entities = result.get("extracted", {}).get("entities", {})
        action_items = entities.get("action_items", [])
        dates = entities.get("dates", [])

        # Create a reminder from the document summary + action items
        text = result["extracted"].get("summary", result["file_name"])
        if action_items:
            text += " | Action: " + "; ".join(action_items[:3])

        return {
            "text": text,
            "due": dates[0] if dates else None,
            "category": result.get("category", "Other"),
            "source": f"DocumentParser:{result['file_name']}",
            "priority": "high" if result.get("category") in ("Legal", "Finance") else "normal",
        }

    def _transform_to_agent_skill(self, result: dict) -> dict:
        """Transform parse result into an Aether Skills Router payload."""
        summary = result["extracted"].get("summary", "")
        entities = result["extracted"].get("entities", {})

        context_parts = [
            f"Document: {result['file_name']}",
            f"Category: {result['category']}",
            f"Source: {result['source_app']}",
        ]
        if entities.get("amounts"):
            context_parts.append(f"Amounts: {', '.join(entities['amounts'][:5])}")
        if entities.get("parties"):
            context_parts.append(f"Parties: {', '.join(entities['parties'][:5])}")
        if entities.get("dates"):
            context_parts.append(f"Key Dates: {', '.join(entities['dates'][:5])}")

        return {
            "prompt": f"Analyze this parsed document and provide actionable recommendations:\n\n{summary}\n\n"
                      f"Raw text preview:\n{result['extracted'].get('raw_text_preview', '')[:1000]}",
            "context": "\n".join(context_parts),
            "skip_critic": False,
        }


# ═══════════════════════════════════════════════════════════
#  CONVENIENCE: Parse + Route in one call
# ═══════════════════════════════════════════════════════════

def parse_and_route(file_path: str, source_app: str = "unknown") -> dict:
    """
    Full pipeline: parse a document, route it, and log to MASTER_INDEX.

    Usage:
        from document_router import parse_and_route
        result = parse_and_route("contract.pdf", source_app="Sentinel_Bridge")
    """
    from document_parser_service import DocumentParserService

    parser = DocumentParserService()
    router = DocumentRouter()

    # Parse
    result = parser.parse(file_path, source_app=source_app)

    # Route
    if result.get("status") == "parsed":
        result = router.route(result)

    # Persist
    parser.log_to_master_index(result)

    return result


if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")

    p = argparse.ArgumentParser(description="Document Router — Test Mode")
    p.add_argument("file", help="Path to document")
    p.add_argument("--app", default="test", help="Source app name")
    args = p.parse_args()

    result = parse_and_route(args.file, source_app=args.app)
    print(json.dumps(result, indent=2, default=str))
# V3 AUTO-HEAL ACTIVE
