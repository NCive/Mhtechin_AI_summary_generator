"""Meeting processing pipeline connecting Audio extraction, Whisper transcription,
transcript windowing, notes extraction, summary merging, and database persistence.
"""
from __future__ import annotations

import logging
from pathlib import Path

from app.db.database import get_db
from app.services.audio import extract_temporary_wav
from app.services.llm import LLMUnavailable, is_server_ready
from app.services.summarizer import merge_and_persist
from app.services.transcription import persist_transcript_segments, transcribe_audio
from app.services.windowing import process_transcript_windows

logger = logging.getLogger(__name__)


def process_meeting_pipeline(meeting_id: str) -> None:
    """Execute the complete end-to-end processing pipeline for an uploaded meeting.

    1. Validates meeting eligibility (source must be 'upload', media_path must exist).
    2. Extracts 16 kHz mono WAV audio and detects duration using FFmpeg/FFprobe.
    3. Transcribes audio to timestamped segments with Whisper.
    4. Persists segments to SQLite (updating duration and processed progress).
    5. Runs Step 3B token-aware transcript windowing and note extraction.
    6. Validates window results; fails if any window extraction failed.
    7. Runs Step 3B summary merging and persistence (overview, progress, challenges, next_steps, action_items).
    8. Marks meeting status = 'done'.

    All long-running AI inference runs outside database write locks.
    """
    logger.info("Starting processing pipeline for meeting %s", meeting_id)

    # 0. Early check: LLM server readiness before CPU/IO heavy FFmpeg and Whisper
    if not is_server_ready():
        raise LLMUnavailable(f"LLM server is not ready before processing meeting {meeting_id}.")

    # 1. Fetch meeting info
    with get_db() as conn:
        row = conn.execute(
            "SELECT id, source, media_path, language, status FROM meetings WHERE id = ?",
            (meeting_id,),
        ).fetchone()
        if not row:
            raise ValueError(f"Meeting '{meeting_id}' not found.")

        meeting = dict(row)
        if meeting.get("source") != "upload" or not meeting.get("media_path"):
            logger.info(
                "Meeting %s is not an uploaded recording (source=%s); skipping pipeline.",
                meeting_id,
                meeting.get("source"),
            )
            return

        media_path = Path(meeting["media_path"])
        language = meeting.get("language")

        # Delete any existing windows from a previous or interrupted run
        conn.execute("DELETE FROM windows WHERE meeting_id = ?", (meeting_id,))

    # 2. Audio Extraction (Temporary 16kHz WAV + Duration)
    with extract_temporary_wav(media_path) as (wav_path, duration):
        logger.info(
            "Extracted temporary WAV for meeting %s (duration: %.2f s)",
            meeting_id,
            duration,
        )

        # 3. Whisper Transcription
        segments = transcribe_audio(wav_path, language=language)
        logger.info(
            "Transcribed %d segments for meeting %s",
            len(segments),
            meeting_id,
        )

        # 4. Persist Segments & Update Processed Seconds
        with get_db() as conn:
            persist_transcript_segments(meeting_id, segments, duration, conn)

        # 5. Check for Silence / Empty audio
        if not segments:
            logger.info("No speech detected in audio for meeting %s.", meeting_id)
            with get_db() as conn:
                conn.execute(
                    "UPDATE meetings SET status = 'done', overview = '[No speech detected in recording.]', error = NULL WHERE id = ?",
                    (meeting_id,),
                )
            return

        # 6. Check LLM Server Availability before window note extraction
        if not is_server_ready():
            logger.warning(
                "LLM server appears unavailable at start of windowing for meeting %s. Attempting extraction with fallbacks...",
                meeting_id,
            )

        # 7. Step 3B: Transcript Windows Note Extraction
        with get_db() as conn:
            window_results = process_transcript_windows(meeting_id, segments, conn)

        if not window_results:
            raise RuntimeError(f"Windowing produced no results for meeting {meeting_id}.")

        # Check for any failed window placeholders
        for idx, win_note in enumerate(window_results):
            summary_text = win_note.get("summary", "")
            if isinstance(summary_text, str) and summary_text.startswith("[Extraction failed:"):
                raise RuntimeError(
                    f"Window {idx} extraction failed: {summary_text}. Meeting marked failed."
                )

        # 8. Step 3B: Summary Merging & Persistence
        with get_db() as conn:
            merge_and_persist(meeting_id, window_results, conn)
            # Final status update to 'done'
            conn.execute(
                "UPDATE meetings SET status = 'done', error = NULL WHERE id = ?",
                (meeting_id,),
            )

    logger.info("Successfully finished processing pipeline for meeting %s", meeting_id)
