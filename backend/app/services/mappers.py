"""Utility functions to map DB rows (snake_case) to API response models (camelCase).
All mappers return plain Python primitives suitable for FastAPI's response models.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, Optional


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


def map_meeting_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """Map a meeting table row to camelCase dict.
    Handles status mapping for pending -> scheduled and done -> completed.
    Leaves other status values unchanged.
    """
    mapping = {
        "meetingId": str(row.get("meeting_id") or row.get("id")),
        "title": row.get("title"),
        "status": _map_status(row.get("status")),
        "overview": row.get("overview"),
        "projectProgress": row.get("project_progress"),
        "challenges": row.get("challenges"),
        "nextSteps": row.get("next_steps"),
        "createdAt": row.get("created_at"),
        "durationSeconds": row.get("duration_seconds"),
        "processedSeconds": row.get("processed_seconds"),
        "mediaPath": row.get("media_path"),
    }
    return {k: v for k, v in mapping.items() if v is not None}


def map_transcript_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "id": str(r.get("id")),
            "startTime": r.get("start_time"),
            "endTime": r.get("end_time"),
            "speaker": r.get("speaker"),
            "text": r.get("text"),
        }
        for r in rows
    ]


def map_speaker_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "id": str(r.get("id")),
            "name": r.get("name"),
            "color": r.get("color"),
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
        }
        for r in rows
    ]


def map_topic_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "id": str(r.get("id")),
            "name": r.get("name"),
        }
        for r in rows
    ]


def map_analytics_row(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    return {
        "participantCount": row.get("participant_count"),
        "durationSeconds": row.get("duration_seconds"),
        "processedSeconds": row.get("processed_seconds"),
    }


def map_meeting_detail(
    meeting: dict[str, Any],
    transcript: list[dict[str, Any]],
    speakers: list[dict[str, Any]],
    topics: list[dict[str, Any]],
    action_items: list[dict[str, Any]],
    analytics: dict[str, Any] | None = None,
    media_url: str | None = None,
) -> dict[str, Any]:
    def _parse_json(val: Any) -> Any:
        if isinstance(val, str):
            try:
                return json.loads(val)
            except (json.JSONDecodeError, ValueError):
                return val
        return val

    overview = meeting.get("overview")
    project_progress = _parse_json(meeting.get("project_progress"))
    challenges = _parse_json(meeting.get("challenges"))
    next_steps = _parse_json(meeting.get("next_steps"))

    summary = None
    if any(v is not None for v in (overview, project_progress, challenges, next_steps)):
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

    meeting_id = str(meeting.get("id") or meeting.get("meeting_id") or meeting.get("meetingId"))
    created_at = meeting.get("created_at") or meeting.get("createdAt")
    return {
        "id": meeting_id,
        "meetingId": meeting_id,
        "title": meeting.get("title"),
        "status": _map_status(meeting.get("status")),
        "createdAt": created_at,
        "date": _derive_date(created_at),
        "summary": summary,
        "transcript": map_transcript_rows(transcript),
        "speakers": map_speaker_rows(speakers),
        "topics": map_topic_rows(topics),
        "actionItems": map_action_item_rows(action_items),
        "analytics": map_analytics_row(analytics),
        "mediaUrl": media_url,
        "mediaType": meeting.get("media_type") or meeting.get("mediaType"),
        "processedSeconds": meeting.get("processed_seconds") if meeting.get("processed_seconds") is not None else meeting.get("processedSeconds"),
        "durationSeconds": meeting.get("duration_seconds") if meeting.get("duration_seconds") is not None else meeting.get("durationSeconds"),
        "error": meeting.get("error"),
    }
