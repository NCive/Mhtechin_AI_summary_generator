import os
import sqlite3
from pathlib import Path
from contextlib import contextmanager
from typing import Generator
from app.core.config import settings

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def get_db_connection(db_path: str = None) -> sqlite3.Connection:
    target_path = db_path or settings.DB_PATH
    # Ensure directory exists if path has parent directories
    parent_dir = Path(target_path).parent
    if parent_dir and not parent_dir.exists():
        parent_dir.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(target_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    return conn


def init_db(db_path: str = None) -> None:
    target_path = db_path or settings.DB_PATH
    conn = get_db_connection(target_path)
    try:
        with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
            schema_sql = f.read()
        conn.executescript(schema_sql)
        conn.commit()
    finally:
        conn.close()

    # Ensure media directory exists
    media_path = Path(settings.MEDIA_DIR)
    if not media_path.exists():
        media_path.mkdir(parents=True, exist_ok=True)


@contextmanager
def get_db() -> Generator[sqlite3.Connection, None, None]:
    conn = get_db_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
