from typing import Any

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
    title: str | None = None
    overview: str | None = None
    createdAt: str | None = None
    date: str | None = None
    status: str | None = None


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
    completed: bool | None = None


class Speaker(BaseModel):
    id: str
    name: str | None = None
    color: str | None = None
    role: str | None = None
    avatar: str | None = None
    talkDurationSeconds: float | None = None
    talkPercentage: float | None = None
    listenPercentage: float | None = None
    talkSeconds: float | None = None
    talkPercent: float | None = None
    listenPercent: float | None = None
    speakingTime: float | None = None


class TranscriptUtterance(BaseModel):
    id: str
    timestampStart: float | None = None
    timestampEnd: float | None = None
    speakerName: str
    speakerColor: str | None = None
    text: str
    startTime: float | None = None
    endTime: float | None = None
    speaker: str | None = None


class MeetingSummaryResponse(BaseModel):
    overview: str | None = None
    projectProgress: list[str] | None = None
    challenges: list[str] | None = None
    challengesFaced: list[str] | None = None
    actionItems: list[ActionItem] | None = None
    nextSteps: list[str] | None = None


class MeetingDetailResponse(BaseModel):
    meetingId: str
    id: str | None = None
    title: str | None = None
    folder: str | None = None
    slotName: str | None = None
    status: str | None = None
    language: str | None = None
    meetingUrl: str | None = None
    createdAt: str | None = None
    date: str | None = None
    summary: MeetingSummaryResponse | None = None
    transcript: list[TranscriptUtterance] | None = None
    speakers: list[Speaker] | None = None
    actionItems: list[ActionItem] | None = None
    mediaUrl: str | None = None
    mediaType: str | None = None
    processedSeconds: float | None = None
    durationSeconds: float | None = None
    participantsCount: int | None = None
    error: str | None = None
