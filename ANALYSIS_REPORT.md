# Chatmeet Project Audit & Analysis Report

**Date of Audit:** 2026-11-19  
**Audit Mode:** Read-Only Inspection & Verification  
**Repository Working Tree:** Clean (Commit `6176266`)

---

## 1. Executive Summary Table (Parts 1 to 5)

| Section | Status | Summary Findings |
|---|---|---|
| **Part 1 – What Changed** | **PASS** | Complete Git history and 35-file inventory documented across `backend/` and `Frontend/src/`. Commit `6176266` added backend services/routers; commit `46946a7` added backend skeleton and frontend action-item patch. |
| **Part 2 – API Inventory** | **FAIL** | 5 routes defined in `backend/app/routers/meetings.py`. **`PATCH /api/v1/meetings/{meeting_id}/action-items/{item_id}` is completely missing from backend router and service**. Media route has path mismatch between router (`/api/v1/meetings/media/{id}`) and service response (`/api/v1/media/{id}`). `_validate_meeting_url` is malformed (missing `def` statement) causing runtime `NameError` on `POST /join`. |
| **Part 3 – Database & Media Bug** | **FAIL** | `settings.DB_PATH` resolves to `D:\Other Projects\AI_Summary\Mhtechin_AI_summary_generator\backend\chatmeet.db`. The file currently exists with 0 bytes and 0 tables because `init_db()` runs only on FastAPI app lifespan and scratch test scripts crashed pytest collection. Root causes of "no such column: meeting_id" and media 404 identified. No media files exist in `backend/media`. |
| **Part 4 – Check Against Decisions** | **FAIL / PARTIAL** | Item 4 is **DONE** (kept components intact). Items 1, 2, 5, 8 are **PARTIAL** (DB schema supports sentences and status mapping, frontend action item patch works, but backend lacks PATCH route, `mappers.py` is dead code, `mockData.ts` still imported). Items 3, 6, 7 are **NOT DONE** (unwanted features not removed from frontend, 5-webcam stock grid remains, no processing/failure time display). Item 9 shows extensive fabricated data across frontend and backend. |
| **Part 5 – Verification Suite** | **FAIL** | `pytest -q` in `backend/`: **FAIL** (2 collection errors in `scratch/test_media_path*.py`). `ruff check .`: **FAIL** (`No module named ruff`, not installed). `npx tsc --noEmit`: **PASS** (0 errors). `npm run build`: **PASS** (built in 8.49s). Upload-then-media test coverage: **NOT DONE** (zero tests for upload or media serving). |

---

## 2. Part 1: What Changed & File Inventory

### Git History Summary
- `6176266` (*BACKEND The 5 endpoints and media serving done*): Created `backend/app/routers/meetings.py`, `backend/app/schemas/meeting.py`, `backend/app/services/mappers.py`, `backend/app/services/meeting_service.py`, `backend/scratch/test_media_path.py`, `backend/scratch/test_media_path2.py`. Updated `config.py` and `main.py`.
- `46946a7` (*Add another endpoint & Backend Step 1*): Initial backend skeleton (`schema.sql`, `database.py`, `config.py`, `test_main.py`), and added `PATCH /api/v1/meetings/{id}/action-items/{item_id}` to frontend `meetingService.ts`, `useMeetingDetail.ts`, `KeyPointsCard.tsx`, and `SummaryTab.tsx`.
- `44ab3eb` (*Restructure project and organize*): Reorganized project into `Frontend/` and root `.gitignore`.

### Detailed File Inventory

