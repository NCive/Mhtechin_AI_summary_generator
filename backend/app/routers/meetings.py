from fastapi import APIRouter, Depends, HTTPException, status, File, Form, UploadFile

from typing import List, Optional

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
