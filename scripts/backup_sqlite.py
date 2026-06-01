#!/usr/bin/env python3
import os
import sqlite3
import sys
import time
from pathlib import Path


DB_PATH = Path(os.environ.get("TCM_DB_PATH", "/opt/tcm-tea-studio/data/tcm_tea_studio.sqlite3"))
BACKUP_DIR = Path(os.environ.get("TCM_BACKUP_DIR", "/root/tcm-tea-studio-backups/sqlite"))
RETENTION_DAYS = int(os.environ.get("TCM_BACKUP_RETENTION_DAYS", "14"))


def backup_database():
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Database not found: {DB_PATH}")

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    backup_path = BACKUP_DIR / f"tcm_tea_studio_{timestamp}.sqlite3"

    source_uri = f"file:{DB_PATH}?mode=ro"
    with sqlite3.connect(source_uri, uri=True) as source:
        with sqlite3.connect(backup_path) as target:
            source.backup(target)
            integrity = target.execute("PRAGMA integrity_check").fetchone()[0]
            if integrity != "ok":
                raise RuntimeError(f"Backup integrity check failed: {integrity}")

    return backup_path


def cleanup_old_backups():
    if RETENTION_DAYS <= 0:
        return []

    cutoff = time.time() - RETENTION_DAYS * 24 * 60 * 60
    removed = []
    for path in BACKUP_DIR.glob("tcm_tea_studio_*.sqlite3"):
        if path.stat().st_mtime < cutoff:
            path.unlink()
            removed.append(path)
    return removed


def main():
    backup_path = backup_database()
    removed = cleanup_old_backups()
    size = backup_path.stat().st_size
    print(f"backup={backup_path} size={size} removed={len(removed)}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"backup_failed={exc}", file=sys.stderr)
        sys.exit(1)