#### Backend (`backend/`)
1. `backend/app/main.py`: FastAPI application entrypoint, lifespan DB initializer, CORS middleware, `/health` route, and API router inclusion.
2. `backend/app/core/config.py`: Pydantic `BaseSettings` loading `DB_PATH`, `MEDIA_DIR`, `LLM_MODEL_PATH`, `WHISPER_MODEL`, `MAX_UPLOAD_MB`, and `CORS_ORIGINS`. Contains duplicate validator bug on lines 17–43.
3. `backend/app/core/__init__.py`: Package initialization.
4. `backend/app/db/database.py`: SQLite helpers (`get_db_connection`, `init_db`, `get_db` context manager) enabling foreign keys and schema execution.
5. `backend/app/db/schema.sql`: DDL for `meetings`, `transcript_segments`, `speakers`, `action_items`, `windows`, and `transcript_fts` (FTS5) with sync triggers and foreign key indexes.
6. `backend/app/db/__init__.py`: Package initialization.
7. `backend/app/routers/meetings.py`: FastAPI APIRouter declaring `/join`, `/upload`, `""` (list), `/{meeting_id}`, and `/media/{meeting_id}`.
8. `backend/app/routers/__init__.py`: Package initialization.
9. `backend/app/schemas/meeting.py`: Pydantic schemas for meeting payloads, lists, and detail responses.
10. `backend/app/services/mappers.py`: Unused helper functions to map DB snake_case columns to camelCase API responses and map status values.
11. `backend/app/services/meeting_service.py`: Business logic for join, upload, list, detail, and media file path resolution. Contains syntax/runtime bug in URL validator.
12. `backend/app/services/__init__.py`: Package initialization.
13. `backend/scratch/test_media_path.py`: Ad-hoc scratch script that calls `get_media_path('nonexistent')` at module top-level (causes pytest collection failure).
14. `backend/scratch/test_media_path2.py`: Duplicate scratch script with `sys.path` append (causes pytest collection failure).
15. `backend/tests/test_main.py`: Pytest test verifying `/health` response and SQLite table creation.
16. `backend/tests/__init__.py`: Package initialization.
17. `backend/requirements.txt`: Python package requirements (`fastapi`, `uvicorn`, `python-multipart`, `pydantic`, `pydantic-settings`, `pytest`, `httpx`).
18. `backend/.env.example`: Configuration environment template.
19. `backend/.gitignore`: Backend directory ignore rules.
20. `backend/README.md`: Setup, installation, test, and execution documentation.
21. `backend/FRONTEND_MISMATCH.md`: Detailed field-by-field schema vs frontend type discrepancy documentation.

