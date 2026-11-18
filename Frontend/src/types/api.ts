import { Meeting, MeetingDetail } from './meeting';

export interface ApiResponse<T> {
  data: T;
  message?: string;
  success: boolean;
}

export interface ApiError {
  message: string;
  statusCode?: number;
  errors?: Record<string, string[]>;
}

export type MeetingsListResponse = Meeting[] | { data: Meeting[]; total?: number };
export type MeetingDetailResponse = MeetingDetail | { data: MeetingDetail };
export type JoinMeetingResponse = { meeting_id: string; meeting?: Meeting } | Meeting;
export type UploadMeetingResponse = { meeting_id: string; meeting?: Meeting } | Meeting;
