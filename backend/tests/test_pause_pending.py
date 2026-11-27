import sqlite3
import subprocess
import sys
from pathlib import Path


def test_pause_pending_script(tmp_path):
    test_db = tmp_path / "chatmeet.db"
    conn = sqlite3.connect(test_db)
    conn.execute(
        """CREATE TABLE meetings (
            id TEXT PRIMARY KEY,
            title TEXT,
            status TEXT CHECK(status IN ('pending', 'processing', 'done', 'failed')) DEFAULT 'pending'
        )"""
    )
    conn.execute("INSERT INTO meetings (id, title, status) VALUES ('1', 'sample_meeting', 'pending')")
    conn.execute("INSERT INTO meetings (id, title, status) VALUES ('2', 'other_meeting_1', 'pending')")
    conn.execute("INSERT INTO meetings (id, title, status) VALUES ('3', 'other_meeting_2', 'pending')")
    conn.execute("INSERT INTO meetings (id, title, status) VALUES ('4', NULL, 'pending')")
    conn.execute("INSERT INTO meetings (id, title, status) VALUES ('5', 'done_meeting', 'done')")
    conn.commit()
    conn.close()

    script_path = Path(__file__).resolve().parent.parent / "scripts" / "pause_pending.py"

    # 1. Run pause_pending.py
    proc = subprocess.run(
        [sys.executable, str(script_path), "--db", str(test_db)],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "Backed up chatmeet.db to chatmeet.db.bak" in proc.stdout
    assert "Changed 3 row(s) from 'pending' to 'paused'." in proc.stdout

    # Verify backup exists and has all rows
    bak_path = tmp_path / "chatmeet.db.bak"
    assert bak_path.exists()
    bak_conn = sqlite3.connect(bak_path)
    bak_rows = bak_conn.execute("SELECT id, status FROM meetings ORDER BY id").fetchall()
    bak_conn.close()
    assert len(bak_rows) == 5
    # In backup, row 2, 3, 4 are still 'pending'
    assert bak_rows[1][1] == "pending"

    # Verify rows in DB after pause: sample_meeting is 'pending', 2, 3, 4 are 'paused', 5 is 'done'
    conn = sqlite3.connect(test_db)
    rows = conn.execute("SELECT id, title, status FROM meetings ORDER BY id").fetchall()
    conn.close()

    assert rows[0] == ("1", "sample_meeting", "pending")
    assert rows[1] == ("2", "other_meeting_1", "paused")
    assert rows[2] == ("3", "other_meeting_2", "paused")
    assert rows[3] == ("4", None, "paused")
    assert rows[4] == ("5", "done_meeting", "done")

    # 2. Run with --undo
    proc_undo = subprocess.run(
        [sys.executable, str(script_path), "--db", str(test_db), "--undo"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "Restored 3 row(s) from 'paused' to 'pending'." in proc_undo.stdout

    # Verify rows in DB after undo
    conn = sqlite3.connect(test_db)
    rows_after_undo = conn.execute("SELECT id, title, status FROM meetings ORDER BY id").fetchall()
    conn.close()

    assert rows_after_undo[0] == ("1", "sample_meeting", "pending")
    assert rows_after_undo[1] == ("2", "other_meeting_1", "pending")
    assert rows_after_undo[2] == ("3", "other_meeting_2", "pending")
    assert rows_after_undo[3] == ("4", None, "pending")
    assert rows_after_undo[4] == ("5", "done_meeting", "done")
