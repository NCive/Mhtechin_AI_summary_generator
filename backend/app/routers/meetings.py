from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Query

from typing import List, Optional

from app.schemas.meeting import (
    JoinMeetingRequest,
    UploadMeetingResponse,
    MeetingListItem,
    MeetingDetailResponse,
)
from app.services.meeting_service import (
    join_meeting,
    upload_meeting,
    list_meetings,
    get_meeting_detail,
    get_media_path,
)
from fastapi.responses import FileResponse

router = APIRouter(prefix="/meetings", tags=["meetings"])

@router.post("/join", response_model=UploadMeetingResponse)
def api_join_meeting(req: JoinMeetingRequest):
    result = join_meeting(req.meetingUrl, req.language, req.slotName)
    return result

@router.post("/upload", response_model=UploadMeetingResponse)
def api_upload_meeting(
    file: UploadFile = File(...),
    language: str = Query(...),
    slotName: str = Query(...),
):
    # language and slotName are required query params
    return upload_meeting(file, language, slotName)


@router.get("", response_model=List[MeetingListItem])
def api_list_meetings(limit: int = 50, offset: int = 0, q: Optional[str] = None):
    return list_meetings(limit=limit, offset=offset, q=q)

@router.get("/{meeting_id}", response_model=MeetingDetailResponse)
def api_get_meeting(meeting_id: str):
    return get_meeting_detail(meeting_id)

@router.get("/media/{meeting_id}")
def api_get_media(meeting_id: str):
    path = get_media_path(meeting_id)
    return FileResponse(path, media_type="application/octet-stream", filename=path.name)
