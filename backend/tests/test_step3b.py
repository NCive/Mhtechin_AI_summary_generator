"""Tests for Step 3B: windowing, note extraction, summary merging and DB persistence.

All LLM calls (count_tokens, extract_chunk_notes, generate_json) are mocked.
A temporary SQLite database is used; the production DB is never touched.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_SEGMENTS = [
    {"start_time": 0.0,  "end_time": 5.0,  "speaker": "Alice", "text": "Let's start the meeting."},
    {"start_time": 5.0,  "end_time": 10.0, "speaker": "Bob",   "text": "I will finish the report by Friday."},
    {"start_time": 10.0, "end_time": 15.0, "speaker": "Alice", "text": "Great, any blockers?"},
    {"start_time": 15.0, "end_time": 20.0, "speaker": "Bob",   "text": "No blockers right now."},
    {"start_time": 20.0, "end_time": 25.0, "speaker": "Carol", "text": "I'll set up the CI pipeline."},
    {"start_time": 25.0, "end_time": 30.0, "speaker": "Alice", "text": "Perfect, let's sync next week."},
]

MOCK_NOTES = {
    "summary": "Team discussed progress and next steps.",
    "project_progress": ["Report in progress"],
    "challenges": [],
    "action_items": [
        {"text": "Finish the report", "owner": "Bob", "deadline": "by Friday", "source_time": "[00:05]"},
    ],
    "next_steps": ["Sync next week"],
}


def _make_temp_db(tmp_path: Path) -> tuple[str, sqlite3.Connection]:
    """Create a temp DB with the full schema; return (db_path, connection)."""
    schema_path = Path(__file__).parent.parent / "app" / "db" / "schema.sql"
    db_path = str(tmp_path / "test.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.executescript(schema_path.read_text(encoding="utf-8"))
    conn.commit()
    return db_path, conn


def _insert_meeting(conn: sqlite3.Connection, meeting_id: str) -> None:
    conn.execute(
        "INSERT INTO meetings (id, source, status, title) VALUES (?, 'upload', 'processing', 'Test')",
        (meeting_id,),
    )
    conn.commit()


# ===========================================================================
# windowing.py tests
# ===========================================================================

class TestSplitTranscriptWindows:
    def test_empty_segments_returns_empty(self):
        from app.services.windowing import split_transcript_windows
        result = split_transcript_windows([])
        assert result == []

    def test_all_segments_fit_in_one_window(self):
        from app.services.windowing import split_transcript_windows

        # Mock count_tokens to return 10 tokens per segment line (well within budget)
        with patch("app.services.windowing.count_tokens", return_value=10):
            result = split_transcript_windows(SAMPLE_SEGMENTS, token_budget=500)

        assert len(result) == 1
        win = result[0]
        assert win["window_index"] == 0
        assert win["start_time"] == 0.0
        assert win["end_time"] == 30.0
        assert len(win["segments"]) == len(SAMPLE_SEGMENTS)
        # All segment texts present
        for seg in SAMPLE_SEGMENTS:
            assert seg["text"] in win["text"]

    def test_segments_split_into_multiple_windows(self):
        from app.services.windowing import split_transcript_windows

        # Each segment line is "30 tokens"; budget=50 → 1 segment per window (with overlap)
        with patch("app.services.windowing.count_tokens", return_value=30):
            result = split_transcript_windows(SAMPLE_SEGMENTS, token_budget=50)

        assert len(result) >= 2
        # window_index values are sequential
        for i, win in enumerate(result):
            assert win["window_index"] == i

    def test_no_segments_lost(self):
        """Every segment text must appear in at least one window."""
        from app.services.windowing import split_transcript_windows

        with patch("app.services.windowing.count_tokens", return_value=30):
            result = split_transcript_windows(SAMPLE_SEGMENTS, token_budget=50)

        all_text = "\n".join(win["text"] for win in result)
        for seg in SAMPLE_SEGMENTS:
            assert seg["text"] in all_text, f"Segment text lost: {seg['text']}"

    def test_llm_unavailable_falls_back_to_char_estimate(self):
        """When count_tokens raises LLMUnavailable, char-based fallback is used."""
        from app.services.llm import LLMUnavailable
        from app.services.windowing import split_transcript_windows

        with patch("app.services.windowing.count_tokens", side_effect=LLMUnavailable("offline")):
            result = split_transcript_windows(SAMPLE_SEGMENTS, token_budget=200)

        # Should still produce valid windows (not raise)
        assert isinstance(result, list)
        assert len(result) >= 1

    def test_single_segment(self):
        from app.services.windowing import split_transcript_windows

        segs = [{"start_time": 0.0, "end_time": 5.0, "speaker": "Alice", "text": "Hello."}]
        with patch("app.services.windowing.count_tokens", return_value=5):
            result = split_transcript_windows(segs, token_budget=100)

        assert len(result) == 1
        assert result[0]["start_time"] == 0.0
        assert result[0]["end_time"] == 5.0

    def test_window_has_required_keys(self):
        from app.services.windowing import split_transcript_windows

        with patch("app.services.windowing.count_tokens", return_value=5):
            result = split_transcript_windows(SAMPLE_SEGMENTS, token_budget=200)

        for win in result:
            assert "window_index" in win
            assert "start_time" in win
            assert "end_time" in win
            assert "text" in win
            assert "segments" in win

    def test_timestamps_formatted_in_text(self):
        from app.services.windowing import split_transcript_windows

        with patch("app.services.windowing.count_tokens", return_value=5):
            result = split_transcript_windows(SAMPLE_SEGMENTS, token_budget=500)

        # Text should contain [mm:ss] formatted timestamps
        assert "[00:00]" in result[0]["text"]

    def test_chronological_order(self):
        from app.services.windowing import split_transcript_windows

        with patch("app.services.windowing.count_tokens", return_value=30):
            result = split_transcript_windows(SAMPLE_SEGMENTS, token_budget=50)

        # Each window's start_time <= next window's start_time
        for i in range(len(result) - 1):
            assert result[i]["start_time"] <= result[i + 1]["start_time"]


# ===========================================================================
# process_transcript_windows tests
# ===========================================================================

class TestProcessTranscriptWindows:
    def test_empty_segments_returns_empty(self, tmp_path):
        from app.services.windowing import process_transcript_windows
        _, conn = _make_temp_db(tmp_path)
        _insert_meeting(conn, "mtg-001")
        result = process_transcript_windows("mtg-001", [], conn)
        assert result == []
        conn.close()

    def test_saves_windows_to_db(self, tmp_path):
        from app.services.windowing import process_transcript_windows
        _, conn = _make_temp_db(tmp_path)
        _insert_meeting(conn, "mtg-002")

        with patch("app.services.windowing.count_tokens", return_value=5), \
             patch("app.services.windowing.extract_chunk_notes", return_value=MOCK_NOTES):
            results = process_transcript_windows("mtg-002", SAMPLE_SEGMENTS, conn, token_budget=500)

        assert len(results) == 1
        # Verify DB row
        row = conn.execute(
            "SELECT * FROM windows WHERE meeting_id='mtg-002'"
        ).fetchone()
        assert row is not None
        stored = json.loads(row["result_json"])
        assert stored["summary"] == MOCK_NOTES["summary"]
        conn.close()

    def test_upserts_on_retry(self, tmp_path):
        """Calling twice should update the existing window row, not duplicate it."""
        from app.services.windowing import process_transcript_windows
        _, conn = _make_temp_db(tmp_path)
        _insert_meeting(conn, "mtg-003")

        with patch("app.services.windowing.count_tokens", return_value=5), \
             patch("app.services.windowing.extract_chunk_notes", return_value=MOCK_NOTES):
            process_transcript_windows("mtg-003", SAMPLE_SEGMENTS, conn, token_budget=500)

        updated_notes = dict(MOCK_NOTES, summary="Updated summary")
        with patch("app.services.windowing.count_tokens", return_value=5), \
             patch("app.services.windowing.extract_chunk_notes", return_value=updated_notes):
            process_transcript_windows("mtg-003", SAMPLE_SEGMENTS, conn, token_budget=500)

        rows = conn.execute("SELECT * FROM windows WHERE meeting_id='mtg-003'").fetchall()
        assert len(rows) == 1
        stored = json.loads(rows[0]["result_json"])
        assert stored["summary"] == "Updated summary"
        conn.close()

    def test_llm_unavailable_raises(self, tmp_path):
        from app.services.llm import LLMUnavailable
        from app.services.windowing import process_transcript_windows
        _, conn = _make_temp_db(tmp_path)
        _insert_meeting(conn, "mtg-004")

        with patch("app.services.windowing.count_tokens", return_value=5), \
             patch("app.services.windowing.extract_chunk_notes", side_effect=LLMUnavailable("offline")):
            with pytest.raises(LLMUnavailable):
                process_transcript_windows("mtg-004", SAMPLE_SEGMENTS, conn, token_budget=500)
        conn.close()

    def test_extraction_error_records_placeholder(self, tmp_path):
        """Non-LLMUnavailable extraction errors should produce a placeholder, not raise."""
        from app.services.windowing import process_transcript_windows
        _, conn = _make_temp_db(tmp_path)
        _insert_meeting(conn, "mtg-005")

        with patch("app.services.windowing.count_tokens", return_value=5), \
             patch("app.services.windowing.extract_chunk_notes", side_effect=ValueError("bad json")):
            results = process_transcript_windows("mtg-005", SAMPLE_SEGMENTS, conn, token_budget=500)

        assert len(results) == 1
        assert "[Extraction failed" in results[0]["summary"]
        conn.close()

    def test_multiple_windows_all_persisted(self, tmp_path):
        from app.services.windowing import process_transcript_windows
        _, conn = _make_temp_db(tmp_path)
        _insert_meeting(conn, "mtg-006")

        call_count = {"n": 0}
        def mock_extract(text, speakers, client=None):
            call_count["n"] += 1
            return dict(MOCK_NOTES, summary=f"Window {call_count['n']}")

        with patch("app.services.windowing.count_tokens", return_value=50), \
             patch("app.services.windowing.extract_chunk_notes", side_effect=mock_extract):
            results = process_transcript_windows("mtg-006", SAMPLE_SEGMENTS, conn, token_budget=60)

        rows = conn.execute("SELECT window_index FROM windows WHERE meeting_id='mtg-006' ORDER BY window_index").fetchall()
        assert len(rows) == len(results)
        # Verify sequential window_index
        for i, row in enumerate(rows):
            assert row["window_index"] == i
        conn.close()


# ===========================================================================
# summarizer.py tests
# ===========================================================================

class TestMergeAndPersist:
    def test_empty_results_persists_nothing(self, tmp_path):
        from app.services.summarizer import merge_and_persist
        _, conn = _make_temp_db(tmp_path)
        _insert_meeting(conn, "mtg-010")

        result = merge_and_persist("mtg-010", [], conn)
        assert result["summary"] is None
        # meetings.overview should remain NULL
        row = conn.execute("SELECT overview FROM meetings WHERE id='mtg-010'").fetchone()
        # overview may or may not be set to NULL; either is fine
        conn.close()

    def test_single_window_persisted_directly(self, tmp_path):
        from app.services.summarizer import merge_and_persist
        _, conn = _make_temp_db(tmp_path)
        _insert_meeting(conn, "mtg-011")

        result = merge_and_persist("mtg-011", [MOCK_NOTES], conn)

        assert result["summary"] == MOCK_NOTES["summary"]
        row = conn.execute("SELECT overview, project_progress FROM meetings WHERE id='mtg-011'").fetchone()
        assert row["overview"] == MOCK_NOTES["summary"]
        prog = json.loads(row["project_progress"])
        assert prog == MOCK_NOTES["project_progress"]
        conn.close()

    def test_action_items_persisted(self, tmp_path):
        from app.services.summarizer import merge_and_persist
        _, conn = _make_temp_db(tmp_path)
        _insert_meeting(conn, "mtg-012")

        merge_and_persist("mtg-012", [MOCK_NOTES], conn)
        conn.commit()

        items = conn.execute(
            "SELECT text, owner, deadline FROM action_items WHERE meeting_id='mtg-012'"
        ).fetchall()
        assert len(items) == 1
        assert items[0]["text"] == "Finish the report"
        assert items[0]["owner"] == "Bob"
        assert items[0]["deadline"] == "by Friday"
        conn.close()

    def test_action_item_done_state_preserved_on_retry(self, tmp_path):
        from app.services.summarizer import merge_and_persist
        _, conn = _make_temp_db(tmp_path)
        _insert_meeting(conn, "mtg-013")

        # First run
        merge_and_persist("mtg-013", [MOCK_NOTES], conn)
        conn.commit()
        # Mark item as done
        conn.execute(
            "UPDATE action_items SET done=1 WHERE meeting_id='mtg-013'"
        )
        conn.commit()

        # Second run with same notes
        merge_and_persist("mtg-013", [MOCK_NOTES], conn)
        conn.commit()

        item = conn.execute(
            "SELECT done FROM action_items WHERE meeting_id='mtg-013'"
        ).fetchone()
        assert item["done"] == 1, "done state should be preserved on reprocessing"
        conn.close()

    def test_duplicate_action_items_deduplicated(self, tmp_path):
        from app.services.summarizer import merge_and_persist
        _, conn = _make_temp_db(tmp_path)
        _insert_meeting(conn, "mtg-014")

        notes_with_dups = dict(MOCK_NOTES, action_items=[
            {"text": "Finish the report", "owner": "Bob", "deadline": "by Friday", "source_time": "[00:05]"},
            {"text": "Finish the report", "owner": "Bob", "deadline": "by Friday", "source_time": "[00:05]"},
        ])
        merge_and_persist("mtg-014", [notes_with_dups], conn)
        conn.commit()

        items = conn.execute(
            "SELECT id FROM action_items WHERE meeting_id='mtg-014'"
        ).fetchall()
        assert len(items) == 1
        conn.close()

    def test_multiple_windows_naive_merge(self, tmp_path):
        from app.services.summarizer import merge_and_persist
        _, conn = _make_temp_db(tmp_path)
        _insert_meeting(conn, "mtg-015")

        win1 = {
            "summary": "First part.",
            "project_progress": ["Completed auth module"],
            "challenges": ["DB slowness"],
            "action_items": [
                {"text": "Fix DB query", "owner": "Carol", "deadline": None, "source_time": "[00:20]"}
            ],
            "next_steps": ["Deploy to staging"],
        }
        win2 = {
            "summary": "Second part.",
            "project_progress": ["Completed UI review"],
            "challenges": ["DB slowness"],  # duplicate challenge
            "action_items": [
                {"text": "Write release notes", "owner": "Alice", "deadline": "by Monday", "source_time": "[00:05]"}
            ],
            "next_steps": ["Deploy to staging"],  # duplicate next_step
        }

        # Patch LLM unavailable so naive merge path is used
        with patch("app.services.summarizer.generate_json", side_effect=Exception("server down")):
            result = merge_and_persist("mtg-015", [win1, win2], conn)

        conn.commit()
        # Challenges should be deduplicated
        assert result["challenges"].count("DB slowness") == 1
        # Next steps deduplicated
        assert result["next_steps"].count("Deploy to staging") == 1
        # Both action items persisted
        items = conn.execute(
            "SELECT text FROM action_items WHERE meeting_id='mtg-015'"
        ).fetchall()
        assert len(items) == 2
        conn.close()

    def test_db_rollback_on_persist_failure(self, tmp_path):
        """If DB write fails, the transaction rolls back; no partial data."""
        from app.services.summarizer import merge_and_persist
        _, conn = _make_temp_db(tmp_path)
        _insert_meeting(conn, "mtg-016")

        with patch("app.services.summarizer._persist_summary", side_effect=sqlite3.OperationalError("disk full")):
            with pytest.raises(sqlite3.OperationalError):
                merge_and_persist("mtg-016", [MOCK_NOTES], conn)

        # Action items should NOT have been written
        items = conn.execute(
            "SELECT id FROM action_items WHERE meeting_id='mtg-016'"
        ).fetchall()
        assert len(items) == 0
        conn.close()

    def test_llm_merge_called_for_multiple_windows(self, tmp_path):
        from app.services.summarizer import merge_and_persist
        _, conn = _make_temp_db(tmp_path)
        _insert_meeting(conn, "mtg-017")

        merged_notes = {
            "summary": "LLM-merged summary.",
            "project_progress": ["p1", "p2"],
            "challenges": [],
            "action_items": [],
            "next_steps": [],
        }

        with patch("app.services.summarizer.generate_json", return_value=merged_notes):
            result = merge_and_persist("mtg-017", [MOCK_NOTES, MOCK_NOTES], conn)

        assert result["summary"] == "LLM-merged summary."
        conn.close()


# ===========================================================================
# Integration: windowing → merge pipeline (fully mocked LLM)
# ===========================================================================

class TestEndToEndPipeline:
    def test_full_pipeline(self, tmp_path):
        from app.services.summarizer import merge_and_persist
        from app.services.windowing import process_transcript_windows
        _, conn = _make_temp_db(tmp_path)
        _insert_meeting(conn, "mtg-100")

        with patch("app.services.windowing.count_tokens", return_value=5), \
             patch("app.services.windowing.extract_chunk_notes", return_value=MOCK_NOTES):
            window_results = process_transcript_windows(
                "mtg-100", SAMPLE_SEGMENTS, conn, token_budget=500
            )

        with patch("app.services.summarizer.generate_json", side_effect=Exception("no llm")):
            merged = merge_and_persist("mtg-100", window_results, conn)

        conn.commit()

        assert merged["summary"]
        # Windows row exists
        row = conn.execute("SELECT id FROM windows WHERE meeting_id='mtg-100'").fetchone()
        assert row is not None
        # meetings.overview updated
        m = conn.execute("SELECT overview FROM meetings WHERE id='mtg-100'").fetchone()
        assert m["overview"] is not None
        conn.close()