#### Frontend (`Frontend/src/`)
1. `Frontend/src/main.tsx`: React DOM root mounting script.
2. `Frontend/src/vite-env.d.ts`: Vite environment type declarations.
3. `Frontend/src/app/App.tsx`: Top-level application shell with React Router setup.
4. `Frontend/src/app/routes.tsx`: Route path mapping (`/` and `/:id`).
5. `Frontend/src/components/common/Badge.tsx`: Reusable status and category pill badge.
6. `Frontend/src/components/common/Button.tsx`: Reusable styled button component.
7. `Frontend/src/components/common/Card.tsx`: Reusable card wrapper component.
8. `Frontend/src/components/common/EmptyState.tsx`: Reusable placeholder for empty data views.
9. `Frontend/src/components/common/ErrorState.tsx`: Reusable error view with retry handler.
10. `Frontend/src/components/common/Input.tsx`: Reusable form input element.
11. `Frontend/src/components/common/LoadingState.tsx`: Reusable spinner loader component.
12. `Frontend/src/components/common/Tabs.tsx`: Reusable tab button selector.
13. `Frontend/src/components/common/Toast.tsx`: Floating notification toast for success/error alerts.
14. `Frontend/src/components/detail/KeyPointsCard.tsx`: 4-quadrant summary card with interactive action item checklist.
15. `Frontend/src/components/detail/MeetingDetailsView.tsx`: Main meeting details layout switching between Summary and Transcript.
16. `Frontend/src/components/detail/MeetingHeader.tsx`: Meeting title, date, folder display, share modal, and PDF export trigger.
17. `Frontend/src/components/detail/OverviewCard.tsx`: Collapsible executive overview section.
18. `Frontend/src/components/detail/ParticipantAnalytics.tsx`: Analytics dashboard card (sentiment, pace, engagement).
19. `Frontend/src/components/detail/SpeakersCard.tsx`: Card containing tabs for Speakers table and Topics list.
20. `Frontend/src/components/detail/SpeakersTab.tsx`: Standalone speaker breakdown component.
21. `Frontend/src/components/detail/SpeakerTimeline.tsx`: Colored speaker talk-time bar component.
22. `Frontend/src/components/detail/SummaryTab.tsx`: Alternative summary view with progress, challenges, action items, next steps.
23. `Frontend/src/components/detail/TopicsTab.tsx`: Standalone topic segmentation component with seek controls.
24. `Frontend/src/components/detail/TranscriptCard.tsx`: Searchable transcript box with speaker utterances.
25. `Frontend/src/components/detail/TranscriptTab.tsx`: Full transcript view with text search and speaker dropdown filter.
26. `Frontend/src/components/detail/VideoPlayer.tsx`: Video/audio preview area with 5-webcam participant grid and video controls.
27. `Frontend/src/components/layout/AppLayout.tsx`: Shared application layout wrapping Navbar, main content, and Footer.
28. `Frontend/src/components/layout/Footer.tsx`: Application footer with copyright and links.
29. `Frontend/src/components/layout/Navbar.tsx`: Top navigation bar with logo and notifications.
30. `Frontend/src/components/meeting/MeetingCard.tsx`: Card representing a meeting in the recent meetings list.
31. `Frontend/src/components/meeting/MeetingMomentSearch.tsx`: Search box for filtering meeting moments.
32. `Frontend/src/components/meeting/NewMeetingSection.tsx`: Container switching between URL join and media upload modes.
33. `Frontend/src/components/meeting/OnlineMeetingInput.tsx`: Form for meeting URL, language, and slot name.
34. `Frontend/src/components/meeting/RecentMeetingsList.tsx`: Grid view of recent meetings with selection handler.
35. `Frontend/src/components/meeting/UploadMeetingInput.tsx`: File upload interface with drag-and-drop and slot selection.
36. `Frontend/src/constants/appConstants.ts`: App name, supported languages, slot presets, and mock fallback configuration.
37. `Frontend/src/constants/meetingConstants.ts`: Meeting status constants.
38. `Frontend/src/constants/routes.ts`: Route path string constants.
39. `Frontend/src/hooks/useMeetingDetail.ts`: Custom hook fetching meeting details and handling action-item toggles.
40. `Frontend/src/hooks/useMeetings.ts`: Custom hook fetching meeting lists and triggering join/upload mutations.
41. `Frontend/src/hooks/useShare.ts`: Custom hook for navigator.share and clipboard copying.
42. `Frontend/src/pages/HomePage.tsx`: Main unified dual-pane landing page.
43. `Frontend/src/pages/MeetingDetailPage.tsx`: Dedicated meeting details view page.
44. `Frontend/src/services/api.ts`: Axios client configured with `/api/v1` base URL.
45. `Frontend/src/services/meetingService.ts`: Client API service for join, upload, list, detail, and action-item updates with mock fallback.
46. `Frontend/src/services/mockData.ts`: Static meeting dataset used when API is unreachable.
47. `Frontend/src/styles/index.css`: Global Tailwind CSS imports.
48. `Frontend/src/types/api.ts`: API request/response TypeScript interfaces.
49. `Frontend/src/types/meeting.ts`: Meeting, speaker, transcript, summary, and action item domain interfaces.
50. `Frontend/src/utils/exportPdf.ts`: Browser PDF print formatting utility.
51. `Frontend/src/utils/formatters.ts`: Seconds-to-time and date formatting helpers.

---

## 3. Part 2: API Inventory & Route Discrepancies

### Actual Router Code (`backend/app/routers/meetings.py`)

| Method | Path | Request Body / Params | Response Model | Status Codes Returned |
|---|---|---|---|---|
| `POST` | `/api/v1/meetings/join` | JSON Body `JoinMeetingRequest` (`meetingUrl`, `language`, `slotName`) | `UploadMeetingResponse` (`meetingId`, `status`) | 200, 422, 500 |
| `POST` | `/api/v1/meetings/upload` | Multipart `file: UploadFile`, Query `language: str`, Query `slotName: str` | `UploadMeetingResponse` (`meetingId`, `status`) | 200, 400, 413, 422, 500 |
| `GET` | `/api/v1/meetings` | Query `limit: int = 50`, `offset: int = 0`, `q: Optional[str] = None` | `List[MeetingListItem]` | 200, 422 |
| `GET` | `/api/v1/meetings/{meeting_id}` | Path `meeting_id: str` | `MeetingDetailResponse` | 200, 404 |
| `GET` | `/api/v1/meetings/media/{meeting_id}` | Path `meeting_id: str` | `FileResponse` (`application/octet-stream`) | 200, 403, 404 |
| `GET` | `/health` *(on root app)* | None | `{"status": "ok"}` | 200 |

