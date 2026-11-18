import { apiClient } from './api';
import {
  Meeting,
  MeetingDetail,
  ActionItem,
  JoinMeetingPayload,
  UploadMeetingPayload,
} from '../types/meeting';
import { APP_CONFIG } from '../constants/appConstants';
import { INITIAL_MEETINGS } from './mockData';

// Local reactive mock store for fallback when backend server is not running
let localMeetings: MeetingDetail[] = [...INITIAL_MEETINGS];

/**
 * 1. POST /api/v1/meetings/join
 * Join an online meeting via URL, language and slot name
 */
export async function joinMeeting(payload: JoinMeetingPayload): Promise<MeetingDetail | { meeting_id: string }> {
  try {
    const response = await apiClient.post('/meetings/join', {
      meeting_url: payload.meeting_url,
      language: payload.language,
      slot_name: payload.slot_name,
    });
    return response.data;
  } catch (error) {
    if (APP_CONFIG.ENABLE_MOCK_FALLBACK) {
      console.warn('[meetingService] Real API unreachable, using mock store fallback for join');
      const newId = `meet-${Date.now()}`;
      const newMeeting: MeetingDetail = {
        id: newId,
        title: `${payload.slot_name} - Online Session`,
        folder: 'Online Meetings',
        slotName: payload.slot_name,
        date: new Date().toISOString(),
        durationSeconds: 1800,
        status: 'completed',
        language: payload.language,
        meetingUrl: payload.meeting_url,
        participantsCount: 3,
        createdAt: new Date().toISOString(),
        summarySnippet: `AI bot joined ${payload.meeting_url} and processed meeting notes.`,
        mediaUrl: 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4',
        summary: {
          overview: `Online session joined via ${payload.meeting_url} in language ${payload.language}. Discussion centered around current project milestones and next execution steps.`,
          projectProgress: [
            { id: `p-${Date.now()}-1`, title: 'Online Session Ingestion', status: 'completed', notes: 'Audio stream captured successfully.' },
          ],
          challengesFaced: [],
          actionItems: [
            { id: `a-${Date.now()}-1`, task: 'Follow up on online discussion items', assignee: 'Me', dueDate: new Date(Date.now() + 86400000).toISOString().split('T')[0], done: false, completed: false, priority: 'medium' },
          ],
          nextSteps: ['Review generated summary and distribute to attendees.'],
        },
        transcript: [
          { id: `t-${Date.now()}-1`, speakerId: 'spk-1', speakerName: 'Host', speakerColor: '#4f46e5', timestampStart: 0, timestampEnd: 15, text: `Hello everyone, welcome to our ${payload.slot_name} session.` },
          { id: `t-${Date.now()}-2`, speakerId: 'spk-2', speakerName: 'Participant', speakerColor: '#0891b2', timestampStart: 16, timestampEnd: 30, text: 'Thanks for organizing. We are ready to review the agenda.' },
        ],
        speakers: [
          { id: 'spk-1', name: 'Host', role: 'Organizer', color: '#4f46e5', talkDurationSeconds: 1000, talkPercentage: 55, wordsPerMinute: 130, sentiment: 'positive' },
          { id: 'spk-2', name: 'Participant', role: 'Attendee', color: '#0891b2', talkDurationSeconds: 800, talkPercentage: 45, wordsPerMinute: 125, sentiment: 'positive' },
        ],
        topics: [
          { id: `top-${Date.now()}-1`, name: `${payload.slot_name} Kickoff`, timestampStart: 0, timestampEnd: 1800, durationSeconds: 1800, keyPoints: ['General sync updates', 'Next sprint alignment'], relevanceScore: 90 },
        ],
        analytics: {
          totalDurationSeconds: 1800,
          overallSentiment: { positive: 75, neutral: 25, negative: 0 },
          totalSpeakers: 2,
          questionsAskedCount: 5,
          averagePaceWpm: 128,
          engagementScore: 85,
          speakerTalkTimeDistribution: [
            { speakerName: 'Host', percentage: 55, durationSeconds: 1000, color: '#4f46e5' },
            { speakerName: 'Participant', percentage: 45, durationSeconds: 800, color: '#0891b2' },
          ],
        },
      };
      localMeetings = [newMeeting, ...localMeetings];
      return newMeeting;
    }
    throw error;
  }
}

