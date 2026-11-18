import sqlite3
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings
from app.db.database import get_db_connection


def test_health_and_database_tables():
    # 1. Start app with TestClient (triggers lifespan which runs init_db)
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    # 2. Inspect SQLite database to check all required tables exist
    conn = get_db_connection(settings.DB_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = {row["name"] for row in cursor.fetchall()}

        required_tables = [
            "meetings",
            "transcript_segments",
            "speakers",
            "action_items",
            "windows",
            "transcript_fts",
        ]

        for table in required_tables:
            assert table in tables, f"Required table '{table}' is missing from database. Found: {tables}"

        # Check indexes exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index';")
        indexes = {row["name"] for row in cursor.fetchall()}
        required_indexes = [
            "idx_transcript_segments_meeting_id",
            "idx_speakers_meeting_id",
            "idx_action_items_meeting_id",
            "idx_windows_meeting_id",
        ]
        for index in required_indexes:
            assert index in indexes, f"Required index '{index}' is missing."

        # Check triggers exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='trigger';")
        triggers = {row["name"] for row in cursor.fetchall()}
        required_triggers = [
            "transcript_segments_ai",
            "transcript_segments_ad",
            "transcript_segments_au",
        ]
        for trigger in required_triggers:
            assert trigger in triggers, f"Required trigger '{trigger}' is missing."

    finally:
        conn.close()
