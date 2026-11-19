"""Utility functions to map DB rows (snake_case) to API response models (camelCase).
All mappers return plain Python primitives suitable for FastAPI's response models.
"""
from typing import List, Dict, Any, Optional


def map_meeting_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """Map a meeting table row to camelCase dict.
    Handles status mapping for pending → scheduled and done → completed.
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
    # Remove keys with None to keep response clean (Pydantic will treat as optional)
    return {k: v for k, v in mapping.items() if v is not None}


def _map_status(status: Optional[str]) -> Optional[str]:
    if status == "pending":
        return "scheduled"
    if status == "done":
        return "completed"
    return status


def map_transcript_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        {
            "segmentId": str(r.get("id")),
            "startTime": r.get("start_time"),
            "endTime": r.get("end_time"),
            "speaker": r.get("speaker"),
            "text": r.get("text"),
        }
        for r in rows
    ]


def map_speaker_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        {
            "speakerId": str(r.get("id")),
            "name": r.get("name"),
            "color": r.get("color"),
            "talkSeconds": r.get("talk_seconds"),
            "talkPercent": r.get("talk_percent"),
            "listenPercent": r.get("listen_percent"),
        }
        for r in rows
    ]


def map_action_item_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        {
            "actionItemId": str(r.get("id")),
            "description": r.get("text"),
            "owner": r.get("owner"),
            "deadline": r.get("deadline"),
            "done": bool(r.get("done")),
        }
        for r in rows
    ]


def map_topic_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        {
            "topicId": str(r.get("id")),
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
