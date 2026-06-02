import json
import time
import uuid
import logging
from pathlib import Path

log = logging.getLogger("DispatchQueue")
MAF_ROOT = Path(__file__).parent.parent.resolve()

def get_queue_dir() -> Path:
    """Resolves the ay2_dispatch_queue directory dynamically."""
    queue_dir = MAF_ROOT / "Master_Architect_Elite_Logic" / "ay2_dispatch_queue"
    queue_dir.mkdir(parents=True, exist_ok=True)
    return queue_dir

def dispatch_mandate(mandate_text: str, source: str = "ClaudeAY") -> str:
    """
    Writes a mandate directly to the ay2_dispatch_queue.
    Returns the blueprint filename for tracking.
    """
    try:
        queue_dir = get_queue_dir()
        blueprint_id = int(time.time())
        filename = f"pending_blueprint_{blueprint_id}.json"

        blueprint = {
            "execution_id": str(uuid.uuid4()),
            "source": source,
            "mandate": mandate_text,
            "timestamp": blueprint_id,
            "status": "pending"
        }

        target_path = queue_dir / filename
        target_path.write_text(
            json.dumps(blueprint, indent=2),
            encoding="utf-8"
        )
        log.info(f"[DISPATCH] Blueprint queued: {filename}")
        return filename
    except Exception as e:
        log.error(f"[DISPATCH] Failed to queue blueprint: {e}")
        raise RuntimeError(f"[DISPATCH QUEUE] Failed: {e}")
