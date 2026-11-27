"""Step 3B – Transcript windowing, per-window note extraction and window persistence.

Transcript segments are split chronologically into token-aware windows.
Each window is processed by extract_chunk_notes() / verify_notes() (Step 3A),
then stored in the existing `windows` table.

The public entry point for Step 4 is:
    process_transcript_windows(meeting_id, segments, conn, client=None) -> list[dict]

Returns the list of validated window-result dicts (one per window).
Does NOT set meeting.status – the caller (worker) controls that.
"""
from __future__ import annotations

import json
import logging
import math
from typing import Any

import httpx

from app.services.llm import LLMUnavailable, count_tokens
from app.services.notes_extractor import extract_chunk_notes

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
# Default context capacity in tokens for the model.  Override via
# LLM_CONTEXT_TOKENS environment variable (read by config.py if added).
_DEFAULT_CONTEXT_TOKENS = 2048

# Tokens reserved for the system prompt, user preamble and expected JSON output.
_PROMPT_RESERVE_TOKENS = 600

# Small overlap: number of segments to repeat at the start of the next window
# so that cross-window references are not lost.
_OVERLAP_SEGMENTS = 2


def _fmt_time(seconds: float) -> str:
    """Format float seconds as [mm:ss] string used in transcript chunks."""
    s = int(seconds)
    return f"[{s // 60:02d}:{s % 60:02d}]"


def _segments_to_text(segments: list[dict[str, Any]]) -> str:
    """Render a list of segment dicts to the [mm:ss] Speaker: text format."""
    lines: list[str] = []
    for seg in segments:
        ts = _fmt_time(float(seg.get("start_time", 0)))
        speaker = seg.get("speaker") or "Unknown Speaker"
        text = str(seg.get("text", "")).strip()
        lines.append(f"{ts} {speaker}: {text}")
    return "\n".join(lines)


def _speaker_names(segments: list[dict[str, Any]]) -> list[str]:
    seen: list[str] = []
    for seg in segments:
        name = seg.get("speaker") or ""
        if name and name not in seen:
            seen.append(name)
    return seen


# ---------------------------------------------------------------------------
# Window splitting
# ---------------------------------------------------------------------------

def split_transcript_windows(
    segments: list[dict[str, Any]],
    token_budget: int | None = None,
    client: httpx.Client | None = None,
) -> list[dict[str, Any]]:
    """Split *segments* into chronological, token-aware windows.

    Parameters
    ----------
    segments:
        List of transcript-segment dicts with at least
        ``start_time``, ``end_time``, ``speaker`` and ``text`` keys.
    token_budget:
        Maximum tokens allowed per window for transcript text.
        Defaults to ``_DEFAULT_CONTEXT_TOKENS - _PROMPT_RESERVE_TOKENS``.
    client:
        Optional shared httpx.Client for llama-server token counting.
        When *None* a short-lived client is created per call.

    Returns
    -------
    list[dict]  – each dict has::

        {
            "window_index": int,          # 0-based
            "start_time":  float,
            "end_time":    float,
            "text":        str,           # formatted chunk text
            "segments":    list[dict],    # raw segment dicts in this window
        }

    All segments are preserved; none are silently discarded.
    """
    if not segments:
        return []

    if token_budget is None:
        token_budget = _DEFAULT_CONTEXT_TOKENS - _PROMPT_RESERVE_TOKENS
    token_budget = max(token_budget, 50)  # sanity floor

    windows: list[dict[str, Any]] = []
    window_segs: list[dict[str, Any]] = []
    window_tokens = 0

    def _flush(segs: list[dict[str, Any]], idx: int) -> dict[str, Any]:
        text = _segments_to_text(segs)
        return {
            "window_index": idx,
            "start_time": float(segs[0].get("start_time", 0)),
            "end_time": float(segs[-1].get("end_time", 0)),
            "text": text,
            "segments": list(segs),
        }

    for seg in segments:
        line = _segments_to_text([seg])
        try:
            line_tokens = count_tokens(line, client=client)
        except (LLMUnavailable, Exception):  # noqa: BLE001
            # Fallback: estimate 1 token ≈ 4 chars
            line_tokens = max(1, math.ceil(len(line) / 4))

        if window_segs and window_tokens + line_tokens > token_budget:
            # Current window is full – flush it
            windows.append(_flush(window_segs, len(windows)))
            # Carry over the last _OVERLAP_SEGMENTS segments to next window
            overlap = window_segs[-_OVERLAP_SEGMENTS:] if _OVERLAP_SEGMENTS else []
            window_segs = list(overlap)
            # Recount overlap tokens (cheap, small)
            window_tokens = sum(
                max(1, math.ceil(len(_segments_to_text([s])) / 4))
                for s in window_segs
            )

        window_segs.append(seg)
        window_tokens += line_tokens

    # Flush remaining segments
    if window_segs:
        windows.append(_flush(window_segs, len(windows)))

    return windows


