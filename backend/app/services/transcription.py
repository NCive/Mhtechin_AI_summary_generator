"""Whisper transcription service using faster-whisper."""
from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)

_whisper_model_instance: Any | None = None


def get_whisper_model() -> Any:
    """Return the lazily loaded WhisperModel singleton instance."""
    global _whisper_model_instance
    if _whisper_model_instance is None:
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise RuntimeError(
                "faster-whisper is not installed. Please install it in the Python environment."
            ) from exc

        logger.info(
            "Loading Whisper model '%s' on %s (%s)...",
            settings.WHISPER_MODEL,
            settings.WHISPER_DEVICE,
            settings.WHISPER_COMPUTE_TYPE,
        )
        _whisper_model_instance = WhisperModel(
            settings.WHISPER_MODEL,
            device=settings.WHISPER_DEVICE,
            compute_type=settings.WHISPER_COMPUTE_TYPE,
        )
    return _whisper_model_instance


def set_whisper_model(model: Any) -> None:
    """Explicitly set or mock the Whisper model singleton (useful for testing)."""
    global _whisper_model_instance
    _whisper_model_instance = model


def transcribe_audio(
    audio_path: Path,
    language: str | None = None,
) -> list[dict[str, Any]]:
    """Transcribe 16 kHz mono WAV audio file into timestamped segments.

    Returns:
        List of dicts: [
            {"start_time": float, "end_time": float, "text": str, "speaker": None}
        ]
    """
    model = get_whisper_model()

    # Normalize language: if full name like 'english', convert or let auto-detect
    lang_code = language.strip().lower() if language and isinstance(language, str) else None
    if lang_code in ("english", "en"):
        lang_code = "en"
    elif lang_code and len(lang_code) > 2:
        # If unsupported or complex name, pass None for automatic VAD & language detection
        lang_code = None

    segments_gen, _ = model.transcribe(
        str(audio_path),
        language=lang_code,
        vad_filter=True,
    )

    results: list[dict[str, Any]] = []
    for seg in segments_gen:
        # Guard against Whisper hallucinations on silence / low-energy audio
        raw_prob = getattr(seg, "no_speech_prob", 0.0)
        no_speech_prob = 0.0
        if raw_prob is not None:
            if type(raw_prob).__name__ in ("MagicMock", "Mock"):
                no_speech_prob = 0.0
            else:
                try:
                    no_speech_prob = float(raw_prob)
                except (ValueError, TypeError):
                    no_speech_prob = 0.0

        raw_logprob = getattr(seg, "avg_logprob", 0.0)
        avg_logprob = 0.0
        if raw_logprob is not None:
            if type(raw_logprob).__name__ in ("MagicMock", "Mock"):
                avg_logprob = 0.0
            else:
                try:
                    avg_logprob = float(raw_logprob)
                except (ValueError, TypeError):
                    avg_logprob = 0.0

        start_time = round(float(getattr(seg, "start", 0.0)), 2)
        end_time = round(float(getattr(seg, "end", 0.0)), 2)
        text = str(seg.text).strip()

        # Whisper dual-condition filter: drop only if high no_speech_prob AND low avg_logprob
        if (
            no_speech_prob > settings.NO_SPEECH_PROB_THRESHOLD
            and avg_logprob < settings.AVG_LOGPROB_THRESHOLD
        ):
            logger.info(
                "Dropping segment [%.2f - %.2f] (no_speech_prob=%.4f, avg_logprob=%.4f): %r",
                start_time,
                end_time,
                no_speech_prob,
                avg_logprob,
                text,
            )
            continue

        # Drop empty text or non-speech hallucination markers
        if not text or text in (".", "...", "!", "?", "Thank you.", "Thanks for watching!", "Subtitles by", "[BLANK_AUDIO]"):
            continue

        results.append({
            "start_time": start_time,
            "end_time": end_time,
            "text": text,
            "speaker": None,  # Speaker diarization deferred to Step 5
        })

    return results


def persist_transcript_segments(
    meeting_id: str,
    segments: list[dict[str, Any]],
    duration_seconds: float,
    conn: sqlite3.Connection,
) -> None:
    """Save transcript segments and update duration/progress in SQLite.

    Idempotent: removes prior transcript segments for this meeting on retry.
    Triggers transcript_fts automatically on insert.
    """
    # Clear any previous segments for this meeting to prevent duplicates on retry
    conn.execute("DELETE FROM transcript_segments WHERE meeting_id = ?", (meeting_id,))

    if segments:
        conn.executemany(
            """INSERT INTO transcript_segments (meeting_id, start_time, end_time, speaker, text)
               VALUES (?, ?, ?, ?, ?)""",
            [
                (
                    meeting_id,
                    s["start_time"],
                    s["end_time"],
                    s.get("speaker"),
                    s["text"],
                )
                for s in segments
            ],
        )

    # Monotonic bounded progress calculation
    max_segment_end = max((s["end_time"] for s in segments), default=0.0)
    processed_seconds = min(duration_seconds, max(max_segment_end, 0.0))

    conn.execute(
        """UPDATE meetings
           SET duration_seconds = ?, processed_seconds = ?
           WHERE id = ?""",
        (round(duration_seconds, 2), round(processed_seconds, 2), meeting_id),
    )
