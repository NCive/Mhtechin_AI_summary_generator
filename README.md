# ChatMeet AI — Meeting Intelligence & Automated Summaries

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688.svg)](https://fastapi.tiangolo.com/)
[![React + Vite](https://img.shields.io/badge/Frontend-React%2018%20%2B%20Vite-61DAFB.svg)](https://vitejs.dev/)
[![SQLite FTS5](https://img.shields.io/badge/Database-SQLite%20FTS5-003B57.svg)](https://www.sqlite.org/fts5.html)
[![Local-First](https://img.shields.io/badge/Privacy-100%25%20Local%20Inference-brightgreen.svg)]()

> **100% Local & Private Meeting Intelligence:** Upload recorded audio/video or stream live meetings directly via a meeting bot. Transcribe with Whisper, extract structured notes and action items using local GGUF LLMs via `llama.cpp`, and search transcripts with grounded semantic Q&A — completely offline without third-party cloud data leaks.

---

## Table of Contents

- [Overview & Key Features](#overview--key-features)
- [Architecture & Processing Pipeline](#architecture--processing-pipeline)
- [Prerequisites](#prerequisites)
- [Project Structure](#project-structure)
- [Quickstart Guide](#quickstart-guide)
  - [1. LLM Server Setup (llama.cpp)](#1-llm-server-setup-llamacpp)
  - [2. Backend Setup (FastAPI)](#2-backend-setup-fastapi)
  - [3. Frontend Setup (React + Vite)](#3-frontend-setup-react--vite)
- [Live Ingestion & Bot Simulation](#live-ingestion--bot-simulation)
- [Environment Configuration](#environment-configuration)
- [API & WebSocket Reference](#api--websocket-reference)
- [Testing & Quality Assurance](#testing--quality-assurance)
- [Security & Production Guardrails](#security--production-guardrails)

---

## Overview & Key Features

### 🎙️ Dual Ingestion Pipelines
- **Recorded File Uploads:** Upload media (`.mp3`, `.wav`, `.mp4`, `.m4a`, `.webm`, `.mov`) up to 2 GB with automatic audio extraction via FFmpeg and asynchronous background queue processing.
- **Live WebSocket Bot Streaming:** Ingest multi-speaker audio live (`/api/v1/meetings/{id}/stream`) with chunked PCM16 16 kHz mono frames. Features real-time energy-based silence detection, contiguity tracking (> 500 ms gap buffer flushing), idle flusher (~2 s silence), connection replacement, and restart recovery.

### 🧠 Local AI Transcription & Summarization
- **Faster-Whisper:** Local speech-to-text inference with Voice Activity Detection (VAD) and hallucination filters (`NO_SPEECH_PROB_THRESHOLD`, `AVG_LOGPROB_THRESHOLD`).
- **Local LLM Intelligence:** Multi-window structured extraction via `llama-server` (e.g., `Qwen2.5-1.5B-Instruct` GGUF), generating:
  - Executive Overview & Comprehensive Meeting Summary
  - Key Decisions & Action Items (with assignees & deadlines)
  - Project Progress, Challenges, and Next Steps
  - Speaker Talk-Time Analytics (duration, percentage, and silent-participant tracking)

### 💬 Grounded Transcript Q&A & Search
- **Full-Text Search (FTS5):** SQLite FTS5 search index automatically synced via database triggers.
- **Context-Grounded Chat:** Ask natural language questions against the meeting transcript. Answers cite exact timestamps and verifiable quotes.

### 📁 Multi-Format Export
- Export meetings into **TXT**, **SRT**, **VTT**, and **JSON** formats with full timestamps and speaker attribution.

---

## Architecture & Processing Pipeline

```mermaid
flowchart TD
    subgraph Inputs ["Ingestion Layer"]
        A1["Recorded Files\n(MP3, WAV, MP4, M4A, WebM)"] -->|POST /upload| B1["Backend Worker Queue"]
        A2["Meeting Bot\n(Recall.ai / fake_bot.py)"] -->|WebSocket /stream\n(PCM16 16kHz Mono)| B2["Live Session Manager"]
    end

    subgraph Processing ["Processing & Intelligence"]
        B1 --> C1["FFmpeg Audio Extractor"]
        C1 --> D["faster-whisper Engine\n(VAD & Energy Check)"]
        B2 -->|Buffer & Contiguity| D
        D --> E["SQLite DB + FTS5 Index\n(transcript_segments)"]
        E --> F["LLM Sliding Window Analysis\n(llama-server / Qwen2.5)"]
        F --> G["Structured Notes, Action Items,\nSummary & Speakers Breakdown"]
    end

    subgraph Client ["Client Interface"]
        G --> H["FastAPI REST & WebSocket APIs"]
        H --> I["React 18 + Tailwind Frontend\n(Dashboard, Detail, Chat & Live View)"]
    end
```

---

## Prerequisites

Before running the application, ensure the following tools are installed:

1. **Python:** Version 3.10 to 3.12 (with SQLite FTS5 support included in standard Python distributions).
2. **Node.js:** Version 18+ and `npm`.
3. **FFmpeg & FFprobe:** Must be installed and accessible on system `PATH` (used for audio extraction, conversions, and metadata probing).
   - Windows: `winget install Gyan.FFmpeg` or `choco install ffmpeg`
   - macOS: `brew install ffmpeg`
   - Linux: `sudo apt update && sudo apt install -y ffmpeg`
4. **llama.cpp / llama-server:** Required for local LLM inference.
   - Download prebuilt binaries from [llama.cpp releases](https://github.com/ggerganov/llama.cpp/releases).
   - Recommended GGUF model: `Qwen2.5-1.5B-Instruct.Q8_0.gguf` (or any compatible instruction-tuned model).

---

## Project Structure

```text
Mhtechin_AI_summary_generator/
├── backend/
│   ├── app/
│   │   ├── core/           # Configuration (settings, .env validation)
│   │   ├── db/             # SQLite connection, FTS5 schema & triggers
│   │   ├── models/         # Pydantic schemas & response models
│   │   ├── prompts/        # LLM system prompts for summary & notes
│   │   ├── routers/        # FastAPI API routes (meetings, chat, streaming)
│   │   └── services/       # Core services (audio, Whisper, LLM, live stream, worker)
│   ├── scripts/
│   │   └── fake_bot.py     # Live bot streaming simulator for testing
│   ├── tests/              # Pytest unit and integration test suite
│   ├── .env.example        # Backend environment template
│   ├── requirements.txt    # Python dependencies
│   ├── requirements-dev.txt# Dev dependencies (ruff)
│   └── README.md           # Backend specific documentation
├── Frontend/
│   ├── src/
│   │   ├── components/     # React UI components (cards, badges, modals, tabs)
│   │   ├── pages/          # Dashboard, Meeting Detail, Live View, Upload
│   │   ├── services/       # Axios API client & WebSocket adapters
│   │   └── types/          # TypeScript interfaces
│   ├── .env.example        # Frontend environment template
│   ├── package.json        # Node.js dependencies
│   └── vite.config.ts      # Vite configuration & dev proxy
├── .gitignore              # Repository gitignore rules
└── README.md               # Main project documentation
```

---

## Quickstart Guide

### 1. LLM Server Setup (llama.cpp)

Download your chosen GGUF model into the project directory (e.g., `Qwen2.5-1.5B-Instruct.Q8_0.gguf`). Start `llama-server`:

```bash
# Start llama-server on port 8080 (CPU or GPU)
llama-server -m Qwen2.5-1.5B-Instruct.Q8_0.gguf --port 8080 -c 4096
```

Verify it is running by checking `http://127.0.0.1:8080/health`.

---

### 2. Backend Setup (FastAPI)

1. Open a terminal and navigate to `backend/`:
   ```bash
   cd backend
   ```

2. Create and activate a Python virtual environment:
   ```bash
   # Windows PowerShell
   python -m venv .venv
   .venv\Scripts\Activate.ps1

   # Linux / macOS
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   ```

4. Configure environment settings:
   ```bash
   cp .env.example .env
   ```
   Generate a secure bot ingestion token:
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```
   Set `BOT_INGEST_TOKEN=<generated_token>` in `backend/.env`.

5. Start the backend development server:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```
   - Health check: `http://localhost:8000/health`
   - Interactive OpenAPI docs: `http://localhost:8000/docs`

---

### 3. Frontend Setup (React + Vite)

1. Open a second terminal and navigate to `Frontend/`:
   ```bash
   cd Frontend
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Configure environment settings:
   ```bash
   cp .env.example .env
   ```

4. Start the frontend development server:
   ```bash
   npm run dev
   ```
   Access the web interface at `http://localhost:3000`.

---

## Live Ingestion & Bot Simulation

The backend exposes a WebSocket ingestion endpoint at:
`ws://localhost:8000/api/v1/meetings/{meeting_id}/stream`

### Security & Authentication
- The bot **must** authenticate by providing the header:
  `X-Bot-Token: <BOT_INGEST_TOKEN>`
  *(Query string authentication is rejected by default to prevent token leakage in server logs).*

### Stream Simulator (`scripts/fake_bot.py`)
You can simulate a real-world multi-speaker meeting using the included test tool:

```bash
# From backend/ with active virtualenv:
python scripts/fake_bot.py <meeting_id> \
  --wav1 path/to/speaker1.wav --speaker1 "Alice" \
  --wav2 path/to/speaker2.wav --speaker2 "Bob" \
  --token "<BOT_INGEST_TOKEN>"
```

Useful simulator flags:
- `--silent2`: Sends digital silence for speaker 2 to test silent participant handling.
- `--synthetic`: Generates synthetic test tone audio without requiring real WAV files.
- `--chunk-ms 1000`: Changes chunk duration (default 1000 ms).
- `--fast`: Sends all chunks immediately without real-time sleep delays.

---

## Environment Configuration

### Backend (`backend/.env`)

| Variable | Default | Description |
|---|---|---|
| `DB_PATH` | `chatmeet.db` | SQLite database file location |
| `MEDIA_DIR` | `media` | Directory for uploaded audio/video and converted files |
| `LLM_SERVER_URL` | `http://127.0.0.1:8080` | URL of the local `llama-server` instance |
| `LLM_TIMEOUT_SECONDS` | `300` | HTTP request timeout for LLM generation |
| `LLM_MAX_TOKENS` | `800` | Maximum token limit per LLM response |
| `WHISPER_MODEL` | `base` | Whisper model size (`tiny`, `base`, `small`, `medium`) |
| `WHISPER_DEVICE` | `cpu` | Device for Whisper inference (`cpu` or `cuda`) |
| `WHISPER_COMPUTE_TYPE` | `int8` | Quantization type (`int8`, `float16`, `float32`) |
| `FFMPEG_PATH` | `ffmpeg` | Path or command for FFmpeg executable |
| `FFPROBE_PATH` | `ffprobe` | Path or command for FFprobe executable |
| `WORKER_POLL_INTERVAL` | `2.0` | Polling interval in seconds for background worker |
| `ENABLE_BACKGROUND_WORKER` | `True` | Enable background queue worker in FastAPI lifespan |
| `MAX_UPLOAD_MB` | `2000` | Max file upload limit in MB |
| `BOT_INGEST_TOKEN` | `change-me` | Secret shared token for live meeting bot ingestion |
| `BOT_DISCONNECT_TIMEOUT_SECONDS` | `600` | Timeout in seconds before finalizing an abandoned live session |
| `BOT_ALLOW_QUERY_TOKEN` | `False` | Allow token in query string (strict False for security) |
| `MAX_SPEAKERS_PER_MEETING` | `50` | Maximum concurrent speakers allowed in one session |
| `MAX_SESSION_BUFFERED_AUDIO_BYTES` | `209715200` | Maximum cumulative audio bytes (200 MB ~ 1.8 hrs) |
| `MAX_SESSION_LENGTH_SECONDS` | `28800` | Hard cap on session duration (8 hours) |
| `NO_SPEECH_PROB_THRESHOLD` | `0.6` | Drop segment if `no_speech_prob > threshold` and low logprob |
| `AVG_LOGPROB_THRESHOLD` | `-1.0` | Average logprob threshold for hallucination filter |
| `CORS_ORIGINS` | `http://localhost:3000` | Allowed origins for cross-origin frontend requests |

### Frontend (`Frontend/.env`)

| Variable | Default | Description |
|---|---|---|
| `VITE_API_BASE_URL` | `/api/v1` | API base path proxy or backend URL |
| `VITE_ENABLE_MOCK_FALLBACK` | `false` | Enable fallback mock data when backend is unreachable |

---

## API & WebSocket Reference

### REST Endpoints (`/api/v1`)

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/meetings/upload` | Upload audio/video file for asynchronous processing |
| `POST` | `/meetings/join` | Register a new live meeting for bot stream ingestion |
| `GET` | `/meetings` | List meetings with pagination, search, and status |
| `GET` | `/meetings/{id}` | Get full meeting detail, summary, notes, and action items |
| `GET` | `/meetings/{id}/transcript` | Get complete transcript segments with speaker attribution |
| `GET` | `/meetings/{id}/speakers` | Get talk-time duration (seconds) and percentage per speaker |
| `PATCH` | `/meetings/{id}/action-items/{item_id}` | Update action item completion status |
| `POST` | `/meetings/{id}/chat` | Ask grounded natural language questions against transcript |
| `GET` | `/meetings/{id}/export?format={txt\|srt\|vtt\|json}` | Export transcript and summary |
| `GET` | `/meetings/media/{id}` | Stream original or extracted media file |

### WebSocket Endpoint

- **URL:** `/api/v1/meetings/{id}/stream`
- **Auth Header:** `X-Bot-Token: <token>`
- **Protocol:**
  - *Metadata Text Frame (JSON):*
    ```json
    {
      "type": "chunk",
      "speaker_id": "spk_1",
      "speaker_name": "Alice",
      "start_ms": 12000
    }
    ```
  - *Binary Frame:* Raw PCM16 16 kHz Mono audio data immediately following the chunk metadata.
  - *End Signal (JSON):*
    ```json
    { "type": "end" }
    ```

---

## Testing & Quality Assurance

### Run Backend Unit & Integration Tests

```bash
# In backend/ directory with .venv active:
pytest backend/tests -v --timeout=120
```

Targeted test execution:
```bash
# Live stream safety & limits
pytest backend/tests/test_live_limits.py -v
# Server restart recovery
pytest backend/tests/test_live_recovery.py -v
# Live stream buffer & contiguity
pytest backend/tests/test_live_stream.py -v
```

### Run Code Linter & Formatting Check

```bash
ruff check backend/
```

### Frontend Build Verification

```bash
# In Frontend/ directory:
npm run build
```

---

## Security & Production Guardrails

- **Zero Secret Commits:** Git ignores all `.env` files across root, frontend, and backend. Only `.env.example` templates are tracked.
- **Constant-Time Token Comparison:** Authentication uses `hmac.compare_digest` to prevent timing attacks.
- **WebSocket Resource Limits:**
  - Max text frame size: 4 KB (rejects oversized headers with code 1009).
  - Max binary chunk size: 1 MB (rejects oversized audio with code 1009).
  - Validates PCM16 16-bit alignment (rejects odd byte counts with code 1003).
  - Session speaker ceiling: max 50 speakers per session.
  - Session cumulative buffer cap: 200 MB.
- **Server Restart Resilience:** Abandoned live sessions undergo graceful background recovery upon server restart, finalizing partial transcripts without leaving meetings in permanent `'processing'` states.
