import os
import time
import json
import shutil
import sqlite3
from datetime import datetime, timezone
from jinja2 import Environment, FileSystemLoader
from xhtml2pdf import pisa

# Directory Setup
ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))
UNIVERSAL_MEMORY_DIR = os.path.dirname(ENGINE_DIR)

QUEUE_DIR = os.path.join(UNIVERSAL_MEMORY_DIR, "Archival_Queue")
PROCESSING_DIR = os.path.join(UNIVERSAL_MEMORY_DIR, "Archival_Processing")
PERMANENT_DIR = os.path.join(UNIVERSAL_MEMORY_DIR, "Permanent_Records")
DEAD_LETTER_DIR = os.path.join(UNIVERSAL_MEMORY_DIR, "Dead_Letter")
REGISTRY_DB_PATH = os.path.join(ENGINE_DIR, "archival_registry.db")

# Jinja2 Initialization
env = Environment(loader=FileSystemLoader(os.path.join(ENGINE_DIR, 'templates')))
template = env.get_template('mwo_template.html')

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

def get_next_sequence(module_code):
    now = datetime.now(timezone.utc)
    year = now.strftime('%Y')
    month = now.strftime('%m')
    
    conn = sqlite3.connect(REGISTRY_DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO sequence_ledger (module_code, year, month, last_sequence)
        VALUES (?, ?, ?, 1)
        ON CONFLICT(module_code, year, month)
        DO UPDATE SET last_sequence = last_sequence + 1
        RETURNING last_sequence
    ''', (module_code, year, month))
    
    last_sequence = cursor.fetchone()[0]
    conn.commit()
    conn.close()
    
    return f"{module_code}-{year}-{month}-{last_sequence:04d}"

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
                        if isinstance(data, dict) and 'payload' in data and 'mwo_id' in data['payload']:
                            source_id = data['payload']['mwo_id']
                    
                    print(f"[ARCHIVAL ENGINE] Claimed and reading payload for: {source_id}")
                    
                    # Generate Canonical Sequence
                    sequence_number = get_next_sequence('MWO')
                    
                    # PDF Compilation Engine (Pure-Python Pivot)
                    rendered_html = template.render(sequence_number=sequence_number, **data['payload'])
                    pdf_filename = filename.replace('.json', '.pdf')
                    pdf_path = os.path.join(PROCESSING_DIR, pdf_filename)
                    
                    with open(pdf_path, "w+b") as result_file:
                        pisa_status = pisa.CreatePDF(rendered_html, dest=result_file)
                        
                    if pisa_status.err:
                        raise Exception("xhtml2pdf compilation failed.")
                    
                    print(f"[ARCHIVAL ENGINE] PDF Compiled for: {sequence_number}")
                    
                except Exception as e:
                    print(f"[ARCHIVAL ENGINE] Error processing payload for {filename}: {e}")
                    dead_letter_path = os.path.join(DEAD_LETTER_DIR, filename)
                    shutil.move(processing_path, dead_letter_path)
                    
                    # Cleanup generated PDF if it exists but failed
                    pdf_filename = filename.replace('.json', '.pdf')
                    pdf_path = os.path.join(PROCESSING_DIR, pdf_filename)
                    if os.path.exists(pdf_path):
                        os.remove(pdf_path)
                else:
                    # Terminal Handover
                    permanent_json_path = os.path.join(PERMANENT_DIR, filename)
                    permanent_pdf_path = os.path.join(PERMANENT_DIR, pdf_filename)
                    shutil.move(processing_path, permanent_json_path)
                    shutil.move(pdf_path, permanent_pdf_path)
        
        time.sleep(5)

if __name__ == "__main__":
    main_loop()
