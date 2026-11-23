from datetime import UTC, datetime
import mimetypes
import os
from pathlib import Path
from typing import List, Optional
from urllib.parse import urlparse
import uuid

from fastapi import HTTPException, UploadFile, status
from pydantic import BaseModel

from app.core.config import settings
from app.db.database import get_db
from app.services.mappers import (
    map_action_item_response,
    map_join_upload_response,
    map_meeting_detail,
    map_meeting_list_item,
)

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

def _validate_meeting_url(url: str):
    """Validate that URL uses https and host is allowed."""
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
    now_iso = datetime.now(UTC).isoformat()
    with get_db() as conn:
        try:
            conn.execute(
                """
                INSERT INTO meetings (id, source, source_url, language, slot_name, status, created_at)
                VALUES (?, 'join', ?, ?, ?, 'pending', ?)
                """,
                (meeting_id, meeting_url, language, slot_name, now_iso),
            )
            row = conn.execute("SELECT id, status FROM meetings WHERE id = ?", (meeting_id,)).fetchone()
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    return map_join_upload_response(dict(row))

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
    now_iso = datetime.now(UTC).isoformat()
    with get_db() as conn:
        try:
            conn.execute(
                """
                INSERT INTO meetings (id, source, media_path, media_type, language, slot_name, title, status, created_at)
                VALUES (?, 'upload', ?, ?, ?, ?, ?, 'pending', ?)
                """,
                (meeting_id, str(saved_path), media_type, language, slot_name, title, now_iso),
            )
            row = conn.execute("SELECT id, status FROM meetings WHERE id = ?", (meeting_id,)).fetchone()
        except Exception as e:
            # Rollback file creation
            if saved_path.exists():
                saved_path.unlink()
            meeting_dir = saved_path.parent
            if meeting_dir.exists():
                meeting_dir.rmdir()
            raise HTTPException(status_code=500, detail=str(e))
    return map_join_upload_response(dict(row))

def list_meetings(limit: int = 50, offset: int = 0, q: Optional[str] = None) -> List[dict]:
    """Return a paginated list of meetings.
    The returned dicts match the ``MeetingListItem`` schema:
    ``meetingId``, ``title``, ``overview``, ``createdAt``, ``status``.
    """
    with get_db() as conn:
        base_sql = "SELECT id, title, overview, created_at, status FROM meetings"
        params: List = []
        if q:
            base_sql += (
                " WHERE title LIKE ? OR overview LIKE ? "
                "OR id IN (SELECT meeting_id FROM transcript_segments WHERE text LIKE ?)"
            )
            like_pattern = f"%{q}%"
            params.extend([like_pattern, like_pattern, like_pattern])
        base_sql += " ORDER BY created_at DESC, rowid DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        rows = conn.execute(base_sql, params).fetchall()
        return [map_meeting_list_item(dict(row)) for row in rows]

def get_meeting_detail(meeting_id: str) -> dict:
    """Fetch detailed meeting information.
    Uses the correct primary key column and existing tables.
    Returns empty collections when optional data is absent.
    """
    with get_db() as conn:
        meeting_row = conn.execute(
            "SELECT * FROM meetings WHERE id = ?",
            (meeting_id,)
        ).fetchone()
        if not meeting_row:
            raise HTTPException(status_code=404, detail="Meeting not found")

        transcript_rows = conn.execute(
            "SELECT * FROM transcript_segments WHERE meeting_id = ? ORDER BY start_time",
            (meeting_id,)
        ).fetchall()

        speaker_rows = conn.execute(
            "SELECT * FROM speakers WHERE meeting_id = ?",
            (meeting_id,)
        ).fetchall()

        action_rows = conn.execute(
            "SELECT * FROM action_items WHERE meeting_id = ?",
            (meeting_id,)
        ).fetchall()

        media_url = f"/api/v1/meetings/{meeting_id}/media" if meeting_row["media_path"] else None

        return map_meeting_detail(
            meeting=dict(meeting_row),
            transcript=[dict(r) for r in transcript_rows],
            speakers=[dict(r) for r in speaker_rows],
            action_items=[dict(r) for r in action_rows],
            media_url=media_url,
        )

def update_action_item(meeting_id: str, item_id: str, done: bool) -> dict:
    with get_db() as conn:
        meeting = conn.execute("SELECT id FROM meetings WHERE id = ?", (meeting_id,)).fetchone()
        if not meeting:
            raise HTTPException(status_code=404, detail="Meeting not found")

        item = conn.execute("SELECT * FROM action_items WHERE id = ?", (item_id,)).fetchone()
        if not item:
            raise HTTPException(status_code=404, detail="Action item not found")
        if item["meeting_id"] != meeting_id:
            raise HTTPException(status_code=404, detail="Action item belongs to a different meeting")

        done_int = 1 if done else 0
        conn.execute(
            "UPDATE action_items SET done = ? WHERE id = ? AND meeting_id = ?",
            (done_int, item_id, meeting_id),
        )
        updated = conn.execute(
            "SELECT * FROM action_items WHERE id = ? AND meeting_id = ?",
            (item_id, meeting_id),
        ).fetchone()

        return map_action_item_response(dict(updated))

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
