import hmac
import json
import logging

from fastapi import (
    APIRouter,
    File,
    Form,
    HTTPException,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.responses import FileResponse
from starlette.datastructures import MutableHeaders
from starlette.types import Message, Receive, Scope, Send

from app.core.config import settings
from app.db.database import get_db
from app.schemas.meeting import (
    ActionItemResponse,
    JoinMeetingRequest,
    MeetingDetailResponse,
    MeetingListItem,
    UpdateActionItemRequest,
    UploadMeetingResponse,
)
from app.services.live_stream import SessionLimitExceeded, live_session_manager
from app.services.meeting_service import (
    get_media_path,
    get_meeting_detail,
    join_meeting,
    list_meetings,
    update_action_item,
    upload_meeting,
)

logger = logging.getLogger(__name__)

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


@router.get("", response_model=list[MeetingListItem])
def api_list_meetings(limit: int = 50, offset: int = 0, q: str | None = None):
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
    # B1. Token check: compare with hmac.compare_digest on bytes
    # Reject if the server token is empty or "change-me"
    server_token = settings.BOT_INGEST_TOKEN.strip() if settings.BOT_INGEST_TOKEN else ""
    if not server_token or server_token == "change-me":
        await websocket.close(code=1008)
        return

    # Reject query-string token if BOT_ALLOW_QUERY_TOKEN is False
    query_token = websocket.query_params.get("token")
    if query_token is not None:
        if not settings.BOT_ALLOW_QUERY_TOKEN:
            logger.warning("Token in query string rejected (BOT_ALLOW_QUERY_TOKEN=False)")
            await websocket.close(code=1008)
            return
        token = query_token
    else:
        token = websocket.headers.get("x-bot-token")
        if not token:
            auth_header = websocket.headers.get("authorization", "")
            if auth_header.lower().startswith("bearer "):
                token = auth_header[7:].strip()
            elif auth_header:
                token = auth_header.strip()

    if not token or not hmac.compare_digest(token.encode("utf-8"), server_token.encode("utf-8")):
        await websocket.close(code=1008)
        return

    # 2. Only accept meetings with source='join'
    with get_db() as conn:
        row = conn.execute(
            "SELECT id, source, status, language FROM meetings WHERE id = ?",
            (meeting_id,),
        ).fetchone()

    if not row or row["source"] != "join" or row["status"] in ("done", "failed"):
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

    # A4: Only one active bot connection per meeting. A new connection replaces the old one.
    old_ws = session.active_websocket
    if old_ws is not None and old_ws != websocket:
        logger.info("Replacing existing active connection for meeting %s", meeting_id)
        session.active_websocket = websocket
        try:
            await old_ws.close(code=1008, reason="Connection replaced by new connection")
        except Exception:  # noqa: BLE001, S110
            pass
    else:
        session.active_websocket = websocket

    session.on_connected()

    pending_chunk_header: dict | None = None

    try:
        while True:
            # If this connection was replaced by a newer connection, exit cleanly
            if session.active_websocket != websocket:
                break

            msg = await websocket.receive()
            msg_type_str = msg.get("type")

            if msg_type_str == "websocket.disconnect":
                raise WebSocketDisconnect(code=msg.get("code", 1000))

            if "text" in msg:
                if pending_chunk_header is not None:
                    await websocket.close(code=1003, reason="Expected binary frame after chunk header")
                    return

                text_raw = msg["text"]
                # B2: Text frame max 4 KB
                if len(text_raw.encode("utf-8")) > 4096:
                    await websocket.close(code=1009, reason="Text frame exceeds 4 KB limit")
                    return

                try:
                    data = json.loads(text_raw)
                except Exception:  # noqa: BLE001
                    await websocket.close(code=1003, reason="Invalid JSON")
                    return

                if not isinstance(data, dict):
                    await websocket.close(code=1003, reason="JSON root must be an object")
                    return

                msg_type = data.get("type")
                if msg_type not in ("chunk", "end"):
                    await websocket.close(code=1003, reason=f"Unknown message type: {msg_type}")
                    return

                if msg_type == "end":
                    try:
                        await session.finalize()
                    finally:
                        if session.active_websocket == websocket:
                            session.active_websocket = None
                        await websocket.close(code=1000)
                    break

                if msg_type == "chunk":
                    # Validate start_ms: int >= 0 and <= 8 hours
                    if "start_ms" not in data:
                        await websocket.close(code=1003, reason="Missing start_ms")
                        return
                    start_ms = data.get("start_ms")
                    if type(start_ms) is not int or start_ms < 0 or start_ms > 8 * 3600 * 1000:
                        await websocket.close(code=1003, reason="start_ms must be an integer between 0 and 8 hours")
                        return

                    # Validate speaker_id: string max 128 chars, strip control characters
                    if "speaker_id" not in data:
                        await websocket.close(code=1003, reason="Missing speaker_id")
                        return
                    speaker_id = data.get("speaker_id")
                    if not isinstance(speaker_id, str):
                        await websocket.close(code=1003, reason="speaker_id must be a string")
                        return
                    clean_speaker_id = "".join(ch for ch in speaker_id if ch.isprintable()).strip()
                    if not clean_speaker_id or len(clean_speaker_id) > 128:
                        await websocket.close(code=1003, reason="speaker_id must be 1-128 printable characters")
                        return

                    # Validate speaker_name: optional string max 200 chars, strip control characters
                    speaker_name = data.get("speaker_name")
                    if speaker_name is not None:
                        if not isinstance(speaker_name, str):
                            await websocket.close(code=1003, reason="speaker_name must be a string or null")
                            return
                        clean_speaker_name = "".join(ch for ch in speaker_name if ch.isprintable()).strip()
                        if len(clean_speaker_name) > 200:
                            await websocket.close(code=1003, reason="speaker_name exceeds 200 characters")
                            return
                        speaker_name = clean_speaker_name if clean_speaker_name else None

                    pending_chunk_header = {
                        "speaker_id": clean_speaker_id,
                        "speaker_name": speaker_name,
                        "start_ms": start_ms,
                    }

            elif "bytes" in msg:
                # B2: A binary frame with no header before it: reject
                if pending_chunk_header is None:
                    await websocket.close(code=1003, reason="Binary frame with no preceding chunk header")
                    return

                pcm_bytes = msg["bytes"]
                # B2: Binary frame max 1 MB
                if len(pcm_bytes) > 1024 * 1024:
                    await websocket.close(code=1009, reason="Binary frame exceeds 1 MB limit")
                    return
                # B2: Even number of bytes (PCM16)
                if len(pcm_bytes) % 2 != 0:
                    await websocket.close(code=1003, reason="Binary frame must be an even number of bytes (PCM16)")
                    return

                header = pending_chunk_header
                pending_chunk_header = None

                try:
                    await session.handle_audio_chunk(
                        speaker_id=header["speaker_id"],
                        speaker_name=header["speaker_name"],
                        start_ms=header["start_ms"],
                        pcm_bytes=pcm_bytes,
                    )
                except SessionLimitExceeded as sle:
                    await websocket.close(code=sle.code, reason=str(sle))
                    return

    except WebSocketDisconnect:
        if session.active_websocket == websocket:
            session.active_websocket = None
            session.on_disconnected()
    except Exception:
        if session.active_websocket == websocket:
            logger.exception("Exception in WebSocket stream for meeting %s", meeting_id)
            session.active_websocket = None
            session.on_disconnected()