### Route Discrepancies & Missing Endpoints

1. **Missing Action Item Endpoint**:
   - `PATCH /api/v1/meetings/{meeting_id}/action-items/{item_id}` with `{ done: boolean }` **does NOT exist in `backend/app/routers/meetings.py`**.
   - No route or service handler was implemented on the backend, even though the frontend actively calls it.
2. **Media URL Route Discrepancy**:
   - In `backend/app/routers/meetings.py#L45`, the route is defined as:
     `@router.get("/media/{meeting_id}")`, which mounts under prefix `/api/v1/meetings` as:
     `GET /api/v1/meetings/media/{meeting_id}`
   - But in `backend/app/services/meeting_service.py#L225`, `get_meeting_detail` generates:
     `response["mediaUrl"] = f"/api/v1/media/{meeting_id}"`
   - These two paths do not match. Any client fetching the returned `mediaUrl` will receive a 404.
3. **Broken URL Validation in `join_meeting`**:
   - In `backend/app/services/meeting_service.py#L24-L41`, the function definition `def _validate_meeting_url(url: str):` was accidentally omitted; the validation logic is placed inside `_media_category` after a `raise` statement.
   - At line 71, `_validate_meeting_url(meeting_url)` is called, which immediately raises `NameError: name '_validate_meeting_url' is not defined`, crashing `POST /api/v1/meetings/join` with HTTP 500.

---

## 4. Part 3: Database & Media Bug Analysis

### Database Resolution & Files on Disk
- **Real `DB_PATH` resolved by app**:  
  `D:\Other Projects\AI_Summary\Mhtechin_AI_summary_generator\backend\chatmeet.db`
- **Real `MEDIA_DIR` resolved by app**:  
  `D:\Other Projects\AI_Summary\Mhtechin_AI_summary_generator\backend\media`
- **Existing `*.db` files in the project**:  
  Only `backend\chatmeet.db`.
  *(Note: This file was created as an empty 0-byte file during pytest collection when `scratch/test_media_path.py` called `sqlite3.connect()`. `init_db()` runs only inside the FastAPI lifespan handler, which was never invoked because pytest crashed during collection).*

### Real SQLite Columns vs `schema.sql`
When initialized, `schema.sql` creates exactly the following schema:
- **`meetings`**: `id` (TEXT PK), `title`, `folder`, `slot_name`, `language`, `source`, `source_url`, `media_path`, `media_type`, `status`, `error`, `duration_seconds`, `processed_seconds`, `created_at`, `overview`, `project_progress`, `challenges`, `next_steps`.
- **`transcript_segments`**: `id` (INTEGER PK), `meeting_id` (TEXT FK), `start_time`, `end_time`, `speaker`, `text`.
- **`speakers`**: `id` (INTEGER PK), `meeting_id` (TEXT FK), `name`, `color`, `talk_seconds`, `talk_percent`, `listen_percent`.
- **`action_items`**: `id` (TEXT PK), `meeting_id` (TEXT FK), `text`, `owner`, `deadline`, `done` (INTEGER).
- **`windows`**: `id` (INTEGER PK), `meeting_id` (TEXT FK), `window_index`, `start_time`, `end_time`, `result_json`.
- **`transcript_fts`**: FTS5 virtual table on `transcript_segments.text`.

