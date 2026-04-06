import os
import shutil
from datetime import datetime
import logging

logger = logging.getLogger("ForgeRollbackManager")
logging.basicConfig(level=logging.INFO)

FACTORY_DIR = os.path.dirname(os.path.abspath(__file__))
BACKUP_DIR = os.path.join(FACTORY_DIR, "forge_backups")

class ForgeRollbackManager:
    """Agentic Version Control for the Autonomous Forge."""
    
    def __init__(self):
        if not os.path.exists(BACKUP_DIR):
            os.makedirs(BACKUP_DIR, exist_ok=True)
            logger.info(f"[RollbackManager] Initialized backup directory at {BACKUP_DIR}")

    def create_backup(self, target_file_path: str) -> str:
        """
        Creates a timestamped backup of a live file before any staging code is merged.
        Returns the path to the backup file.
        """
        if not os.path.exists(target_file_path):
            logger.warning(f"[RollbackManager] Target file {target_file_path} does not exist. No backup created.")
            return ""

        filename = os.path.basename(target_file_path)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"{filename}.{timestamp}.bak"
        backup_path = os.path.join(BACKUP_DIR, backup_filename)

        try:
            shutil.copy2(target_file_path, backup_path)
            logger.info(f"[RollbackManager] Secured backup of {filename} -> {backup_filename}")
            return backup_path
        except Exception as e:
            logger.error(f"[RollbackManager] Failed to create backup for {filename}: {e}")
            raise

    def restore_backup(self, backup_path: str, target_file_path: str) -> bool:
        """
        Restores a file from a specific backup path.
        """
        if not os.path.exists(backup_path):
            logger.error(f"[RollbackManager] Backup file {backup_path} not found.")
            return False

        try:
            shutil.copy2(backup_path, target_file_path)
            logger.info(f"[RollbackManager] Successfully restored {target_file_path} from backup.")
            return True
        except Exception as e:
            logger.error(f"[RollbackManager] Failed to restore backup: {e}")
            return False

if __name__ == "__main__":
    # Internal module test
    manager = ForgeRollbackManager()
    logger.info("ForgeRollbackManager stands ready.")
