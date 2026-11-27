"""Tests for Part A: Server restart during live meeting, recovery tasks, and connection replacement."""
from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest
from app.core.config import settings
from app.db.database import get_db
from app.main import app
from app.services.live_stream import live_session_manager
from app.services.worker import recover_interrupted_meetings
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect


def _create_meeting(
    meeting_id: str,
    source: str = "join",
    status: str = "processing",
    language: str = "English",
) -> None:
    with get_db() as conn:
        conn.execute("DELETE FROM meetings WHERE id = ?", (meeting_id,))
        conn.execute("DELETE FROM transcript_segments WHERE meeting_id = ?", (meeting_id,))
        conn.execute("DELETE FROM speakers WHERE meeting_id = ?", (meeting_id,))
        conn.execute(
            """INSERT INTO meetings (id, title, folder, slot_name, language, source, status, duration_seconds, processed_seconds)
               VALUES (?, ?, ?, ?, ?, ?, ?, 0.0, 0.0)""",
            (meeting_id, f"Meeting {meeting_id}", "test-folder", "Chatmeet", language, source, status),
        )


@pytest.fixture(autouse=True)
def mock_external_services():
    """Mock LLM and Whisper services to ensure fast, isolated tests."""
    with (
        patch("app.services.llm.is_server_ready", return_value=True),
        patch("app.services.live_stream.is_server_ready", return_value=True),
        patch("app.services.llm.count_tokens", return_value=10),
        patch("app.services.windowing.count_tokens", return_value=10),
        patch(
            "app.services.windowing.extract_chunk_notes",
            return_value={"summary": "Automated summary test.", "action_items": []},
        ),
        patch(
            "app.services.summarizer.generate_json",
            return_value={
                "overview": "Meeting overview",
                "project_progress": [],
                "challenges": [],
                "next_steps": [],
            },
        ),
        patch("app.services.transcription.transcribe_audio", return_value=[]),
    ):
        yield


class TestLiveRecoveryPartA:
    @pytest.mark.anyio
    async def test_restart_with_segments_finalizes_after_timeout(self):
        """A1: On startup, live meeting in 'processing' with segments finalizes to 'done' after timeout."""
        meeting_id = "test-recovery-with-segs"
        _create_meeting(meeting_id, source="join", status="processing")

        with get_db() as conn:
            conn.execute(
                """INSERT INTO transcript_segments (meeting_id, start_time, end_time, speaker, text)
                   VALUES (?, ?, ?, ?, ?)""",
                (meeting_id, 0.0, 5.0, "Alice", "Spoken content before restart"),
            )

        with patch.object(settings, "BOT_DISCONNECT_TIMEOUT_SECONDS", 0.05):
            live_session_manager.start_recovery_tasks()
            assert meeting_id in live_session_manager.recovery_tasks

            # Wait for the recovery timeout task to complete
            await asyncio.sleep(0.15)

            with get_db() as conn:
                row = conn.execute("SELECT status, error FROM meetings WHERE id = ?", (meeting_id,)).fetchone()
                assert row["status"] == "done"
                assert row["error"] is None

    @pytest.mark.anyio
    async def test_restart_without_segments_ends_failed(self):
        """A1: On startup, live meeting in 'processing' with NO segments fails with exact error message."""
        meeting_id = "test-recovery-no-segs"
        _create_meeting(meeting_id, source="join", status="processing")

        with patch.object(settings, "BOT_DISCONNECT_TIMEOUT_SECONDS", 0.05):
            live_session_manager.start_recovery_tasks()
            assert meeting_id in live_session_manager.recovery_tasks

            await asyncio.sleep(0.15)

            with get_db() as conn:
                row = conn.execute("SELECT status, error FROM meetings WHERE id = ?", (meeting_id,)).fetchone()
                assert row["status"] == "failed"
                assert row["error"] == "Live session ended before any speech was saved"

    def test_reconnect_before_timeout_cancels_recovery_task(self):
        """A1 & A3: Bot reconnect cancels the startup recovery task and keeps status 'processing'."""
        meeting_id = "test-reconnect-cancels-task"
        _create_meeting(meeting_id, source="join", status="processing")

        with (
            patch.object(settings, "BOT_DISCONNECT_TIMEOUT_SECONDS", 10.0),
            TestClient(app) as client,
        ):
                task = live_session_manager.recovery_tasks.get(meeting_id)
                assert task is not None
                assert not task.done()

                # Bot reconnects
                token = settings.BOT_INGEST_TOKEN
                with client.websocket_connect(
                    f"/api/v1/meetings/{meeting_id}/stream",
                    headers={"x-bot-token": token},
                ) as ws:
                    # Once connected, the recovery task should be cancelled
                    assert task.cancelled() or task.done()
                    assert meeting_id not in live_session_manager.recovery_tasks

                    # Send a chunk and end
                    ws.send_json({
                        "type": "chunk",
                        "speaker_id": "spk1",
                        "speaker_name": "Alice",
                        "start_ms": 0,
                    })
                    ws.send_bytes(b"\x00\x00" * 16000)
                    ws.send_json({"type": "end"})

    def test_upload_recovery_does_not_touch_join_meeting(self):
        """A2: worker.recover_interrupted_meetings only resets source='upload', never 'join'."""
        upload_id = "mtg-upload-interrupted"
        join_id = "mtg-join-interrupted"

        _create_meeting(upload_id, source="upload", status="processing")
        _create_meeting(join_id, source="join", status="processing")

        recovered_count = recover_interrupted_meetings()
        assert recovered_count >= 1

        with get_db() as conn:
            upload_row = conn.execute("SELECT status FROM meetings WHERE id = ?", (upload_id,)).fetchone()
            join_row = conn.execute("SELECT status FROM meetings WHERE id = ?", (join_id,)).fetchone()

            # Upload meeting reset to pending
            assert upload_row["status"] == "pending"
            # Join meeting stays processing (not touched by upload recovery)
            assert join_row["status"] == "processing"

    def test_second_connection_replaces_first(self):
        """A4: Only one active connection per meeting; a second connection replaces the first (1008)."""
        meeting_id = "test-dual-conn"
        _create_meeting(meeting_id, source="join", status="processing")
        token = settings.BOT_INGEST_TOKEN
        client = TestClient(app)

        with client.websocket_connect(
            f"/api/v1/meetings/{meeting_id}/stream",
            headers={"x-bot-token": token},
        ) as ws1:
            # Send chunk from ws1
            ws1.send_json({
                "type": "chunk",
                "speaker_id": "spk1",
                "speaker_name": "Alice",
                "start_ms": 0,
            })
            ws1.send_bytes(b"\x00\x00" * 16000)

            # Connect ws2 for the same meeting -> should replace ws1
            with client.websocket_connect(
                f"/api/v1/meetings/{meeting_id}/stream",
                headers={"x-bot-token": token},
            ) as ws2:
                # ws1 should be closed by server with close code 1008
                with pytest.raises(WebSocketDisconnect) as exc_info:
                    ws1.receive_json()
                assert exc_info.value.code == 1008

                # ws2 can stream and finalize normally
                ws2.send_json({
                    "type": "chunk",
                    "speaker_id": "spk1",
                    "speaker_name": "Alice",
                    "start_ms": 1000,
                })
                ws2.send_bytes(b"\x00\x00" * 16000)
                ws2.send_json({"type": "end"})

        with get_db() as conn:
            row = conn.execute("SELECT status FROM meetings WHERE id = ?", (meeting_id,)).fetchone()
            assert row["status"] == "done"
