"""Automated tests for Step 4: Audio extraction, Whisper transcription,
pipeline integration, and background worker lifecycle.
"""
from __future__ import annotations

import asyncio
import json
import sqlite3
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.core.config import settings
from app.db.database import get_db, init_db
from app.services.audio import (
    extract_audio_to_wav,
    extract_temporary_wav,
    get_media_duration,
)
from app.services.pipeline import process_meeting_pipeline
from app.services.transcription import (
    persist_transcript_segments,
    set_whisper_model,
    transcribe_audio,
)
from app.services.worker import (
    WorkerManager,
    claim_pending_meeting,
    recover_interrupted_meetings,
)


@pytest.fixture(autouse=True)
def setup_test_db(tmp_path):
    """Isolate each test in a clean SQLite DB and media directory."""
    temp_db = tmp_path / "step4_test.db"
    temp_media = tmp_path / "media"
    temp_media.mkdir(parents=True, exist_ok=True)

    settings.DB_PATH = str(temp_db)
    settings.MEDIA_DIR = str(temp_media)
    settings.ENABLE_BACKGROUND_WORKER = False

    init_db()
    yield
    set_whisper_model(None)


def _create_meeting(
    meeting_id: str,
    source: str = "upload",
    status: str = "pending",
    media_path: str | None = None,
    language: str = "en",
) -> None:
    with get_db() as conn:
        conn.execute(
            """INSERT INTO meetings (id, source, status, media_path, language, title)
               VALUES (?, ?, ?, ?, ?, 'Test Meeting')""",
            (meeting_id, source, status, media_path, language),
        )


# ===========================================================================
# 1. Audio Extraction Tests
# ===========================================================================

class TestAudioExtraction:
    def test_get_media_duration_success(self, tmp_path):
        media_file = tmp_path / "test.mp4"
        media_file.write_bytes(b"dummy video data")

        mock_proc = MagicMock(returncode=0, stdout="42.50\n", stderr="")
        with patch("subprocess.run", return_value=mock_proc) as mock_run:
            duration = get_media_duration(media_file)
            assert duration == 42.50
            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            assert args[0] == settings.FFPROBE_PATH
            assert str(media_file) in args

    def test_get_media_duration_missing_binary(self, tmp_path):
        media_file = tmp_path / "test.mp4"
        media_file.write_bytes(b"dummy")

        with patch("subprocess.run", side_effect=FileNotFoundError):
            with pytest.raises(FileNotFoundError, match="ffprobe binary not found"):
                get_media_duration(media_file)

    def test_get_media_duration_failure(self, tmp_path):
        media_file = tmp_path / "corrupt.mp4"
        media_file.write_bytes(b"bad")

        mock_proc = MagicMock(returncode=1, stdout="", stderr="Invalid data found")
        with patch("subprocess.run", return_value=mock_proc):
            with pytest.raises(RuntimeError, match="ffprobe failed"):
                get_media_duration(media_file)

    def test_extract_audio_to_wav_success(self, tmp_path):
        media_dir = Path(settings.MEDIA_DIR)
        media_file = media_dir / "sample.mp4"
        media_file.write_bytes(b"video data")

        out_wav = tmp_path / "out.wav"

        def fake_ffmpeg(cmd, **kwargs):
            out_wav.write_bytes(b"RIFFWAVEfmt ")
            return MagicMock(returncode=0, stdout="", stderr="")

        with patch("subprocess.run", side_effect=fake_ffmpeg):
            res = extract_audio_to_wav(media_file, out_wav)
            assert res == out_wav
            assert res.exists()

    def test_extract_audio_to_wav_missing_file_raises(self, tmp_path):
        nonexistent = Path(settings.MEDIA_DIR) / "ghost.mp4"
        with pytest.raises(ValueError, match="not a valid file|does not exist"):
            extract_audio_to_wav(nonexistent)

    def test_extract_temporary_wav_cleans_up_on_success_and_error(self, tmp_path):
        media_dir = Path(settings.MEDIA_DIR)
        media_file = media_dir / "clean_test.mp3"
        media_file.write_bytes(b"audio data")

        created_wav = None

        with patch("app.services.audio.get_media_duration", return_value=15.0), \
             patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="", stderr="")):

            with extract_temporary_wav(media_file) as (wav_path, duration):
                assert duration == 15.0
                assert wav_path.exists()
                created_wav = wav_path

            # Should be deleted after exiting context manager
            assert not created_wav.exists()

        # Test cleanup on exception inside block
        with patch("app.services.audio.get_media_duration", return_value=15.0), \
             patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="", stderr="")):

            with pytest.raises(ZeroDivisionError):
                with extract_temporary_wav(media_file) as (wav_path, duration):
                    created_wav = wav_path
                    assert wav_path.exists()
                    _ = 1 / 0

            # Verified clean up after exception
            assert not created_wav.exists()


# ===========================================================================
# 2. Whisper Transcription Tests
# ===========================================================================

