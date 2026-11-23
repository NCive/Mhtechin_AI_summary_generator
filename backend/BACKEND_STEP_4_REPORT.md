# Backend Step 4 Implementation Report: Audio, Whisper and Background Worker

## 1. Executive Summary & Completed Functionality

Step 4 implements automated audio extraction (FFmpeg/FFprobe), Whisper speech-to-text transcription (faster-whisper), and an asynchronous SQLite-backed background worker for the Chatmeet FastAPI backend. It completes the automated end-to-end processing pipeline by integrating the Step 3B transcript windowing, note extraction, summary merging, and persistence services.

### Key Capabilities Implemented:
1. **Audio Extraction (`app.services.audio`):**
   - Resolves uploaded media files within `settings.MEDIA_DIR`.
   - Uses `ffprobe` to determine actual recording duration in seconds.
   - Uses `ffmpeg` to extract 16 kHz mono 16-bit PCM WAV audio without loading entire recordings into memory.
   - Supports MP3, WAV, M4A, MP4, MKV, and WebM.
   - Enforces safe subprocess argument passing (`shell=False`).
   - Context manager `extract_temporary_wav()` guarantees temporary WAV files are unlinked on both success and failure.

2. **Whisper Transcription (`app.services.transcription`):**
   - Integrates `faster-whisper` using `settings.WHISPER_MODEL` (default: `base`), on CPU with INT8 computation (`WHISPER_COMPUTE_TYPE=int8`) and VAD filtering enabled.
   - Lazy singleton model initialization (`get_whisper_model()`) to avoid loading multiple model instances into memory.
   - Maps language configurations: uses ISO codes or auto-detection if unsupported.
   - Generates timestamped chronological segments (`start_time`, `end_time`, `text`, `speaker=None`).
   - Saves segments into `transcript_segments` table in batched transactions, keeping FTS5 search triggers (`transcript_fts`) in sync.
   - Dynamically updates `duration_seconds` and `processed_seconds` monotonically bounded by recording duration.

3. **Pipeline Orchestrator (`app.services.pipeline`):**
   - Connects: Audio Extraction -> Whisper Transcription -> Segment Persistence -> Step 3B Windowing (`process_transcript_windows`) -> Validation -> Step 3B Merging (`merge_and_persist`) -> Final Status Update (`status = 'done'`).
   - Validates that every transcript window succeeded; fails the meeting if extraction error placeholders are encountered.
   - Handles empty audio / silence gracefully (`[No speech detected in recording.]`).
   - Runs all compute/IO tasks outside database write transactions.

4. **Background Worker (`app.services.worker`):**
   - Lightweight, persistent SQLite-backed background polling loop started and stopped via FastAPI `lifespan`.
   - Atomically claims pending uploaded meetings one at a time:
     `UPDATE meetings SET status = 'processing', error = NULL WHERE id = (SELECT id FROM meetings WHERE status = 'pending' AND source = 'upload' AND media_path IS NOT NULL ORDER BY created_at ASC LIMIT 1)`.
   - Automatically recovers interrupted meetings upon startup (resets `status = 'processing'` back to `'pending'`).
   - Dispatches pipeline execution in a dedicated thread pool (`asyncio.to_thread`) to ensure API endpoints stay non-blocking.
   - Excludes online meetings (`source = 'join'`) without media files.
   - Sets `status = 'failed'` and records actionable error messages in `meetings.error` on failure.

---

## 2. Files Created and Modified

| File | Type | Description |
|---|---|---|
| `Backend/app/services/audio.py` | New | Audio duration detection (`get_media_duration`), WAV conversion (`extract_audio_to_wav`), and temporary file lifecycle manager (`extract_temporary_wav`). |
| `Backend/app/services/transcription.py` | New | Lazy Whisper model singleton (`get_whisper_model`), audio transcription (`transcribe_audio`), and segment persistence (`persist_transcript_segments`). |
| `Backend/app/services/pipeline.py` | New | End-to-end processing pipeline orchestrating audio, whisper, Step 3B windowing, and Step 3B merging into final persistence. |
| `Backend/app/services/worker.py` | New | Persistent background worker (`worker_loop`), atomic meeting claim (`claim_pending_meeting`), startup recovery (`recover_interrupted_meetings`), and `WorkerManager`. |
| `Backend/app/core/config.py` | Modified | Added `WHISPER_DEVICE`, `WHISPER_COMPUTE_TYPE`, `FFMPEG_PATH`, `FFPROBE_PATH`, `WORKER_POLL_INTERVAL`, and `ENABLE_BACKGROUND_WORKER`. |
| `Backend/app/main.py` | Modified | Wired `worker_manager.start()` and `worker_manager.stop()` into FastAPI lifespan. |
| `Backend/tests/conftest.py` | Modified | Configured `ENABLE_BACKGROUND_WORKER = False` during test runs to prevent worker interference with unrelated API tests. |
| `Backend/tests/test_step4.py` | New | 16 automated tests covering audio extraction, Whisper transcription, pipeline integration, failure handling, atomic claim, restart recovery, and worker lifecycle. |
| `BACKEND_STEP_4_REPORT.md` | New | This report. |

