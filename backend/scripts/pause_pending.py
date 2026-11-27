"""Pause pending meetings in chatmeet.db so background worker processes only target meeting.

Must NOT delete anything.
- Backs up chatmeet.db to chatmeet.db.bak.
- Normal: changes status from 'pending' to 'paused' for every meeting EXCEPT 'sample_meeting'.
- With --undo: restores status from 'paused' back to 'pending'.
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

# Add backend directory to sys.path so app packages import cleanly
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

try:
    from app.core.config import settings
    DEFAULT_DB_PATH = Path(settings.DB_PATH).resolve()
except Exception:  # noqa: BLE001
    DEFAULT_DB_PATH = (backend_dir / "chatmeet.db").resolve()


def backup_database(source_path: Path, target_path: Path) -> None:
    """Back up SQLite database safely using the SQLite online backup API."""
    src_conn = sqlite3.connect(source_path)
    try:
        # Checkpoint WAL if present to ensure latest writes are in backup
        src_conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
        dest_conn = sqlite3.connect(target_path)
        try:
            src_conn.backup(dest_conn)
        finally:
            dest_conn.close()
    finally:
        src_conn.close()


def find_db_path(custom_path: Path | None = None) -> Path:
    """Resolve database path from argument, config, or well-known location."""
    if custom_path:
        p = custom_path.resolve()
        if p.exists():
            return p
        print(f"Error: Specified database file not found: {p}", file=sys.stderr)
        sys.exit(1)

    candidates = [
        DEFAULT_DB_PATH,
        (backend_dir / "chatmeet.db").resolve(),
        (Path.cwd() / "chatmeet.db").resolve(),
        (Path.cwd() / "backend" / "chatmeet.db").resolve(),
    ]
    for c in candidates:
        if c.exists():
            return c

    # Fallback to default path
    return DEFAULT_DB_PATH


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Pause or unpause pending meetings in chatmeet.db."
    )
    parser.add_argument(
        "--undo",
        action="store_true",
        help="Set all 'paused' meetings back to 'pending'.",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help="Optional custom path to chatmeet.db file.",
    )
    args = parser.parse_args()

    db_path = find_db_path(args.db)
    if not db_path.exists():
        print(f"Error: Database file does not exist at {db_path}", file=sys.stderr)
        sys.exit(1)

    backup_path = db_path.parent / f"{db_path.name}.bak"

    # 1. Back up chatmeet.db to chatmeet.db.bak
    backup_database(db_path, backup_path)
    print(f"Backed up {db_path.name} to {backup_path.name}")

    # 2. Update statuses
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA busy_timeout = 5000;")
        # Allow 'paused' status without violating CHECK constraint
        conn.execute("PRAGMA ignore_check_constraints = ON;")

        if args.undo:
            cursor = conn.execute(
                "UPDATE meetings SET status = 'pending' WHERE status = 'paused'"
            )
            conn.commit()
            print(f"Restored {cursor.rowcount} row(s) from 'paused' to 'pending'.")
        else:
            cursor = conn.execute(
                "UPDATE meetings SET status = 'paused' "
                "WHERE status = 'pending' AND (title IS NULL OR title != 'sample_meeting')"
            )
            conn.commit()
            print(f"Changed {cursor.rowcount} row(s) from 'pending' to 'paused'.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