/**
 * 2. POST /api/v1/meetings/upload
 * Upload a recorded meeting media file, language and slot name
 */
export async function uploadMeeting(payload: UploadMeetingPayload): Promise<MeetingDetail | { meeting_id: string }> {
  try {
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
  } catch (error) {
    if (APP_CONFIG.ENABLE_MOCK_FALLBACK) {
      console.warn('[meetingService] Real API unreachable, using mock store fallback for upload');
      const newId = `meet-${Date.now()}`;
      const objectUrl = URL.createObjectURL(payload.file);
      const newMeeting: MeetingDetail = {
        id: newId,
        title: `${payload.slot_name} - Uploaded Recording`,
        folder: 'Recordings',
        slotName: payload.slot_name,
        date: new Date().toISOString(),
        durationSeconds: 1240,
        status: 'completed',
        language: payload.language,
        participantsCount: 2,
        createdAt: new Date().toISOString(),
        summarySnippet: `Processed uploaded file: ${payload.file.name} (${Math.round(payload.file.size / 1024 / 1024)} MB).`,
        mediaUrl: objectUrl,
        summary: {
          overview: `Uploaded recording (${payload.file.name}) processed for slot "${payload.slot_name}". The AI summary generator extracted key takeaways, action items, and topic distribution.`,
          projectProgress: [
            { id: `p-${Date.now()}-1`, title: 'Uploaded Media Ingestion', status: 'completed', notes: `Processed ${payload.file.name}.` },
            { id: `p-${Date.now()}-2`, title: 'Transcript Generation', status: 'completed', notes: 'Diarization and speech-to-text done.' },
          ],
          challengesFaced: [],
          actionItems: [
            { id: `a-${Date.now()}-1`, task: 'Review transcript timestamps and accuracy', assignee: 'Me', dueDate: new Date(Date.now() + 86400000).toISOString().split('T')[0], done: false, completed: false, priority: 'high' },
          ],
          nextSteps: ['Share summary link with team members.', 'Export PDF report for archiving.'],
        },
        transcript: [
          { id: `t-${Date.now()}-1`, speakerId: 'spk-1', speakerName: 'Primary Speaker', speakerColor: '#4f46e5', timestampStart: 0, timestampEnd: 12, text: `Reviewing recorded audio for ${payload.file.name}.` },
          { id: `t-${Date.now()}-2`, speakerId: 'spk-2', speakerName: 'Secondary Speaker', speakerColor: '#0891b2', timestampStart: 13, timestampEnd: 28, text: 'All action items and milestones have been registered.' },
        ],
        speakers: [
          { id: 'spk-1', name: 'Primary Speaker', role: 'Presenter', color: '#4f46e5', talkDurationSeconds: 700, talkPercentage: 56, wordsPerMinute: 135, sentiment: 'positive' },
          { id: 'spk-2', name: 'Secondary Speaker', role: 'Collaborator', color: '#0891b2', talkDurationSeconds: 540, talkPercentage: 44, wordsPerMinute: 128, sentiment: 'positive' },
        ],
        topics: [
          { id: `top-${Date.now()}-1`, name: `${payload.slot_name} Discussion`, timestampStart: 0, timestampEnd: 1240, durationSeconds: 1240, keyPoints: ['File uploaded & transcribed', 'Key action items extracted'], relevanceScore: 92 },
        ],
        analytics: {
          totalDurationSeconds: 1240,
          overallSentiment: { positive: 70, neutral: 25, negative: 5 },
          totalSpeakers: 2,
          questionsAskedCount: 6,
          averagePaceWpm: 131,
          engagementScore: 82,
          speakerTalkTimeDistribution: [
            { speakerName: 'Primary Speaker', percentage: 56, durationSeconds: 700, color: '#4f46e5' },
            { speakerName: 'Secondary Speaker', percentage: 44, durationSeconds: 540, color: '#0891b2' },
          ],
        },
      };
      localMeetings = [newMeeting, ...localMeetings];
      return newMeeting;
    }
    throw error;
  }
}

/**
 * 3. GET /api/v1/meetings
 * List recent meetings with optional 'q' search for meeting moments
 */
