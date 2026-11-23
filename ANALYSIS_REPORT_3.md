# Chatmeet Audit Report 3 (Read-Only)
**Audit Date:** November 23, 2026  
**Audited Repository Path:** `D:\Other Projects\AI_Summary\Mhtechin_AI_summary_generator`  
**Git Branch:** `Neil` | **Commit:** `d4ca035` (`Implement backend Step 3B and Step 4 with transcription and AI summarization pipeline`)  
**Working Tree Status:** Clean (no uncommitted modifications)

---

## 1. Executive Summary Table

### Steps 1 to 3A Quick Recheck
- **Step 1 (Core Infrastructure & SQLite WAL):** `HEALTHY`. WAL mode (`PRAGMA journal_mode=WAL`), `PRAGMA busy_timeout=5000`, foreign keys enabled. All 6 base tables (`meetings`, `transcript_segments`, `speakers`, `action_items`, `windows`, `sqlite_sequence`) and FTS5 virtual table (`transcript_fts`) active and triggered.
- **Step 2 (REST API & Media Serving):** `HEALTHY`. All 5 endpoints (`/join`, `/upload`, `/meetings`, `/meetings/{id}`, `/meetings/{id}/action-items/{id}`) and media streaming endpoint functional; directory traversal tests pass with HTTP 403.
- **Step 3A (LLM Extraction Engine for Single Chunk):** `HEALTHY`. Synchronous `httpx` client in `app/services/llm.py` (`is_server_ready`, `count_tokens`, `generate_json`), `notes_extractor.py` deterministic verification with `source_time` line parsing.

### Detailed Step 3B & Step 4 Audit