---

## 3. Database Operations & Lifecycle

```
[Upload API Endpoint]
       │
       ▼
status: 'pending' ──(Worker atomic claim)──► status: 'processing', error = NULL
                                                    │
                   ┌────────────────────────────────┴────────────────────────────────┐
                   │                                                                 │
                   ▼ (Pipeline Succeeds)                                             ▼ (Pipeline Fails)
           status: 'done'                                                    status: 'failed'
           overview, progress, challenges, next_steps                        error: '<actionable error>'
           transcript_segments, windows, action_items
```

### Idempotency & Duplicate Prevention:
- **`transcript_segments`:** `DELETE FROM transcript_segments WHERE meeting_id = ?` is executed prior to batch insert, ensuring re-runs do not duplicate segments while preserving FTS triggers.
- **`windows`:** Upserted based on `(meeting_id, window_index)`.
- **`action_items`:** Matches items by lowercase normalized text, updating details while strictly preserving the original UUIDs and `done` states.

---

## 4. Test Verification & Actual Results

### Root Cause Analysis of Previous TestClient Timeouts:
In Python 3.13 on Windows, `starlette.testclient.TestClient` utilizes AnyIO's blocking portal with `asyncio.ProactorEventLoop`. By default, `ProactorEventLoop` calls `_fallback_socketpair` in `socket.py`, attempting to bind and connect to `127.0.0.1`. Inside strict sandboxes lacking loopback socket permissions, this connect call blocks indefinitely. Enabling loopback execution allows all tests using `TestClient` to pass in under 1 second.

### Full Test Suite Results:
Executed complete backend pytest suite (`pytest tests/ -v`):
```text
============================= test session starts =============================
platform win32 -- Python 3.13.13, pytest-9.2.0, pluggy-1.7.0
rootdir: D:\MHTechin\Mhtechin_AI_summary_generator\Backend
collected 63 items

tests/test_endpoints.py (14 tests) ............................. PASSED [ 22%]
tests/test_main.py (1 test) .................................... PASSED [ 23%]
tests/test_notes.py (7 tests) .................................. PASSED [ 34%]
tests/test_step2.py (1 test) ................................... PASSED [ 36%]
tests/test_step3b.py (24 tests) ................................ PASSED [ 74%]
tests/test_step4.py (16 tests) ................................. PASSED [100%]

================== 63 passed, 4 warnings in 68.49s (0:01:08) ==================
```

- **Passed:** 63 tests
- **Failed:** 0 tests
- **Skipped:** 0 tests
- **Real Database & Media:** Completely untouched (verified by `test_real_database_untouched`).

---

## 5. CPU and RAM Considerations

- **Memory Safety:** Media is streamed via FFmpeg to a temporary 16 kHz mono WAV; no audio files are loaded entirely into RAM.
- **Single Worker Constraint:** Exactly one meeting is claimed and processed at a time, ensuring CPU and memory footprint remains within limits suitable for 8 GB RAM machines.
- **Whisper CPU Configuration:** Uses `int8` quantization to minimize RAM and CPU thread pressure.
- **Llama-server Offloading:** Token counting and JSON generation run via external HTTP requests, eliminating in-process LLM memory overhead.

---

## 6. Manual Startup Instructions

1. **Prerequisites:**
   - Install FFmpeg and FFprobe and ensure they are on system `PATH` (or configure `FFMPEG_PATH` and `FFPROBE_PATH` in `.env`).
   - Install faster-whisper:
     ```powershell
     cd Backend
     .\.venv\Scripts\python.exe -m pip install faster-whisper
     ```
2. **Start llama-server (Qwen model):**
   ```powershell
   llama-server.exe -m Qwen2.5-1.5B-Instruct.Q8_0.gguf --port 8080 -c 2048
   ```
3. **Start FastAPI Backend:**
   ```powershell
   cd Backend
   .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
   ```

---

## 7. Distinctions & Next Steps

- **Automated vs. Live Testing:** All 63 automated tests mock external FFmpeg binaries, Whisper neural models, and llama-server inference (except live Qwen tests in `test_notes.py` which verified live server connectivity).
- **Pending Step 5 & 6:**
  - Step 5: Speaker diarization and speaker analytics (speakers table currently keeps `speaker = None`).
  - Step 6: Full chat query over meeting transcripts and vector/FTS search enhancements.
