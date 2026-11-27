"""Live audio ingestion service with WebSocket streaming, speaker buffering,
lazy Whisper transcription, speakers table tracking, and finalization pipeline.
"""
from __future__ import annotations

import array
import asyncio
import logging
import sqlite3
import tempfile
import time
import wave
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.core.locks import HEAVY_JOB_LOCK
from app.db.database import get_db
from app.services.llm import is_server_ready
from app.services.summarizer import merge_and_persist
from app.services.transcription import transcribe_audio
from app.services.windowing import process_transcript_windows

logger = logging.getLogger(__name__)

SPEAKER_PALETTE = [
    "#5932ea",
    "#00c49f",
    "#ffbb28",
    "#ff8042",
    "#a855f7",
    "#ec4899",
    "#3b82f6",
    "#10b981",
]


def is_pcm_silent(pcm_bytes: bytes, threshold: int = 100) -> bool:
    """Fast energy check on 16-bit mono PCM.
    Returns True if maximum sample amplitude is below threshold (digital silence or ambient noise floor).
    """
    if not pcm_bytes:
        return True
    even_len = len(pcm_bytes) - (len(pcm_bytes) % 2)
    if even_len < 2:
        return True
    samples = array.array("h", pcm_bytes[:even_len])
    return max(samples) < threshold and min(samples) > -threshold


