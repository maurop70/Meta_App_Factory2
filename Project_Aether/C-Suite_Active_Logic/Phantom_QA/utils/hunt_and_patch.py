# hunt_and_patch.py
# To be saved in the root Antigravity-AI Agents directory

import os
import sys
from pathlib import Path

# --- Configuration ---
# Assuming this script is in Meta_App_Factory/Project_Aether/C-Suite_Active_Logic/Phantom_QA/utils
PHANTOM_QA_ROOT_DIR = str(Path(__file__).parent.parent)
TARGET_FILE_EXTENSIONS = ('.jsx', '.tsx', '.html')

OLD_VERSION_STRING = "v1.0.0"
NEW_VERSION_STRING = "V3.0 Backend"

OLD_BRAND_STRING = "ANTIGRAVITY-AI"
NEW_BRAND_STRING = "Phantom QA Elite"

def hunt_and_patch():
    """
    Recursively scans the Phantom_QA directory for specified file types,
    replaces hardcoded version and brand strings, and overwrites the files.
    """
    phantom_qa_path = Path(PHANTOM_QA_ROOT_DIR)

    if not phantom_qa_path.is_dir():
        print(f"Error: Directory '{PHANTOM_QA_ROOT_DIR}' not found. "
              f"Ensure the script is in the parent directory of '{PHANTOM_QA_ROOT_DIR}'.")
        sys.exit(1)

    print(f"Initiating Omniscient Hunt in '{phantom_qa_path}' for '{OLD_VERSION_STRING}' and '{OLD_BRAND_STRING}'...")
    patched_files_count = 0

    for root, _, files in os.walk(phantom_qa_path):
        for filename in files:
            if filename.lower().endswith(TARGET_FILE_EXTENSIONS): # .lower() for case-insensitive extension check
                file_path = Path(root) / filename
                print(f"Scanning: {file_path}")
                try:
                    original_content = file_path.read_text(encoding='utf-8')
                    new_content = original_content
                    file_modified = False

                    # Check for version string
                    if OLD_VERSION_STRING in new_content:
                        new_content = new_content.replace(OLD_VERSION_STRING, NEW_VERSION_STRING)
                        print(f"  - Replaced '{OLD_VERSION_STRING}' with '{NEW_VERSION_STRING}'")
                        file_modified = True

                    # Check for brand string
                    if OLD_BRAND_STRING in new_content:
                        new_content = new_content.replace(OLD_BRAND_STRING, NEW_BRAND_STRING)
                        print(f"  - Replaced '{OLD_BRAND_STRING}' with '{NEW_BRAND_STRING}'")
                        file_modified = True

                    if file_modified:
                        file_path.write_text(new_content, encoding='utf-8')
                        print(f"Successfully patched and overwrote: {file_path}")
                        patched_files_count += 1

                except UnicodeDecodeError:
                    print(f"  Warning: Could not read {file_path} with utf-8 encoding. Skipping.")
                except Exception as e:
                    print(f"  Error processing {file_path}: {e}")

    if patched_files_count > 0:
        print(f"\nOmniscient Hunt complete. Total files patched: {patched_files_count}")
    else:
        print("\nOmniscient Hunt complete. No matching files found or no changes needed.")

if __name__ == "__main__":
    hunt_and_patch()
