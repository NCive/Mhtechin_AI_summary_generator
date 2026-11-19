from pydantic import BaseModel, Field
from typing import List, Optional

class JoinMeetingRequest(BaseModel):
    meetingUrl: str = Field(..., alias="meetingUrl")
    language: str
    slotName: str

class UploadMeetingResponse(BaseModel):
    meetingId: str
    status: str

class MeetingListItem(BaseModel):
    meetingId: str
    title: Optional[str] = None
    overview: Optional[str] = None
    createdAt: Optional[str] = None
    status: Optional[str] = None

class ActionItem(BaseModel):
    id: str
    description: Optional[str] = None
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
    title: Optional[str] = None
    status: Optional[str] = None
    summary: Optional[dict] = None
    transcript: Optional[List[dict]] = None
    speakers: Optional[List[Speaker]] = None
    topics: Optional[List[Topic]] = None
    actionItems: Optional[List[ActionItem]] = None
    analytics: Optional[Analytics] = None
    mediaUrl: Optional[str] = None
