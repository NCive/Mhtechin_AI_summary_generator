"""Step 3B – Summary merging and final DB persistence.

Takes the list of validated per-window ChunkNotes dicts produced by
``process_transcript_windows`` and merges them into one structured summary
which is then persisted to the ``meetings`` and ``action_items`` tables.

The public entry point for Step 4 is::

    merge_and_persist(meeting_id, window_results, conn, client=None) -> dict

Returns the merged summary dict (not a full meeting row).
Does NOT set meeting.status – the caller (worker) controls that.
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import Any

import httpx

from app.services.llm import LLMUnavailable, generate_json
from app.services.notes_extractor import CHUNK_NOTES_SCHEMA, SYSTEM_PROMPT, verify_notes

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Merge helpers
# ---------------------------------------------------------------------------

def _dedup_strings(items: list[str]) -> list[str]:
    """Remove exact-duplicate strings, preserving order."""
    seen: set[str] = set()
    out: list[str] = []
    for s in items:
        norm = s.strip()
        if norm and norm not in seen:
            seen.add(norm)
            out.append(norm)
    return out


def _dedup_action_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Remove duplicate action items by normalised text, preserving first occurrence."""
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for item in items:
        key = str(item.get("text", "")).strip().lower()
        if key and key not in seen:
            seen.add(key)
            out.append(item)
    return out


def _naive_merge(window_results: list[dict[str, Any]]) -> dict[str, Any]:
    """Fast local merge: concatenate lists, deduplicate, combine summaries."""
    summaries: list[str] = []
    progress: list[str] = []
    challenges: list[str] = []
    action_items: list[dict[str, Any]] = []
    next_steps: list[str] = []

    for w in window_results:
        s = str(w.get("summary", "")).strip()
        if s and not s.startswith("[Extraction failed"):
            summaries.append(s)
        progress.extend(w.get("project_progress") or [])
        challenges.extend(w.get("challenges") or [])
        for ai in w.get("action_items") or []:
            if isinstance(ai, dict):
                action_items.append(ai)
        next_steps.extend(w.get("next_steps") or [])

    return {
        "summary": " ".join(summaries),
        "project_progress": _dedup_strings(progress),
        "challenges": _dedup_strings(challenges),
        "action_items": _dedup_action_items(action_items),
        "next_steps": _dedup_strings(next_steps),
    }


def _llm_merge(
    window_results: list[dict[str, Any]],
    client: httpx.Client | None,
) -> dict[str, Any]:
    """Use llama-server to produce a coherent merged summary."""
    combined_text = "\n\n---\n\n".join(
        json.dumps(w, indent=2)
        for w in window_results
        if not str(w.get("summary", "")).startswith("[Extraction failed")
    )
    if not combined_text.strip():
        return _naive_merge(window_results)

    merge_system = (
        "You are a strict meeting notes consolidator.\n"
        "You receive JSON notes from multiple consecutive transcript windows of the SAME meeting.\n"
        "Merge them into one coherent, deduplicated set of notes.\n"
        "Rules:\n"
        "1. Remove duplicate points; keep the most informative phrasing.\n"
        "2. Never invent new information.\n"
        "3. Never convert planned work into completed progress.\n"
        "4. Keep action_item source_time values exactly as given.\n"
        "5. If owner, deadline or source_time are null in all windows, keep null.\n"
        "6. Produce a 2-4 sentence plain-text 'summary' field.\n"
        "7. Output only valid JSON matching the schema; no extra keys.\n"
    )
    user_prompt = (
        f"Window notes to merge:\n{combined_text}\n\n"
        "Produce the merged JSON now."
    )
    try:
        raw = generate_json(
            system_prompt=merge_system,
            user_prompt=user_prompt,
            schema=CHUNK_NOTES_SCHEMA,
            client=client,
        )
        # Verify produces clean output but we have no single chunk to validate
        # evidence against, so pass empty text (evidence already verified per window).
        all_speakers: list[str] = []
        for w in window_results:
            for ai in w.get("action_items") or []:
                if isinstance(ai, dict) and ai.get("owner"):
                    name = ai["owner"]
                    if name and name not in all_speakers:
                        all_speakers.append(name)
        verified = verify_notes(raw, "", all_speakers)
        return verified
    except (LLMUnavailable, Exception) as exc:
        logger.warning("LLM merge failed (%s); falling back to naive merge.", exc)
        return _naive_merge(window_results)


