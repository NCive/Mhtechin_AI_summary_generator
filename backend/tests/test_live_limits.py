"""Tests for Part B: Token validation, frame limits, session limits, and privacy."""
from __future__ import annotations

import logging
from unittest.mock import patch

import pytest
from app.core.config import settings
from app.db.database import get_db
from app.main import app
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


class TestLiveLimitsPartB:
    def test_query_string_token_rejected_when_setting_false(self):
        """B1: When BOT_ALLOW_QUERY_TOKEN is False, query string token is rejected (1008)."""
        meeting_id = "test-query-token-reject"
        _create_meeting(meeting_id)
        token = settings.BOT_INGEST_TOKEN

        client = TestClient(app)
        with (
            patch.object(settings, "BOT_ALLOW_QUERY_TOKEN", False),
            pytest.raises(WebSocketDisconnect) as exc_info,
            client.websocket_connect(f"/api/v1/meetings/{meeting_id}/stream?token={token}"),
        ):
            pass
        assert exc_info.value.code == 1008

    def test_token_never_in_logs(self, caplog):
        """B1: Verify no log statement ever contains the secret token."""
        meeting_id = "test-log-privacy"
        _create_meeting(meeting_id)
        secret_token = "SECRET_SUPER_CONFIDENTIAL_TOKEN_12345"

        client = TestClient(app)
        with (
            caplog.at_level(logging.DEBUG),
            patch.object(settings, "BOT_INGEST_TOKEN", secret_token),
            patch.object(settings, "BOT_ALLOW_QUERY_TOKEN", False),
        ):
            # Attempt with query token (rejected)
            with pytest.raises(WebSocketDisconnect), client.websocket_connect(
                f"/api/v1/meetings/{meeting_id}/stream?token={secret_token}"
            ):
                pass

            # Attempt with wrong token
            with pytest.raises(WebSocketDisconnect), client.websocket_connect(
                f"/api/v1/meetings/{meeting_id}/stream",
                headers={"x-bot-token": "WRONG_TOKEN"},
            ):
                pass

            # Connect successfully with valid header token
            with client.websocket_connect(
                f"/api/v1/meetings/{meeting_id}/stream",
                headers={"x-bot-token": secret_token},
            ) as ws:
                ws.send_json({"type": "end"})

        # Check all captured log output
        for record in caplog.records:
            assert secret_token not in record.message
            assert secret_token not in str(record.args)

    def test_oversized_text_frame_rejected(self):
        """B2: Text frame exceeding 4 KB is closed with code 1009."""
        meeting_id = "test-oversized-text"
        _create_meeting(meeting_id)
        token = settings.BOT_INGEST_TOKEN

        client = TestClient(app)
        with client.websocket_connect(
            f"/api/v1/meetings/{meeting_id}/stream",
            headers={"x-bot-token": token},
        ) as ws:
            huge_text = '{"type": "chunk", "data": "' + ("A" * 5000) + '"}'
            with pytest.raises(WebSocketDisconnect) as exc_info:
                ws.send_text(huge_text)
                ws.receive_json()
            assert exc_info.value.code == 1009

    def test_oversized_binary_frame_rejected(self):
        """B2: Binary frame exceeding 1 MB is closed with code 1009."""
        meeting_id = "test-oversized-binary"
        _create_meeting(meeting_id)
        token = settings.BOT_INGEST_TOKEN

        client = TestClient(app)
        with client.websocket_connect(
            f"/api/v1/meetings/{meeting_id}/stream",
            headers={"x-bot-token": token},
        ) as ws:
            ws.send_json({
                "type": "chunk",
                "speaker_id": "spk1",
                "speaker_name": "Alice",
                "start_ms": 0,
            })
            huge_pcm = b"\x00" * (1024 * 1024 + 2)  # > 1 MB
            with pytest.raises(WebSocketDisconnect) as exc_info:
                ws.send_bytes(huge_pcm)
                ws.receive_json()
            assert exc_info.value.code == 1009

    def test_odd_length_binary_frame_rejected(self):
        """B2: Binary frame with odd length (not valid 16-bit PCM) is closed with code 1003."""
        meeting_id = "test-odd-binary"
        _create_meeting(meeting_id)
        token = settings.BOT_INGEST_TOKEN

        client = TestClient(app)
        with client.websocket_connect(
            f"/api/v1/meetings/{meeting_id}/stream",
            headers={"x-bot-token": token},
        ) as ws:
            ws.send_json({
                "type": "chunk",
                "speaker_id": "spk1",
                "speaker_name": "Alice",
                "start_ms": 0,
            })
            odd_pcm = b"\x00" * 32001  # Odd number of bytes
            with pytest.raises(WebSocketDisconnect) as exc_info:
                ws.send_bytes(odd_pcm)
                ws.receive_json()
            assert exc_info.value.code == 1003

    def test_binary_frame_without_header_rejected(self):
        """B2: A binary frame received without a preceding chunk header is closed with code 1003."""
        meeting_id = "test-orphan-binary"
        _create_meeting(meeting_id)
        token = settings.BOT_INGEST_TOKEN

        client = TestClient(app)
        with client.websocket_connect(
            f"/api/v1/meetings/{meeting_id}/stream",
            headers={"x-bot-token": token},
        ) as ws:
            with pytest.raises(WebSocketDisconnect) as exc_info:
                ws.send_bytes(b"\x00\x00" * 16000)
                ws.receive_json()
            assert exc_info.value.code == 1003

    def test_bad_json_rejected(self):
        """B2: Invalid JSON or non-object root is closed with code 1003."""
        meeting_id = "test-bad-json"
        _create_meeting(meeting_id)
        token = settings.BOT_INGEST_TOKEN

        client = TestClient(app)
        with client.websocket_connect(
            f"/api/v1/meetings/{meeting_id}/stream",
            headers={"x-bot-token": token},
        ) as ws:
            with pytest.raises(WebSocketDisconnect) as exc_info:
                ws.send_text("this is not valid json")
                ws.receive_json()
            assert exc_info.value.code == 1003

    def test_wrong_types_rejected(self):
        """B2: Missing or wrong-typed fields, or unknown type are closed with code 1003."""
        meeting_id = "test-wrong-types"
        _create_meeting(meeting_id)
        token = settings.BOT_INGEST_TOKEN

        client = TestClient(app)

        # 1. Unknown message type
        with client.websocket_connect(f"/api/v1/meetings/{meeting_id}/stream", headers={"x-bot-token": token}) as ws:
            with pytest.raises(WebSocketDisconnect) as exc_info:
                ws.send_json({"type": "unknown_action"})
                ws.receive_json()
            assert exc_info.value.code == 1003

        # 2. Non-integer start_ms
        with client.websocket_connect(f"/api/v1/meetings/{meeting_id}/stream", headers={"x-bot-token": token}) as ws:
            with pytest.raises(WebSocketDisconnect) as exc_info:
                ws.send_json({"type": "chunk", "speaker_id": "spk1", "start_ms": "1000"})
                ws.receive_json()
            assert exc_info.value.code == 1003

        # 3. Negative start_ms
        with client.websocket_connect(f"/api/v1/meetings/{meeting_id}/stream", headers={"x-bot-token": token}) as ws:
            with pytest.raises(WebSocketDisconnect) as exc_info:
                ws.send_json({"type": "chunk", "speaker_id": "spk1", "start_ms": -50})
                ws.receive_json()
            assert exc_info.value.code == 1003

        # 4. Non-string speaker_id
        with client.websocket_connect(f"/api/v1/meetings/{meeting_id}/stream", headers={"x-bot-token": token}) as ws:
            with pytest.raises(WebSocketDisconnect) as exc_info:
                ws.send_json({"type": "chunk", "speaker_id": 12345, "start_ms": 0})
                ws.receive_json()
            assert exc_info.value.code == 1003

    def test_too_many_speakers_rejected(self):
        """B3: Exceeding MAX_SPEAKERS_PER_MEETING closes connection with code 1008."""
        meeting_id = "test-too-many-speakers"
        _create_meeting(meeting_id)
        token = settings.BOT_INGEST_TOKEN

        client = TestClient(app)
        with (
            patch.object(settings, "MAX_SPEAKERS_PER_MEETING", 3),
            client.websocket_connect(
                f"/api/v1/meetings/{meeting_id}/stream",
                headers={"x-bot-token": token},
            ) as ws,
        ):
            # Send 3 speakers (allowed)
                for i in range(1, 4):
                    ws.send_json({
                        "type": "chunk",
                        "speaker_id": f"spk_{i}",
                        "speaker_name": f"Speaker {i}",
                        "start_ms": (i - 1) * 1000,
                    })
                    ws.send_bytes(b"\x00\x00" * 16000)

                # Send 4th speaker (exceeds limit 3)
                ws.send_json({
                    "type": "chunk",
                    "speaker_id": "spk_4",
                    "speaker_name": "Speaker 4",
                    "start_ms": 3000,
                })
                with pytest.raises(WebSocketDisconnect) as exc_info:
                    ws.send_bytes(b"\x00\x00" * 16000)
                    ws.receive_json()
                assert exc_info.value.code == 1008
