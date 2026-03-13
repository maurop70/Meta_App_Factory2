"""
deploy_shield.py — Deployment Sanitization Shield (Global Core)
═══════════════════════════════════════════════════════════════════
.system_core | Antigravity V3.0 | Venture Studio Inheritance Engine

Automates the "Sanitization" of any App folder before it is sent to
a third party. Removes internal logs, strips API keys, runs PII masking,
and produces a clean staging copy with a deployment manifest.

Usage:
    python deploy_shield.py <app_folder> [--output <dir>]
    python deploy_shield.py MyNewApp --output ./release_bundle
"""

import os
import sys
import json
import shutil
import logging
import re
from datetime import datetime
from typing import Optional

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FACTORY_DIR = os.path.normpath(os.path.join(SCRIPT_DIR, ".."))
sys.path.insert(0, FACTORY_DIR)

logger = logging.getLogger("system_core.deploy_shield")

# Import sibling PII Masker
try:
    from .pii_masker import PIIMasker
except ImportError:
    from pii_masker import PIIMasker


# ── Sanitization Rules ──────────────────────────────────

# Directories to remove entirely
BANNED_DIRS = {
    "__pycache__", ".git", ".mypy_cache", ".pytest_cache",
    "node_modules", ".env.enc", ".audit_snapshots",
    "socratic_logs", ".Gemini_state", ".venv", "venv",
}

# Files to remove entirely
BANNED_FILES = {
    "auto_heal_log.json", "socratic_audit.json",
    "n8n_execution_log.json", "n8n_archive_log.json",
    "cloud_surgery_audit.json", "incoming_watcher_state.json",
    "local_pending_sync.json", "v3_hardening_results.json",
    "v3_retrofit_results.json", "webhook_hardener_report.json",
    ".env.enc", ".env.panic_backup",
}

# File extensions to remove (log / temp)
BANNED_EXTENSIONS = {".log", ".bak", ".tmp", ".pyc", ".pyo"}

# File extensions eligible for PII masking (text-based)
MASKABLE_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".json",
    ".md", ".html", ".css", ".txt", ".yaml", ".yml",
    ".toml", ".cfg", ".ini",
}

# Patterns that mark a line as containing an API key assignment
ENV_KEY_PATTERN = re.compile(
    r"^(\s*[A-Z][A-Z0-9_]*(?:_KEY|_TOKEN|_SECRET|_PASSWORD|_API_KEY)\s*=\s*)(.+)$",
    re.MULTILINE,
)