class TestTranscription:
    def test_transcribe_audio_with_mock_model(self, tmp_path):
        wav_file = tmp_path / "test.wav"
        wav_file.write_bytes(b"audio")

        # Mock segment objects returned by faster-whisper
        seg1 = MagicMock(start=0.0, end=4.5, text="Welcome everyone to the sprint review.")
        seg2 = MagicMock(start=4.5, end=9.0, text="I will handle the deployment tomorrow.")
        mock_model = MagicMock()
        mock_model.transcribe.return_value = ([seg1, seg2], MagicMock())

        set_whisper_model(mock_model)

        segments = transcribe_audio(wav_file, language="english")
        assert len(segments) == 2
        assert segments[0]["start_time"] == 0.0
        assert segments[0]["end_time"] == 4.5
        assert segments[0]["text"] == "Welcome everyone to the sprint review."
        assert segments[0]["speaker"] is None

        # Verify language passed as 'en'
        mock_model.transcribe.assert_called_once()
        assert mock_model.transcribe.call_args[1]["language"] == "en"
        assert mock_model.transcribe.call_args[1]["vad_filter"] is True

    def test_persist_transcript_segments_updates_duration_and_fts(self):
        meeting_id = "test-mtg-transcribe"
        _create_meeting(meeting_id)

        segments = [
            {"start_time": 0.0, "end_time": 5.0, "speaker": None, "text": "Feature development status."},
            {"start_time": 5.0, "end_time": 10.0, "speaker": None, "text": "Testing is complete."},
        ]

        with get_db() as conn:
            persist_transcript_segments(meeting_id, segments, 10.0, conn)

        with get_db() as conn:
            # Check rows in transcript_segments
            rows = conn.execute(
                "SELECT * FROM transcript_segments WHERE meeting_id = ? ORDER BY start_time",
                (meeting_id,),
            ).fetchall()
            assert len(rows) == 2
            assert rows[0]["text"] == "Feature development status."

            # Check meetings duration and processed seconds
            m = conn.execute("SELECT duration_seconds, processed_seconds FROM meetings WHERE id = ?", (meeting_id,)).fetchone()
            assert m["duration_seconds"] == 10.0
            assert m["processed_seconds"] == 10.0

            # Check FTS5 virtual table trigger inserted text
            fts_rows = conn.execute("SELECT text FROM transcript_fts WHERE text MATCH 'Feature'").fetchall()
            assert len(fts_rows) >= 1

    def test_persist_transcript_segments_idempotent_on_retry(self):
        meeting_id = "test-mtg-retry"
        _create_meeting(meeting_id)

        initial_segments = [
            {"start_time": 0.0, "end_time": 5.0, "speaker": None, "text": "First attempt segment."},
        ]
        with get_db() as conn:
            persist_transcript_segments(meeting_id, initial_segments, 5.0, conn)

        # Retry with updated segments
        new_segments = [
            {"start_time": 0.0, "end_time": 4.0, "speaker": None, "text": "New segment 1."},
            {"start_time": 4.0, "end_time": 8.0, "speaker": None, "text": "New segment 2."},
        ]
        with get_db() as conn:
            persist_transcript_segments(meeting_id, new_segments, 8.0, conn)

        with get_db() as conn:
            rows = conn.execute("SELECT * FROM transcript_segments WHERE meeting_id = ?", (meeting_id,)).fetchall()
            assert len(rows) == 2
            assert rows[0]["text"] == "New segment 1."


# ===========================================================================
# 3. Pipeline Integration Tests
# ===========================================================================

