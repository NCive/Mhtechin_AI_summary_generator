# Frontend vs Backend Schema Discrepancy Analysis

This document identifies differences between the frontend TypeScript types in `Frontend/src/types/meeting.ts` and `Frontend/src/types/api.ts` and the SQLite backend schema defined in `backend/app/db/schema.sql`.

---

## 1. `meetings` Table vs `Meeting` / `MeetingDetail`

| Backend Schema (`meetings`) | Frontend Field (`Meeting` / `MeetingDetail`) | Discrepancies & Notes |
|---|---|---|
| `id` (TEXT UUID PK) | `id` (string) | Matches. |
| `title` (TEXT) | `title` (string) | Matches. |
| `folder` (TEXT) | `folder` (string) | Matches. |
| `slot_name` (TEXT) | `slotName` (string) | **Casing mismatch**: DB uses snake_case `slot_name`, frontend uses camelCase `slotName`. |
| `language` (TEXT) | `language` (string) | Matches. |
| `source` ('upload' \| 'join') | *(Not defined on model)* | DB has explicit source enum; frontend has no `source` field. |
| `source_url` (TEXT) | `meetingUrl` (string) | **Name mismatch**: DB uses `source_url`, frontend uses `meetingUrl`. |
| `media_path` (TEXT) | `mediaUrl` (string) | **Name & semantic mismatch**: DB stores local server filesystem path (`media_path`), frontend expects a playable HTTP URL (`mediaUrl`). |
| `media_type` ('video' \| 'audio') | *(Not defined on model)* | DB tracks media type; frontend assumes video with fallback audio. |
| `status` ('pending' \| 'processing' \| 'done' \| 'failed') | `status` ('completed' \| 'processing' \| 'scheduled' \| 'failed') | **Enum value mismatch**: DB uses `'pending'` and `'done'`, frontend uses `'scheduled'` and `'completed'`. Note: Frontend `MeetingStatus` explicitly accepts `'processing'` and `'failed'` directly. |
| `error` (TEXT) | *(Not defined on model)* | DB persists error strings; frontend handles errors via HTTP responses. |
| `duration_seconds` (REAL) | `durationSeconds` (number) | **Casing mismatch**: `duration_seconds` vs `durationSeconds`. |
| `processed_seconds` (REAL) | *(Not defined on model)* | DB tracks ingestion progress; frontend does not have this field. |
| `created_at` (TEXT) | `createdAt` (string) | **Casing mismatch**: `created_at` vs `createdAt`. |
| `overview` (TEXT) | `summary.overview` (string) | **Nesting mismatch**: DB stores at root of `meetings`; frontend expects it nested inside `summary`. |
| `project_progress` (JSON TEXT) | `summary.projectProgress` (`ProgressItem[]`) | **Type & nesting mismatch**: DB stores JSON string at root; frontend expects parsed array of `{ id, title, status, notes }` inside `summary`. |
| `challenges` (JSON TEXT) | `summary.challengesFaced` (`ChallengeItem[]`) | **Name & nesting mismatch**: DB column is `challenges`; frontend expects `challengesFaced` / `challenges_faced` containing `{ id, title, description, severity, impact }` inside `summary`. |
| `next_steps` (JSON TEXT) | `summary.nextSteps` (`string[]`) | **Nesting mismatch**: DB stores at root; frontend expects string array inside `summary`. |
| *(Not in DB)* | `date` (string) | Frontend expects formatted date string (e.g. `"Mon, April 29, 2025"`). |
| *(Not in DB)* | `timeRange` (string) | Frontend expects formatted time range (e.g. `"8:00 PM to 5:20 PM (440 mins)"`). |
| *(Not in DB)* | `durationLabel` (string) | Frontend expects duration badge label (e.g. `"30m"`). |
| *(Not in DB)* | `thumbnailUrl` (string) | Frontend meeting cards support video thumbnail preview. |
| *(Not in DB)* | `summarySnippet` (string) | Frontend meeting cards display a brief snippet summary. |
| *(Not in DB)* | `participantsCount` (number) | Frontend displays attendee count badge. |
| *(Not in DB)* | `participantAvatars` (`string[]`) | Frontend displays list of attendee avatar URLs. |
| *(Not in DB)* | `topics` (`Topic[]`) | Frontend expects an array of topics (`{ id, name, timestampStart, timestampEnd, durationSeconds, keyPoints, relevanceScore }`). The DB has `windows` instead. |
| *(Not in DB)* | `analytics` (`ParticipantAnalytics`) | Frontend detail view has an analytics dashboard object (`totalDurationSeconds`, `overallSentiment`, `totalSpeakers`, `questionsAskedCount`, `averagePaceWpm`, `engagementScore`, `speakerTalkTimeDistribution`). No DB table or columns exist for this. |

---

## 2. `transcript_segments` Table vs `TranscriptUtterance`

| Backend Schema (`transcript_segments`) | Frontend Field (`TranscriptUtterance`) | Discrepancies & Notes |
|---|---|---|
| `id` (INTEGER PK AUTOINCREMENT) | `id` (string) | **Type mismatch**: Integer in DB vs string in frontend. |
| `start_time` (REAL) | `timestampStart` (number) | **Name mismatch**: `start_time` in DB vs `timestampStart` in frontend. |
| `end_time` (REAL) | `timestampEnd` (number) | **Name mismatch**: `end_time` in DB vs `timestampEnd` in frontend. |
| `speaker` (TEXT) | `speakerName` (string) | **Name mismatch**: `speaker` in DB vs `speakerName` in frontend. |
| `text` (TEXT) | `text` (string) | Matches. |
| *(Not in DB)* | `speakerId` (string) | Frontend utterances link to a speaker ID (e.g. `"spk-1"`). |
| *(Not in DB)* | `speakerAvatar` (string) | Frontend utterance supports avatar URL. |
| *(Not in DB)* | `speakerColor` (string) | Frontend utterance uses color code (e.g. `"#4f46e5"`). |

