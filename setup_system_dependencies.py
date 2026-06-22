import os
import sys
import shutil
import subprocess

def check_command(cmd):
    """Check if command is available on PATH."""
    return shutil.which(cmd) is not None

def check_windows_path(paths):
    """Check if any of the common Windows paths exist."""
    for p in paths:
        if os.path.exists(p):
            return p
    return None

def is_tesseract_installed():
    if check_command("tesseract"):
        return True
    if sys.platform == "win32":
        win_paths = [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"
        ]
        if check_windows_path(win_paths):
            return True
    return False

def is_libreoffice_installed():
    if check_command("soffice") or check_command("libreoffice"):
        return True
    if sys.platform == "win32":
        win_paths = [
            r"C:\Program Files\LibreOffice\program\soffice.exe",
            r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"
        ]
        if check_windows_path(win_paths):
            return True
    return False

def install_tesseract():
    print("  [SETUP] Tesseract OCR not found. Installing automatically...")
    try:
        if sys.platform == "win32":
            print("  [SETUP] Running winget to install Tesseract OCR...")
            subprocess.run([
                "winget", "install", "--id", "UB-Mannheim.TesseractOCR", 
                "--accept-source-agreements", "--accept-package-agreements"
            ], check=True)
            print("  [OK] Tesseract OCR installation initiated successfully!")
        elif sys.platform == "linux" or sys.platform == "linux2":
            print("  [SETUP] Running apt-get to install tesseract-ocr...")
            subprocess.run(["sudo", "apt-get", "update"], check=True)
            subprocess.run(["sudo", "apt-get", "install", "-y", "tesseract-ocr"], check=True)
            print("  [OK] Tesseract OCR installed successfully!")
        elif sys.platform == "darwin":
            print("  [SETUP] Running brew to install tesseract...")
            subprocess.run(["brew", "install", "tesseract"], check=True)
            print("  [OK] Tesseract OCR installed successfully!")
        else:
            print("  [WARN] Unknown platform. Please install Tesseract OCR manually.")
    except Exception as e:
        print(f"  [ERROR] Failed to install Tesseract OCR: {e}")
        print("  Please install it manually.")

def install_libreoffice():
    print("  [SETUP] LibreOffice not found. Installing automatically...")
    try:
        if sys.platform == "win32":
            print("  [SETUP] Running winget to install LibreOffice...")
            # Run normally so if UAC pops up, user can approve it
            subprocess.run([
                "winget", "install", "--id", "TheDocumentFoundation.LibreOffice", 
                "--accept-source-agreements", "--accept-package-agreements"
            ], check=True)
            print("  [OK] LibreOffice installation initiated successfully!")
        elif sys.platform == "linux" or sys.platform == "linux2":
            print("  [SETUP] Running apt-get to install libreoffice...")
            subprocess.run(["sudo", "apt-get", "update"], check=True)
            subprocess.run(["sudo", "apt-get", "install", "-y", "libreoffice"], check=True)
            print("  [OK] LibreOffice installed successfully!")
        elif sys.platform == "darwin":
            print("  [SETUP] Running brew to install libreoffice...")
            subprocess.run(["brew", "install", "--cask", "libreoffice"], check=True)
            print("  [OK] LibreOffice installed successfully!")
        else:
            print("  [WARN] Unknown platform. Please install LibreOffice manually.")
    except Exception as e:
        print(f"  [ERROR] Failed to install LibreOffice: {e}")
        print("  Please install it manually.")

def main():
    print("\n" + "="*60)
    print("  ⚡ Antigravity System Dependencies Auto-Installer")
    print("="*60 + "\n")
    
    # 1. Check Tesseract
    if is_tesseract_installed():
        print("  [OK] Tesseract OCR is already installed.")
    else:
        install_tesseract()
        
    # 2. Check LibreOffice
    if is_libreoffice_installed():
        print("  [OK] LibreOffice is already installed.")
    else:
        install_libreoffice()
        
    print("\n" + "="*60 + "\n")

if __name__ == "__main__":
    main()
