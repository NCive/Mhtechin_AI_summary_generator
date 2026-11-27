# ChatMeet Backend

FastAPI and SQLite (FTS5) backend for ChatMeet AI Meeting Intelligence & Automated Summaries.

---

## Architecture Overview

```text
backend/
├── app/
│   ├── core/           # Pydantic BaseSettings, configuration & .env loader
│   ├── db/             # SQLite connection helpers, schema.sql (FTS5 & triggers)
│   ├── models/         # Pydantic schemas (Meeting, Transcript, Speakers, Chat)
│   ├── prompts/        # LLM system prompts for summary & structured notes
│   ├── routers/        # FastAPI route definitions (meetings, chat, streaming)
│   └── services/       # Core business logic:
│       ├── audio.py           # FFmpeg audio conversion, validation & duration probing
│       ├── transcription.py   # faster-whisper STT with VAD & silence filter
│       ├── windowing.py       # Transcript chunking & context windowing
│       ├── notes_extractor.py # LLM structured notes extraction
│       ├── summarizer.py      # LLM executive summary & action items
│       ├── chat_service.py    # SQLite FTS5 retrieval & grounded Q&A
│       ├── live_stream.py     # WebSocket live audio session manager
│       ├── worker.py          # Background processing worker for uploaded media
│       └── llm.py             # HTTP client for local llama-server
├── scripts/
│   └── fake_bot.py     # Live multi-speaker bot stream simulator
├── tests/              # Pytest test suite
├── .env.example        # Environment configuration template
├── requirements.txt    # Production dependencies
└── requirements-dev.txt# Development dependencies (ruff)
```

---

## Requirements

- **Python:** 3.10 to 3.12 (standard builds include SQLite FTS5 support)
- **FFmpeg & FFprobe:** Installed and available on system PATH
- **llama-server:** Running on `http://127.0.0.1:8080` with a local GGUF model

---

## Setup & Installation

1. Navigate to `backend/`:
   ```bash
   cd backend
   ```

2. Create and activate a Python virtual environment:
   ```bash
   # Windows PowerShell:
   python -m venv .venv
   .venv\Scripts\Activate.ps1

   # Linux / macOS:
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
   Generate a secret bot ingestion token:
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```
   Update `BOT_INGEST_TOKEN` in `backend/.env`.

---

## Running the Application

### 1. Start the LLM Server (llama.cpp)
```bash
llama-server -m ../Qwen2.5-1.5B-Instruct.Q8_0.gguf --port 8080 -c 4096
```

### 2. Start the Backend API Server
```bash
uvicorn app.main:app --reload --port 8000
```

- **Health check:** `http://localhost:8000/health`
- **Interactive OpenAPI Documentation:** `http://localhost:8000/docs`
- **Alternative ReDoc Documentation:** `http://localhost:8000/redoc`

---

## Live Bot Stream Simulation (`scripts/fake_bot.py`)

Test the WebSocket live ingestion endpoint (`/api/v1/meetings/{id}/stream`):

```bash
# Interleaved multi-speaker streaming with input WAV files
python scripts/fake_bot.py <meeting_id> \
  --wav1 path/to/speaker1.wav --speaker1 "Alice" \
  --wav2 path/to/speaker2.wav --speaker2 "Bob" \
  --token "<BOT_INGEST_TOKEN>"

# Synthetic tone stream for quick verification
python scripts/fake_bot.py <meeting_id> --synthetic --token "<BOT_INGEST_TOKEN>"

# Test silent participant handling (Alice speaks, Bob is silent)
python scripts/fake_bot.py <meeting_id> \
  --wav1 path/to/alice.wav --speaker1 "Alice" \
  --silent2 --speaker2 "Bob" \
  --token "<BOT_INGEST_TOKEN>"
```

---

## Testing & Linting

### Run Tests
```bash
pytest tests/ -v --timeout=120
```

Target specific test modules:
```bash
# Live stream safety, token check & frame limits
pytest tests/test_live_limits.py -v

# Live stream server restart recovery
pytest tests/test_live_recovery.py -v

# Live stream audio buffering & contiguity
pytest tests/test_live_stream.py -v

# Transcription & VAD filtering
pytest tests/test_transcription.py -v
```

### Run Linter
```bash
ruff check .
```