# ---------------------------------------------------------------------------
# DB persistence helpers
# ---------------------------------------------------------------------------

def _persist_summary(conn: Any, meeting_id: str, merged: dict[str, Any]) -> None:
    """Write merged summary fields to the meetings row."""
    overview = str(merged.get("summary", "")).strip() or None
    progress = merged.get("project_progress") or []
    challenges = merged.get("challenges") or []
    next_steps = merged.get("next_steps") or []

    conn.execute(
        """UPDATE meetings
           SET overview=?, project_progress=?, challenges=?, next_steps=?
           WHERE id=?""",
        (
            overview,
            json.dumps(progress),
            json.dumps(challenges),
            json.dumps(next_steps),
            meeting_id,
        ),
    )


def _persist_action_items(
    conn: Any, meeting_id: str, action_items: list[dict[str, Any]]
) -> None:
    """Upsert action items; preserve existing IDs and done states for matching text."""
    # Deduplicate by normalised text before writing (handles duplicate-laden single windows)
    action_items = _dedup_action_items(action_items)
    # Load existing items to match by normalised text
    existing_rows = conn.execute(
        "SELECT id, text, done FROM action_items WHERE meeting_id=?",
        (meeting_id,),
    ).fetchall()
    existing_by_text: dict[str, dict[str, Any]] = {
        str(r["text"]).strip().lower(): {"id": r["id"], "done": r["done"]}
        for r in existing_rows
    }

    # Track IDs we are keeping (to delete orphans later)
    kept_ids: set[str] = set()

    for item in action_items:
        text = str(item.get("text", "")).strip()
        if not text:
            continue
        key = text.lower()
        owner = item.get("owner")
        deadline = item.get("deadline")

        if key in existing_by_text:
            # Preserve existing ID and done state; update owner/deadline
            existing = existing_by_text[key]
            item_id = existing["id"]
            done = existing["done"]
            conn.execute(
                "UPDATE action_items SET owner=?, deadline=? WHERE id=? AND meeting_id=?",
                (owner, deadline, item_id, meeting_id),
            )
        else:
            item_id = str(uuid.uuid4())
            done = 0
            conn.execute(
                "INSERT INTO action_items (id, meeting_id, text, owner, deadline, done) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (item_id, meeting_id, text, owner, deadline, done),
            )
        kept_ids.add(item_id)

    # Remove action items from previous processing runs that are no longer present
    if existing_rows:
        for r in existing_rows:
            if r["id"] not in kept_ids:
                conn.execute(
                    "DELETE FROM action_items WHERE id=? AND meeting_id=?",
                    (r["id"], meeting_id),
                )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def merge_and_persist(
    meeting_id: str,
    window_results: list[dict[str, Any]],
    conn: Any,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """Merge per-window notes and persist the final summary to SQLite.

    Parameters
    ----------
    meeting_id:
        UUID of the meeting.
    window_results:
        List of validated ``ChunkNotes`` dicts from ``process_transcript_windows``.
    conn:
        Open SQLite connection (caller manages transaction).
    client:
        Optional shared httpx.Client.  When provided and llama-server is
        available, the LLM is used for a coherent merge; otherwise a simple
        local concatenation/dedup is used.

    Returns
    -------
    dict – the merged summary dict with keys:
        ``summary``, ``project_progress``, ``challenges``,
        ``action_items``, ``next_steps``.
    """
    if not window_results:
        logger.warning("merge_and_persist: no window results for meeting %s", meeting_id)
        return {
            "summary": None,
            "project_progress": [],
            "challenges": [],
            "action_items": [],
            "next_steps": [],
        }

    # Try LLM merge when multiple windows; fall back gracefully
    if len(window_results) == 1:
        merged = dict(window_results[0])
    else:
        try:
            merged = _llm_merge(window_results, client=client)
        except Exception as exc:
            logger.warning("merge failed (%s); using naive merge", exc)
            merged = _naive_merge(window_results)

    _persist_summary(conn, meeting_id, merged)
    _persist_action_items(conn, meeting_id, merged.get("action_items") or [])

    return merged