---

## 3. `speakers` Table vs `Speaker`

| Backend Schema (`speakers`) | Frontend Field (`Speaker`) | Discrepancies & Notes |
|---|---|---|
| `id` (INTEGER PK AUTOINCREMENT) | `id` (string) | **Type mismatch**: Integer vs string ID. |
| `name` (TEXT) | `name` (string) | Matches. |
| `color` (TEXT) | `color` (string) | Matches. |
| `talk_seconds` (REAL) | `talkDurationSeconds` (number) | **Name mismatch**: `talk_seconds` vs `talkDurationSeconds`. |
| `talk_percent` (REAL) | `talkPercentage` (number) | **Name mismatch**: `talk_percent` vs `talkPercentage`. |
| `listen_percent` (REAL) | `listenPercentage` (number) | **Name mismatch**: `listen_percent` vs `listenPercentage`. |
| *(Not in DB)* | `role` (string) | **Missing field**: Frontend UI renders participant role (e.g. `"Core Developer"`, `"UI Engineer"`). |
| *(Not in DB)* | `avatar` (string) | **Missing field**: Frontend renders participant avatar image URL. |
| *(Not in DB)* | `taskTimeLabel` (string) | **Undefined in DB**: Frontend speakers table renders `"Task Time"` column (e.g. `"25m"`). |
| *(Not in DB)* | `talkDurationLabel` (string) | Frontend UI renders formatted label (e.g. `"1h"`). |
| *(Not in DB)* | `wordsPerMinute` (number) | Frontend displays speech pace in wpm. |
| *(Not in DB)* | `sentiment` ('positive' \| 'neutral' \| 'critical') | Frontend renders participant sentiment badge. |

---

## 4. `action_items` Table vs `ActionItem`

| Backend Schema (`action_items`) | Frontend Field (`ActionItem`) | Discrepancies & Notes |
|---|---|---|
| `id` (TEXT UUID PK) | `id` (string) | Matches. |
| `text` (TEXT) | `task` (string) | **Name mismatch**: `text` in DB vs `task` in frontend. |
| `owner` (TEXT, nullable) | `assignee` (string) | **Name mismatch**: `owner` in DB vs `assignee` in frontend. |
| `deadline` (TEXT, nullable) | `dueDate` / `due_date` (string) | **Name mismatch**: `deadline` in DB vs `dueDate` / `due_date` in frontend. |
| `done` (INTEGER, 0 or 1) | `done` (boolean) / `completed` (boolean) | **Type mismatch**: Integer (0/1) in DB vs boolean in frontend. |
| *(Not in DB)* | `assigneeAvatar` (string) | Frontend displays avatar image of assigned person. |
| *(Not in DB)* | `priority` ('high' \| 'medium' \| 'low') | Frontend displays priority tags (`high`, `medium`, `low`). |

---

## 5. `windows` Table

- **Backend Table**: `windows` (`id`, `meeting_id`, `window_index`, `start_time`, `end_time`, `result_json`).
- **Frontend Model**: Has no `Window` interface. The frontend expects `Topic[]` (`id`, `name`, `timestampStart`, `timestampEnd`, `durationSeconds`, `keyPoints`, `relevanceScore`).
- **Requirement for Backend Integration**: When constructing `MeetingDetail` responses, window analysis results should either be transformed into topics or exposed as a separate endpoint.

---

## 6. Endpoints & Payload Contracts

1. **Join Meeting**:
   - Frontend sends: `{ meeting_url: string, language: string, slot_name: string }`
   - Backend DB stores: `source_url`, `language`, `slot_name` with `source = 'join'`.
2. **Upload Meeting**:
   - Frontend sends: Multipart Form with `file`, `language`, `slot_name`.
   - Backend DB stores: `media_path`, `media_type`, `language`, `slot_name` with `source = 'upload'`.
3. **Patch Action Item**:
   - Frontend sends: `PATCH /api/v1/meetings/{meeting_id}/action-items/{item_id}` with `{ done: boolean }`.
   - Backend DB stores: `action_items.done` as integer `1` or `0`.

---

## 7. Status Type Verification (`Frontend/src/types/meeting.ts`)

Inspection of `Frontend/src/types/meeting.ts` (line 1):
```typescript
export type MeetingStatus = 'completed' | 'processing' | 'scheduled' | 'failed';
```
- **Acceptance of `processing` and `failed`**: **YES**. The frontend type definition explicitly accepts `'processing'` and `'failed'` directly.
- **Mapping behavior**:
  - Backend database stores: `'pending'`, `'done'`, `'processing'`, `'failed'`.
  - Backend response mapper (`app/services/mappers.py`) dynamically maps:
    - `'pending'` -> `'scheduled'`
    - `'done'` -> `'completed'`
    - `'processing'` -> `'processing'` (unchanged)
    - `'failed'` -> `'failed'` (unchanged)
  - The stored database value is never altered.
