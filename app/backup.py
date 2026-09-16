# SPDX-License-Identifier: AGPL-3.0-or-later
"""
backup.py - Nightly database backup using SQLite's online backup API.

Safe to run while the live app has the database open (a plain file copy is
not, and can produce a corrupt backup mid-write). Keeps a rolling window of
recent daily backups rather than growing forever.
"""

import sqlite3
import sys
from datetime import datetime
from pathlib import Path

from app.utils import load_config, get_logger, is_mount_available

RETENTION_DAYS = 14


def backup_dir(config: dict) -> Path:
    """Where backups go: the office share if mounted, else the local sync/ fallback."""
    mount = config["office_sync"]["mount_path"]
    fallback = Path(config["office_sync"]["fallback_local"])
    base = Path(mount) / "backups" if is_mount_available(mount) else fallback / "backups"
    base.mkdir(parents=True, exist_ok=True)
    return base


def run_backup(config: dict, logger) -> Path:
    """
    Back up the live database with SQLite's online backup API and prune
    backups older than RETENTION_DAYS. Returns the path written.
    """
    src_path = Path(config["database"]["path"])
    dest_path = backup_dir(config) / f"bookshop_{datetime.now().strftime('%Y-%m-%d')}.db"

    src = sqlite3.connect(src_path)
    try:
        dest = sqlite3.connect(dest_path)
        try:
            src.backup(dest)
        finally:
            dest.close()
    finally:
        src.close()

    logger.info(f"Backup written to {dest_path}")
    _prune_old_backups(dest_path.parent, logger)
    return dest_path


def _prune_old_backups(directory: Path, logger) -> None:
    """Keep only the most recent RETENTION_DAYS backups in directory."""
    backups = sorted(directory.glob("bookshop_*.db"))
    for stale in backups[:-RETENTION_DAYS] if len(backups) > RETENTION_DAYS else []:
        stale.unlink()
        logger.info(f"Pruned old backup: {stale}")


def main():
    config = load_config()
    logger = get_logger("backup", config)
    try:
        path = run_backup(config, logger)
        print(f"Backup written to {path}")
    except Exception:
        logger.exception("Backup failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
