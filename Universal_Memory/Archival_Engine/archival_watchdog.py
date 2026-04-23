import os
import time
import json
import shutil
import sqlite3

# Directory Setup
ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))
UNIVERSAL_MEMORY_DIR = os.path.dirname(ENGINE_DIR)

QUEUE_DIR = os.path.join(UNIVERSAL_MEMORY_DIR, "Archival_Queue")
PROCESSING_DIR = os.path.join(UNIVERSAL_MEMORY_DIR, "Archival_Processing")
PERMANENT_DIR = os.path.join(UNIVERSAL_MEMORY_DIR, "Permanent_Records")
DEAD_LETTER_DIR = os.path.join(UNIVERSAL_MEMORY_DIR, "Dead_Letter")
REGISTRY_DB_PATH = os.path.join(ENGINE_DIR, "archival_registry.db")

def bootstrapper():
    """Dynamically verify and create necessary archival directories."""
    os.makedirs(QUEUE_DIR, exist_ok=True)
    os.makedirs(PROCESSING_DIR, exist_ok=True)
    os.makedirs(PERMANENT_DIR, exist_ok=True)
    os.makedirs(DEAD_LETTER_DIR, exist_ok=True)
    
    # Initialize SQLite Registry for Sequence Generation
    conn = sqlite3.connect(REGISTRY_DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sequence_ledger (
            module_code TEXT,
            year TEXT,
            month TEXT,
            last_sequence INTEGER,
            PRIMARY KEY (module_code, year, month)
        )
    ''')
    conn.commit()
    conn.close()
    
    print("[ARCHIVAL ENGINE] IO Bootstrapper complete. Watchdog active.")

def main_loop():
    bootstrapper()
    
    # The Atomic Watchdog Loop
    while True:
        for filename in os.listdir(QUEUE_DIR):
            # Explicitly ignore temporal locks
            if filename.endswith(".tmp"):
                continue
            
            if filename.endswith(".json"):
                queue_path = os.path.join(QUEUE_DIR, filename)
                processing_path = os.path.join(PROCESSING_DIR, filename)
                
                # The Mutual Exclusion Claim
                try:
                    shutil.move(queue_path, processing_path)
                except FileNotFoundError:
                    # Move failed: another worker thread successfully claimed it
                    continue
                
                # Mock Processing
                source_id = filename.replace('.json', '')
                try:
                    with open(processing_path, 'r') as f:
                        data = json.load(f)
                        # Optional: attempt to parse actual document ID if available
                        if isinstance(data, dict) and 'payload' in data and 'mwo_id' in data['payload']:
                            source_id = data['payload']['mwo_id']
                    print(f"[ARCHIVAL ENGINE] Claimed and reading payload for: {source_id}")
                except Exception as e:
                    print(f"[ARCHIVAL ENGINE] Error reading JSON payload for {filename}: {e}")
                    dead_letter_path = os.path.join(DEAD_LETTER_DIR, filename)
                    shutil.move(processing_path, dead_letter_path)
                else:
                    # Terminal Handover
                    permanent_path = os.path.join(PERMANENT_DIR, filename)
                    shutil.move(processing_path, permanent_path)
        
        time.sleep(5)

if __name__ == "__main__":
    main_loop()
