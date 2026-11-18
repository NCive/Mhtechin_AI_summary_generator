# Chatmeet Backend

FastAPI and SQLite backend for Chatmeet AI Meeting Intelligence & Automated Summaries.

## Requirements
- Python 3.10+
- SQLite with FTS5 support (included in standard Python builds)

## Setup & Installation

1. Navigate to the `backend/` directory:
   ```bash
   cd backend
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   # Windows PowerShell:
   .venv\Scripts\Activate.ps1
   # Windows CMD:
   .venv\Scripts\activate.bat
   # Linux/macOS:
   source .venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Environment Configuration:
   Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

## Running Tests

Run the test suite with pytest:
```bash
pytest
```

## Running the Development Server

Start the FastAPI server using Uvicorn:
```bash
uvicorn app.main:app --reload --port 8000
```

Once running:
- Health check: `http://localhost:8000/health`
- Interactive API Docs: `http://localhost:8000/docs`
