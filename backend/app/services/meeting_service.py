import os
import uuid
import mimetypes
from pathlib import Path
from typing import List, Optional

from fastapi import UploadFile, HTTPException, status
from pydantic import BaseModel

from app.core.config import settings
from app.db.database import get_db

# Helper functions
def _media_category(mime_type: Optional[str]) -> str:
    """Convert a full MIME type like "video/mp4" to the category used in the DB.
    Returns "video" or "audio". Raises HTTPException for unsupported types.
    """
    if not mime_type:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unable to determine media type")
    if mime_type.startswith('video/'):
        return 'video'
    if mime_type.startswith('audio/'):
        return 'audio'
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Unsupported media type')

    """Validate that URL uses https and host is allowed."""
    from urllib.parse import urlparse
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="URL must use https.")
    allowed_hosts = [
        "meet.google.com",
        "zoom.us",
        "teams.microsoft.com",
        "teams.live.com",
    ]
    # allow subdomains of zoom.us
    host = parsed.hostname or ""
    if host in allowed_hosts or host.endswith('.zoom.us'):
        return
    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Host not allowed.")

def _allowed_extension(filename: str) -> bool:
    allowed = {".mp3", ".wav", ".m4a", ".mp4", ".mkv", ".webm"}
    return Path(filename).suffix.lower() in allowed

def _save_upload_file(file: UploadFile, meeting_id: str) -> Path:
    # Ensure media directory exists
    meeting_dir = Path(settings.MEDIA_DIR) / meeting_id
    meeting_dir.mkdir(parents=True, exist_ok=True)
    # Use safe filename: meeting_id/original.<ext>
    ext = Path(file.filename).suffix.lower()
    dest_path = meeting_dir / f"original{ext}"
    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    written = 0
    try:
        with dest_path.open("xb") as out_file:
            while True:
                chunk = file.file.read(1024 * 1024)  # 1 MB
                if not chunk:
                    break
                written += len(chunk)
                if written > max_bytes:
                    raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Upload exceeds size limit.")
                out_file.write(chunk)
    finally:
        file.file.close()
    return dest_path

def join_meeting(meeting_url: str, language: str, slot_name: str) -> dict:
    _validate_meeting_url(meeting_url)
    meeting_id = str(uuid.uuid4())
    with get_db() as conn:
        try:
            conn.execute(
                """
                INSERT INTO meetings (id, source, source_url, language, slot_name, status)
                VALUES (?, 'join', ?, ?, ?, 'pending')
                """,
                (meeting_id, meeting_url, language, slot_name),
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    return {"meetingId": meeting_id, "status": "scheduled"}

def upload_meeting(file: UploadFile, language: str, slot_name: str) -> dict:
    if not _allowed_extension(file.filename):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="File type not allowed.")
    meeting_id = str(uuid.uuid4())
    # Save file safely
    try:
        saved_path = _save_upload_file(file, meeting_id)
    except HTTPException:
        # Cleanup any partial file
        partial_dir = Path(settings.MEDIA_DIR) / meeting_id
        if partial_dir.exists():
            for p in partial_dir.iterdir():
                p.unlink()
            partial_dir.rmdir()
        raise
    media_type_full, _ = mimetypes.guess_type(str(saved_path))
    media_type = _media_category(media_type_full)

    # Derive a title from the uploaded filename (without extension)
    title = Path(file.filename).stem
    with get_db() as conn:
        try:
            conn.execute(
                """
                INSERT INTO meetings (id, source, media_path, media_type, language, slot_name, title, status)
                VALUES (?, 'upload', ?, ?, ?, ?, ?, 'pending')
                """,
                (meeting_id, str(saved_path), media_type, language, slot_name, title),
            )
        except Exception as e:
            # Rollback file creation
            if saved_path.exists():
                saved_path.unlink()
            meeting_dir = saved_path.parent
            if meeting_dir.exists():
                meeting_dir.rmdir()
            raise HTTPException(status_code=500, detail=str(e))
    return {"meetingId": meeting_id, "status": "scheduled"}