### Root Cause of "no such column: meeting_id"
- **Root Cause**: The `meetings` table defines its primary key column as `id` (`backend/app/db/schema.sql#L5`), whereas related child tables (`transcript_segments`, `speakers`, `action_items`, `windows`) use `meeting_id` as the foreign key column.
- **Evidence**:
  1. In `backend/app/services/mappers.py#L13`:  
     `"meetingId": str(row.get("meeting_id") or row.get("id"))`  
     shows prior confusion assuming `meetings` contained a column named `meeting_id`.
  2. In `backend/app/services/meeting_service.py#L152, L158`:  
     Comments explicitly note `# Core meeting record – primary key column is id` and query `WHERE id = ?`, fixing an earlier bug where `SELECT * FROM meetings WHERE meeting_id = ?` was executed.
  3. In `backend/app/services/meeting_service.py#L231`:  
     `get_media_path` correctly uses `SELECT media_path FROM meetings WHERE id = ?`.

### Media File Existence
- `backend/app/services/meeting_service.py#L241-L242` checks:
  `if not path.is_file(): raise HTTPException(status_code=404, detail="Media file missing")`
- Currently, `backend/media/` contains **0 files and 0 directories**. No uploaded files exist on disk, so all media requests return 404.

---

## 5. Part 4: Check Against Decisions

| # | Decision Item | Status | Evidence (File & Line) |
|---|---|---|---|
| **1** | **Transcript stored as one row per sentence in `transcript_segments`** | **PARTIAL** | Table `transcript_segments` exists in `backend/app/db/schema.sql#L26-L33`, and `get_meeting_detail` queries it in `backend/app/services/meeting_service.py#L172-L176`. However, no audio processing or transcript ingestion logic exists yet; no rows are created on upload or join. |
| **2** | **Action-item ticks saved via PATCH endpoint; frontend calls it with optimistic tick & rollback** | **PARTIAL** | **Frontend is DONE**: `Frontend/src/hooks/useMeetingDetail.ts#L35-L135`, `Frontend/src/services/meetingService.ts#L237-L312`, and `Frontend/src/components/detail/KeyPointsCard.tsx#L70-L100` implement optimistic tick, API dispatch, undo on failure, and toast display. **Backend is NOT DONE**: `backend/app/routers/meetings.py` and `backend/app/services/meeting_service.py` completely lack the PATCH endpoint. |
| **3** | **REMOVED from frontend**: `TopicsTab`, Topics in Speakers card, sentiment, concerns, question count, engagement score, severity badges on challenges, status pills on progress items, and `taskTimeLabel` | **NOT DONE** | **None of these have been removed**: <br>• `TopicsTab.tsx` still exists (`Frontend/src/components/detail/TopicsTab.tsx`). <br>• Topics tab still in Speakers card (`Frontend/src/components/detail/SpeakersCard.tsx#L38-L50, L115-L160`). <br>• Sentiment still present (`Frontend/src/components/detail/SpeakersTab.tsx#L61-L66`, `Frontend/src/components/detail/ParticipantAnalytics.tsx#L14-L17`). <br>• Concerns still present (`Frontend/src/components/detail/ParticipantAnalytics.tsx#L89, L108`). <br>• Question count and engagement score still present (`Frontend/src/components/detail/ParticipantAnalytics.tsx#L19, L22`). <br>• Severity badges on challenges still present (`Frontend/src/components/detail/SummaryTab.tsx#L45, L153`). <br>• Status pills on progress items still present (`Frontend/src/components/detail/SummaryTab.tsx#L32, L127`). <br>• `taskTimeLabel` still present (`Frontend/src/types/meeting.ts#L70`, `Frontend/src/components/detail/SpeakersCard.tsx#L61, L81`, `Frontend/src/services/mockData.ts#L94`). |
| **4** | **KEPT in frontend**: transcript search, speaker filter, slot presets, Navbar, Footer | **DONE** | • Transcript search: `Frontend/src/components/detail/TranscriptCard.tsx#L28-L37` & `TranscriptTab.tsx#L34-L43`. <br>• Speaker filter: `Frontend/src/components/detail/TranscriptTab.tsx#L46-L50`. <br>• Slot presets: `Frontend/src/constants/appConstants.ts#L18-L26`. <br>• Navbar: `Frontend/src/components/layout/Navbar.tsx`. <br>• Footer: `Frontend/src/components/layout/Footer.tsx`. |
| **5** | **`mockData.ts` deleted or only used behind dev flag** | **PARTIAL** | Not deleted. Imported in `Frontend/src/services/meetingService.ts#L10` and used in fallback branches guarded by `APP_CONFIG.ENABLE_MOCK_FALLBACK` (`meetingService.ts#L28, L105, L183, L216, L254`). |
| **6** | **Five-webcam portrait grid replaced by speaker tiles; audio-only recording shows audio player** | **NOT DONE** | In `Frontend/src/components/detail/VideoPlayer.tsx#L77-L138`, the hardcoded 5-participant Unsplash image grid ("Brian Walker", "Emily Wilson", "Alex Brown", "Noah Reynolds") is still present. No dynamic speaker tiles or dedicated audio player component exist. |
| **7** | **Detail page shows clear message while status is processing/failed, and shows processed time out of total time** | **NOT DONE** | In `Frontend/src/pages/MeetingDetailPage.tsx#L22-L51` and `Frontend/src/components/detail/MeetingDetailsView.tsx#L83-L105`, only generic loading and "Summary not available" messages appear. `meeting.status` ('processing' / 'failed') is not checked, and `processed_seconds` is never rendered. |
| **8** | **Status mapping `pending` → `scheduled` and `done` → `completed` exists only in mappers; stored value never changed** | **PARTIAL** | DB stores `'pending'` and `'done'`. `backend/app/services/mappers.py#L29-L34` defines `_map_status`. However, `mappers.py` is **dead code** (never imported). `meeting_service.py#L148, L215` returns raw unmapped DB values (`'pending'`/`'done'`), while `join_meeting` (`L84`) and `upload_meeting` (`L123`) return hardcoded `"scheduled"`. |
| **9** | **No fabricated data anywhere** | **FAIL** | Multiple locations invent data: <br>• `backend/app/services/meeting_service.py#L104-L105`: invents title from filename stem. <br>• `backend/app/services/meeting_service.py#L225`: invents incorrect media URL. <br>• `Frontend/src/services/mockData.ts`: 305 lines of fabricated meetings, avatars, transcripts, and metrics. <br>• `Frontend/src/services/meetingService.ts#L29-L79, L106-L157, L223-L226`: creates fake BigBuckBunny media URLs, fake scores, and re-assigns ID of first mock meeting if ID not found. <br>• `Frontend/src/components/detail/VideoPlayer.tsx#L77-L154`: hardcoded Unsplash webcam images and fake timeline width percentages. <br>• `Frontend/src/components/detail/SpeakersCard.tsx#L81, L102-L108, L150-L156`: hardcoded '25m' task times and hardcoded fallback speaker/topic lists. <br>• `Frontend/src/components/detail/MeetingHeader.tsx#L28-L30`: defaults missing folder to 'General', date to 'Today', duration to '45 mins'. |

