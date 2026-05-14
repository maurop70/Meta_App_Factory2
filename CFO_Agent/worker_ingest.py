import sys
import os
import json
import csv
from datetime import date
from pydantic import BaseModel, ValidationError

class LedgerRow(BaseModel):
    date: date
    transaction_type: str
    amount: float
    balance: float

def process_csv(filepath: str):
    accepted = 0
    rejected = 0
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    LedgerRow(**row)
                    accepted += 1
                except ValidationError:
                    rejected += 1
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        
    filename = os.path.basename(filepath)
    job_id = os.path.splitext(filename)[0]
    
    summary = {
        "job_id": job_id,
        "accepted_rows": accepted,
        "rejected_rows": rejected
    }
    
    summary_path = os.path.join(os.path.dirname(filepath), f"job_{job_id}_summary.json")
    with open(summary_path, 'w') as f:
        json.dump(summary, f)
        
    try:
        os.remove(filepath)
        print(f"Successfully processed and removed {filepath}")
    except Exception as e:
        print(f"Failed to remove {filepath}: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        process_csv(sys.argv[1])
    else:
        print("Error: No CSV filepath provided.")
