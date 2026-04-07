import os
import json
from forge_orchestrator import ForgeOrchestrator
from forge_rollback_manager import BACKUP_DIR
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ForgeVerifier")

def verify():
    orchestrator = ForgeOrchestrator()
    
    print("=== Verification 1: Timeout Test ===")
    res1 = orchestrator.execute_staging_cycle("timeout_test.py")
    print(f"Result: {json.dumps(res1, indent=2)}\n")
    
    print("=== Verification 2: Syntax Error Test ===")
    res2 = orchestrator.execute_staging_cycle("syntax_error_test.py")
    print(f"Result: {json.dumps(res2, indent=2)}\n")

    print("=== Verification 3 & 4: Merge to Live & Rollback Gen ===")
    # Create a dummy live file
    test_live_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dummy_live.py")
    with open(test_live_file, "w") as f:
        f.write("print('Old live file')")
        
    staging_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "staging_environment", "safe_script.py")
    
    merge_success = orchestrator.merge_to_live(staging_file_path, test_live_file)
    print(f"Merge success: {merge_success}")
    
    backups = []
    if os.path.exists(BACKUP_DIR):
        backups = [f for f in os.listdir(BACKUP_DIR) if f.startswith("dummy_live.py")]
    print(f"Backups generated: {backups}\n")
    
    # Cleanup
    if os.path.exists(test_live_file):
        os.remove(test_live_file)
    
    print("=== Verification 5: Executive Fork ===")
    print("Attempting to trigger Executive fork...")
    try:
        orchestrator.trigger_executive_fork("Testing the fork logic.", ["Option A", "Option B"])
    except Exception as e:
        print(f"Fork Triggered exception as expected: {e}")

if __name__ == "__main__":
    verify()
