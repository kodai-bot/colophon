# SPDX-License-Identifier: AGPL-3.0-or-later
"""
tests/test_backup.py - Tests for the SQLite online-backup mechanism (S-31)
"""

import sqlite3

from app.backup import run_backup, _prune_old_backups


def _make_config(tmp_path):
    db_path = tmp_path / "bookshop.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE catalog (id INTEGER PRIMARY KEY, title TEXT)")
    conn.execute("INSERT INTO catalog (title) VALUES ('Test Book')")
    conn.commit()
    conn.close()

    sync_dir = tmp_path / "sync"
    sync_dir.mkdir()
    return {
        "database": {"path": str(db_path)},
        "office_sync": {
            "mount_path": str(tmp_path / "nonexistent_mount"),
            "fallback_local": str(sync_dir) + "/",
        },
    }, db_path


class _NullLogger:
    def info(self, *a, **k): pass
    def exception(self, *a, **k): pass


def test_backup_produces_valid_distinct_file(tmp_path):
    config, db_path = _make_config(tmp_path)
    backup_path = run_backup(config, _NullLogger())

    assert backup_path != db_path
    assert backup_path.exists()

    conn = sqlite3.connect(backup_path)
    row = conn.execute("SELECT title FROM catalog").fetchone()
    conn.close()
    assert row[0] == "Test Book"


def test_prune_keeps_only_recent_backups(tmp_path):
    directory = tmp_path / "backups"
    directory.mkdir()
    for i in range(20):
        (directory / f"bookshop_2026-01-{i + 1:02d}.db").write_text("x")

    _prune_old_backups(directory, _NullLogger())

    remaining = sorted(directory.glob("bookshop_*.db"))
    assert len(remaining) == 14
    assert remaining[-1].name == "bookshop_2026-01-20.db"
