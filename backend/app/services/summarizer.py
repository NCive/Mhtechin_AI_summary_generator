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

import difflib
import json
import logging
import re
import uuid
from typing import Any

import httpx

from app.services.llm import LLMUnavailable, generate_json

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Schema for overview merge only
# ---------------------------------------------------------------------------

OVERVIEW_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "overview": {
            "type": "string",
            "description": "A cohesive overview paragraph (2-4 sentences) summarizing the entire meeting.",
        },
    },
    "required": ["overview"],
}

# ---------------------------------------------------------------------------
# Plain-code fuzzy deduplication helpers (difflib ratio > 0.85)
# ---------------------------------------------------------------------------

def _normalize_text(s: str) -> str:
    """Lowercase and strip punctuation/whitespace for fuzzy deduplication."""
    lowered = s.lower().strip()
    return re.sub(r"[^\w\s]", "", lowered).strip()


def _is_fuzzy_duplicate(
    candidate_norm: str, existing_norms: list[str], threshold: float = 0.85
) -> bool:
    """Check if candidate_norm is identical or has difflib ratio > threshold with any existing item."""
    if not candidate_norm:
        return True
    for existing in existing_norms:
        if candidate_norm == existing:
            return True
        matcher = difflib.SequenceMatcher(None, candidate_norm, existing)
        if matcher.ratio() > threshold:
            return True
    return False


def _merge_string_lists(window_results: list[dict[str, Any]], key: str) -> list[str]:
    """Merge string lists (project_progress, challenges, next_steps) in window order with fuzzy dedup."""
    merged: list[str] = []
    seen_norms: list[str] = []

    for w in window_results:
        raw_list = w.get(key) or []
        for item in raw_list:
            text = str(item).strip()
            if not text:
                continue
            norm = _normalize_text(text)
            if not _is_fuzzy_duplicate(norm, seen_norms):
                merged.append(text)
                seen_norms.append(norm)

    return merged


def _merge_action_items(window_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge action_items in window order, deduplicating with difflib ratio > 0.85.

    Keeps the first occurrence with its owner, deadline, and source_time.
    """
    merged: list[dict[str, Any]] = []
    seen_norms: list[str] = []

    for w in window_results:
        raw_items = w.get("action_items") or []
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            text = str(item.get("text", "")).strip()
            if not text:
                continue
            norm = _normalize_text(text)
            if not _is_fuzzy_duplicate(norm, seen_norms):
                merged.append({
                    "text": text,
                    "owner": item.get("owner"),
                    "deadline": item.get("deadline"),
                    "source_time": item.get("source_time"),
                })
                seen_norms.append(norm)

    return merged


def _dedup_action_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate action items preserving first occurrence."""
    return _merge_action_items([{"action_items": items}])


def _merge_overview_llm(
    window_results: list[dict[str, Any]],
    client: httpx.Client | None = None,
) -> str:
    """Use llama-server to produce a 2-4 sentence cohesive overview from window summaries."""
    summaries: list[str] = []
    for w in window_results:
        s = str(w.get("summary") or w.get("overview") or "").strip()
        if s and not s.startswith("[Extraction failed"):
            summaries.append(s)

    if not summaries:
        return ""

    joined = "\n\n".join(summaries)
    system_prompt = (
        "You are an executive assistant.\n"
        "Combine the following section summaries from consecutive parts of a single meeting "
        "into one unified, cohesive overview paragraph (2-4 sentences).\n"
        "Never invent new information.\n"
        "Output valid JSON matching the schema."
    )
    user_prompt = (
        f"Section summaries to merge:\n\n{joined}\n\nProduce the merged overview JSON now."
    )

    try:
        raw = generate_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            schema=OVERVIEW_SCHEMA,
            client=client,
        )
        ov = raw.get("overview") or raw.get("summary")
        if ov and str(ov).strip():
            return str(ov).strip()
        return " ".join(summaries)
    except (LLMUnavailable, Exception) as exc:  # noqa: BLE001
        logger.warning(
            "LLM overview merge failed (%s); falling back to concatenated summaries.",
            exc,
        )
        return " ".join(summaries)


def _naive_merge(window_results: list[dict[str, Any]]) -> dict[str, Any]:
    """Fast local merge without LLM: concatenate summaries, deduplicate lists and action items."""
    summaries: list[str] = []
    for w in window_results:
        s = str(w.get("summary") or w.get("overview") or "").strip()
        if s and not s.startswith("[Extraction failed"):
            summaries.append(s)

    ov = " ".join(summaries)
    return {
        "summary": ov,
        "overview": ov,
        "project_progress": _merge_string_lists(window_results, "project_progress"),
        "challenges": _merge_string_lists(window_results, "challenges"),
        "action_items": _merge_action_items(window_results),
        "next_steps": _merge_string_lists(window_results, "next_steps"),
    }


# ---------------------------------------------------------------------------
# DB persistence helpers
# ---------------------------------------------------------------------------

def _persist_summary(conn: Any, meeting_id: str, merged: dict[str, Any]) -> None:
    """Write merged summary fields to the meetings row."""
    overview = str(merged.get("overview") or merged.get("summary") or "").strip() or None
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
        Optional shared httpx.Client.

    Returns
    -------
    dict – the merged summary dict with keys:
        ``summary``, ``overview``, ``project_progress``, ``challenges``,
        ``action_items``, ``next_steps``.
    """
    if not window_results:
        logger.warning("merge_and_persist: no window results for meeting %s", meeting_id)
        return {
            "summary": None,
            "overview": None,
            "project_progress": [],
            "challenges": [],
            "action_items": [],
            "next_steps": [],
        }

    # 1. Single window shortcut: no LLM merge needed
    if len(window_results) == 1:
        merged = dict(window_results[0])
        ov = merged.get("overview") or merged.get("summary")
        merged["overview"] = ov
        merged["summary"] = ov
    else:
        # 2. Multi-window merge: plain code for lists/items, LLM for overview
        progress = _merge_string_lists(window_results, "project_progress")
        challenges = _merge_string_lists(window_results, "challenges")
        next_steps = _merge_string_lists(window_results, "next_steps")
        action_items = _merge_action_items(window_results)

        overview = _merge_overview_llm(window_results, client=client)

        merged = {
            "summary": overview,
            "overview": overview,
            "project_progress": progress,
            "challenges": challenges,
            "action_items": action_items,
            "next_steps": next_steps,
        }

    _persist_summary(conn, meeting_id, merged)
    _persist_action_items(conn, meeting_id, merged.get("action_items") or [])

    return merged