def list_meetings(limit: int = 50, offset: int = 0, q: Optional[str] = None) -> List[dict]:
    """Return a paginated list of meetings.
    The returned dicts match the ``MeetingListItem`` schema:
    ``meetingId``, ``title``, ``overview``, ``createdAt``, ``status``.
    """
    with get_db() as conn:
        # Select columns with names that match the Pydantic schema keys.
        base_sql = (
            "SELECT id AS meetingId, title, overview, created_at AS createdAt, status "
            "FROM meetings"
        )
        params: List = []
        if q:
            # Simple text search on title/overview. Using LIKE avoids complex FTS joins.
            # The query is case‑insensitive by default in SQLite.
            base_sql += " WHERE title LIKE ? OR overview LIKE ?"
            like_pattern = f"%{q}%"
            params.extend([like_pattern, like_pattern])
        # Apply ordering and pagination.
        base_sql += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        rows = conn.execute(base_sql, params).fetchall()
        # ``sqlite3.Row`` behaves like a dict; convert each row to a plain dict.
        return [dict(row) for row in rows]

def get_meeting_detail(meeting_id: str) -> dict:
    """Fetch detailed meeting information.
    Uses the correct primary key column and existing tables.
    Returns empty collections when optional data is absent.
    """
    with get_db() as conn:
        # Core meeting record – primary key column is ``id``
        meeting_row = conn.execute(
            "SELECT * FROM meetings WHERE id = ?",
            (meeting_id,)
        ).fetchone()
        if not meeting_row:
            raise HTTPException(status_code=404, detail="Meeting not found")
        # Convert sqlite row to dict for easy .get() access
        meeting = dict(meeting_row)

        # Summary fields are stored directly in the meetings table.
        summary_fields = ["overview", "project_progress", "challenges", "next_steps"]
        summary = {field: meeting.get(field) for field in summary_fields if meeting.get(field) is not None}
        summary = summary or None

        # Transcript segments (ordered by start_time)
        transcript_rows = conn.execute(
            "SELECT * FROM transcript_segments WHERE meeting_id = ? ORDER BY start_time",
            (meeting_id,)
        ).fetchall()
        transcript = [dict(r) for r in transcript_rows] if transcript_rows else []

        # Speakers
        speaker_rows = conn.execute(
            "SELECT * FROM speakers WHERE meeting_id = ?",
            (meeting_id,)
        ).fetchall()
        speakers = [dict(r) for r in speaker_rows] if speaker_rows else []

        # Topics – optional table; return empty list if missing.
        try:
            topic_rows = conn.execute(
                "SELECT * FROM topics WHERE meeting_id = ?",
                (meeting_id,)
            ).fetchall()
            topics = [dict(r) for r in topic_rows] if topic_rows else []
        except Exception:
            topics = []

        # Action items
        action_rows = conn.execute(
            "SELECT * FROM action_items WHERE meeting_id = ?",
            (meeting_id,)
        ).fetchall()
        action_items = [dict(r) for r in action_rows] if action_rows else []

        # Analytics – optional table.
        try:
            analytics_row = conn.execute(
                "SELECT * FROM analytics WHERE meeting_id = ?",
                (meeting_id,)
            ).fetchone()
            analytics = dict(analytics_row) if analytics_row else None
        except Exception:
            analytics = None

        response = {
            "meetingId": meeting["id"],
            "title": meeting.get("title"),
            "status": meeting.get("status"),
            "summary": summary,
            "transcript": transcript,
            "speakers": speakers,
            "topics": topics,
            "actionItems": action_items,
            "analytics": analytics,
            "mediaUrl": None,
        }
        if meeting.get("media_path"):
            response["mediaUrl"] = f"/api/v1/media/{meeting_id}"
        return response

def get_media_path(meeting_id: str) -> Path:
    with get_db() as conn:
        row = conn.execute(
            "SELECT media_path FROM meetings WHERE id = ?",
            (meeting_id,)
        ).fetchone()
        if not row or not row["media_path"]:
            raise HTTPException(status_code=404, detail="Media not found for meeting")
        path = Path(row["media_path"])
        # Prevent path traversal: ensure resolved path is within MEDIA_DIR
        media_root = Path(settings.MEDIA_DIR).resolve()
        if not path.resolve().is_relative_to(media_root):
            raise HTTPException(status_code=403, detail="Invalid media path")
        if not path.is_file():
            raise HTTPException(status_code=404, detail="Media file missing")
        return path