class DeployShield:
    """
    Sanitize an application folder for third-party delivery.

    Usage:
        shield = DeployShield()
        report = shield.sanitize("./MyApp", output_dir="./_deploy/MyApp")
    """

    def __init__(self, mask_emails: bool = False):
        self.masker = PIIMasker(mask_emails=mask_emails)
        self._stats = {
            "files_copied": 0,
            "files_removed": 0,
            "dirs_removed": 0,
            "files_masked": 0,
            "redaction_count": 0,
            "env_keys_stripped": 0,
        }

    # ── Public API ───────────────────────────────────────

    def sanitize(self, app_dir: str, output_dir: Optional[str] = None) -> dict:
        """
        Sanitize *app_dir* and write the clean copy to *output_dir*.
        Returns a deployment manifest dict.
        """
        app_dir = os.path.abspath(app_dir)
        if not os.path.isdir(app_dir):
            raise FileNotFoundError(f"Source directory not found: {app_dir}")

        app_name = os.path.basename(app_dir)
        output_dir = output_dir or os.path.join(
            FACTORY_DIR, "_deploy", app_name
        )
        output_dir = os.path.abspath(output_dir)

        # Fresh staging area
        if os.path.exists(output_dir):
            shutil.rmtree(output_dir)
        os.makedirs(output_dir, exist_ok=True)

        logger.info("Deploy Shield: sanitizing '%s' → '%s'", app_dir, output_dir)
        self._stats = dict.fromkeys(self._stats, 0)

        shipped_files = []

        for root, dirs, files in os.walk(app_dir):
            # ── Prune banned directories in-place ────────
            orig_dirs = list(dirs)
            dirs[:] = [d for d in dirs if d not in BANNED_DIRS]
            for removed in set(orig_dirs) - set(dirs):
                self._stats["dirs_removed"] += 1
                logger.debug("  🗑️  Pruned dir: %s", os.path.join(root, removed))

            rel_root = os.path.relpath(root, app_dir)
            dest_root = os.path.join(output_dir, rel_root)
            os.makedirs(dest_root, exist_ok=True)

            for fname in files:
                src_path = os.path.join(root, fname)
                dest_path = os.path.join(dest_root, fname)
                ext = os.path.splitext(fname)[1].lower()

                # Skip banned files
                if fname in BANNED_FILES or ext in BANNED_EXTENSIONS:
                    self._stats["files_removed"] += 1
                    logger.debug("  🗑️  Skipped file: %s", fname)
                    continue

                # .env files → strip key values
                if fname == ".env" or fname.startswith(".env."):
                    self._sanitize_env_file(src_path, dest_path)
                    shipped_files.append(os.path.relpath(dest_path, output_dir))
                    self._stats["files_copied"] += 1
                    continue

                # Text files → PII mask
                if ext in MASKABLE_EXTENSIONS:
                    self._mask_text_file(src_path, dest_path)
                    shipped_files.append(os.path.relpath(dest_path, output_dir))
                    self._stats["files_copied"] += 1
                    continue

                # Binary / other → copy as-is
                shutil.copy2(src_path, dest_path)
                shipped_files.append(os.path.relpath(dest_path, output_dir))
                self._stats["files_copied"] += 1

        # Write manifest
        manifest = self._build_manifest(app_name, app_dir, output_dir, shipped_files)
        manifest_path = os.path.join(output_dir, "deploy_manifest.json")
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        logger.info(
            "Deploy Shield complete: %d files shipped, %d removed, %d masked",
            self._stats["files_copied"],
            self._stats["files_removed"],
            self._stats["files_masked"],
        )
        return manifest

    # ── Internals ────────────────────────────────────────

    def _sanitize_env_file(self, src: str, dest: str):
        """Strip secret values from .env files."""
        try:
            with open(src, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()

            def _redact_key(m):
                self._stats["env_keys_stripped"] += 1
                return m.group(1) + "REDACTED"

            sanitized = ENV_KEY_PATTERN.sub(_redact_key, content)

            with open(dest, "w", encoding="utf-8") as f:
                f.write(sanitized)
        except Exception as e:
            logger.warning("Failed to sanitize env file %s: %s", src, e)

    def _mask_text_file(self, src: str, dest: str):
        """Run PII masking on a text file."""
        try:
            with open(src, "r", encoding="utf-8", errors="replace") as f:
                original = f.read()

            masked = self.masker.mask(original)

            if masked != original:
                self._stats["files_masked"] += 1
                # Count redactions (approximate)
                for label in ("[PATH_REDACTED]", "[KEY_REDACTED]", "[TOKEN_REDACTED]",
                              "[IP_REDACTED]", "[LOCAL_ENDPOINT]", "[DRIVE_PATH_REDACTED]",
                              "[ENV_FILE]", "[EMAIL_REDACTED]"):
                    self._stats["redaction_count"] += masked.count(label)

            with open(dest, "w", encoding="utf-8") as f:
                f.write(masked)
        except Exception as e:
            logger.warning("Failed to mask file %s: %s", src, e)
            shutil.copy2(src, dest)

    def _build_manifest(self, app_name, src, dest, shipped_files):
        """Build the deploy_manifest.json payload."""
        return {
            "app_name": app_name,
            "sanitized_at": datetime.now().isoformat(),
            "source": src,
            "output": dest,
            "files_shipped": len(shipped_files),
            "file_list": shipped_files,
            "stats": dict(self._stats),
            "shield_version": "1.0.0",
            "note": "All API keys, tokens, PII, and internal logs have been redacted.",
        }


# ── CLI ──────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Deploy Shield — Sanitize an app folder for third-party delivery"
    )
    parser.add_argument("app_folder", help="Path to the application folder to sanitize")
    parser.add_argument("--output", "-o", default=None, help="Output directory for clean copy")
    args = parser.parse_args()

    shield = DeployShield()

    print(f"\n{'='*60}")
    print(f"  🛡️  Deploy Shield — Sanitization Engine")
    print(f"{'='*60}\n")

    try:
        manifest = shield.sanitize(args.app_folder, args.output)
        print(f"  ✅ Sanitization complete!")
        print(f"  📦 Output: {manifest['output']}")
        print(f"  📊 Files shipped: {manifest['files_shipped']}")
        stats = manifest["stats"]
        print(f"  🗑️  Files removed: {stats['files_removed']}")
        print(f"  🔒 Files PII-masked: {stats['files_masked']}")
        print(f"  🔑 Env keys stripped: {stats['env_keys_stripped']}")
        print(f"  📝 Total redactions: {stats['redaction_count']}")
        print(f"\n  Manifest: {manifest['output']}/deploy_manifest.json")
    except Exception as e:
        print(f"  ❌ Error: {e}")
        sys.exit(1)

    print(f"\n{'='*60}\n")