class TestPipeline:
    def test_process_meeting_pipeline_success(self, tmp_path):
        meeting_id = "mtg-pipe-success"
        media_file = Path(settings.MEDIA_DIR) / f"{meeting_id}.mp4"
        media_file.write_bytes(b"valid video")
        _create_meeting(meeting_id, media_path=str(media_file))

        fake_segments = [
            {"start_time": 0.0, "end_time": 5.0, "speaker": None, "text": "Let's review the quarterly metrics."},
            {"start_time": 5.0, "end_time": 10.0, "speaker": None, "text": "I will deliver the slides by Thursday."},
        ]
        fake_notes = {
            "summary": "Team reviewed metrics and scheduled slide delivery.",
            "project_progress": ["Quarterly review completed"],
            "challenges": [],
            "action_items": [
                {"text": "Deliver slides", "owner": "Presenter", "deadline": "by Thursday", "source_time": "[00:05]"}
            ],
            "next_steps": ["Distribute slides to stakeholders"],
        }

        with patch("app.services.pipeline.extract_temporary_wav") as mock_extract, \
             patch("app.services.pipeline.transcribe_audio", return_value=fake_segments), \
             patch("app.services.pipeline.is_server_ready", return_value=True), \
             patch("app.services.pipeline.process_transcript_windows", return_value=[fake_notes]):

            # Yield dummy wav path and duration
            mock_extract.return_value.__enter__.return_value = (tmp_path / "dummy.wav", 10.0)

            process_meeting_pipeline(meeting_id)

        with get_db() as conn:
            row = conn.execute("SELECT status, overview, error, duration_seconds FROM meetings WHERE id = ?", (meeting_id,)).fetchone()
            assert row["status"] == "done"
            assert row["overview"] == fake_notes["summary"]
            assert row["error"] is None
            assert row["duration_seconds"] == 10.0

            action_items = conn.execute("SELECT text, deadline FROM action_items WHERE meeting_id = ?", (meeting_id,)).fetchall()
            assert len(action_items) == 1
            assert action_items[0]["text"] == "Deliver slides"

    def test_process_meeting_pipeline_silence_handling(self, tmp_path):
        meeting_id = "mtg-pipe-silence"
        media_file = Path(settings.MEDIA_DIR) / f"{meeting_id}.mp3"
        media_file.write_bytes(b"silent audio")
        _create_meeting(meeting_id, media_path=str(media_file))

        with patch("app.services.pipeline.extract_temporary_wav") as mock_extract, \
             patch("app.services.pipeline.transcribe_audio", return_value=[]):

            mock_extract.return_value.__enter__.return_value = (tmp_path / "silent.wav", 20.0)
            process_meeting_pipeline(meeting_id)

        with get_db() as conn:
            row = conn.execute("SELECT status, overview FROM meetings WHERE id = ?", (meeting_id,)).fetchone()
            assert row["status"] == "done"
            assert "[No speech detected" in row["overview"]

    def test_process_meeting_pipeline_failed_window_raises(self, tmp_path):
        meeting_id = "mtg-pipe-fail-window"
        media_file = Path(settings.MEDIA_DIR) / f"{meeting_id}.mp4"
        media_file.write_bytes(b"video")
        _create_meeting(meeting_id, media_path=str(media_file))

        fake_segments = [{"start_time": 0.0, "end_time": 5.0, "speaker": None, "text": "Speech."}]
        failed_window_result = {
            "summary": "[Extraction failed: JSONDecodeError]",
            "project_progress": [],
            "challenges": [],
            "action_items": [],
            "next_steps": [],
        }

        with patch("app.services.pipeline.extract_temporary_wav") as mock_extract, \
             patch("app.services.pipeline.transcribe_audio", return_value=fake_segments), \
             patch("app.services.pipeline.process_transcript_windows", return_value=[failed_window_result]):

            mock_extract.return_value.__enter__.return_value = (tmp_path / "wav.wav", 5.0)

            with pytest.raises(RuntimeError, match="Window 0 extraction failed"):
                process_meeting_pipeline(meeting_id)


# ===========================================================================
# 4. Background Worker Tests
# ===========================================================================

class TestBackgroundWorker:
    def test_claim_pending_meeting_atomic(self):
        m1 = "mtg-claim-1"
        m2 = "mtg-claim-2"
        _create_meeting(m1, source="upload", status="pending", media_path="C:/media/1.mp4")
        _create_meeting(m2, source="upload", status="pending", media_path="C:/media/2.mp4")

        claimed = claim_pending_meeting()
        assert claimed == m1

        with get_db() as conn:
            r1 = conn.execute("SELECT status FROM meetings WHERE id = ?", (m1,)).fetchone()
            assert r1["status"] == "processing"

        claimed_second = claim_pending_meeting()
        assert claimed_second == m2

        assert claim_pending_meeting() is None

    def test_claim_pending_ignores_online_join_meetings(self):
        m_join = "mtg-online-join"
        _create_meeting(m_join, source="join", status="pending", media_path=None)

        assert claim_pending_meeting() is None

        with get_db() as conn:
            r = conn.execute("SELECT status FROM meetings WHERE id = ?", (m_join,)).fetchone()
            assert r["status"] == "pending"

    def test_recover_interrupted_meetings(self):
        m_interrupted = "mtg-interrupted"
        _create_meeting(m_interrupted, source="upload", status="processing", media_path="C:/media/int.mp4")

        recovered = recover_interrupted_meetings()
        assert recovered == 1

        with get_db() as conn:
            r = conn.execute("SELECT status FROM meetings WHERE id = ?", (m_interrupted,)).fetchone()
            assert r["status"] == "pending"

    def test_worker_manager_lifecycle(self):
        manager = WorkerManager()
        settings.ENABLE_BACKGROUND_WORKER = False

        # Disabled setting should not start task
        manager.start()
        assert manager._task is None

        # When enabled with a mock task
        settings.ENABLE_BACKGROUND_WORKER = True

        async def _test():
            # Start dummy background task
            async def _dummy():
                await asyncio.sleep(100)

            manager._task = asyncio.create_task(_dummy())
            assert not manager._task.done()

            # Stop cancels and cleans up the active task
            await manager.stop()
            assert manager._task is None

        asyncio.run(_test())
