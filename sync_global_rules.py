import os
import shutil
import sys
from pathlib import Path

def sync():
    print("--- ANTIGRAVITY RULE SYNCHRONIZATION ---")
    
    # 1. Resolve source paths relative to script location
    script_dir = Path(__file__).parent.resolve()
    templates_dir = script_dir / ".agent" / "global_templates"
    
    claude_src = templates_dir / "CLAUDE.md"
    gemini_src = templates_dir / "GEMINI.md"
    
    if not (claude_src.exists() and gemini_src.exists()):
        print(f"[!] Templates not found under {templates_dir}")
        sys.exit(1)
        
    # 2. Resolve destination paths relative to user home directory
    home = Path.home()
    claude_dest_dir = home / ".claude"
    gemini_dest_dir = home / ".gemini"
    
    claude_dest = claude_dest_dir / "CLAUDE.md"
    gemini_dest = gemini_dest_dir / "GEMINI.md"
    
    # 3. Create target directories if missing
    claude_dest_dir.mkdir(parents=True, exist_ok=True)
    gemini_dest_dir.mkdir(parents=True, exist_ok=True)
    
    # 4. Copy templates
    print(f"[*] Syncing CLAUDE.md: {claude_src} -> {claude_dest}")
    shutil.copy2(claude_src, claude_dest)
    
    print(f"[*] Syncing GEMINI.md: {gemini_src} -> {gemini_dest}")
    shutil.copy2(gemini_src, gemini_dest)
    
    print("[+] Rule synchronization complete. Global files are now consistent.")

if __name__ == "__main__":
    sync()