| Component | Feature / Requirement | Status | Evidence (File & Line) | Notes / Deviations |
| :--- | :--- | :--- | :--- | :--- |
| **Step 3B** | Token-aware transcript splitting | **DONE** | [`windowing.py:34-93`](file:///d:/Other%20Projects/AI_Summary/Mhtechin_AI_summary_generator/backend/app/services/windowing.py#L34-L93) | Calls `count_tokens(text)` with fallback `math.ceil(len/4)`. Respects `_OVERLAP_SEGMENTS = 2`. Never splits mid-segment. |
| **Step 3B** | Incremental window resume | **PARTIAL** | [`windowing.py:118-149`](file:///d:/Other%20Projects/AI_Summary/Mhtechin_AI_summary_generator/backend/app/services/windowing.py#L118-L149) | Upserts into `windows` table, but does **not** check if window was already extracted; re-runs LLM extraction on every run. `final` parameter omitted. |
| **Step 3B** | Single-window bypass | **DONE** | [`summarizer.py:114-117`](file:///d:/Other%20Projects/AI_Summary/Mhtechin_AI_summary_generator/backend/app/services/summarizer.py#L114-L117) | If `len(window_notes) == 1`, returns `dict(window_notes[0])` directly without invoking an extra merge LLM call. |
| **Step 3B** | Multi-window LLM merge | **PARTIAL (DEFECT)** | [`summarizer.py:59-87`](file:///d:/Other%20Projects/AI_Summary/Mhtechin_AI_summary_generator/backend/app/services/summarizer.py#L59-L87) | Uses executive assistant prompt with `generate_json`. **Defect:** Line 83 calls `verify_notes(raw_summary, "", all_speakers)` with empty string for `chunk_text`, causing line parsing to fail and wiping out all action item `owner` and `deadline` values to `None`. |
| **Step 3B** | Deduplication logic | **DONE** | [`summarizer.py:30-56`](file:///d:/Other%20Projects/AI_Summary/Mhtechin_AI_summary_generator/backend/app/services/summarizer.py#L30-L56) | Action items deduplicated by normalized lowercase text. Key lists (`project_progress`, `challenges`, `next_steps`) deduplicated via set of stripped strings. |
| **Step 3B** | Merge persistence & UUID preservation | **DONE** | [`summarizer.py:133-195`](file:///d:/Other%20Projects/AI_Summary/Mhtechin_AI_summary_generator/backend/app/services/summarizer.py#L133-L195) | Updates `meetings.overview` and JSON list columns. Reconciles action items: matches existing text to preserve original UUID and `done` toggle state. |
| **Step 4** | Media duration probe (`ffprobe`) | **DONE** | [`audio.py:23-51`](file:///d:/Other%20Projects/AI_Summary/Mhtechin_AI_summary_generator/backend/app/services/audio.py#L23-L51) | Executes `ffprobe` via `subprocess.run` with list arguments (`shell=False`). Parses float seconds safely. |
| **Step 4** | Audio extraction to 16kHz WAV | **DONE** | [`audio.py:54-106`](file:///d:/Other%20Projects/AI_Summary/Mhtechin_AI_summary_generator/backend/app/services/audio.py#L54-L106) | Executes `ffmpeg -y -i <in> -vn -acodec pcm_s16le -ar 16000 -ac 1 <out>`. Note: line 76 has minor logic bug `and not ... exists()` instead of `or`. |
| **Step 4** | Temporary WAV lifecycle | **DONE** | [`audio.py:109-142`](file:///d:/Other%20Projects/AI_Summary/Mhtechin_AI_summary_generator/backend/app/services/audio.py#L109-L142) | Context manager `extract_temporary_wav` yields `(Path, duration)` and cleans up the WAV file in a `finally:` block. |
| **Step 4** | Whisper Model singleton & transcription | **DONE** | [`transcription.py:20-64`](file:///d:/Other%20Projects/AI_Summary/Mhtechin_AI_summary_generator/backend/app/services/transcription.py#L20-L64) | Lazy singleton initialization for `WhisperModel`. Runs with `vad_filter=True`, `beam_size=5`. Defers speaker diarization to Step 5 (`speaker: None`). |
| **Step 4** | Transcript persistence & progress tracking | **DONE** | [`transcription.py:67-111`](file:///d:/Other%20Projects/AI_Summary/Mhtechin_AI_summary_generator/backend/app/services/transcription.py#L67-L111) | Deletes stale segments on retry, bulk inserts new segments (triggers FTS5 triggers), updates `duration_seconds` and `processed_seconds`. |
| **Step 4** | Silence handling | **DONE** | [`pipeline.py:75-87`](file:///d:/Other%20Projects/AI_Summary/Mhtechin_AI_summary_generator/backend/app/services/pipeline.py#L75-L87) | If `segments` is empty, writes `overview="[No speech detected in audio file]"`, sets `status='completed'`, and exits cleanly. |
| **Step 4** | Pipeline Orchestration | **DONE** | [`pipeline.py:32-123`](file:///d:/Other%20Projects/AI_Summary/Mhtechin_AI_summary_generator/backend/app/services/pipeline.py#L32-L123) | Orchestrates WAV extraction -> Whisper -> segments -> LLM ready check -> windowing -> merge & persist -> `status='completed'`. Short DB transactions avoid lock contention. |
| **Step 4** | Background Worker & claim | **DONE** | [`worker.py:15-40`](file:///d:/Other%20Projects/AI_Summary/Mhtechin_AI_summary_generator/backend/app/services/worker.py#L15-L40) | Atomic claim: `SELECT ... WHERE status='pending' AND source='upload'` followed by `UPDATE ... SET status='processing' WHERE id=? AND status='pending'`. |
| **Step 4** | Startup recovery of interrupted meetings | **DONE** | [`worker.py:43-54`](file:///d:/Other%20Projects/AI_Summary/Mhtechin_AI_summary_generator/backend/app/services/worker.py#L43-L54) | Resets `status='processing'` back to `'pending'` on worker startup so interrupted jobs are retried. |
| **Step 4** | Async Worker Loop & Threadpool offloading | **DONE** | [`worker.py:57-93`](file:///d:/Other%20Projects/AI_Summary/Mhtechin_AI_summary_generator/backend/app/services/worker.py#L57-L93) | Runs `process_meeting_pipeline` via `asyncio.to_thread` to prevent blocking FastAPI's event loop. Traps errors into `meetings.error`. |
| **Step 4** | Lifespan integration | **DONE** | [`main.py:9-16`](file:///d:/Other%20Projects/AI_Summary/Mhtechin_AI_summary_generator/backend/app/main.py#L9-L16) | Starts worker in FastAPI lifespan context; cancels task and awaits clean exit on server shutdown. |
| **Frontend/API** | Detail Schema & Mapper contract | **PARTIAL (DEFECT)** | [`mappers.py:60-70`](file:///d:/Other%20Projects/AI_Summary/Mhtechin_AI_summary_generator/backend/app/services/mappers.py#L60-L70), [`TranscriptCard.tsx:20`](file:///d:/Other%20Projects/AI_Summary/Mhtechin_AI_summary_generator/Frontend/src/components/detail/TranscriptCard.tsx#L20) | Backend returns `{startTime, endTime, speaker, text}`; Frontend expects `{timestampStart, timestampEnd, speakerName, speakerColor, text}`. Calling `t.speakerName.toLowerCase()` causes a client-side JavaScript crash. |

---

## 2. Direct Answer: Can the User Start the Backend, Upload a Meeting, and Get an AI Summary Today?

### **No.** 
If a user starts the backend and uploads a meeting today, the pipeline will **immediately crash and fail**. Furthermore, starting the backend today will cause the background worker to immediately fail 10 existing uploaded meetings.

### The Exact Blockers (in required order of resolution):

1. **Missing `ffmpeg` and `ffprobe` Binaries on System PATH:**
   - **Current State:** Both `ffmpeg -version` and `ffprobe -version` return `CommandNotFoundException`.
   - **Impact if not solved:** The moment `get_media_duration` or `extract_temporary_wav` is invoked, Python raises `FileNotFoundError: ffprobe binary not found` or `ffmpeg binary not found`. The meeting status is marked `failed`.
2. **Missing `faster-whisper` Python Package in Virtual Environment:**
   - **Current State:** `pip show faster-whisper` returns `Package(s) not found: faster-whisper`.
   - **Impact if not solved:** When `transcription.py` executes `from faster_whisper import WhisperModel`, it raises `ModuleNotFoundError: No module named 'faster_whisper'`.
3. **Missing Whisper Model Weights in Local Cache:**
   - **Current State:** Local HuggingFace cache (`~/.cache/huggingface/download`) contains only `Qwen2.5-1.5B-Instruct.Q8_0.gguf`. No Whisper model files exist.
   - **Impact if not solved:** When initialized without pre-downloaded weights, `faster-whisper` will attempt to connect to HuggingFace Hub to download the `base` model. If the machine is offline or blocked by corporate proxies, initialization throws an unhandled network error.
4. **`llama-server` is Offline:**
   - **Current State:** `http://127.0.0.1:8080/health` refused connection (`[WinError 10061]`).
   - **Impact if not solved:** After audio transcription completes, `pipeline.py` checks `is_server_ready()`. Because the server is offline, it raises `LLMUnavailable` and marks the meeting as `failed`.
5. **Multi-Window LLM Merge Action Item Wipeout (Code Defect):**
   - **Current State:** `summarizer.py:83` passes `chunk_text=""` into `verify_notes`.
   - **Impact if not solved:** For any meeting that spans 2 or more windows (roughly >2-3 minutes of speaking), `verify_notes` finds no matching transcript lines, stripping `owner` and `deadline` from **all** action items and setting them to `None`.
6. **Frontend-Backend Contract Mismatch in Transcript Utterances (Crash Defect):**
   - **Current State:** Backend `map_transcript_rows` returns `startTime`, `endTime`, and `speaker`. Frontend `TranscriptCard.tsx:20` and `TranscriptTab.tsx:24` call `t.speakerName.toLowerCase()`.
   - **Impact if not solved:** When viewing any completed meeting that has a transcript, the browser crashes with `TypeError: Cannot read properties of undefined (reading 'toLowerCase')`.

---

## 3. Code vs Decision Mismatches

1. **`verify_notes` Called with Empty String in Multi-Window Summarizer:**
   - *Specified/Intended:* `verify_notes` checks that every action-item owner is backed by an explicit commitment phrase spoken at that `source_time`.
   - *What the Code Does:* [`summarizer.py:83`](file:///d:/Other%20Projects/AI_Summary/Mhtechin_AI_summary_generator/backend/app/services/summarizer.py#L83) passes `verify_notes(raw_summary, "", all_speakers)`. With `chunk_text=""`, parsed lines are empty, so every single action item has its `owner` and `deadline` overwritten with `None`.
2. **Missing `final` Parameter in Windowing Functions:**
   - *Previous Specifications:* Windowing was proposed to accept a `final: bool` parameter to differentiate between live intermediate chunks and final end-of-meeting summarization.
   - *What the Code Does:* [`windowing.py`](file:///d:/Other%20Projects/AI_Summary/Mhtechin_AI_summary_generator/backend/app/services/windowing.py) accepts only `(meeting_id, segments, conn)`. No `final` flag exists.
3. **Path Traversal Security Check in `audio.py`:**
   - *Intended:* Deny access to any media file outside `MEDIA_DIR`.
   - *What the Code Does:* Line 76:
     ```python
     if not resolved_input.is_relative_to(media_root) and not resolved_input.exists():
         raise PermissionError(...)
     ```
     Because of `and not`, if a path is outside `MEDIA_DIR` but *does* exist on the host system (e.g. `C:\Windows\System32\drivers\etc\hosts`), the check evaluates to `True and False == False`, bypassing the security check! It should be `if not resolved_input.is_relative_to(media_root):`.
4. **Environment Configuration vs `.env.example`:**
   - *Settings in `app/core/config.py`:* `WHISPER_MODEL`, `WHISPER_DEVICE`, `WHISPER_COMPUTE_TYPE`, `FFMPEG_PATH`, `FFPROBE_PATH`, `WORKER_POLL_INTERVAL`, `ENABLE_BACKGROUND_WORKER`, `MAX_UPLOAD_MB`.
   - *Missing from `.env.example`:* `WHISPER_DEVICE`, `WHISPER_COMPUTE_TYPE`, `FFMPEG_PATH`, `FFPROBE_PATH`, `WORKER_POLL_INTERVAL`, `ENABLE_BACKGROUND_WORKER`.
5. **`.gitignore` Gaps for SQLite WAL and SHM Files:**
   - `chatmeet.db-wal` and `chatmeet.db-shm` are generated whenever SQLite runs in WAL mode. `git check-ignore chatmeet.db-wal` confirmed that these files are **not** ignored.

---

## 4. Risks for the First Real Run

### A. Automatic Processing of the 10 Existing Pending Meetings
Inspection of the real database (`backend/chatmeet.db`) reveals **10 meetings** currently in `status='pending'` with `source='upload'`:
- `8639fc87...` (`sample_meeting` - `original.wav` exists)
- `fbcf370c...` (`FUNK ÓPTICA` - `original.mp3` exists)
- `4abf3ffe...` (`Amor Na Praia` - `original.mp3` exists)
- `f4e58146...` (`Amor Na Praia` - `original.mp3` exists)
- `b325390f...` (`Final1` - `original.mp4` exists)
- `d1120072...` (`Final1` - `original.mp4` exists)
- `509fbd58...` (`Final2` - `original.mp4` exists)
- `29ac71a2...` (`stream` - `original.mp4` exists)
- `8bfda94e...` (`clip` - `original.mp4` exists)
- `98f667c5...` (`Final2` - `original.mp4` exists)

**What will happen on server start:**
The background worker starts immediately upon `lifespan(app)` startup.
1. If `ffmpeg` or `faster-whisper` are missing, the worker will iterate through all 10 meetings, failing them in rapid succession and writing error messages to `meetings.error`.
2. If dependencies *are* installed and `ENABLE_BACKGROUND_WORKER=True`, the worker will sequentially execute `ffmpeg`, Whisper, and `llama-server` on all 10 audio and video files.

### B. CPU and RAM Load on Real Media
- Running `faster-whisper` (`base` model on CPU `int8`) will consume 100% of available CPU cores during audio transcription.
- Running `llama-server` concurrently on CPU with a 1.5B model will also take 100% of CPU during token generation.
- If both execute or if requests arrive while the worker is processing large `.mp4` video files (e.g. `stream`, `clip`), the host machine will experience extreme CPU throttling and memory pressure.

### C. Action-Item Owners When Speakers are Unknown
In Step 4, `transcription.py` yields `speaker: None`. When window segments are formatted for LLM chunk extraction:
- Utterances are formatted as `[mm:ss] Unknown Speaker: text`.
- If a speaker line contains a commitment phrase (e.g. `"I will make sure this gets pushed today"`), `verify_notes` assigns `owner = line_speaker`.
- Because the speaker name is `"Unknown Speaker"`, the resulting action item owner is set to the literal string `"Unknown Speaker"`, rather than `null`.

### D. Timeouts During Chunk Extraction
- `LLM_TIMEOUT_SECONDS` is set to `300` (5 minutes) in `config.py`.
- If an uploaded meeting is 30 minutes long, it splits into 6–10 windows. At ~3 to 4 minutes per chunk on a CPU-bound `llama-server`, end-to-end processing will take 20 to 40 minutes per meeting.

---

## 5. Dead Code and Cleanup List

1. **Unused Imports and Deprecated Syntax (82 Ruff Warnings):**
   - `backend/app/core/config.py`: `typing.List`, `typing.Union` deprecated in Python 3.12+ (use `list`, `X | Y`).
   - `backend/app/db/database.py`: Unused import `import os`.
   - `backend/app/services/windowing.py`: Unused import `math`.
   - `backend/tests/test_step4.py`: Unused imports `json`, `sqlite3`, `subprocess`.
2. **Missing Speaker Fallback in `map_transcript_rows`:**
   - In `app/services/mappers.py:60-70`, `map_transcript_rows` maps DB columns to dictionary keys that omit `timestampStart`, `timestampEnd`, `speakerName`, and `speakerColor`.
3. **Inconsistent Status String in `pipeline.py`:**
   - `pipeline.py:118` writes `status = 'completed'` directly to SQLite, whereas `mappers.py:29` expects DB status to be `'done'` and maps `'done' -> 'completed'`. While harmless due to passthrough, it violates internal consistency.

---

## 6. Look Ahead: Step 5 (Diarization), WebSockets, and FTS5

1. **Step 5 (Speaker Diarization):**
   - *Current Code:* `transcription.py` sets `speaker = None`. The `speakers` table in SQLite has 0 rows across all meetings.
   - *Impact on Pipeline:* When diarization is integrated (e.g. PyAnnote or simple clustering), segments must be tagged with real speaker identifiers before `process_transcript_windows` is called.
   - *What Must Be Refactored:* `verify_notes` currently treats `"Unknown Speaker"` as a valid name because it appears in `all_speakers`. The verification logic must explicitly reject `"Unknown Speaker"` and `"Unknown"` as valid action item owners.
2. **Streaming WebSocket:**
   - The current pipeline architecture is purely batch-driven (`process_meeting_pipeline` takes a complete `media_path` and transcribes the entire file at once).
   - For live meetings (`source='join'`), audio chunks arrive incrementally via WebSockets. The batch file context manager `extract_temporary_wav` cannot be used for streaming frames.
3. **FTS5 Full-Text Search:**
   - Triggers on `transcript_segments` (`transcript_ai`, `transcript_ad`, `transcript_au`) work correctly and automatically update `transcript_fts`.
   - The `/meetings?q=...` endpoint uses `transcript_fts MATCH ?` with `bm25()` ranking. This is completely functional and ready for search queries once transcripts are persisted.

---

## 7. Prioritized One-Line Fix List

1. **[Config / Git]** Add `chatmeet.db-wal` and `chatmeet.db-shm` to `.gitignore`.
2. **[Dependencies]** Install `ffmpeg` & `ffprobe` binaries onto system PATH and verify via terminal.
3. **[Dependencies]** Install `faster-whisper==1.2.1` in `backend/.venv` via `pip install faster-whisper==1.2.1`.
4. **[Security]** In `backend/app/services/audio.py:76`, fix path traversal logic by removing `and not resolved_input.exists()`.
5. **[Code Defect]** In `backend/app/services/summarizer.py:83`, pass the concatenated window text instead of `""` to `verify_notes` so action-item owners are not cleared.
6. **[Code Defect]** In `backend/app/services/notes_extractor.py:151`, forbid assigning `"Unknown Speaker"` or `"Unknown"` as an action-item owner.
7. **[API Contract]** In `backend/app/services/mappers.py:60-70`, alias transcript fields to include `timestampStart`, `timestampEnd`, `speakerName` (defaulting to `"Speaker"`), and `speakerColor`.
8. **[DB Hygiene]** Decide whether to clear or reset the 10 pending meetings in `chatmeet.db` before restarting the worker to prevent CPU overload.
9. **[Config]** Update `.env.example` with missing Step 4 configuration variables (`WHISPER_DEVICE`, `WHISPER_COMPUTE_TYPE`, `FFMPEG_PATH`, etc.).
10. **[Linter]** Run `ruff check --fix .` across `backend/` to resolve the 82 formatting and import warnings.
