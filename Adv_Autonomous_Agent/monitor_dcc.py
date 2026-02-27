import sys
import os
import time
import json
from datetime import datetime

# Path Configuration
# Assumes script is run from project root or utils
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
if "utils" in PROJECT_DIR.lower():
    PROJECT_DIR = os.path.dirname(PROJECT_DIR)
    
CACHE_FILE = os.path.join(PROJECT_DIR, ".Gemini_state", ".sentry_cache.json")

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def load_cache():
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, 'r') as f:
                return json.load(f)
        else:
            return []
    except Exception as e:
        return ["ERROR: " + str(e)]

if __name__ == "__main__":
    clear_screen()
    print(f"--- DCC CONTEXT MONITOR [Interval: 10s] ---")
    print(f"Watching: {CACHE_FILE}\n")
    print("Press Ctrl+C to stop.\n")
    
    try:
        while True:
            timestamp = datetime.now().strftime("%H:%M:%S")
            data = load_cache()
            
            # Repaint
            clear_screen()
            print(f"==========================================")
            print(f"   DCC COMMAND CENTER MONITOR  |  {timestamp}")
            print(f"==========================================")
            
            if isinstance(data, list):
                if not data:
                    print("  (Status: IDLE / No Context)")
                else:
                    print(f"  Status: ACTIVE ({len(data)} Items in Context Memory)")
                    print("-" * 42)
                    for i, item in enumerate(data):
                        # Clean up formatting for display
                        preview = item.replace('\n', ' ')
                        preview = (preview[:80] + '...') if len(preview) > 80 else preview
                        print(f"  {i+1}. {preview}")
            else:
                 print(f"  Status: UNKNOWN FORMAT ({type(data)})")

            print("-" * 42)
            print("\nUpdating in 10s...")
            
            time.sleep(10)

    except KeyboardInterrupt:
        print("\nMonitor Stopped.")
