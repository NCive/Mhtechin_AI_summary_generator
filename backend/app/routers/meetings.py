import logging

logger = logging.getLogger(__name__)
from fastapi import APIRouter, Depends, HTTPException, status, File, Form, UploadFile, WebSocket, WebSocketDisconnect

from typing import List, Optional

from app.core.config import settings
from app.db.database import get_db
from app.services.live_stream import live_session_manager

from app.schemas.meeting import (
    ActionItemResponse,
    JoinMeetingRequest,
    MeetingDetailResponse,
    MeetingListItem,
    UpdateActionItemRequest,
    UploadMeetingResponse,
)
from app.services.meeting_service import (
    get_media_path,
    get_meeting_detail,
    join_meeting,
    list_meetings,
    update_action_item,
    upload_meeting,
)
from fastapi.responses import FileResponse
from starlette.datastructures import MutableHeaders
from starlette.types import Message, Receive, Scope, Send

MEDIA_TYPE_MAP = {
    ".mp4": "video/mp4",
    ".webm": "video/webm",
    ".mkv": "video/x-matroska",
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".m4a": "audio/mp4",
}


class MediaFileResponse(FileResponse):
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(raw=message["headers"])
                headers.setdefault("accept-ranges", "bytes")
            await send(message)

        await super().__call__(scope, receive, send_wrapper)

router = APIRouter(prefix="/meetings", tags=["meetings"])

@router.post("/join", response_model=UploadMeetingResponse)
def api_join_meeting(req: JoinMeetingRequest):
    result = join_meeting(req.meetingUrl, req.language, req.slotName)
    return result

@router.post("/upload", response_model=UploadMeetingResponse)
def api_upload_meeting(
    file: UploadFile = File(...),
    language: str = Form(...),
    slot_name: str | None = Form(None, alias="slot_name"),
    slotName: str | None = Form(None, alias="slotName"),
):
    slot = slot_name or slotName
    if not slot:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Field 'slot_name' or 'slotName' is required",
        )
    return upload_meeting(file, language, slot)


@router.get("", response_model=List[MeetingListItem])
def api_list_meetings(limit: int = 50, offset: int = 0, q: Optional[str] = None):
    return list_meetings(limit=limit, offset=offset, q=q)

@router.get("/{meeting_id}", response_model=MeetingDetailResponse)
def api_get_meeting(meeting_id: str):
    return get_meeting_detail(meeting_id)

@router.patch("/{meeting_id}/action-items/{item_id}", response_model=ActionItemResponse)
def api_update_action_item(
    meeting_id: str,
    item_id: str,
    req: UpdateActionItemRequest,
):
    return update_action_item(meeting_id, item_id, req.done)

@router.get("/{meeting_id}/media")
def api_get_media(meeting_id: str):
    path = get_media_path(meeting_id)
    ext = path.suffix.lower()
    media_type = MEDIA_TYPE_MAP.get(ext, "application/octet-stream")
    return MediaFileResponse(
        path,
        media_type=media_type,
        filename=path.name,
        content_disposition_type="inline",
    )


@router.websocket("/{meeting_id}/stream")
async def api_meeting_stream(websocket: WebSocket, meeting_id: str):
    # 1. Require shared secret BOT_INGEST_TOKEN via query param or header
    token = websocket.query_params.get("token")
    if not token:
        token = websocket.headers.get("x-bot-token")
    if not token:
        auth_header = websocket.headers.get("authorization", "")
        if auth_header.lower().startswith("bearer "):
            token = auth_header[7:].strip()
        elif auth_header:
            token = auth_header.strip()

    server_token = settings.BOT_INGEST_TOKEN.strip() if settings.BOT_INGEST_TOKEN else ""
    if not server_token or server_token == "change-me" or not token or token != server_token:
        await websocket.close(code=1008)
        return

    # 2. Only accept meetings with source='join'
    with get_db() as conn:
        row = conn.execute(
            "SELECT id, source, status, language FROM meetings WHERE id = ?",
            (meeting_id,),
        ).fetchone()

    if not row or row["source"] != "join":
        await websocket.close(code=1008)
        return

    # 3. Accept connection and mark status='processing'
    await websocket.accept()
    with get_db() as conn:
        conn.execute(
            "UPDATE meetings SET status = 'processing', error = NULL WHERE id = ?",
            (meeting_id,),
        )

    session = live_session_manager.get_or_create(meeting_id, language=row["language"])
    session.on_connected()

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "chunk":
                speaker_id = data.get("speaker_id")
                speaker_name = data.get("speaker_name")
                start_ms = int(data.get("start_ms", 0))

                # Expected binary PCM16 frame follows
                pcm_bytes = await websocket.receive_bytes()
                await session.handle_audio_chunk(
                    speaker_id=str(speaker_id) if speaker_id is not None else "unknown",
                    speaker_name=speaker_name,
                    start_ms=start_ms,
                    pcm_bytes=pcm_bytes,
                )
            elif msg_type == "end":
                try:
                    await session.finalize()
                finally:
                    await websocket.close(code=1000)
                break
            else:
                logger.warning("Unknown message type on live stream for meeting %s: %s", meeting_id, msg_type)
    except WebSocketDisconnect:
        session.on_disconnected()
    except Exception:
        logger.exception("Exception in WebSocket stream for meeting %s", meeting_id)
        session.on_disconnected()