def transcribe_pcm_bytes(
    pcm_bytes: bytes,
    language: str | None = None,
) -> list[dict[str, Any]]:
    """Convert 16 kHz mono 16-bit PCM bytes into a temporary WAV file and transcribe using Whisper."""
    if not pcm_bytes or len(pcm_bytes) < 320:  # Minimum 10 ms of audio
        return []

    # Skip buffer if clearly silent to save CPU
    if is_pcm_silent(pcm_bytes):
        logger.debug("Skipping Whisper transcription: buffer is digitally silent.")
        return []

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        temp_path = Path(f.name)

    try:
        with wave.open(str(temp_path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(pcm_bytes)
        return transcribe_audio(temp_path, language=language)
    finally:
        temp_path.unlink(missing_ok=True)


def sync_speakers_and_progress(
    meeting_id: str,
    conn: sqlite3.Connection,
    known_speakers: list[str] | set[str] | None = None,
) -> None:
    """Calculate and persist talk duration/percentages per speaker and progress seconds.
    Includes participants who were present but silent (talk_seconds=0, talk_percent=0).
    """
    rows = conn.execute(
        "SELECT start_time, end_time, speaker FROM transcript_segments WHERE meeting_id = ? ORDER BY start_time ASC",
        (meeting_id,),
    ).fetchall()

    talk_totals: dict[str, float] = {}
    max_end = 0.0

    # Initialize known speakers with 0.0 so silent participants appear in speakers table
    if known_speakers:
        for spk in known_speakers:
            if spk and str(spk).strip():
                talk_totals[str(spk).strip()] = 0.0

    # Also keep any existing speakers from prior syncs
    existing_rows = conn.execute("SELECT name FROM speakers WHERE meeting_id = ?", (meeting_id,)).fetchall()
    for er in existing_rows:
        er_name = er["name"]
        if er_name and er_name not in talk_totals:
            talk_totals[er_name] = 0.0

    for r in rows:
        start = float(r["start_time"])
        end = float(r["end_time"])
        max_end = max(max_end, end)
        spk = r["speaker"]
        if spk and str(spk).strip():
            name = str(spk).strip()
            dur = max(0.0, end - start)
            talk_totals[name] = talk_totals.get(name, 0.0) + dur

    total_speech = sum(talk_totals.values())
    conn.execute("DELETE FROM speakers WHERE meeting_id = ?", (meeting_id,))
    for idx, (spk_name, talk_sec) in enumerate(talk_totals.items()):
        talk_sec_round = round(talk_sec, 2)
        talk_pct = round((talk_sec_round / total_speech) * 100.0, 1) if total_speech > 0 else 0.0
        color = SPEAKER_PALETTE[idx % len(SPEAKER_PALETTE)]
        conn.execute(
            """INSERT INTO speakers (meeting_id, name, color, talk_seconds, talk_percent, listen_percent)
               VALUES (?, ?, ?, ?, ?, NULL)""",
            (meeting_id, spk_name, color, talk_sec_round, talk_pct),
        )

    conn.execute(
        "UPDATE meetings SET processed_seconds = ? WHERE id = ?",
        (max_end, meeting_id),
    )


@dataclass
class SpeakerBuffer:
    speaker_id: str
    speaker_name: str | None = None
    buffer_start_ms: int = 0
    audio_data: bytearray = field(default_factory=bytearray)
    last_activity_time: float = field(default_factory=time.monotonic)


class LiveSession:
    """Manages audio buffering, Whisper transcription, and finalization for an active live meeting."""

    def __init__(self, meeting_id: str, language: str | None = None) -> None:
        self.meeting_id = meeting_id
        self.language = language
        self.buffers: dict[str, SpeakerBuffer] = {}
        self.speaker_map: dict[str, str | None] = {}
        self._is_finalized = False
        self._disconnect_timer: asyncio.Task | None = None
        self._idle_task: asyncio.Task | None = None
        self._start_idle_task()

    def _start_idle_task(self) -> None:
        try:
            loop = asyncio.get_running_loop()
            self._idle_task = loop.create_task(self._idle_flush_loop())
        except RuntimeError:
            self._idle_task = None

    def register_speaker(self, speaker_id: str, speaker_name: str | None) -> str | None:
        """Map speaker_id to a unique display name, suffixing duplicates with ' (2)', ' (3)'.
        Never invents a name: if speaker_name is missing or empty, returns None.
        """
        # after a server restart the map is rebuilt in reconnect order,
        # so two people with the same name could swap labels (rare,
        # accepted for now)
        if not speaker_name or not str(speaker_name).strip():
            if speaker_id not in self.speaker_map:
                self.speaker_map[speaker_id] = None
            return self.speaker_map[speaker_id]

        clean_name = str(speaker_name).strip()
        if self.speaker_map.get(speaker_id):
            return self.speaker_map[speaker_id]

        existing_assigned = {v for v in self.speaker_map.values() if v is not None}
        if clean_name not in existing_assigned:
            assigned = clean_name
        else:
            idx = 2
            while f"{clean_name} ({idx})" in existing_assigned:
                idx += 1
            assigned = f"{clean_name} ({idx})"

        self.speaker_map[speaker_id] = assigned
        return assigned

    def get_registered_display_names(self) -> list[str]:
        """Return list of distinct registered display names for participants who connected."""
        seen: set[str] = set()
        result: list[str] = []
        for name in self.speaker_map.values():
            if name and str(name).strip() and name not in seen:
                seen.add(name)
                result.append(name)
        return result

    async def handle_audio_chunk(
        self,
        speaker_id: str,
        speaker_name: str | None,
        start_ms: int,
        pcm_bytes: bytes,
    ) -> None:
        """Process incoming 16 kHz mono PCM16 audio chunk with contiguity and 30s buffer bounds."""
        if self._is_finalized:
            return

        self.register_speaker(speaker_id, speaker_name)
        buf = self.buffers.get(speaker_id)
        if buf is None:
            buf = SpeakerBuffer(speaker_id=speaker_id, speaker_name=speaker_name)
            self.buffers[speaker_id] = buf
        buf.speaker_name = speaker_name

        if len(buf.audio_data) > 0:
            buffered_ms = len(buf.audio_data) / 32.0  # 16000 samples/s * 2 bytes/sample = 32 bytes/ms
            expected_start_ms = buf.buffer_start_ms + buffered_ms
            gap_ms = start_ms - expected_start_ms

            # 2a: Contiguity check (> 500 ms gap flushes existing buffer before starting new buffer)
            if gap_ms > 500:
                logger.info(
                    "Contiguity gap of %.1f ms detected for speaker %s; flushing prior buffer.",
                    gap_ms,
                    speaker_id,
                )
                await self.flush_speaker(speaker_id)
            elif len(buf.audio_data) + len(pcm_bytes) >= 30 * 32000:  # ~30 s max buffer size
                logger.info("Buffer limit (~30s) reached for speaker %s; flushing buffer.", speaker_id)
                await self.flush_speaker(speaker_id)

        if len(buf.audio_data) == 0:
            buf.buffer_start_ms = start_ms

        buf.audio_data.extend(pcm_bytes)
        buf.last_activity_time = time.monotonic()

    async def flush_speaker(self, speaker_id: str) -> None:
        """Transcribe and persist audio segments for a specific speaker buffer."""
        buf = self.buffers.get(speaker_id)
        if not buf or len(buf.audio_data) == 0:
            return

        pcm_bytes = bytes(buf.audio_data)
        buf_start_ms = buf.buffer_start_ms
        buf.audio_data.clear()
        buf.buffer_start_ms = 0
        display_name = self.speaker_map.get(speaker_id)

        # 2. Skip buffer if clearly silent (cheap PCM energy check) to save CPU
        if is_pcm_silent(pcm_bytes):
            logger.debug("Speaker %s buffer is silent; skipping Whisper transcription.", speaker_id)
            with get_db() as conn:
                sync_speakers_and_progress(
                    self.meeting_id,
                    conn,
                    known_speakers=self.get_registered_display_names(),
                )
            return

        # Transcribe in worker thread under shared lock
        async with HEAVY_JOB_LOCK:
            segments = await asyncio.to_thread(transcribe_pcm_bytes, pcm_bytes, self.language)

        with get_db() as conn:
            if segments:
                for s in segments:
                    seg_start = round((buf_start_ms / 1000.0) + s["start_time"], 2)
                    seg_end = round((buf_start_ms / 1000.0) + s["end_time"], 2)
                    conn.execute(
                        """INSERT INTO transcript_segments (meeting_id, start_time, end_time, speaker, text)
                           VALUES (?, ?, ?, ?, ?)""",
                        (self.meeting_id, seg_start, seg_end, display_name, s["text"]),
                    )
            sync_speakers_and_progress(
                self.meeting_id,
                conn,
                known_speakers=self.get_registered_display_names(),
            )

    async def flush_all_buffers(self) -> None:
        """Flush all pending speaker buffers to transcript segments."""
        for spk_id in list(self.buffers.keys()):
            await self.flush_speaker(spk_id)

    async def _idle_flush_loop(self) -> None:
        """2b: Background timer flushing any speaker buffer idle for ~2 seconds."""
        try:
            while not self._is_finalized:
                await asyncio.sleep(0.5)
                now = time.monotonic()
                to_flush = [
                    spk_id
                    for spk_id, buf in list(self.buffers.items())
                    if len(buf.audio_data) > 0 and (now - buf.last_activity_time >= 2.0)
                ]
                for spk_id in to_flush:
                    await self.flush_speaker(spk_id)
        except asyncio.CancelledError:
            pass

    def on_connected(self) -> None:
        """Handle new connection or reconnection."""
        if self._idle_task is None or self._idle_task.done():
            self._start_idle_task()

        if self._disconnect_timer and not self._disconnect_timer.done():
            logger.info("Bot reconnected to meeting %s; cancelled disconnect timer.", self.meeting_id)
            self._disconnect_timer.cancel()
            self._disconnect_timer = None

    def on_disconnected(self) -> None:
        """Handle dropped connection: preserve status 'processing' and schedule 10 min timeout."""
        if self._is_finalized:
            return

        logger.info(
            "WebSocket dropped for meeting %s; keeping status 'processing' and starting %d s timeout.",
            self.meeting_id,
            settings.BOT_DISCONNECT_TIMEOUT_SECONDS,
        )
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.flush_all_buffers())
            self._disconnect_timer = loop.create_task(self._wait_disconnect_timeout())
        except RuntimeError:
            pass

    async def _wait_disconnect_timeout(self) -> None:
        try:
            await asyncio.sleep(settings.BOT_DISCONNECT_TIMEOUT_SECONDS)
            logger.warning(
                "Disconnect timeout expired (%d s) for meeting %s; finalizing.",
                settings.BOT_DISCONNECT_TIMEOUT_SECONDS,
                self.meeting_id,
            )
            await self.finalize()
        except asyncio.CancelledError:
            pass

    async def finalize(self) -> None:
        """Finalize meeting: flush buffers, run window note extraction & summary merge, set status 'done'."""
        if self._is_finalized:
            return
        self._is_finalized = True

        if self._idle_task and not self._idle_task.done():
            self._idle_task.cancel()
        if self._disconnect_timer and not self._disconnect_timer.done():
            self._disconnect_timer.cancel()

        await self.flush_all_buffers()

        async with HEAVY_JOB_LOCK:
            await asyncio.to_thread(self._finalize_sync)

    def _finalize_sync(self) -> None:
        try:
            with get_db() as conn:
                rows = conn.execute(
                    "SELECT id, start_time, end_time, speaker, text FROM transcript_segments WHERE meeting_id = ? ORDER BY start_time ASC",
                    (self.meeting_id,),
                ).fetchall()
                segments = [dict(r) for r in rows]

                max_end = max((s["end_time"] for s in segments), default=0.0)
                conn.execute(
                    "UPDATE meetings SET duration_seconds = ?, processed_seconds = ? WHERE id = ?",
                    (max_end, max_end, self.meeting_id),
                )

            if not segments:
                with get_db() as conn:
                    sync_speakers_and_progress(
                        self.meeting_id,
                        conn,
                        known_speakers=self.get_registered_display_names(),
                    )
                    conn.execute(
                        "UPDATE meetings SET status = 'done', overview = '[No speech detected in recording.]', error = NULL WHERE id = ?",
                        (self.meeting_id,),
                    )
                logger.info("Live meeting %s had no speech segments; marked done.", self.meeting_id)
                return

            if not is_server_ready():
                error_msg = f"llama-server is not reachable at {settings.LLM_SERVER_URL}. Note extraction failed."
                logger.error("LLM server is not ready when finalizing live meeting %s: %s", self.meeting_id, error_msg)
                with get_db() as conn:
                    sync_speakers_and_progress(
                        self.meeting_id,
                        conn,
                        known_speakers=self.get_registered_display_names(),
                    )
                    conn.execute(
                        "UPDATE meetings SET status = 'failed', error = ? WHERE id = ?",
                        (error_msg, self.meeting_id),
                    )
                return

            with get_db() as conn:
                conn.execute("DELETE FROM windows WHERE meeting_id = ?", (self.meeting_id,))
                window_results = process_transcript_windows(self.meeting_id, segments, conn)

            if not window_results:
                raise RuntimeError(f"Windowing produced no results for meeting {self.meeting_id}.")

            for idx, win_note in enumerate(window_results):
                summary_text = win_note.get("summary", "")
                if isinstance(summary_text, str) and summary_text.startswith("[Extraction failed:"):
                    raise RuntimeError(
                        f"Window {idx} extraction failed: {summary_text}. Meeting marked failed."
                    )

            with get_db() as conn:
                merge_and_persist(self.meeting_id, window_results, conn)
                sync_speakers_and_progress(
                    self.meeting_id,
                    conn,
                    known_speakers=self.get_registered_display_names(),
                )
                conn.execute(
                    "UPDATE meetings SET status = 'done', error = NULL WHERE id = ?",
                    (self.meeting_id,),
                )
            logger.info("Successfully finalized live meeting %s with status 'done'.", self.meeting_id)
        except Exception as exc:
            logger.exception("Failed to finalize live meeting %s", self.meeting_id)
            with get_db() as conn:
                sync_speakers_and_progress(
                    self.meeting_id,
                    conn,
                    known_speakers=self.get_registered_display_names(),
                )
                conn.execute(
                    "UPDATE meetings SET status = 'failed', error = ? WHERE id = ?",
                    (str(exc), self.meeting_id),
                )


class LiveSessionManager:
    """Thread-safe manager for active live meeting sessions."""

    def __init__(self) -> None:
        self.sessions: dict[str, LiveSession] = {}

    def get_or_create(self, meeting_id: str, language: str | None = None) -> LiveSession:
        session = self.sessions.get(meeting_id)
        if session is None or session._is_finalized:
            session = LiveSession(meeting_id=meeting_id, language=language)
            self.sessions[meeting_id] = session
        return session

    def get(self, meeting_id: str) -> LiveSession | None:
        return self.sessions.get(meeting_id)

    def remove(self, meeting_id: str) -> None:
        self.sessions.pop(meeting_id, None)


live_session_manager = LiveSessionManager()
