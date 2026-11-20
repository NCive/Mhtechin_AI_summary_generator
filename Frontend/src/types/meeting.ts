export type MeetingStatus = 'completed' | 'processing' | 'scheduled' | 'failed';

export interface ActionItem {
  id?: string;
  done?: boolean;
  task: string;
  assignee?: string;
  assigneeAvatar?: string;
  dueDate?: string;
  due_date?: string;
  completed?: boolean;
}

export interface ChallengeItem {
  id?: string;
  title: string;
  description?: string;
  severity?: 'high' | 'medium' | 'low';
  impact?: string;
}

export interface ProgressItem {
  id?: string;
  title: string;
  status?: 'completed' | 'in_progress' | 'blocked';
  notes?: string;
}

export interface MeetingSummary {
  overview?: string;
  projectProgress?: (string | ProgressItem)[];
  challengesFaced?: (string | ChallengeItem)[];
  actionItems?: (string | ActionItem)[];
  nextSteps?: string[];
  // Support snake_case responses from backend API
  project_progress?: (string | ProgressItem)[];
  challenges_faced?: (string | ChallengeItem)[];
  challenge_faced?: (string | ChallengeItem)[];
  action_items?: (string | ActionItem)[];
  next_steps?: string[];
  key_points?: {
    project_progress?: (string | ProgressItem)[];
    challenges_faced?: (string | ChallengeItem)[];
    challenge_faced?: (string | ChallengeItem)[];
    action_items?: (string | ActionItem)[];
    next_steps?: string[];
  };
}

export interface TranscriptUtterance {
  id: string;
  speakerId: string;
  speakerName: string;
  speakerAvatar?: string;
  speakerColor: string;
  timestampStart: number;
  timestampEnd: number;
  text: string;
}

export interface Speaker {
  id: string;
  name: string;
  role: string;
  avatar?: string;
  color: string;
  talkDurationSeconds?: number;
  talkDurationLabel?: string; // e.g. "1h"
  talkPercentage: number; // e.g. 42
  listenPercentage?: number; // e.g. 70
}

export interface Meeting {
  id: string;
  title: string;
  folder: string;
  slotName: string;
  date: string;
  timeRange?: string;
  durationSeconds?: number | null;
  durationLabel?: string;
  status: MeetingStatus;
  language: string;
  mediaUrl?: string;
  thumbnailUrl?: string;
  summarySnippet?: string;
  participantsCount: number;
  participantAvatars?: string[];
  meetingUrl?: string;
  createdAt: string;
}

export interface MeetingDetail extends Meeting {
  summary?: MeetingSummary;
  transcript?: TranscriptUtterance[];
  speakers?: Speaker[];
  mediaType?: 'audio' | 'video' | null;
  processedSeconds?: number | null;
  durationSeconds?: number | null;
  error?: string | null;
}

export interface JoinMeetingPayload {
  meeting_url: string;
  language: string;
  slot_name: string;
}

export interface UploadMeetingPayload {
  file: File;
  language: string;
  slot_name: string;
}