# ---------------------------------------------------------------------------
# Per-window note extraction + DB persistence
# ---------------------------------------------------------------------------

def _save_window(
    conn: Any,
    meeting_id: str,
    window_index: int,
    start_time: float,
    end_time: float,
    result: dict[str, Any],
) -> None:
    """Upsert one validated window result into the `windows` table."""
    result_json = json.dumps(result)
    existing = conn.execute(
        "SELECT id FROM windows WHERE meeting_id = ? AND window_index = ?",
        (meeting_id, window_index),
    ).fetchone()
    if existing:
        conn.execute(
            "UPDATE windows SET start_time=?, end_time=?, result_json=? "
            "WHERE meeting_id=? AND window_index=?",
            (start_time, end_time, result_json, meeting_id, window_index),
        )
    else:
        conn.execute(
            "INSERT INTO windows (meeting_id, window_index, start_time, end_time, result_json) "
            "VALUES (?, ?, ?, ?, ?)",
            (meeting_id, window_index, start_time, end_time, result_json),
        )


def process_transcript_windows(
    meeting_id: str,
    segments: list[dict[str, Any]],
    conn: Any,
    client: httpx.Client | None = None,
    token_budget: int | None = None,
) -> list[dict[str, Any]]:
    """Split segments into windows, extract notes per window, persist results.

    Parameters
    ----------
    meeting_id:
        UUID of the meeting in the DB.
    segments:
        Ordered transcript segments (from ``transcript_segments`` table).
    conn:
        Open SQLite connection (caller manages transaction).
    client:
        Optional shared httpx.Client for llama-server calls.
    token_budget:
        Max transcript tokens per window (default: context – reserve).

    Returns
    -------
    list[dict] – validated ``ChunkNotes`` dicts, one per window.
    """
    if not segments:
        logger.warning("process_transcript_windows: no segments for meeting %s", meeting_id)
        return []

    windows = split_transcript_windows(segments, token_budget=token_budget, client=client)
    speaker_names = _speaker_names(segments)
    results: list[dict[str, Any]] = []

    for win in windows:
        idx = win["window_index"]

        # Resume support: skip LLM extraction if window is already saved in DB
        existing = conn.execute(
            "SELECT result_json FROM windows WHERE meeting_id = ? AND window_index = ?",
            (meeting_id, idx),
        ).fetchone()
        if existing and existing["result_json"]:
            try:
                saved = json.loads(existing["result_json"])
                if isinstance(saved, dict) and not str(saved.get("summary", "")).startswith("[Extraction failed"):
                    logger.info("Window %d already processed for meeting %s; skipping LLM extraction.", idx, meeting_id)
                    results.append(saved)
                    continue
            except (json.JSONDecodeError, TypeError):
                pass

        logger.info(
            "Processing window %d/%d for meeting %s (%.1f–%.1f s)",
            idx + 1, len(windows), meeting_id, win["start_time"], win["end_time"],
        )
        try:
            notes = extract_chunk_notes(win["text"], speaker_names, client=client)
        except LLMUnavailable:
            raise  # propagate so worker can mark meeting failed
        except Exception as exc:  # noqa: BLE001
            logger.error("Window %d extraction failed: %s", idx, exc)
            # Store a placeholder so the window row is recorded
            notes = {
                "summary": f"[Extraction failed: {exc}]",
                "project_progress": [],
                "challenges": [],
                "action_items": [],
                "next_steps": [],
            }

        _save_window(conn, meeting_id, idx, win["start_time"], win["end_time"], notes)
        results.append(notes)

    return results
