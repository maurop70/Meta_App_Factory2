"""
Sentinel Bridge — Vault Importer CLI
======================================
Securely ingests a GCP Service Account JSON credential file, encrypts it
using Fernet AES-128 via FernetVault, and stores it in the SQLite/vault matrix.
Doctrine Enforcement: Moves the original JSON file to a .secure_backup/ directory
and secures it with OS-level permissions.
"""

import os
import sys
import json
import argparse
import shutil
import subprocess
from pathlib import Path

# Add parent directory to sys.path to resolve imports correctly
sys.path.insert(0, str(Path(__file__).resolve().parent))
from fernet_vault import FernetVault

def secure_folder_windows(folder_path: Path):
    """
    Apply strict OS-level permissions on Windows using icacls.
    Removes inheritance and grants Full Control only to the current user.
    """
    try:
        folder_str = str(folder_path.resolve())
        username = os.getlogin()
        
        # 1. Disable inheritance and copy permissions
        subprocess.run(["icacls", folder_str, "/inheritance:r"], capture_output=True, check=True)
        # 2. Grant Full Control only to the active user
        subprocess.run(["icacls", folder_str, "/grant:r", f"{username}:(OI)(CI)F"], capture_output=True, check=True)
        print(f"[IMPORTER] Secured backup folder '{folder_path.name}' with exclusive permissions for User '{username}'.")
    except Exception as e:
        print(f"[WARNING] Could not apply strict ACLs via icacls: {e}. Falling back to standard chmod.")
        try:
            os.chmod(folder_path, 0o700)
        except Exception:
            pass

def main():
    parser = argparse.ArgumentParser(description="Secure GCP JSON Credentials Importer for Fernet Vault")
    parser.add_argument(
        "--file", 
        required=True, 
        help="Path to the plaintext GCP JSON Service Account key file"
    )
    parser.add_argument(
        "--key", 
        default="google_drive_service_account", 
        help="Key name to store the credentials in the vault (default: google_drive_service_account)"
    )
    
    args = parser.parse_args()
    
    file_path = Path(args.file)
    if not file_path.exists():
        print(f"FATAL: Source file '{args.file}' does not exist.")
        sys.exit(1)
        
    try:
        # Validate that the file is valid JSON
        with open(file_path, "r", encoding="utf-8") as f:
            creds_data = json.load(f)
            
        # Ensure it contains typical GCP service account fields
        required_fields = ["project_id", "private_key", "client_email", "type"]
        if not all(field in creds_data for field in required_fields):
            print("WARNING: Input JSON does not appear to contain standard GCP service account fields.")
            
        creds_str = json.dumps(creds_data)
        
        # Store in FernetVault
        vault = FernetVault()
        vault.store(args.key, creds_str)
        print(f"[IMPORTER] Decrypted credentials successfully encrypted and saved to vault under key: '{args.key}'")
        
        # Doctrine Enforcement: Move to .secure_backup/ with strict permissions
        backup_dir = Path(__file__).resolve().parent.parent / ".secure_backup"
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Set OS permissions on backup directory
        if os.name == 'nt':
            secure_folder_windows(backup_dir)
        else:
            os.chmod(backup_dir, 0o700)
            
        backup_file_path = backup_dir / f"{file_path.stem}_backup_{int(os.getpid())}.json"
        
        # Move the source file to backup
        shutil.move(str(file_path), str(backup_file_path))
        print(f"[IMPORTER] Plaintext source file securely moved to: {backup_file_path}")
        
    except json.JSONDecodeError:
        print("FATAL: Provided file is not a valid JSON document.")
        sys.exit(1)
    except Exception as e:
        print(f"FATAL: Encryption or move operation failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