---

## 6. Part 5: Verification Suite Results

### 1. Pytest (`backend/`)
- **Command**: `.\.venv\Scripts\python.exe -m pytest -q` (executed from `backend/`)
- **Result**: **FAILED (2 Errors)**
- **Output**:
  ```
  ERROR scratch/test_media_path.py - sqlite3.OperationalError: no such table: meetings
  ERROR scratch/test_media_path2.py - sqlite3.OperationalError: no such table: meetings
  2 warnings, 2 errors in 1.44s
  ```
- **Cause**: Pytest auto-discovered `backend/scratch/test_media_path.py` and `test_media_path2.py`. Both files execute top-level database queries before tables are created.

### 2. Ruff Check (`backend/`)
- **Command**: `.\.venv\Scripts\python.exe -m ruff check .` (executed from `backend/`)
- **Result**: **FAILED**
- **Output**:
  ```
  No module named ruff
  ```
- **Cause**: `ruff` is not listed in `backend/requirements.txt` and is not installed in `.venv`.

### 3. Frontend Type Check (`Frontend/`)
- **Command**: `npx tsc --noEmit` (executed from `Frontend/`)
- **Result**: **PASSED** (Exit Code 0, 0 errors).

### 4. Frontend Production Build (`Frontend/`)
- **Command**: `npm run build` (executed from `Frontend/`)
- **Result**: **PASSED** (Exit Code 0, built in 8.49s).

