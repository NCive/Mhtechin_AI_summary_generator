from typing import Any, List, Optional
from pydantic import BaseModel, Field, model_validator

class JoinMeetingRequest(BaseModel):
    meetingUrl: str = Field(..., alias="meetingUrl")
    language: str
    slotName: str

    model_config = {"populate_by_name": True}

    @model_validator(mode="before")
    @classmethod
    def assemble_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "meeting_url" in data and "meetingUrl" not in data:
                data["meetingUrl"] = data["meeting_url"]
            if "slot_name" in data and "slotName" not in data:
                data["slotName"] = data["slot_name"]
        return data

class UploadMeetingResponse(BaseModel):
    meetingId: str
    status: str

class MeetingListItem(BaseModel):
    meetingId: str
    id: str | None = None
    title: Optional[str] = None
    overview: Optional[str] = None
    createdAt: Optional[str] = None
    date: str | None = None
    status: Optional[str] = None

class UpdateActionItemRequest(BaseModel):
    done: bool

class ActionItemResponse(BaseModel):
    id: str
    task: str
    assignee: str | None = None
    dueDate: str | None = None
    done: bool

class ActionItem(BaseModel):
    id: str
    task: str | None = None
    description: str | None = None
    assignee: str | None = None
    dueDate: str | None = None
    done: bool

class Speaker(BaseModel):
    id: str
    name: Optional[str] = None
    speakingTime: Optional[float] = None

class Topic(BaseModel):
    id: str
    name: Optional[str] = None

class Analytics(BaseModel):
    participantCount: Optional[int] = None
    durationSeconds: Optional[int] = None
    processedSeconds: Optional[int] = None

class MeetingDetailResponse(BaseModel):
    meetingId: str
    id: str | None = None
    title: Optional[str] = None
    status: Optional[str] = None
    createdAt: str | None = None
    date: str | None = None
    summary: Optional[dict] = None
    transcript: Optional[List[dict]] = None
    speakers: Optional[List[Speaker]] = None
    topics: Optional[List[Topic]] = None
    actionItems: Optional[List[ActionItem]] = None
    analytics: Optional[Analytics] = None
    mediaUrl: Optional[str] = None
    mediaType: str | None = None
    processedSeconds: float | None = None
    durationSeconds: float | None = None
    error: str | None = None
