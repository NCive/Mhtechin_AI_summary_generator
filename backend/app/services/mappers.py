"""Utility functions to map DB rows (snake_case) to API response models (camelCase).
All mappers return plain Python primitives suitable for FastAPI's response models.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any


def _derive_date(created_at: str | None) -> str | None:
    if not created_at:
        return None
    try:
        clean = created_at.replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean)
        return dt.strftime("%b %d, %Y")
    except (ValueError, TypeError, OverflowError):
        try:
            dt = datetime.strptime(created_at[:19], "%Y-%m-%d %H:%M:%S")
            return dt.strftime("%b %d, %Y")
        except (ValueError, TypeError, OverflowError):
            return None


def _map_status(status: str | None) -> str | None:
    """Map DB status to API response status.
    pending -> scheduled
    done -> completed
    processing and failed remain unchanged.
    """
    if status == "pending":
        return "scheduled"
    if status == "done":
        return "completed"
    return status


def map_join_upload_response(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "meetingId": str(row.get("id") or row.get("meeting_id") or row.get("meetingId")),
        "status": _map_status(row.get("status")),
    }


def map_meeting_list_item(row: dict[str, Any]) -> dict[str, Any]:
    meeting_id = str(row.get("id") or row.get("meeting_id") or row.get("meetingId"))
    created_at = row.get("created_at") or row.get("createdAt")
    return {
        "id": meeting_id,
        "meetingId": meeting_id,
        "title": row.get("title"),
        "overview": row.get("overview"),
        "createdAt": created_at,
        "date": _derive_date(created_at),
        "status": _map_status(row.get("status")),
    }


def map_transcript_rows(
    rows: list[dict[str, Any]],
    speaker_colors: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    colors = speaker_colors or {}
    result = []
    for r in rows:
        stored_speaker = r.get("speaker")
        if stored_speaker and str(stored_speaker).strip():
            name = str(stored_speaker).strip()
            color = colors.get(name.lower())
        else:
            name = "Unknown speaker"
            color = None

        result.append({
            "id": str(r.get("id")),
            "timestampStart": float(r.get("start_time", 0.0)) if r.get("start_time") is not None else None,
            "timestampEnd": float(r.get("end_time", 0.0)) if r.get("end_time") is not None else None,
            "speakerName": name,
            "speakerColor": color,
            "text": str(r.get("text", "")),
        })
    return result


def map_speaker_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "id": str(r.get("id")),
            "name": r.get("name"),
            "color": r.get("color"),
            "role": r.get("role") or "",
            "avatar": r.get("avatar"),
            "talkDurationSeconds": r.get("talk_seconds"),
            "talkPercentage": r.get("talk_percent"),
            "listenPercentage": r.get("listen_percent"),
            "talkSeconds": r.get("talk_seconds"),
            "talkPercent": r.get("talk_percent"),
            "listenPercent": r.get("listen_percent"),
            "speakingTime": r.get("talk_seconds"),
        }
        for r in rows
    ]


def map_action_item_response(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(row.get("id")),
        "task": row.get("text") or row.get("task") or "",
        "assignee": row.get("owner") or row.get("assignee"),
        "dueDate": row.get("deadline") or row.get("dueDate"),
        "done": bool(row.get("done")),
    }


def map_action_item_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "id": str(r.get("id")),
            "task": r.get("text") or r.get("task") or "",
            "description": r.get("text") or r.get("description"),
            "assignee": r.get("owner") or r.get("assignee"),
            "dueDate": r.get("deadline") or r.get("dueDate"),
            "done": bool(r.get("done")),
            "completed": bool(r.get("done")),
        }
        for r in rows
    ]


def map_meeting_detail(
    meeting: dict[str, Any],
    transcript: list[dict[str, Any]],
    speakers: list[dict[str, Any]],
    action_items: list[dict[str, Any]],
    media_url: str | None = None,
) -> dict[str, Any]:
    def _parse_json(val: Any) -> Any:
        if isinstance(val, str):
            try:
                return json.loads(val)
            except (json.JSONDecodeError, ValueError):
                return val
        return val

    # Build speaker color dictionary (case-insensitive name -> color)
    speaker_colors: dict[str, str] = {}
    for spk in speakers:
        spk_name = spk.get("name")
        spk_color = spk.get("color")
        if spk_name and spk_color:
            speaker_colors[str(spk_name).strip().lower()] = str(spk_color).strip()

    overview = meeting.get("overview")
    project_progress = _parse_json(meeting.get("project_progress"))
    challenges = _parse_json(meeting.get("challenges"))
    next_steps = _parse_json(meeting.get("next_steps"))

    mapped_actions = map_action_item_rows(action_items)

    summary = None
    if any(v is not None for v in (overview, project_progress, challenges, next_steps)) or mapped_actions:
        summary = {}
        if overview is not None:
            summary["overview"] = overview
        if project_progress is not None:
            summary["projectProgress"] = project_progress
        if challenges is not None:
            summary["challenges"] = challenges
            summary["challengesFaced"] = challenges
        if next_steps is not None:
            summary["nextSteps"] = next_steps
        if mapped_actions:
            summary["actionItems"] = mapped_actions

    meeting_id = str(meeting.get("id") or meeting.get("meeting_id") or meeting.get("meetingId"))
    created_at = meeting.get("created_at") or meeting.get("createdAt")
    return {
        "id": meeting_id,
        "meetingId": meeting_id,
        "title": meeting.get("title"),
        "folder": meeting.get("folder") or "",
        "slotName": meeting.get("slot_name") or "",
        "status": _map_status(meeting.get("status")),
        "language": meeting.get("language") or "en",
        "meetingUrl": meeting.get("source_url"),
        "createdAt": created_at,
        "date": _derive_date(created_at),
        "summary": summary,
        "transcript": map_transcript_rows(transcript, speaker_colors=speaker_colors),
        "speakers": map_speaker_rows(speakers),
        "actionItems": mapped_actions,
        "mediaUrl": media_url,
        "mediaType": meeting.get("media_type") or meeting.get("mediaType"),
        "processedSeconds": meeting.get("processed_seconds") if meeting.get("processed_seconds") is not None else meeting.get("processedSeconds"),
        "durationSeconds": meeting.get("duration_seconds") if meeting.get("duration_seconds") is not None else meeting.get("durationSeconds"),
        "participantsCount": len(speakers),
        "error": meeting.get("error"),
    }