### 5. Upload-then-Media Test Coverage
- **Finding**: **NOT DONE / INSERTS BY HAND (NONE AT ALL)**.
- **Evidence**: `backend/tests/test_main.py` contains only `test_health_and_database_tables`, which calls `/health` and inspects `sqlite_master`. There are **zero tests** that execute `POST /api/v1/meetings/upload` and then request `GET /api/v1/meetings/media/{id}`.

---

## 7. Risks for Steps 3A, 3B, and Step 4

1. **`join_meeting` Runtime Crash (Step 3A/4)**:
   Calling `join_meeting()` in `backend/app/services/meeting_service.py#L71` crashes with `NameError: name '_validate_meeting_url' is not defined`. Any online meeting join will fail with HTTP 500.
2. **Pytest CI/CD Blocking (Step 3B/4)**:
   The presence of `backend/scratch/test_media_path*.py` will fail any future `pytest` run in CI or test runners, blocking automated test pipelines.
3. **Media Playback Breakage in Frontend (Step 3B/4)**:
   Because the backend returns `mediaUrl = "/api/v1/media/{meeting_id}"` while the FastAPI router is registered at `/api/v1/meetings/media/{meeting_id}`, the frontend `<video>` and audio players will receive 404 errors for all processed media.
4. **Action Item Sync Failure (Step 4)**:
   When frontend users check an action item, the frontend dispatches `PATCH /api/v1/meetings/{id}/action-items/{item_id}`. Because this endpoint does not exist on the backend, the request fails, reverting the checkbox and showing an error toast.
5. **Background Worker Schema Incompatibility (Step 4)**:
   `meetings.status` in the DB accepts `'pending' | 'processing' | 'done' | 'failed'`. The backend services currently return unmapped status strings to the frontend, which expects `'scheduled' | 'processing' | 'completed' | 'failed'`. Background workers transitioning jobs to `'done'` will cause the frontend to display unexpected status badges unless mappers are integrated.
6. **FTS5 Synchronization During Long Transcriptions (Step 3A/4)**:
   `schema.sql` triggers sync `transcript_fts` on every single row insertion into `transcript_segments`. Inserting thousands of Whisper utterance segments in individual transactions will degrade SQLite write performance unless wrapped in a single batch transaction.

---

## 8. Recommended Fix List (Smallest & Safest First)

1. **Fix `_validate_meeting_url` definition**: Restore the `def _validate_meeting_url(url: str):` signature on line 26 of `backend/app/services/meeting_service.py`.
2. **Remove or move scratch test files**: Delete or rename `backend/scratch/test_media_path.py` and `test_media_path2.py` so pytest does not collect them.
3. **Remove duplicate validator in `config.py`**: Delete the redundant `assemble_cors_origins` method and duplicate `CORS_ORIGINS` declaration in `backend/app/core/config.py`.
4. **Fix media route path alignment**: Align `response["mediaUrl"] = f"/api/v1/meetings/media/{meeting_id}"` in `backend/app/services/meeting_service.py#L225` with the router path in `backend/app/routers/meetings.py#L45`.
5. **Implement backend `PATCH` action-item route**: Add `PATCH /meetings/{meeting_id}/action-items/{item_id}` to `backend/app/routers/meetings.py` and update the SQLite `action_items` table.
6. **Connect `mappers.py` in `meeting_service.py`**: Use `map_meeting_row` and `_map_status` in `list_meetings` and `get_meeting_detail` instead of returning raw unmapped DB rows.
7. **Write an end-to-end upload-then-media test**: Add an integration test in `backend/tests/` that uploads a test WAV/MP4 file and verifies media file download.
8. **Remove obsolete frontend components**: Delete `TopicsTab.tsx` and strip sentiment, concerns, question count, and severity badges from `Frontend/src/components/detail/`.
9. **Replace hardcoded webcam grid with dynamic speaker tiles**: Refactor `Frontend/src/components/detail/VideoPlayer.tsx` to render real speaker tiles or an audio player for audio-only uploads.
10. **Implement processing/failure progress UI**: Update `Frontend/src/components/detail/MeetingDetailsView.tsx` to check `meeting.status` and render `processed_seconds` / `duration_seconds`.
