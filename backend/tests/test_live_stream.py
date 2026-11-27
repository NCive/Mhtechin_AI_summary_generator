"""Tests for Step 5A: Live ingestion with speaker names over WebSocket.
Verifies auth, sources, speaker mapping, contiguity, idle flush, disconnect/reconnect,
speakers table metrics, finalization, and real Whisper integration.
"""
from __future__ import annotations

import concurrent.futures
import json
import os
import subprocess
import time
import wave
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from app.core.config import settings
from app.db.database import get_db, init_db
from app.main import app
from app.services.live_stream import (
    SPEAKER_PALETTE,
    LiveSession,
    is_pcm_silent,
    live_session_manager,
    sync_speakers_and_progress,
)
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect


def receive_text_with_timeout(ws: Any, timeout: float = 5.0) -> str:
    """Helper to receive text frame from test websocket with a timeout, failing fast if server hangs."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(ws.receive_text)
        try:
            return future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            pytest.fail(f"WebSocket receive_text timed out after {timeout}s (server blocked or hung)")


def _default_mock_llm_generate(system_prompt, user_prompt, schema=None, client=None):
    if schema and "overview" in schema.get("properties", {}):
        return {"overview": "Test meeting overview."}
    return {
        "summary": "Test meeting summary.",
        "project_progress": ["Progress item"],
        "challenges": [],
        "action_items": [{"text": "Action item", "owner": "Speaker", "deadline": "Tomorrow"}],
        "next_steps": ["Next step"],
    }


@pytest.fixture(autouse=True)
def setup_test_environment(tmp_path):
    """Isolate DB, media, and reset session manager between tests. Mocks llama-server by default."""
    temp_db = tmp_path / "live_stream_test.db"
    temp_media = tmp_path / "media"
    temp_media.mkdir(parents=True, exist_ok=True)

    settings.DB_PATH = str(temp_db)
    settings.MEDIA_DIR = str(temp_media)
    settings.ENABLE_BACKGROUND_WORKER = False
    settings.BOT_INGEST_TOKEN = "test-bot-token"
    settings.BOT_DISCONNECT_TIMEOUT_SECONDS = 600
    settings.BOT_ALLOW_QUERY_TOKEN = True

    init_db()
    live_session_manager.sessions.clear()

    # Make every live-stream test independent of llama-server by default
    with (
        patch("app.services.llm.is_server_ready", return_value=True),
        patch("app.services.live_stream.is_server_ready", return_value=True),
        patch("app.services.llm.count_tokens", side_effect=lambda t, client=None: max(1, len(t) // 4)),
        patch("app.services.windowing.count_tokens", side_effect=lambda t, client=None: max(1, len(t) // 4)),
        patch("app.services.notes_extractor.generate_json", side_effect=_default_mock_llm_generate),
        patch("app.services.summarizer.generate_json", side_effect=_default_mock_llm_generate),
    ):
        yield

    live_session_manager.sessions.clear()


def _create_meeting(
    meeting_id: str,
    source: str = "join",
    status: str = "pending",
    language: str = "en",
    source_url: str = "https://zoom.us/j/1234567890",
) -> None:
    with get_db() as conn:
        conn.execute(
            """INSERT INTO meetings (id, source, status, language, source_url, title)
               VALUES (?, ?, ?, ?, ?, 'Live Sync')""",
            (meeting_id, source, status, language, source_url),
        )


def _generate_pcm16_chunk(duration_ms: int = 1000, silent: bool = False) -> bytes:
    """Generate synthetic PCM16 16 kHz mono bytes (32 bytes per ms)."""
    num_samples = int(16000 * (duration_ms / 1000.0))
    if silent:
        return b"\x00\x00" * num_samples
    import array
    return array.array("h", [1000] * num_samples).tobytes()


# ===========================================================================
# 1. Authentication & Source Validation Tests
# ===========================================================================

class TestWebSocketAuthAndSource:
    def test_reject_missing_token(self):
        client = TestClient(app)
        m_id = "mtg-auth-missing"
        _create_meeting(m_id, source="join")

        with pytest.raises(WebSocketDisconnect) as exc_info, client.websocket_connect(f"/api/v1/meetings/{m_id}/stream"):
            pass
        assert exc_info.value.code == 1008

    def test_reject_wrong_token(self):
        client = TestClient(app)
        m_id = "mtg-auth-wrong"
        _create_meeting(m_id, source="join")

        with pytest.raises(WebSocketDisconnect) as exc_info, client.websocket_connect(f"/api/v1/meetings/{m_id}/stream?token=invalid-secret"):
            pass
        assert exc_info.value.code == 1008

    def test_reject_meeting_source_upload(self):
        client = TestClient(app)
        m_id = "mtg-src-upload"
        _create_meeting(m_id, source="upload")

        with pytest.raises(WebSocketDisconnect) as exc_info, client.websocket_connect(f"/api/v1/meetings/{m_id}/stream?token={settings.BOT_INGEST_TOKEN}"):
            pass
        assert exc_info.value.code == 1008

    def test_reject_nonexistent_meeting(self):
        client = TestClient(app)
        with pytest.raises(WebSocketDisconnect) as exc_info, client.websocket_connect(f"/api/v1/meetings/non-existent-id/stream?token={settings.BOT_INGEST_TOKEN}"):
            pass
        assert exc_info.value.code == 1008

    def test_accept_valid_token_query_and_sets_processing(self):
        client = TestClient(app)
        m_id = "mtg-auth-valid"
        _create_meeting(m_id, source="join", status="pending")

        with patch.object(settings, "BOT_ALLOW_QUERY_TOKEN", True), client.websocket_connect(f"/api/v1/meetings/{m_id}/stream?token={settings.BOT_INGEST_TOKEN}"), get_db() as conn:
            row = conn.execute("SELECT status FROM meetings WHERE id = ?", (m_id,)).fetchone()
            assert row["status"] == "processing"

    def test_reject_placeholder_token_change_me(self):
        client = TestClient(app)
        m_id = "mtg-auth-placeholder"
        _create_meeting(m_id, source="join")

        original_token = settings.BOT_INGEST_TOKEN
        settings.BOT_INGEST_TOKEN = "change-me"
        try:
            with pytest.raises(WebSocketDisconnect) as exc_info, client.websocket_connect(f"/api/v1/meetings/{m_id}/stream?token=change-me"):
                pass
            assert exc_info.value.code == 1008
        finally:
            settings.BOT_INGEST_TOKEN = original_token

    def test_reject_empty_server_token(self):
        client = TestClient(app)
        m_id = "mtg-auth-empty-server"
        _create_meeting(m_id, source="join")

        original_token = settings.BOT_INGEST_TOKEN
        settings.BOT_INGEST_TOKEN = ""
        try:
            with pytest.raises(WebSocketDisconnect) as exc_info, client.websocket_connect(f"/api/v1/meetings/{m_id}/stream?token=any-token"):
                pass
            assert exc_info.value.code == 1008
        finally:
            settings.BOT_INGEST_TOKEN = original_token


# ===========================================================================
# 2. Speaker Mapping & Buffer Tests
# ===========================================================================

class TestSpeakerMappingAndBuffering:
    def test_duplicate_speaker_names_disambiguation(self):
        session = LiveSession(meeting_id="mtg-names")

        # First Alex
        n1 = session.register_speaker("spk-1", "Alex")
        assert n1 == "Alex"

        # Same speaker sends same name again
        assert session.register_speaker("spk-1", "Alex") == "Alex"

        # Second Alex (different speaker_id) -> "Alex (2)"
        n2 = session.register_speaker("spk-2", "Alex")
        assert n2 == "Alex (2)"

        # Third Alex -> "Alex (3)"
        n3 = session.register_speaker("spk-3", "Alex")
        assert n3 == "Alex (3)"

        # Missing name must remain None (never invent a name)
        n4 = session.register_speaker("spk-4", None)
        assert n4 is None
        n5 = session.register_speaker("spk-5", "")
        assert n5 is None

    def test_two_speakers_buffered_and_saved(self):
        client = TestClient(app)
        m_id = "mtg-two-spk"
        _create_meeting(m_id, source="join")

        fake_segments_spk1 = [{"start_time": 0.0, "end_time": 1.0, "text": "Hello from Alice."}]
        fake_segments_spk2 = [{"start_time": 0.0, "end_time": 1.0, "text": "Hi from Bob."}]

        call_count = 0
        def mock_transcribe(pcm, lang):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return fake_segments_spk1
            return fake_segments_spk2

        with (
            patch("app.services.live_stream.transcribe_pcm_bytes", side_effect=mock_transcribe),
            client.websocket_connect(f"/api/v1/meetings/{m_id}/stream?token={settings.BOT_INGEST_TOKEN}") as ws,
        ):
            # Alice speaks at 0 ms for 1000 ms
            ws.send_text(json.dumps({
                "type": "chunk",
                "speaker_id": "spk-1",
                "speaker_name": "Alice",
                "start_ms": 0,
            }))
            ws.send_bytes(_generate_pcm16_chunk(1000))

            # Bob speaks at 1000 ms for 1000 ms
            ws.send_text(json.dumps({
                "type": "chunk",
                "speaker_id": "spk-2",
                "speaker_name": "Bob",
                "start_ms": 1000,
            }))
            ws.send_bytes(_generate_pcm16_chunk(1000))

            # Send end to flush and finalize
            with (
                patch("app.services.live_stream.is_server_ready", return_value=True),
                patch("app.services.live_stream.process_transcript_windows", return_value=[{"summary": "Test"}]),
                patch("app.services.live_stream.merge_and_persist"),
            ):
                ws.send_text(json.dumps({"type": "end"}))
                with pytest.raises(WebSocketDisconnect) as close_info:
                    receive_text_with_timeout(ws)
                assert close_info.value.code == 1000

        with get_db() as conn:
            rows = conn.execute(
                "SELECT start_time, end_time, speaker, text FROM transcript_segments WHERE meeting_id = ? ORDER BY start_time ASC",
                (m_id,),
            ).fetchall()
            assert len(rows) == 2
            assert rows[0]["speaker"] == "Alice"
            assert rows[0]["start_time"] == 0.0
            assert rows[0]["end_time"] == 1.0
            assert rows[0]["text"] == "Hello from Alice."

            assert rows[1]["speaker"] == "Bob"
            assert rows[1]["start_time"] == 1.0
            assert rows[1]["end_time"] == 2.0
            assert rows[1]["text"] == "Hi from Bob."


# ===========================================================================
# 3. Contiguity & Idle Flush Tests
# ===========================================================================

class TestContiguityAndIdleFlush:
    def test_contiguity_gap_forces_flush(self):
        """2a: A gap > 500 ms must flush existing buffer before starting new buffer.
        Speaker speaks at 0-5 s and again at 40 s -> segment at ~40 s.
        """
        client = TestClient(app)
        m_id = "mtg-contiguity"
        _create_meeting(m_id, source="join")

        def mock_transcribe(pcm, lang):
            # Record that a flush occurred and return segment matching buffer duration
            dur = len(pcm) / 32000.0
            return [{"start_time": 0.0, "end_time": dur, "text": f"Spoken for {dur}s"}]

        with (
            patch("app.services.live_stream.transcribe_pcm_bytes", side_effect=mock_transcribe),
            client.websocket_connect(f"/api/v1/meetings/{m_id}/stream?token={settings.BOT_INGEST_TOKEN}") as ws,
        ):
            # 0-5 s audio chunk (5000 ms)
            ws.send_text(json.dumps({
                "type": "chunk",
                "speaker_id": "spk-1",
                "speaker_name": "Speaker 1",
                "start_ms": 0,
            }))
            ws.send_bytes(_generate_pcm16_chunk(5000))

            # New chunk arrives at 40 s (40000 ms > 5000 ms + 500 ms gap)
            ws.send_text(json.dumps({
                "type": "chunk",
                "speaker_id": "spk-1",
                "speaker_name": "Speaker 1",
                "start_ms": 40000,
            }))
            ws.send_bytes(_generate_pcm16_chunk(1000))

            # Flush all and finish
            with (
                patch("app.services.live_stream.is_server_ready", return_value=True),
                patch("app.services.live_stream.process_transcript_windows", return_value=[{"summary": "Test"}]),
                patch("app.services.live_stream.merge_and_persist"),
            ):
                ws.send_text(json.dumps({"type": "end"}))
                with pytest.raises(WebSocketDisconnect) as close_info:
                    receive_text_with_timeout(ws)
                assert close_info.value.code == 1000

        with get_db() as conn:
            rows = conn.execute(
                "SELECT start_time, end_time, speaker, text FROM transcript_segments WHERE meeting_id = ? ORDER BY start_time ASC",
                (m_id,),
            ).fetchall()
            assert len(rows) == 2
            # Segment 1 at 0-5s
            assert rows[0]["start_time"] == 0.0
            assert rows[0]["end_time"] == 5.0
            # Segment 2 MUST start at 40.0s, NOT at 5.0s!
            assert rows[1]["start_time"] == 40.0
            assert rows[1]["end_time"] == 41.0

    def test_idle_flush_after_silence(self):
        """2b: A speaker who says one sentence and stops talking must be flushed by the timer (~2 s)."""
        client = TestClient(app)
        m_id = "mtg-idle-flush"
        _create_meeting(m_id, source="join")

        fake_segments = [{"start_time": 0.0, "end_time": 1.0, "text": "One quick sentence."}]

        with (
            patch("app.services.live_stream.transcribe_pcm_bytes", return_value=fake_segments),
            client.websocket_connect(f"/api/v1/meetings/{m_id}/stream?token={settings.BOT_INGEST_TOKEN}") as ws,
        ):
            ws.send_text(json.dumps({
                "type": "chunk",
                "speaker_id": "spk-idle",
                "speaker_name": "Quick Speaker",
                "start_ms": 0,
            }))
            ws.send_bytes(_generate_pcm16_chunk(1000))

            # Wait for idle flush timer (> 2.0 s)
            time.sleep(2.5)

            # Verify transcript_segments already has the segment without sending "end"
            with get_db() as conn:
                rows = conn.execute(
                    "SELECT start_time, end_time, speaker, text FROM transcript_segments WHERE meeting_id = ?",
                    (m_id,),
                ).fetchall()
                assert len(rows) == 1
                assert rows[0]["speaker"] == "Quick Speaker"
                assert rows[0]["text"] == "One quick sentence."


# ===========================================================================
# 4. Speakers Table & Disconnect/Reconnect Tests
# ===========================================================================

class TestSpeakersTableAndDisconnect:
    def test_speakers_table_talk_seconds_and_percentage(self):
        m_id = "mtg-spk-table"
        _create_meeting(m_id, source="join")

        with get_db() as conn:
            # Alice talked 6s, Bob talked 4s
            conn.execute(
                "INSERT INTO transcript_segments (meeting_id, start_time, end_time, speaker, text) VALUES (?, 0.0, 6.0, 'Alice', 'Alice speaks')",
                (m_id,),
            )
            conn.execute(
                "INSERT INTO transcript_segments (meeting_id, start_time, end_time, speaker, text) VALUES (?, 6.0, 10.0, 'Bob', 'Bob speaks')",
                (m_id,),
            )
            sync_speakers_and_progress(m_id, conn)

            rows = conn.execute(
                "SELECT name, color, talk_seconds, talk_percent, listen_percent FROM speakers WHERE meeting_id = ? ORDER BY talk_seconds DESC",
                (m_id,),
            ).fetchall()

            assert len(rows) == 2
            # Alice
            assert rows[0]["name"] == "Alice"
            assert rows[0]["talk_seconds"] == 6.0
            assert rows[0]["talk_percent"] == 60.0
            assert rows[0]["color"] == SPEAKER_PALETTE[0]
            assert rows[0]["listen_percent"] is None

            # Bob
            assert rows[1]["name"] == "Bob"
            assert rows[1]["talk_seconds"] == 4.0
            assert rows[1]["talk_percent"] == 40.0
            assert rows[1]["color"] == SPEAKER_PALETTE[1]
            assert rows[1]["listen_percent"] is None

            # Check meeting processed_seconds
            mtg = conn.execute("SELECT processed_seconds FROM meetings WHERE id = ?", (m_id,)).fetchone()
            assert mtg["processed_seconds"] == 10.0

    def test_disconnect_and_reconnect_preserves_segments(self):
        client = TestClient(app)
        m_id = "mtg-reconnect"
        _create_meeting(m_id, source="join")

        fake_seg1 = [{"start_time": 0.0, "end_time": 1.0, "text": "Segment before drop."}]
        fake_seg2 = [{"start_time": 0.0, "end_time": 1.0, "text": "Segment after reconnect."}]

        call_idx = 0
        def mock_transcribe(pcm, lang):
            nonlocal call_idx
            call_idx += 1
            return fake_seg1 if call_idx == 1 else fake_seg2

        with patch("app.services.live_stream.transcribe_pcm_bytes", side_effect=mock_transcribe):
            # Session 1: Send chunk and disconnect without "end"
            with client.websocket_connect(f"/api/v1/meetings/{m_id}/stream?token={settings.BOT_INGEST_TOKEN}") as ws:
                ws.send_text(json.dumps({
                    "type": "chunk",
                    "speaker_id": "spk-1",
                    "speaker_name": "Alice",
                    "start_ms": 0,
                }))
                ws.send_bytes(_generate_pcm16_chunk(1000))
                # Let client context exit (dropped connection)

            # Check that status is still processing and segment is saved
            with get_db() as conn:
                mtg = conn.execute("SELECT status FROM meetings WHERE id = ?", (m_id,)).fetchone()
                assert mtg["status"] == "processing"
                count = conn.execute("SELECT count(*) FROM transcript_segments WHERE meeting_id = ?", (m_id,)).fetchone()[0]
                assert count == 1

            # Session 2: Reconnect to same meeting
            with client.websocket_connect(f"/api/v1/meetings/{m_id}/stream?token={settings.BOT_INGEST_TOKEN}") as ws:
                ws.send_text(json.dumps({
                    "type": "chunk",
                    "speaker_id": "spk-1",
                    "speaker_name": "Alice",
                    "start_ms": 5000,
                }))
                ws.send_bytes(_generate_pcm16_chunk(1000))

                with (
                    patch("app.services.live_stream.is_server_ready", return_value=True),
                    patch("app.services.live_stream.process_transcript_windows", return_value=[{"summary": "Test"}]),
                    patch("app.services.live_stream.merge_and_persist"),
                ):
                    ws.send_text(json.dumps({"type": "end"}))
                    with pytest.raises(WebSocketDisconnect) as close_info:
                        receive_text_with_timeout(ws)
                    assert close_info.value.code == 1000

        with get_db() as conn:
            mtg = conn.execute("SELECT status FROM meetings WHERE id = ?", (m_id,)).fetchone()
            assert mtg["status"] == "done"
            segments = conn.execute("SELECT text FROM transcript_segments WHERE meeting_id = ? ORDER BY start_time ASC", (m_id,)).fetchall()
            assert len(segments) == 2
            assert segments[0]["text"] == "Segment before drop."
            assert segments[1]["text"] == "Segment after reconnect."

    def test_live_finalize_fails_fast_when_llama_server_unavailable(self):
        """When llama-server is unavailable, finalize must fail fast, set meetings.error, and WebSocket still answers."""
        client = TestClient(app)
        m_id = "mtg-llama-down"
        _create_meeting(m_id, source="join")

        fake_segments = [{"start_time": 0.0, "end_time": 1.0, "text": "Speech before end."}]

        with (
            patch("app.services.live_stream.transcribe_pcm_bytes", return_value=fake_segments),
            patch("app.services.live_stream.is_server_ready", return_value=False),
            client.websocket_connect(f"/api/v1/meetings/{m_id}/stream?token={settings.BOT_INGEST_TOKEN}") as ws,
        ):
            ws.send_text(json.dumps({
                "type": "chunk",
                "speaker_id": "spk-1",
                "speaker_name": "Speaker",
                "start_ms": 0,
            }))
            ws.send_bytes(_generate_pcm16_chunk(1000))

            ws.send_text(json.dumps({"type": "end"}))
            # Must answer promptly and close with 1000 (not hang)
            with pytest.raises(WebSocketDisconnect) as close_info:
                receive_text_with_timeout(ws, timeout=5.0)
            assert close_info.value.code == 1000

        with get_db() as conn:
            mtg = conn.execute("SELECT status, error FROM meetings WHERE id = ?", (m_id,)).fetchone()
            assert mtg["status"] == "failed"
            assert mtg["error"] is not None
            assert "llama-server" in mtg["error"]


# ===========================================================================
# 5. Real Whisper Integration Test
# ===========================================================================

class TestRealWhisperIntegration:
    def test_real_speech_wav_live_stream_integration(self, tmp_path):
        """Run live stream with a real 5-10 s WAV of speech, mock only llama-server, run real Whisper."""
        speech_raw_wav = tmp_path / "raw_speech.wav"
        speech_16k_wav = tmp_path / "speech_16k.wav"

        # Generate 5 seconds of real English speech using Windows System.Speech.Synthesis
        ps_cmd = (
            "Add-Type -AssemblyName System.Speech; "
            "$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            f"$synth.SetOutputToWaveFile('{speech_raw_wav!s}'); "
            "$synth.Speak('Hello team, welcome to the sprint review meeting. We are making good progress on our quarterly milestones.'); "
            "$synth.Dispose()"
        )
        res = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_cmd],
            capture_output=True,
            check=False,
        )
        if res.returncode != 0 or not speech_raw_wav.exists():
            pytest.skip("PowerShell speech synthesis unavailable in environment")

        # Convert to 16 kHz mono 16-bit PCM WAV using FFmpeg
        res_ff = subprocess.run(
            [settings.FFMPEG_PATH, "-y", "-i", str(speech_raw_wav), "-ar", "16000", "-ac", "1", str(speech_16k_wav)],
            capture_output=True,
            check=False,
        )
        if res_ff.returncode != 0 or not speech_16k_wav.exists():
            pytest.skip("FFmpeg audio conversion unavailable")

        # Read PCM frames
        with wave.open(str(speech_16k_wav), "rb") as wf:
            frames = wf.readframes(wf.getnframes())
            duration = wf.getnframes() / wf.getframerate()
            assert duration >= 3.0  # Real speech duration

        client = TestClient(app)
        m_id = "mtg-real-speech"
        _create_meeting(m_id, source="join")

        def mock_llm_generate(system_prompt, user_prompt, schema=None, client=None):
            if schema and "overview" in schema.get("properties", {}):
                return {"overview": "The team reviewed the sprint and made progress on quarterly milestones."}
            return {
                "summary": "The team discussed sprint review and quarterly milestones.",
                "project_progress": ["Quarterly milestones on track"],
                "challenges": [],
                "action_items": [{"text": "Continue sprint execution", "owner": "Project Lead", "deadline": "Friday"}],
                "next_steps": ["Continue sprint execution"],
            }

        # Mock ONLY llama-server (is_server_ready, count_tokens and generate_json LLM responses)
        with (
            patch("app.services.llm.is_server_ready", return_value=True),
            patch("app.services.live_stream.is_server_ready", return_value=True),
            patch("app.services.llm.count_tokens", side_effect=lambda t, client=None: max(1, len(t) // 4)),
            patch("app.services.windowing.count_tokens", side_effect=lambda t, client=None: max(1, len(t) // 4)),
            patch("app.services.notes_extractor.generate_json", side_effect=mock_llm_generate),
            patch("app.services.summarizer.generate_json", side_effect=mock_llm_generate),
            client.websocket_connect(f"/api/v1/meetings/{m_id}/stream?token={settings.BOT_INGEST_TOKEN}") as ws,
        ):
            # Stream the real audio in ~1 s chunks
            chunk_bytes = 32000
            current_ms = 0
            for offset in range(0, len(frames), chunk_bytes):
                chunk = frames[offset : offset + chunk_bytes]
                ws.send_text(json.dumps({
                    "type": "chunk",
                    "speaker_id": "spk_lead",
                    "speaker_name": "Project Lead",
                    "start_ms": current_ms,
                }))
                ws.send_bytes(chunk)
                current_ms += int(len(chunk) / 32)

            # End meeting and wait for close frame
            ws.send_text(json.dumps({"type": "end"}))
            with pytest.raises(WebSocketDisconnect) as close_info:
                receive_text_with_timeout(ws)
            assert close_info.value.code == 1000

        # Verify DB state
        with get_db() as conn:
            mtg = conn.execute("SELECT status, overview FROM meetings WHERE id = ?", (m_id,)).fetchone()
            assert mtg["status"] == "done"
            assert "sprint review" in mtg["overview"]

            segments = conn.execute("SELECT speaker, text FROM transcript_segments WHERE meeting_id = ?", (m_id,)).fetchall()
            assert len(segments) > 0
            # Real Whisper should have transcribed words like "Hello", "team", "welcome", "sprint"
            full_text = " ".join(s["text"].lower() for s in segments)
            assert any(word in full_text for word in ("hello", "welcome", "team", "sprint", "meeting", "progress"))
            assert all(s["speaker"] == "Project Lead" for s in segments)

            # Check speakers table
            speakers = conn.execute("SELECT name, talk_seconds, talk_percent FROM speakers WHERE meeting_id = ?", (m_id,)).fetchall()
            assert len(speakers) == 1
            assert speakers[0]["name"] == "Project Lead"
            assert speakers[0]["talk_seconds"] > 0
            assert speakers[0]["talk_percent"] == 100.0

    def test_silent_participant_produces_zero_segments_and_speakers_row(self, tmp_path):
        """One speaker streams ~20 s of digital silence, another streams real speech.
        The silent speaker must produce 0 segments, no invented text, and a speakers row with 0 talk_seconds.
        Meeting must finish 'done'.
        """
        speech_raw_wav = tmp_path / "raw_speech_2.wav"
        speech_16k_wav = tmp_path / "speech_16k_2.wav"

        ps_cmd = (
            "Add-Type -AssemblyName System.Speech; "
            "$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            f"$synth.SetOutputToWaveFile('{speech_raw_wav!s}'); "
            "$synth.Speak('We are now discussing the project deliverables and key milestones for the quarter.'); "
            "$synth.Dispose()"
        )
        res = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_cmd],
            capture_output=True,
            check=False,
        )
        if res.returncode != 0 or not speech_raw_wav.exists():
            pytest.skip("PowerShell speech synthesis unavailable in environment")

        res_ff = subprocess.run(
            [settings.FFMPEG_PATH, "-y", "-i", str(speech_raw_wav), "-ar", "16000", "-ac", "1", str(speech_16k_wav)],
            capture_output=True,
            check=False,
        )
        if res_ff.returncode != 0 or not speech_16k_wav.exists():
            pytest.skip("FFmpeg audio conversion unavailable")

        with wave.open(str(speech_16k_wav), "rb") as wf:
            speech_frames = wf.readframes(wf.getnframes())

        client = TestClient(app)
        m_id = "mtg-silent-and-active"
        _create_meeting(m_id, source="join")

        def mock_llm_generate(system_prompt, user_prompt, schema=None, client=None):
            if schema and "overview" in schema.get("properties", {}):
                return {"overview": "The team discussed deliverables and key milestones."}
            return {
                "summary": "Project deliverables and milestones review.",
                "project_progress": ["Milestones reviewed"],
                "challenges": [],
                "action_items": [{"text": "Deliver project milestones", "owner": "Active Alice", "deadline": "Friday"}],
                "next_steps": ["Deliver milestones"],
            }

        with (
            patch("app.services.llm.is_server_ready", return_value=True),
            patch("app.services.live_stream.is_server_ready", return_value=True),
            patch("app.services.llm.count_tokens", side_effect=lambda t, client=None: max(1, len(t) // 4)),
            patch("app.services.windowing.count_tokens", side_effect=lambda t, client=None: max(1, len(t) // 4)),
            patch("app.services.notes_extractor.generate_json", side_effect=mock_llm_generate),
            patch("app.services.summarizer.generate_json", side_effect=mock_llm_generate),
            client.websocket_connect(f"/api/v1/meetings/{m_id}/stream?token={settings.BOT_INGEST_TOKEN}") as ws,
        ):
            # 1. Stream ~20 s of digital silence for speaker "Silent Bob"
            # 20 chunks of 1000 ms (32000 bytes each) = 20 seconds
            for i in range(20):
                ws.send_text(json.dumps({
                    "type": "chunk",
                    "speaker_id": "spk_silent",
                    "speaker_name": "Silent Bob",
                    "start_ms": i * 1000,
                }))
                ws.send_bytes(b"\x00\x00" * 16000)

            # 2. Stream real speech for speaker "Active Alice" starting at 20000 ms
            chunk_bytes = 32000
            current_ms = 20000
            for offset in range(0, len(speech_frames), chunk_bytes):
                chunk = speech_frames[offset : offset + chunk_bytes]
                ws.send_text(json.dumps({
                    "type": "chunk",
                    "speaker_id": "spk_active",
                    "speaker_name": "Active Alice",
                    "start_ms": current_ms,
                }))
                ws.send_bytes(chunk)
                current_ms += int(len(chunk) / 32)

            # 3. End meeting
            ws.send_text(json.dumps({"type": "end"}))
            with pytest.raises(WebSocketDisconnect) as close_info:
                receive_text_with_timeout(ws)
            assert close_info.value.code == 1000

        # Verify DB state
        with get_db() as conn:
            mtg = conn.execute("SELECT status, overview FROM meetings WHERE id = ?", (m_id,)).fetchone()
            assert mtg["status"] == "done"
            assert "deliverables" in mtg["overview"].lower() or "milestones" in mtg["overview"].lower()

            segments = conn.execute(
                "SELECT speaker, text FROM transcript_segments WHERE meeting_id = ?",
                (m_id,),
            ).fetchall()
            assert len(segments) > 0

            # Silent speaker must produce ZERO segments and no invented text
            silent_segments = [s for s in segments if s["speaker"] == "Silent Bob"]
            assert len(silent_segments) == 0

            # All transcribed segments belong to Active Alice
            for s in segments:
                assert s["speaker"] == "Active Alice"
                text = s["text"].strip()
                assert len(text) > 0
                assert text not in (".", "...", "!", "?", "Thank you.", "Thanks for watching!")

            # Verify speakers table
            speakers = conn.execute(
                "SELECT name, color, talk_seconds, talk_percent, listen_percent FROM speakers WHERE meeting_id = ? ORDER BY name ASC",
                (m_id,),
            ).fetchall()
            spk_by_name = {s["name"]: s for s in speakers}

            assert "Active Alice" in spk_by_name
            assert "Silent Bob" in spk_by_name

            alice = spk_by_name["Active Alice"]
            assert alice["talk_seconds"] > 0
            assert alice["talk_percent"] == 100.0
            assert alice["color"] is not None
            assert alice["listen_percent"] is None

            bob = spk_by_name["Silent Bob"]
            assert bob["talk_seconds"] == 0.0
            assert bob["talk_percent"] == 0.0
            assert bob["color"] is not None
            assert bob["listen_percent"] is None


# ===========================================================================
# 6. Silence Detection & Energy Check Unit Tests
# ===========================================================================

class TestSilenceDetection:
    def test_is_pcm_silent_pure_digital_silence(self):
        silence = b"\x00\x00" * 16000
        assert is_pcm_silent(silence) is True

    def test_is_pcm_silent_empty_or_too_short(self):
        assert is_pcm_silent(b"") is True
        assert is_pcm_silent(b"\x00") is True

    def test_is_pcm_silent_low_energy_noise(self):
        import struct
        samples = [25, -30, 40, -10, 0, 15] * 100
        pcm = struct.pack(f"<{len(samples)}h", *samples)
        assert is_pcm_silent(pcm, threshold=100) is True

    def test_is_pcm_silent_speech_or_loud_tone(self):
        import struct
        samples = [0, 5000, -5000, 1000] * 100
        pcm = struct.pack(f"<{len(samples)}h", *samples)
        assert is_pcm_silent(pcm, threshold=100) is False

    def test_transcribe_pcm_bytes_skips_whisper_on_silence(self):
        from app.services.live_stream import transcribe_pcm_bytes
        with patch("app.services.live_stream.transcribe_audio") as mock_transcribe:
            result = transcribe_pcm_bytes(b"\x00\x00" * 16000)
            assert result == []
            mock_transcribe.assert_not_called()