export async function getMeetings(query?: string): Promise<Meeting[]> {
  try {
    const params = query && query.trim() ? { q: query.trim() } : {};
    const response = await apiClient.get('/meetings', { params });
    // Support either { data: [...] } or direct [...] array
    if (Array.isArray(response.data)) {
      return response.data;
    }
    if (response.data && Array.isArray(response.data.data)) {
      return response.data.data;
    }
    return [];
  } catch (error) {
    if (APP_CONFIG.ENABLE_MOCK_FALLBACK) {
      console.warn('[meetingService] Real API unreachable, using mock store fallback for getMeetings');
      let filtered = [...localMeetings];
      if (query && query.trim()) {
        const q = query.trim().toLowerCase();
        filtered = filtered.filter((m) => {
          const matchTitle = m.title.toLowerCase().includes(q);
          const matchSlot = m.slotName.toLowerCase().includes(q);
          const matchSnippet = m.summarySnippet?.toLowerCase().includes(q);
          const matchFolder = m.folder.toLowerCase().includes(q);
          const matchTranscript = m.transcript?.some((t) => t.text.toLowerCase().includes(q));
          const matchTopics = m.topics?.some((top) => top.name.toLowerCase().includes(q));
          return matchTitle || matchSlot || matchSnippet || matchFolder || matchTranscript || matchTopics;
        });
      }
      return filtered;
    }
    throw error;
  }
}

/**
 * 4. GET /api/v1/meetings/{meeting_id}
 * Complete meeting details including summary, transcript, speakers, topics, analytics, and media URL
 */
export async function getMeetingById(meetingId: string): Promise<MeetingDetail> {
  try {
    const response = await apiClient.get(`/meetings/${meetingId}`);
    if (response.data && response.data.data) {
      return response.data.data;
    }
    return response.data;
  } catch (error) {
    if (APP_CONFIG.ENABLE_MOCK_FALLBACK) {
      console.warn('[meetingService] Real API unreachable, using mock store fallback for getMeetingById');
      const found = localMeetings.find((m) => m.id === meetingId);
      if (found) {
        return found;
      }
      // If not found in localMeetings, fallback to the first meeting or throw
      if (localMeetings.length > 0) {
        return {
          ...localMeetings[0],
          id: meetingId,
        };
      }
      throw new Error(`Meeting with ID ${meetingId} not found.`);
    }
    throw error;
  }
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
  try {
    const response = await apiClient.patch(
      `/meetings/${meetingId}/action-items/${itemId}`,
      payload
    );
    if (response.data && response.data.data) {
      return response.data.data;
    }
    return response.data;
  } catch (error) {
    if (APP_CONFIG.ENABLE_MOCK_FALLBACK) {
      console.warn('[meetingService] Real API unreachable, using mock store fallback for updateActionItem');
      const meeting = localMeetings.find((m) => m.id === meetingId);
      if (!meeting) {
        throw new Error(`Meeting with ID ${meetingId} not found.`);
      }

      let updatedItem: ActionItem | null = null;
      const updateList = (items?: (string | ActionItem)[]) => {
        if (!items || !Array.isArray(items)) return items;
        return items.map((it) => {
          if (typeof it === 'string') return it;
          if (it.id === itemId) {
            updatedItem = {
              ...it,
              id: it.id,
              done: payload.done,
              completed: payload.done,
            };
            return updatedItem;
          }
          return it;
        });
      };

      if (meeting.summary) {
        if (meeting.summary.actionItems) {
          meeting.summary.actionItems = updateList(meeting.summary.actionItems);
        }
        if (meeting.summary.action_items) {
          meeting.summary.action_items = updateList(meeting.summary.action_items);
        }
        if (meeting.summary.key_points?.action_items) {
          meeting.summary.key_points.action_items = updateList(meeting.summary.key_points.action_items);
        }
      }

      if (updatedItem) {
        return updatedItem;
      }

      const fallbackItem: ActionItem = {
        id: itemId,
        task: 'Action item',
        done: payload.done,
        completed: payload.done,
      };
      return fallbackItem;
    }
    throw error;
  }
}

export const patchActionItem = updateActionItem;
