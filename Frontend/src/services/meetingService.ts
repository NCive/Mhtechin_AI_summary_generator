import { apiClient } from './api';
import {
  Meeting,
  MeetingDetail,
  ActionItem,
  JoinMeetingPayload,
  UploadMeetingPayload,
} from '../types/meeting';

/**
 * 1. POST /api/v1/meetings/join
 * Join an online meeting via URL, language and slot name
 */
export async function joinMeeting(
  payload: JoinMeetingPayload
): Promise<MeetingDetail | { meeting_id: string; meetingId?: string }> {
  const response = await apiClient.post('/meetings/join', {
    meetingUrl: payload.meeting_url,
    meeting_url: payload.meeting_url,
    language: payload.language,
    slotName: payload.slot_name,
    slot_name: payload.slot_name,
  });
  return response.data;
}

/**
 * 2. POST /api/v1/meetings/upload
 * Upload a recorded meeting media file, language and slot name
 */
export async function uploadMeeting(
  payload: UploadMeetingPayload
): Promise<MeetingDetail | { meeting_id: string; meetingId?: string }> {
  const formData = new FormData();
  formData.append('file', payload.file);
  formData.append('language', payload.language);
  formData.append('slot_name', payload.slot_name);

  const response = await apiClient.post('/meetings/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  return response.data;
}

/**
 * 3. GET /api/v1/meetings
 * List recent meetings with optional 'q' search for meeting moments
 */
export async function getMeetings(query?: string): Promise<Meeting[]> {
  const params = query && query.trim() ? { q: query.trim() } : {};
  const response = await apiClient.get('/meetings', { params });
  const rawList: any[] = Array.isArray(response.data)
    ? response.data
    : response.data && Array.isArray(response.data.data)
    ? response.data.data
    : [];
  return rawList.map((item: any) => ({
    ...item,
    id: String(item.id || item.meetingId || ''),
    meetingId: String(item.meetingId || item.id || ''),
    date: item.date || '',
    summarySnippet: item.summarySnippet || item.overview || '',
  }));
}

/**
 * 4. GET /api/v1/meetings/{meeting_id}
 * Complete meeting details including summary, transcript, speakers, topics, analytics, and media URL
 */
export async function getMeetingById(meetingId: string): Promise<MeetingDetail> {
  const response = await apiClient.get(`/meetings/${meetingId}`);
  const data = response.data && response.data.data ? response.data.data : response.data;
  return {
    ...data,
    id: String(data.id || data.meetingId || meetingId),
    meetingId: String(data.meetingId || data.id || meetingId),
    date: data.date || '',
  };
}

/**
 * 5. PATCH /api/v1/meetings/{meeting_id}/action-items/{item_id}
 * Update action item status with body { done: boolean }, returning the updated action item
 */
export async function updateActionItem(
  meetingId: string,
  itemId: string,
  body: { done: boolean } | boolean
): Promise<ActionItem> {
  const payload = typeof body === 'boolean' ? { done: body } : body;
  const response = await apiClient.patch(
    `/meetings/${meetingId}/action-items/${itemId}`,
    payload
  );
  if (response.data && response.data.data) {
    return response.data.data;
  }
  return response.data;
}

export const patchActionItem = updateActionItem;
