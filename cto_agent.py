import json
import time
import shutil
from pathlib import Path

PENDING_DIR = Path("vault/blueprints/pending")

def finalize_execution_handoff(mandate_name: str, blueprint_data: dict, biological_summary: str):
    PENDING_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = int(time.time())
    
    tmp_json_path = PENDING_DIR / f"{mandate_name}_{timestamp}_Blueprint.json.tmp"
    final_json_path = PENDING_DIR / f"{mandate_name}_{timestamp}_Blueprint.json"
    
    with open(tmp_json_path, 'w') as f:
        json.dump(blueprint_data, f, indent=4)
    
    shutil.move(str(tmp_json_path), str(final_json_path))
        
    md_path = PENDING_DIR / f"{mandate_name}_{timestamp}_Summary.md"
    with open(md_path, 'w') as f:
        f.write(f"# STRUCTURAL EXECUTION SUMMARY: {mandate_name}\n\n")
        f.write(biological_summary)
        
    print(f"[CTO NODE] Dual-Payload synthesized to {PENDING_DIR}. Awaiting biological actuation.")
